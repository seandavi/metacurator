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


def test_cmd_dynamic_bindings():
    d = Dictionary()
    assert d.field("disease").binding.branch_root == "NCIT:C7057"
    assert d.field("body_site").binding.ontology == "uberon"
    assert d.field("body_site").binding.branch_root == "UBERON:0001062"
    assert d.field("country").binding.branch_root == "NCIT:C25464"
    # sex stays a static enum with a verified meaning.
    assert d.field("sex").is_dynamic_enum is False
    assert d.field("sex").permissible_values["Male"] == "NCIT:C20197"


def test_cmd_ontologies_needed():
    assert {"ncit", "uberon"} <= Dictionary().ontologies_needed()
