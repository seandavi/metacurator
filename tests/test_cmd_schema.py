"""The one place that asserts the shipped cmd schema specifically (SPEC 060).

Everything else tests the generic dictionary contract against the synthetic test schema, so
cmd.yaml can evolve without churning the suite — only this file tracks it.
"""

from __future__ import annotations

from metacurator.dictionary import Dictionary


def test_cmd_loads_with_expected_shape():
    d = Dictionary()  # default: schema/cmd.yaml, Sample
    fields = d.fields()
    assert {"study_name", "sample_id", "disease", "body_site", "country", "sex"} <= set(fields)
    assert d.identifier == "sample_id"
    assert d.field("age").range == "float"
    assert d.field("ncbi_accession").multivalued is True
    # new optional slots are present and optional.
    assert {"target_condition", "age_group", "ancestry", "sequencing_platform"} <= set(fields)
    assert d.field("age_group").required is False


def test_cmd_dynamic_bindings():
    d = Dictionary()
    assert d.field("disease").binding.branch_root == "NCIT:C7057"
    assert d.field("body_site").binding.ontology == "uberon"
    assert d.field("body_site").binding.branch_root == "UBERON:0001062"
    assert d.field("country").binding.branch_root == "NCIT:C25464"
    # ancestry is a dynamic HANCESTRO enum (audited at 99% agreement).
    assert d.field("ancestry").binding.ontology == "hancestro"
    assert d.field("ancestry").binding.branch_root == "HANCESTRO:0004"
    # age_group is STATIC with verified meanings (dynamic grounding picked the wrong NCIT
    # "Adult"); target_condition is a free string (spans multiple ontologies). See cmd.yaml.
    assert d.field("age_group").is_dynamic_enum is False
    assert d.field("age_group").permissible_values["Adult"] == "NCIT:C49685"
    assert d.field("target_condition").is_dynamic_enum is False
    assert d.field("target_condition").is_enum is False
    # sex stays a static enum with a verified meaning.
    assert d.field("sex").is_dynamic_enum is False
    assert d.field("sex").permissible_values["Male"] == "NCIT:C20197"


def test_cmd_ontologies_needed():
    # ancestry adds HANCESTRO to the set a backend must ensure.
    assert {"ncit", "uberon", "hancestro"} <= Dictionary().ontologies_needed()
