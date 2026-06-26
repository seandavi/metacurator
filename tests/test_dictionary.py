"""dictionary tests (SPEC 060) — the generic contract, against the synthetic test schema.

Uses tests/fixtures/test_schema.yaml (the ``tdict`` fixture), not the shipped cmd schema,
so these tests don't churn when cmd.yaml's bindings change. cmd-specific assertions live in
test_cmd_schema.py.
"""

from __future__ import annotations

from metacurator.models import CandidateRow, ColumnMapping, MappingItem


def _mapping(*pairs: tuple[str, str]) -> ColumnMapping:
    return ColumnMapping(
        items=[MappingItem(source_col=s, target_field=t, confidence=1.0) for s, t in pairs]
    )


def test_load_fields(tdict):
    fields = tdict.fields()
    expected = {"record_id", "group", "accession", "score", "status", "site", "condition"}
    assert set(fields) == expected
    assert tdict.identifier == "record_id"
    assert tdict.field("score").range == "float"
    assert tdict.field("accession").multivalued is True
    assert tdict.field("group").required is True


def test_static_enum_with_meaning(tdict):
    status = tdict.field("status")
    assert status.is_enum is True
    assert status.is_dynamic_enum is False
    assert status.permissible_values["Case"] == "NCIT:C49152"


def test_dynamic_enum_bindings(tdict):
    site = tdict.field("site")
    assert site.is_dynamic_enum is True
    assert site.binding.ontology == "uberon"
    assert site.binding.branch_root == "UBERON:0001062"

    condition = tdict.field("condition")
    assert condition.is_dynamic_enum is True
    assert condition.binding.ontology == "ncit"
    assert condition.binding.branch_root == "NCIT:C7057"
    assert "Healthy" in condition.permissible_values  # explicit permissible value


def test_ontologies_needed(tdict):
    assert {"uberon", "ncit"} <= tdict.ontologies_needed()


def test_validate_mapping_unknown_field(tdict):
    errors = tdict.validate_mapping(_mapping(("A", "site"), ("B", "not_a_field")))
    assert len(errors) == 1 and "not_a_field" in errors[0]


def test_validate_mapping_ok(tdict):
    assert tdict.validate_mapping(_mapping(("A", "status"), ("B", "score"))) == []


def test_validate_row_static_enum_reject(tdict):
    errors = tdict.validate_row(CandidateRow(key="s1", values={"status": "Nope"}))
    assert len(errors) == 1 and "status" in errors[0]


def test_validate_row_static_enum_accept(tdict):
    assert tdict.validate_row(CandidateRow(key="s1", values={"status": "Case"})) == []


def test_validate_row_numeric(tdict):
    assert tdict.validate_row(CandidateRow(key="s1", values={"score": "65.0"})) == []
    bad = tdict.validate_row(CandidateRow(key="s1", values={"score": "Not applicable"}))
    assert len(bad) == 1 and "score" in bad[0]


def test_validate_row_site_grounds_to_uberon(tdict, backend):
    ok = tdict.validate_row(CandidateRow(key="s1", values={"site": "feces"}), backend=backend)
    assert ok == []
    bad = tdict.validate_row(
        CandidateRow(key="s1", values={"site": "United States"}), backend=backend
    )
    assert len(bad) == 1 and "UBERON:0001062" in bad[0]


def test_validate_row_condition_in_branch(tdict, backend):
    row = CandidateRow(key="s1", values={"condition": "Colorectal Carcinoma"})
    assert tdict.validate_row(row, backend=backend) == []


def test_validate_row_condition_off_branch(tdict, backend):
    row = CandidateRow(key="s1", values={"condition": "United States"})
    errors = tdict.validate_row(row, backend=backend)
    assert len(errors) == 1 and "NCIT:C7057" in errors[0]


def test_validate_row_condition_healthy_permissible(tdict, backend):
    # 'Healthy' is an explicit permissible value, accepted without grounding.
    row = CandidateRow(key="s1", values={"condition": "Healthy"})
    assert tdict.validate_row(row, backend=backend) == []


def test_validate_row_unknown_field(tdict):
    errors = tdict.validate_row(CandidateRow(key="s1", values={"nope": "x"}))
    assert len(errors) == 1 and "nope" in errors[0]
