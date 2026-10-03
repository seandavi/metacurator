"""The one place that asserts the shipped cmd curation target specifically (ADR-0010).

Everything else tests the generic contracts against the synthetic test schema, so
targets/cmd/ can evolve without churning the suite — only this file tracks it.
"""

from __future__ import annotations

import pytest

from metacurator.dictionary import Dictionary
from metacurator.target import load_target


@pytest.fixture(scope="module")
def cmd() -> Dictionary:
    return Dictionary(load_target("cmd").schema_path)


def test_cmd_loads_with_expected_shape(cmd):
    fields = cmd.fields()
    assert {"study_name", "sample_id", "disease", "body_site", "country", "sex"} <= set(fields)
    assert cmd.identifier == "sample_id"
    assert cmd.field("age").range == "float"
    assert cmd.field("ncbi_accession").multivalued is True
    # new optional slots are present and optional.
    assert {"target_condition", "age_group", "ancestry", "sequencing_platform"} <= set(fields)
    assert cmd.field("age_group").required is False


def test_cmd_dynamic_bindings(cmd):
    assert cmd.field("disease").binding.branch_root == "NCIT:C7057"
    assert cmd.field("body_site").binding.ontology == "uberon"
    assert cmd.field("body_site").binding.branch_root == "UBERON:0001062"
    assert cmd.field("country").binding.branch_root == "NCIT:C25464"
    # ancestry is a dynamic HANCESTRO enum (audited at 99% agreement).
    assert cmd.field("ancestry").binding.ontology == "hancestro"
    assert cmd.field("ancestry").binding.branch_root == "HANCESTRO:0004"
    # age_group is STATIC with verified meanings (dynamic grounding picked the wrong NCIT
    # "Adult"); target_condition is a free string (spans multiple ontologies). See
    # targets/cmd/schema.yaml.
    assert cmd.field("age_group").is_dynamic_enum is False
    assert cmd.field("age_group").permissible_values["Adult"] == "NCIT:C49685"
    assert cmd.field("target_condition").is_dynamic_enum is False
    assert cmd.field("target_condition").is_enum is False
    # sex stays a static enum with a verified meaning.
    assert cmd.field("sex").is_dynamic_enum is False
    assert cmd.field("sex").permissible_values["Male"] == "NCIT:C20197"


def test_cmd_ontologies_needed(cmd):
    # ancestry adds HANCESTRO to the set a backend must ensure.
    assert {"ncit", "uberon", "hancestro"} <= cmd.ontologies_needed()
