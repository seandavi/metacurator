"""dictionary tests (SPEC 060) — load cmd.yaml, introspect, validate."""

from __future__ import annotations

import pytest

from metacurator.dictionary import Dictionary
from metacurator.models import CandidateRow, ColumnMapping, MappingItem


@pytest.fixture
def cmd() -> Dictionary:
    return Dictionary()  # default cmd.yaml, Sample class


def _mapping(*pairs: tuple[str, str]) -> ColumnMapping:
    return ColumnMapping(
        items=[MappingItem(source_col=s, target_field=t, confidence=1.0) for s, t in pairs]
    )


def test_load_cmd_fields(cmd):
    fields = cmd.fields()
    assert {"study_name", "sample_id", "disease", "body_site", "age"} <= set(fields)
    assert cmd.identifier == "sample_id"
    assert cmd.field("age").range == "float"
    assert cmd.field("ncbi_accession").multivalued is True
    assert cmd.field("study_name").required is True


def test_static_enum_permissible_values(cmd):
    body = cmd.field("body_site")
    assert body.is_enum is True
    assert body.is_dynamic_enum is False
    assert body.permissible_values["feces"] == "UBERON:0001988"


def test_dynamic_enum_binding(cmd):
    disease = cmd.field("disease")
    assert disease.is_dynamic_enum is True
    assert disease.binding.ontology == "ncit"
    assert disease.binding.branch_root == "NCIT:C7057"
    assert "Healthy" in disease.permissible_values  # explicit permissible value


def test_ontologies_needed(cmd):
    needed = cmd.ontologies_needed()
    assert {"ncit", "uberon", "ncbitaxon"} <= needed


def test_validate_mapping_unknown_field(cmd):
    errors = cmd.validate_mapping(_mapping(("Disease", "disease"), ("Col2", "not_a_field")))
    assert len(errors) == 1
    assert "not_a_field" in errors[0]


def test_validate_mapping_ok(cmd):
    assert cmd.validate_mapping(_mapping(("Sex", "sex"), ("BMI", "bmi"))) == []


def test_validate_row_static_enum_reject(cmd):
    row = CandidateRow(key="s1", values={"body_site": "spleen"})
    errors = cmd.validate_row(row)
    assert len(errors) == 1 and "body_site" in errors[0]


def test_validate_row_static_enum_accept(cmd):
    row = CandidateRow(key="s1", values={"body_site": "feces", "sex": "Male"})
    assert cmd.validate_row(row) == []


def test_validate_row_numeric(cmd):
    assert cmd.validate_row(CandidateRow(key="s1", values={"age": "65.0"})) == []
    bad = cmd.validate_row(CandidateRow(key="s1", values={"age": "Not applicable"}))
    assert len(bad) == 1 and "age" in bad[0]


def test_validate_row_dynamic_enum_in_branch(cmd, backend):
    row = CandidateRow(key="s1", values={"disease": "Colorectal Carcinoma"})
    assert cmd.validate_row(row, backend=backend) == []


def test_validate_row_dynamic_enum_off_branch(cmd, backend):
    row = CandidateRow(key="s1", values={"disease": "United States"})
    errors = cmd.validate_row(row, backend=backend)
    assert len(errors) == 1 and "NCIT:C7057" in errors[0]


def test_validate_row_dynamic_enum_healthy_permissible(cmd, backend):
    # 'Healthy' is an explicit permissible value, accepted without grounding.
    row = CandidateRow(key="s1", values={"disease": "Healthy"})
    assert cmd.validate_row(row, backend=backend) == []


def test_validate_row_unknown_field(cmd):
    errors = cmd.validate_row(CandidateRow(key="s1", values={"nope": "x"}))
    assert len(errors) == 1 and "nope" in errors[0]
