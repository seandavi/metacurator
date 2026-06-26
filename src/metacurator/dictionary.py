"""dictionary — LinkML schema load & validation. Implement to SPEC 060. [deterministic]

Loads the active LinkML curation schema (default: cmd) via linkml-runtime; exposes fields,
enums (with ontology ``meaning``s), and dynamic-enum (``reachable_from``) bindings; and
validates a ColumnMapping (targets exist) and a CandidateRow (types, permissible values,
ontology-branch constraints). Branch checks delegate to SPEC 070 — the dictionary never
grounds or mints a CURIE itself (ADR-0004).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from linkml_runtime import SchemaView

from .ground import ground
from .grounding.base import GroundingBackend
from .models import CandidateRow, ColumnMapping

_NUMERIC_RANGES = {"float", "double", "decimal", "integer", "int"}
_DEFAULT_PREDICATES = ("rdfs:subClassOf",)


def _onto_from_source(source_ontology: str) -> str:
    """``obo:ncit`` / ``ncit`` -> grounding backend key ``ncit``."""
    return source_ontology.split(":")[-1].lower()


def _onto_from_curie(curie: str) -> str:
    """``UBERON:0001988`` -> ontology key ``uberon``."""
    return curie.split(":")[0].lower()


def default_schema_path() -> Path:
    """Locate ``cmd.yaml``: ``$METACURATOR_SCHEMA``, else ``schema/cmd.yaml`` up-tree."""
    env = os.environ.get("METACURATOR_SCHEMA")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "schema" / "cmd.yaml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "could not locate schema/cmd.yaml; set $METACURATOR_SCHEMA to the schema path"
    )


@dataclass(frozen=True)
class OntologyBinding:
    """A field's dynamic-enum binding: values must be reachable from ``branch_root``."""

    ontology: str
    branch_root: str
    predicates: tuple[str, ...] = _DEFAULT_PREDICATES


@dataclass(frozen=True)
class FieldSpec:
    """One slot of the active record class (SPEC 060)."""

    name: str
    range: str | None
    required: bool
    multivalued: bool
    enum_name: str | None
    permissible_values: dict[str, str | None]  # value -> meaning CURIE (or None)
    binding: OntologyBinding | None

    @property
    def is_enum(self) -> bool:
        return self.enum_name is not None

    @property
    def is_dynamic_enum(self) -> bool:
        return self.binding is not None


class Dictionary:
    """Loaded curation schema for one record class (default ``Sample``). See SPEC 060."""

    def __init__(self, path: Path | str | None = None, *, class_name: str = "Sample") -> None:
        self.path = Path(path) if path is not None else default_schema_path()
        if not self.path.exists():
            raise FileNotFoundError(f"schema not found: {self.path}")
        self.sv = SchemaView(str(self.path))
        if class_name not in self.sv.all_classes():
            raise KeyError(f"class {class_name!r} not in schema {self.path}")
        self.class_name = class_name
        self._fields: dict[str, FieldSpec] = self._build_fields()

    # -- construction -----------------------------------------------------------
    def _build_fields(self) -> dict[str, FieldSpec]:
        fields: dict[str, FieldSpec] = {}
        for slot in self.sv.class_induced_slots(self.class_name):
            enum_name = slot.range if slot.range in self.sv.all_enums() else None
            pv: dict[str, str | None] = {}
            binding: OntologyBinding | None = None
            if enum_name is not None:
                enum = self.sv.get_enum(enum_name)
                pv = {k: v.meaning for k, v in (enum.permissible_values or {}).items()}
                binding = self._binding_for(enum)
            fields[slot.name] = FieldSpec(
                name=slot.name,
                range=slot.range,
                required=bool(slot.required),
                multivalued=bool(slot.multivalued),
                enum_name=enum_name,
                permissible_values=pv,
                binding=binding,
            )
        return fields

    @staticmethod
    def _binding_for(enum) -> OntologyBinding | None:
        """Extract a dynamic-enum branch binding from ``include: [{reachable_from}]``."""
        for inc in enum.include or []:
            rq = getattr(inc, "reachable_from", None)
            if rq and rq.source_nodes:
                preds = (
                    tuple(rq.relationship_types)
                    if rq.relationship_types
                    else _DEFAULT_PREDICATES
                )
                return OntologyBinding(
                    ontology=_onto_from_source(rq.source_ontology),
                    branch_root=rq.source_nodes[0],
                    predicates=preds,
                )
        return None

    # -- introspection ----------------------------------------------------------
    def fields(self) -> dict[str, FieldSpec]:
        return dict(self._fields)

    def field(self, name: str) -> FieldSpec:
        return self._fields[name]

    @property
    def identifier(self) -> str | None:
        slot = self.sv.get_identifier_slot(self.class_name)
        return slot.name if slot else None

    def bindings(self) -> dict[str, OntologyBinding]:
        return {n: f.binding for n, f in self._fields.items() if f.binding is not None}

    def ontologies_needed(self) -> set[str]:
        """Every ontology a backend must `ensure`: dynamic bindings + static meanings."""
        needed = {b.ontology for b in self.bindings().values()}
        for f in self._fields.values():
            for meaning in f.permissible_values.values():
                if meaning:
                    needed.add(_onto_from_curie(meaning))
        return needed

    # -- validation -------------------------------------------------------------
    def validate_mapping(self, mapping: ColumnMapping) -> list[str]:
        """Every mapping target must be a slot of the active class (SPEC 060)."""
        return [
            f"unknown target field {item.target_field!r} (not a slot of {self.class_name})"
            for item in mapping.items
            if item.target_field not in self._fields
        ]

    def validate_row(
        self, row: CandidateRow, *, backend: GroundingBackend | None = None
    ) -> list[str]:
        """Type / permissible-value / ontology-branch checks for a candidate row."""
        errors: list[str] = []
        for name, raw in row.values.items():
            fs = self._fields.get(name)
            if fs is None:
                errors.append(f"unknown field {name!r}")
                continue
            values = raw if (fs.multivalued and isinstance(raw, list)) else [raw]
            for value in values:
                if value is None or value == "":
                    continue
                errors.extend(self._check_value(fs, value, backend))
        return errors

    def _check_value(
        self, fs: FieldSpec, value, backend: GroundingBackend | None
    ) -> list[str]:
        if fs.range in _NUMERIC_RANGES:
            try:
                float(value)
            except (TypeError, ValueError):
                return [f"{fs.name}: {value!r} is not a valid {fs.range}"]
            return []

        if fs.is_dynamic_enum:
            if value in fs.permissible_values:  # explicit permissible (e.g. Healthy)
                return []
            if backend is None:
                return []  # cannot verify a dynamic value without a grounding backend
            b = fs.binding
            terms = ground(str(value), b.ontology, backend=backend, branch_root=b.branch_root)
            if not any(t.branch_ok and not t.obsolete for t in terms):
                return [
                    f"{fs.name}: {value!r} does not ground to a term under {b.branch_root}"
                ]
            return []

        if fs.is_enum and value not in fs.permissible_values:
            allowed = ", ".join(sorted(fs.permissible_values)) or "(none)"
            return [f"{fs.name}: {value!r} not a permissible value [{allowed}]"]
        return []


# Back-compat alias for the original stub name.
Schema = Dictionary
