"""DuckLakeBackend — opt-in grounding against an existing DuckLake. SPEC 070, ADR-0005.

For teams that maintain a DuckLake with an ``ontology`` schema (e.g. cdsci-lake) of the
same table shape as the local backend. Connects read-only; the grounding queries are
identical to LocalDuckDBBackend (shared store contract). Requires DuckLake access; not
the default.
"""

from __future__ import annotations

from ..models import GroundedTerm
from .base import DEFAULT_PREDICATES


class DuckLakeBackend:
    """Grounding backend backed by a read-only DuckLake ontology schema. See SPEC 070."""

    def __init__(self, *, dsn: str, schema: str = "ontology", read_only: bool = True) -> None:
        raise NotImplementedError("SPEC 070 — attach DuckLake read-only; query ontology.*")

    def ensure(self, ontologies: list[str]) -> None: ...
    def lookup(self, value, ontology, *, scopes=("exact", "label")) -> list[GroundedTerm]: ...
    def get(self, curie, ontology) -> GroundedTerm | None: ...
    def reachable_from(self, curie, root, ontology, *, predicates=DEFAULT_PREDICATES) -> bool: ...
    def is_obsolete(self, curie, ontology) -> bool: ...
    def replaced_by(self, curie, ontology) -> str | None: ...
