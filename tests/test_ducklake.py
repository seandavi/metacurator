"""DuckLakeBackend integration test (SPEC 070, ADR-0005) — live, gated.

Runs only when RUN_INTEGRATION=1 and METACURATOR_DUCKLAKE_DSN point at a real DuckLake whose
``ontology`` schema has the four-table store shape (e.g. a Postgres-catalog DuckLake:
``ducklake:postgres:dbname=lake host=... user=postgres``). Offline coverage of the same
query logic lives in test_grounding.py (the schema-qualified store).
"""

from __future__ import annotations

import os

import pytest

from metacurator.ground import ground
from metacurator.models import ConfidenceTier

DSN = os.environ.get("METACURATOR_DUCKLAKE_DSN")

pytestmark = pytest.mark.skipif(
    not (os.environ.get("RUN_INTEGRATION") and DSN),
    reason="set RUN_INTEGRATION=1 and METACURATOR_DUCKLAKE_DSN for a live DuckLake",
)


def test_ducklake_grounds_real_term():
    from metacurator.grounding.ducklake import DuckLakeBackend

    backend = DuckLakeBackend(dsn=DSN)
    # 'asthma' is DOID:2841, under DOID:4 "disease" — a stable, broadly-available ontology.
    terms = ground("asthma", "doid", backend=backend, branch_root="DOID:4")
    assert any(
        t.curie == "DOID:2841" and t.confidence_tier == ConfidenceTier.auto for t in terms
    )
    assert backend.reachable_from("DOID:2841", "DOID:4", "doid") is True
    assert backend.get("DOID:2841", "doid").label == "asthma"
