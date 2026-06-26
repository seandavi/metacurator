"""LocalDuckDBBackend — default, zero-infrastructure grounding. SPEC 070, ADR-0005.

Builds a small local ontology store from semantic-sql's public ``bbop-sqlite`` files:
download the needed ``<onto>.db.gz``, project the four tables (terms/synonyms/xrefs/edges)
into a local DuckDB, and ground against it. Only ontologies the active schema references
are fetched. Closure is a recursive CTE over ``edges`` (no materialized entailed_edge).

This is the "helper for users without DuckLake access" — works with just a network
connection. The projection logic mirrors the cdsci-lake ontology source (validated facts
restated in SPEC 070): literals in ``value``, IRI objects in ``object``, ``oio:`` synonym
predicates, ``edge`` is a view of asserted direct edges.
"""

from __future__ import annotations

from pathlib import Path

from ..models import GroundedTerm
from .base import DEFAULT_PREDICATES

SEMSQL_BASE_URL = "https://s3.amazonaws.com/bbop-sqlite"


class LocalDuckDBBackend:
    """Grounding backend backed by a locally-built DuckDB ontology store. See SPEC 070."""

    def __init__(self, cache_dir: Path, *, base_url: str = SEMSQL_BASE_URL) -> None:
        raise NotImplementedError("SPEC 070 — build local DuckDB store from semsql .db.gz")

    def ensure(self, ontologies: list[str]) -> None: ...
    def lookup(self, value, ontology, *, scopes=("exact", "label")) -> list[GroundedTerm]: ...
    def get(self, curie, ontology) -> GroundedTerm | None: ...
    def reachable_from(self, curie, root, ontology, *, predicates=DEFAULT_PREDICATES) -> bool: ...
    def is_obsolete(self, curie, ontology) -> bool: ...
    def replaced_by(self, curie, ontology) -> str | None: ...
