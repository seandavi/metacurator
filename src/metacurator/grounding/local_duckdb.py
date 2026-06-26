"""LocalDuckDBBackend — default, zero-infrastructure grounding. SPEC 070, ADR-0005.

Builds a small local ontology store from semantic-sql's public ``bbop-sqlite`` files:
``ensure()`` downloads the needed ``<onto>.db.gz``, projects the four tables
(terms/synonyms/xrefs/edges) into a local DuckDB cache, and grounds against it. Only
ontologies the active schema references are fetched. Closure is a recursive CTE over
``edges`` (no materialized entailed_edge) — see ``_store.DuckStore``.

The projection mirrors the cdsci-lake ontology source (facts restated in SPEC 070):
literals live in ``statements.value``, IRI objects in ``statements.object``, ``oio:``
synonym predicates, and ``edge`` is a view of asserted direct edges.
"""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import duckdb

from ..models import GroundedTerm
from ._store import STORE_DDL, DuckStore
from .base import DEFAULT_PREDICATES

SEMSQL_BASE_URL = "https://s3.amazonaws.com/bbop-sqlite"

# semantic-sql predicate IRIs/CURIEs the projection reads (SPEC 070).
_P_LABEL = "rdfs:label"
_P_DEFINITION = "IAO:0000115"
_P_DEPRECATED = "owl:deprecated"
_P_REPLACED_BY = "IAO:0100001"
_SYNONYM_SCOPES = {
    "oio:hasExactSynonym": "exact",
    "oio:hasBroadSynonym": "broad",
    "oio:hasNarrowSynonym": "narrow",
    "oio:hasRelatedSynonym": "related",
}


class LocalDuckDBBackend:
    """Grounding backend backed by a locally-built DuckDB ontology store. See SPEC 070."""

    def __init__(self, cache_dir: Path, *, base_url: str = SEMSQL_BASE_URL) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self.db_path = self.cache_dir / "ontology.duckdb"
        self.con = duckdb.connect(str(self.db_path))
        self.con.execute(STORE_DDL)
        self.store = DuckStore(self.con)

    # -- availability -----------------------------------------------------------
    def ensure(self, ontologies: list[str]) -> None:
        """Make the named ontologies available locally, fetching only what's missing."""
        loaded = self.store.loaded_ontologies()
        for onto in ontologies:
            if onto.lower() in loaded:
                continue
            self._build(onto.lower())

    def _build(self, ontology: str) -> None:
        """Download ``<ontology>.db.gz``, project semantic-sql into the four tables."""
        db_gz = self.cache_dir / f"{ontology}.db.gz"
        db_file = self.cache_dir / f"{ontology}.db"
        if not db_file.exists():
            if not db_gz.exists():
                self._download(f"{self.base_url}/{ontology}.db.gz", db_gz)
            with gzip.open(db_gz, "rb") as fin, open(db_file, "wb") as fout:
                shutil.copyfileobj(fin, fout)
        self._project(ontology, db_file)

    def _download(self, url: str, dest: Path) -> None:
        import httpx

        with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def _project(self, ontology: str, sqlite_db: Path) -> None:
        """Project a semantic-sql sqlite DB into our four tables for ``ontology``."""
        con = self.con
        con.execute("INSTALL sqlite; LOAD sqlite;")
        # ATTACH does not accept bind parameters; inline the (trusted, local) path.
        safe_path = str(sqlite_db).replace("'", "''")
        con.execute(f"ATTACH '{safe_path}' AS semsql (TYPE sqlite, READ_ONLY)")
        try:
            # Materialize just the statement slices we need (+ edges) into native DuckDB in
            # one pass, so the term self-joins below don't rescan the attached SQLite — that
            # matters for big ontologies (NCIT/NCBITaxon have millions of statements).
            wanted = (_P_LABEL, _P_DEFINITION, _P_DEPRECATED, _P_REPLACED_BY, *_SYNONYM_SCOPES)
            placeholders = ", ".join("?" for _ in wanted)
            con.execute(
                f"CREATE TEMP TABLE _st AS SELECT subject, predicate, object, value "  # noqa: S608
                f"FROM semsql.statements WHERE predicate IN ({placeholders})",
                list(wanted),
            )
            con.execute(
                "CREATE TEMP TABLE _ed AS "
                "SELECT subject, predicate, object FROM semsql.edge WHERE object IS NOT NULL"
            )
            # terms: subjects carrying a label, with optional definition/deprecation/replacement.
            con.execute(
                "INSERT INTO terms (ontology, curie, label, definition, obsolete, replaced_by) "
                "SELECT ?, lbl.subject, MAX(lbl.value), MAX(dfn.value), "
                "       COALESCE(MAX(dep.value) = 'true', FALSE), MAX(rep.object) "
                "FROM _st lbl "
                "LEFT JOIN _st dfn ON dfn.subject = lbl.subject AND dfn.predicate = ? "
                "LEFT JOIN _st dep ON dep.subject = lbl.subject AND dep.predicate = ? "
                "LEFT JOIN _st rep ON rep.subject = lbl.subject AND rep.predicate = ? "
                "WHERE lbl.predicate = ? AND lbl.value IS NOT NULL "
                "GROUP BY lbl.subject",
                [ontology, _P_DEFINITION, _P_DEPRECATED, _P_REPLACED_BY, _P_LABEL],
            )
            # synonyms: one row per oio synonym predicate.
            for pred, scope in _SYNONYM_SCOPES.items():
                con.execute(
                    "INSERT INTO synonyms (ontology, curie, synonym, scope) "
                    "SELECT ?, subject, value, ? FROM _st "
                    "WHERE predicate = ? AND value IS NOT NULL",
                    [ontology, scope, pred],
                )
            # edges: asserted direct edges (the semsql `edge` table).
            con.execute(
                "INSERT INTO edges (ontology, subject, predicate, object) "
                "SELECT ?, subject, predicate, object FROM _ed",
                [ontology],
            )
            con.execute("DROP TABLE _st")
            con.execute("DROP TABLE _ed")
        finally:
            con.execute("DETACH semsql")

    # -- query primitives (delegate to the shared store) ------------------------
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
