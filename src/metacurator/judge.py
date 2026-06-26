"""judge — THE AGENT BOUNDARY (the only module that invokes an LLM). SPEC 100, ADR-0004.

Exactly three judgment calls, each consuming and producing typed objects (SPEC 010) —
never an identifier or curated value. The LLM client is injected (model-agnostic). A skill
supplies the prompts/technique corpus for these calls. The MCP server does NOT host these
(ADR-0006): the consuming agent brings its own model.

No-hallucination enforcement lives here structurally:
- `classify_tables` returns an index + rationale, no data.
- `propose_mapping` returns a *projection description* (no values) and is validated against
  the active schema; an unknown target field is rejected loudly.
- `disambiguate` may only return one of the provided grounded CURIEs (or None); a CURIE
  outside the candidate set raises.
"""

from __future__ import annotations

from typing import Any, Protocol

from .dictionary import Dictionary
from .models import (
    ColumnMapping,
    DisambiguationChoice,
    GroundedTerm,
    SourceTable,
    TableChoice,
)

LOW_CONFIDENCE = 0.5


class JudgeContractError(ValueError):
    """An LLM response violated the no-hallucination / typed-output contract (SPEC 100)."""


class LLMClient(Protocol):
    """Minimal injected LLM interface; implementations live outside the deterministic core."""

    def complete(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


# -- JSON response schemas the model is constrained to -----------------------

_TABLE_CHOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "table_index": {"type": "integer"},
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["table_index"],
}
_MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_col": {"type": "string"},
                    "target_field": {"type": "string"},
                    "transform": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": ["string", "null"]},
                },
                "required": ["source_col", "target_field", "confidence"],
            },
        }
    },
    "required": ["items"],
}
_CHOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "curie": {"type": ["string", "null"]},
        "rationale": {"type": "string"},
    },
    "required": ["curie"],
}

_SYS_CLASSIFY = (
    "You select which loaded supplement table is the per-subject characteristics table "
    "(one row per study subject/sample). Return only the table index and a short rationale. "
    "Do not extract or invent any data."
)
_SYS_MAPPING = (
    "You map source table columns to target schema fields. Return a projection description "
    "only — never values. Use a target_field only if it is in the provided schema field list."
)
_SYS_DISAMBIGUATE = (
    "You choose the single best ontology term for a value from the provided candidates. "
    "You may only return one of the candidate CURIEs exactly, or null. Never invent a CURIE."
)


def _describe_table(idx: int, table: SourceTable, max_sample: int = 3) -> str:
    cols = getattr(table.frame, "columns", [])
    sample = getattr(table.frame, "records", [])[:max_sample]
    prov = table.provenance
    loc = prov.sheet or (f"table {prov.table_index}" if prov.table_index is not None else prov.file)
    return (
        f"[{idx}] location={loc} rows={table.n_rows} cols={table.n_cols}\n"
        f"     columns: {', '.join(map(str, cols))}\n"
        f"     sample: {sample}"
    )


def _schema_fields_blurb(dictionary: Dictionary) -> str:
    lines = []
    for name, fs in dictionary.fields().items():
        bits = [f"range={fs.range}"]
        if fs.required:
            bits.append("required")
        if fs.multivalued:
            bits.append("multivalued")
        if fs.is_enum:
            vals = ", ".join(sorted(fs.permissible_values)) or "(dynamic)"
            bits.append(f"enum[{vals}]")
        lines.append(f"- {name}: {', '.join(bits)}")
    return "\n".join(lines)


def classify_tables(
    tables: list[SourceTable], schema: Dictionary | None, *, llm: LLMClient
) -> TableChoice:
    """Pick the index of the per-subject characteristics table (+ rationale). SPEC 100."""
    if not tables:
        raise ValueError("classify_tables: no tables provided")
    prompt = "Loaded tables:\n" + "\n".join(
        _describe_table(i, t) for i, t in enumerate(tables)
    )
    if schema is not None:
        prompt += f"\n\nTarget schema fields:\n{_schema_fields_blurb(schema)}"
    raw = llm.complete(system=_SYS_CLASSIFY, prompt=prompt, schema=_TABLE_CHOICE_SCHEMA)
    choice = TableChoice.model_validate(raw)
    needs_review = choice.confidence < LOW_CONFIDENCE
    if not (0 <= choice.table_index < len(tables)):
        # An out-of-range index is not trustworthy: clamp + force review, never silently.
        choice = choice.model_copy(update={"table_index": 0})
        needs_review = True
    return choice.model_copy(update={"needs_review": needs_review})


def propose_mapping(
    table: SourceTable, schema: Dictionary, *, llm: LLMClient
) -> ColumnMapping:
    """Map source columns → schema fields; returns a ColumnMapping (no values). SPEC 100."""
    cols = getattr(table.frame, "columns", [])
    sample = getattr(table.frame, "records", [])[:5]
    prompt = (
        f"Source columns: {', '.join(map(str, cols))}\n"
        f"Sample rows: {sample}\n\n"
        f"Target schema fields:\n{_schema_fields_blurb(schema)}"
    )
    raw = llm.complete(system=_SYS_MAPPING, prompt=prompt, schema=_MAPPING_SCHEMA)
    mapping = ColumnMapping.model_validate(raw)
    errors = schema.validate_mapping(mapping)
    if errors:
        raise JudgeContractError("; ".join(errors))
    return mapping


def disambiguate(
    value: str, candidates: list[GroundedTerm], *, llm: LLMClient
) -> DisambiguationChoice:
    """Choose among REAL grounded candidates (or None). Cannot mint a CURIE. SPEC 100."""
    allowed = {c.curie for c in candidates if c.curie}
    if not allowed:
        return DisambiguationChoice(curie=None, rationale="no candidates")
    listing = "\n".join(
        f"- {c.curie} : {c.label} (scope={c.scope}, tier={c.confidence_tier})"
        for c in candidates
        if c.curie
    )
    prompt = f"Value: {value!r}\nCandidates:\n{listing}\n\nReturn one CURIE above, or null."
    raw = llm.complete(system=_SYS_DISAMBIGUATE, prompt=prompt, schema=_CHOICE_SCHEMA)
    choice = DisambiguationChoice.model_validate(raw)
    if choice.curie is not None and choice.curie not in allowed:
        raise JudgeContractError(
            f"disambiguate returned {choice.curie!r}, not in candidate set {sorted(allowed)}"
        )
    return choice
