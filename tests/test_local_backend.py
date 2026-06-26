"""Offline coverage of LocalDuckDBBackend's semantic-sql projection (SPEC 070).

We can't download a real ``<onto>.db.gz`` in CI, but we can exercise the exact projection
SQL by hand-building a tiny SQLite with semantic-sql's ``statements`` + ``edge`` shape and
pointing ``ensure()`` at it (placing the ``.db`` so the download/gunzip steps are skipped).
"""

from __future__ import annotations

import sqlite3

from metacurator.ground import ground
from metacurator.grounding.local_duckdb import LocalDuckDBBackend
from metacurator.models import ConfidenceTier


def _build_semsql(path) -> None:
    """Minimal semantic-sql store: an 8-column ``statements`` table + an ``edge`` table."""
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE statements (
            stanza TEXT, subject TEXT, predicate TEXT, object TEXT,
            value TEXT, datatype TEXT, language TEXT, graph TEXT
        );
        CREATE TABLE edge (subject TEXT, predicate TEXT, object TEXT);
        """
    )
    stmts = [
        ("NCIT:C2955", "rdfs:label", None, "Colorectal Carcinoma"),
        ("NCIT:C2955", "IAO:0000115", None, "A carcinoma of the colon or rectum."),
        ("NCIT:C2955", "oio:hasExactSynonym", None, "Colorectal Cancer"),
        ("NCIT:C9305", "rdfs:label", None, "Neoplasm"),
        ("NCIT:C2991", "rdfs:label", None, "Disease or Disorder"),
        ("NCIT:C99999", "rdfs:label", None, "Obsolete Disease"),
        ("NCIT:C99999", "owl:deprecated", None, "true"),
        ("NCIT:C99999", "IAO:0100001", "NCIT:C2955", None),
    ]
    con.executemany(
        "INSERT INTO statements (subject, predicate, object, value) VALUES (?, ?, ?, ?)",
        stmts,
    )
    con.executemany(
        "INSERT INTO edge (subject, predicate, object) VALUES (?, ?, ?)",
        [
            ("NCIT:C2955", "rdfs:subClassOf", "NCIT:C9305"),
            ("NCIT:C9305", "rdfs:subClassOf", "NCIT:C2991"),
        ],
    )
    con.commit()
    con.close()


def test_ensure_projects_semsql_then_grounds(tmp_path):
    _build_semsql(tmp_path / "ncit.db")  # placed so ensure() skips download + gunzip
    backend = LocalDuckDBBackend(cache_dir=tmp_path)
    backend.ensure(["ncit"])

    assert "ncit" in backend.store.loaded_ontologies()

    # Label projected; branch reachable through the projected edges -> auto.
    terms = ground("Colorectal Carcinoma", "ncit", backend=backend, branch_root="NCIT:C2991")
    assert len(terms) == 1
    assert terms[0].curie == "NCIT:C2955"
    assert terms[0].confidence_tier == ConfidenceTier.auto

    # Exact synonym projected.
    syn = ground("Colorectal Cancer", "ncit", backend=backend, branch_root="NCIT:C2991")
    assert syn[0].curie == "NCIT:C2955"

    # Deprecation + replacement projected.
    assert backend.is_obsolete("NCIT:C99999", "ncit") is True
    assert backend.replaced_by("NCIT:C99999", "ncit") == "NCIT:C2955"


def test_ensure_is_idempotent(tmp_path):
    _build_semsql(tmp_path / "ncit.db")
    backend = LocalDuckDBBackend(cache_dir=tmp_path)
    backend.ensure(["ncit"])
    backend.ensure(["ncit"])  # second call must not double-insert
    n = backend.con.execute(
        "SELECT count(*) FROM terms WHERE ontology = 'ncit' AND curie = 'NCIT:C2955'"
    ).fetchone()[0]
    assert n == 1
