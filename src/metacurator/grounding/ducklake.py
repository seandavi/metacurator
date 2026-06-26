"""DuckLakeBackend — opt-in grounding against an existing DuckLake. SPEC 070, ADR-0005.

For teams that maintain a DuckLake with an ``ontology`` schema (e.g. cdsci-lake) of the
same table shape as the local backend. Connects read-only; the grounding queries are
identical to LocalDuckDBBackend (shared ``DuckStore`` contract). Requires DuckLake access;
not the default.
"""

from __future__ import annotations

import duckdb

from ..models import GroundedTerm
from ._store import DuckStore
from .base import DEFAULT_PREDICATES


class DuckLakeBackend:
    """Grounding backend backed by a read-only DuckLake ontology schema. See SPEC 070."""

    def __init__(self, *, dsn: str, schema: str = "ontology", read_only: bool = True) -> None:
        self.dsn = dsn
        self.schema = schema
        self.con = duckdb.connect()
        self.con.execute("INSTALL ducklake; LOAD ducklake;")
        mode = "READ_ONLY" if read_only else ""
        self.con.execute(f"ATTACH ? AS lake (TYPE ducklake, {mode})", [dsn])
        self.con.execute("USE lake")
        # Tables live under <schema>.{terms,synonyms,xrefs,edges}; share all query logic.
        self.store = DuckStore(self.con, qualifier=f"{schema}.")

    def ensure(self, ontologies: list[str]) -> None:
        """No-op: a DuckLake is curated upstream; this backend only reads it (SPEC 070)."""
        missing = [o for o in ontologies if o.lower() not in self.store.loaded_ontologies()]
        if missing:
            raise LookupError(
                f"ontologies not present in DuckLake schema {self.schema!r}: {missing}"
            )

    def lookup(
        self, value: str, ontology: str, *, scopes: tuple[str, ...] = ("exact", "label")
    ) -> list[GroundedTerm]:
        return self.store.lookup(value, ontology, scopes=scopes)

    def get(self, curie: str, ontology: str) -> GroundedTerm | None:
        return self.store.get(curie, ontology)

    def reachable_from(
        self, curie: str, root: str, ontology: str, *, predicates=DEFAULT_PREDICATES
    ) -> bool:
        return self.store.reachable_from(curie, root, ontology, predicates=predicates)

    def is_obsolete(self, curie: str, ontology: str) -> bool:
        return self.store.is_obsolete(curie, ontology)

    def replaced_by(self, curie: str, ontology: str) -> str | None:
        return self.store.replaced_by(curie, ontology)
