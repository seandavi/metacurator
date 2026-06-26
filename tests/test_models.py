"""Framework-contract tests (SPEC 010). These pass at the scaffold stage — the typed
models are real even though the spine functions are stubs.
"""

from __future__ import annotations

import pytest

from metacurator.models import (
    AccessionMap,
    AccessionRow,
    ColumnMapping,
    ConfidenceTier,
    GroundedTerm,
    MappingItem,
    OAStatus,
    StudyRef,
)


def test_studyref_roundtrips():
    s = StudyRef(pmid="123", pmcid="PMC1", oa_status=OAStatus.oa)
    assert StudyRef.model_validate_json(s.model_dump_json()) == s


def test_accession_map_holds_rows():
    m = AccessionMap(project="PRJEB1", rows=[AccessionRow(run="ERR1", sample="SAMEA1")])
    assert m.rows[0].run == "ERR1"


def test_column_mapping_confidence_bounds():
    ColumnMapping(items=[MappingItem(source_col="Age", target_field="age", confidence=1.0)])
    with pytest.raises(ValueError):
        MappingItem(source_col="x", target_field="y", confidence=2.0)


def test_grounded_term_defaults_to_unconfirmed():
    g = GroundedTerm(query="heart", ontology="uberon")
    # A grounding with no verified CURIE must default to the 'none' tier (ADR-0004).
    assert g.curie is None
    assert g.confidence_tier == ConfidenceTier.none
    assert g.branch_ok is False
