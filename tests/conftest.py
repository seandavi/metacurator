"""Shared offline test fixtures.

A tiny ontology store (UBERON + NCIT) mirroring the bindings in ``schema/cmd.yaml``,
built directly into the four-table store shape (SPEC 070) so grounding tests run with no
network and no downloaded ``.db.gz``.
"""

from __future__ import annotations

import duckdb
import pytest

from metacurator.grounding._store import STORE_DDL, DuckStore
from metacurator.grounding.local_duckdb import LocalDuckDBBackend

# (ontology, curie, label, definition, obsolete, replaced_by)
FIXTURE_TERMS = [
    ("uberon", "UBERON:0001988", "feces", None, False, None),
    ("uberon", "UBERON:0000167", "oral cavity", None, False, None),
    # A second term sharing the "feces" label, to exercise ambiguity demotion.
    ("uberon", "UBERON:8888888", "feces", None, False, None),
    ("ncit", "NCIT:C7057", "Disease, Disorder or Finding", None, False, None),
    ("ncit", "NCIT:C2991", "Disease or Disorder", None, False, None),
    ("ncit", "NCIT:C9305", "Neoplasm", None, False, None),
    ("ncit", "NCIT:C2955", "Colorectal Carcinoma", None, False, None),
    ("ncit", "NCIT:C115935", "Healthy", None, False, None),
    ("ncit", "NCIT:C17234", "United States", None, False, None),  # geographic, off-branch
    ("ncit", "NCIT:C99999", "Obsolete Disease", None, True, "NCIT:C2955"),
    # Label-vs-synonym competition: 'Hypertension' is C3117's label but also an exact
    # synonym of C168203 ('Family History of Hypertension'). The label hit must win.
    ("ncit", "NCIT:C3117", "Hypertension", None, False, None),
    ("ncit", "NCIT:C168203", "Family History of Hypertension", None, False, None),
]

# (ontology, curie, synonym, scope)
FIXTURE_SYNONYMS = [
    ("uberon", "UBERON:0001988", "stool", "exact"),
    ("uberon", "UBERON:0001988", "intestinal mass", "broad"),
    ("ncit", "NCIT:C2955", "Colorectal Cancer", "exact"),
    # NCIT also lists a term's preferred name as an exact synonym, so a value can hit one
    # CURIE via both label and synonym — grounding must collapse that to a single term.
    ("ncit", "NCIT:C2955", "Colorectal Carcinoma", "exact"),
    ("ncit", "NCIT:C168203", "Hypertension", "exact"),  # synonym competitor (loses to label)
]

# (ontology, subject, predicate, object)
FIXTURE_EDGES = [
    ("ncit", "NCIT:C2955", "rdfs:subClassOf", "NCIT:C9305"),
    ("ncit", "NCIT:C9305", "rdfs:subClassOf", "NCIT:C2991"),
    ("ncit", "NCIT:C2991", "rdfs:subClassOf", "NCIT:C7057"),  # under the broad root
    ("ncit", "NCIT:C99999", "rdfs:subClassOf", "NCIT:C2991"),
    ("ncit", "NCIT:C3117", "rdfs:subClassOf", "NCIT:C7057"),  # Hypertension (a Finding)
    ("ncit", "NCIT:C168203", "rdfs:subClassOf", "NCIT:C7057"),
    # C17234 (United States) and C115935 (Healthy) are deliberately NOT under C2991/C7057.
]


def _insert(con: duckdb.DuckDBPyConnection, q: str = "") -> None:
    con.executemany(f"INSERT INTO {q}terms VALUES (?, ?, ?, ?, ?, ?)", FIXTURE_TERMS)
    con.executemany(f"INSERT INTO {q}synonyms VALUES (?, ?, ?, ?)", FIXTURE_SYNONYMS)
    con.executemany(f"INSERT INTO {q}edges VALUES (?, ?, ?, ?)", FIXTURE_EDGES)


@pytest.fixture
def backend(tmp_path) -> LocalDuckDBBackend:
    """A LocalDuckDBBackend whose store is pre-seeded with the fixture ontology."""
    b = LocalDuckDBBackend(cache_dir=tmp_path)
    _insert(b.con)
    return b


@pytest.fixture
def schema_qualified_store() -> DuckStore:
    """The same fixture data under an ``ontology.`` schema — the DuckLake table shape.

    Lets us prove shape parity (identical query logic via the qualifier) offline, without
    requiring the DuckLake extension; real DuckLake attach is covered under integration.
    """
    con = duckdb.connect()
    con.execute("CREATE SCHEMA ontology")
    con.execute(STORE_DDL.replace("TABLE IF NOT EXISTS ", "TABLE IF NOT EXISTS ontology."))
    _insert(con, "ontology.")
    return DuckStore(con, qualifier="ontology.")
