"""Grounding tests (SPEC 070) — offline, against the tiny fixture store in conftest."""

from __future__ import annotations

from metacurator.ground import ground
from metacurator.models import ConfidenceTier, Scope

NCIT_DISEASE_ROOT = "NCIT:C2991"


def test_exact_label_in_branch_is_auto(backend):
    """Exact label hit, branch-ok, not obsolete -> a single ``auto`` GroundedTerm."""
    terms = ground("Colorectal Carcinoma", "ncit", backend=backend, branch_root=NCIT_DISEASE_ROOT)
    assert len(terms) == 1
    t = terms[0]
    assert t.curie == "NCIT:C2955"
    assert t.scope == Scope.label
    assert t.branch_ok is True
    assert t.obsolete is False
    assert t.confidence_tier == ConfidenceTier.auto


def test_exact_synonym_hit(backend):
    """An exact-synonym match grounds with ``scope == exact`` and is auto-eligible."""
    terms = ground("Colorectal Cancer", "ncit", backend=backend, branch_root=NCIT_DISEASE_ROOT)
    assert len(terms) == 1
    t = terms[0]
    assert t.curie == "NCIT:C2955"
    assert t.scope == Scope.exact
    assert t.confidence_tier == ConfidenceTier.auto


def test_no_branch_constraint_grounds_auto(backend):
    """With no declared branch root, an exact non-obsolete label is auto (branch N/A)."""
    terms = ground("oral cavity", "uberon", backend=backend)
    assert len(terms) == 1
    assert terms[0].curie == "UBERON:0000167"
    assert terms[0].confidence_tier == ConfidenceTier.auto


def test_out_of_branch_is_not_auto(backend):
    """A term outside the declared branch is returned but branch_ok=False, tier review."""
    terms = ground("United States", "ncit", backend=backend, branch_root=NCIT_DISEASE_ROOT)
    assert len(terms) == 1
    t = terms[0]
    assert t.curie == "NCIT:C17234"
    assert t.branch_ok is False
    assert t.confidence_tier == ConfidenceTier.review


def test_obsolete_term_rejected_with_replacement(backend):
    """A deprecated term -> obsolete=True, replaced_by surfaced, tier none."""
    terms = ground("Obsolete Disease", "ncit", backend=backend, branch_root=NCIT_DISEASE_ROOT)
    assert len(terms) == 1
    t = terms[0]
    assert t.obsolete is True
    assert t.replaced_by == "NCIT:C2955"
    assert t.confidence_tier == ConfidenceTier.none


def test_ambiguous_exact_hits_demoted_to_review(backend):
    """Two terms share the label 'feces' -> ambiguous, so neither is auto (all review)."""
    terms = ground("feces", "uberon", backend=backend)
    assert len(terms) == 2
    assert {t.curie for t in terms} == {"UBERON:0001988", "UBERON:8888888"}
    assert all(t.confidence_tier == ConfidenceTier.review for t in terms)


def test_label_and_exact_synonym_collapse_to_one_auto(backend):
    """A value that is both a term's label and an exact synonym -> one auto term, not two.

    (Regression: real NCIT lists 'Colorectal Carcinoma' as both; the un-deduped result
    looked like ambiguity and demoted to review.)
    """
    terms = ground("Colorectal Carcinoma", "ncit", backend=backend, branch_root=NCIT_DISEASE_ROOT)
    assert len(terms) == 1
    assert terms[0].curie == "NCIT:C2955"
    assert terms[0].confidence_tier == ConfidenceTier.auto


def test_label_match_outranks_synonym_matches(backend):
    """A clean label hit is auto even when other terms match the value as a synonym.

    (Regression: 'Hypertension' is C3117's label but also an exact synonym of C168203
    'Family History of Hypertension'; the synonym competitor must not demote the label hit.)
    """
    terms = ground("Hypertension", "ncit", backend=backend, branch_root="NCIT:C7057")
    autos = [t for t in terms if t.confidence_tier == ConfidenceTier.auto]
    assert [t.curie for t in autos] == ["NCIT:C3117"]
    assert any(
        t.curie == "NCIT:C168203" and t.confidence_tier == ConfidenceTier.review
        for t in terms
    )


def test_no_hit_returns_empty(backend):
    assert ground("not a real value", "uberon", backend=backend) == []


def test_lookup_restricted_to_one_ontology(backend):
    """A value present only in NCIT does not leak when querying UBERON."""
    assert ground("Colorectal Carcinoma", "uberon", backend=backend) == []


# -- branch-closure (recursive CTE) primitive --------------------------------


def test_reachable_from_multihop(backend):
    assert backend.reachable_from("NCIT:C2955", "NCIT:C2991", "ncit") is True


def test_reachable_from_self(backend):
    assert backend.reachable_from("NCIT:C2991", "NCIT:C2991", "ncit") is True


def test_reachable_from_false_when_off_branch(backend):
    assert backend.reachable_from("NCIT:C17234", "NCIT:C2991", "ncit") is False


# -- shape parity: same query logic, schema-qualified (DuckLake table shape) ---


def test_shape_parity_local_vs_qualified(backend, schema_qualified_store):
    """Identical lookup results from the local store and a schema-qualified store."""
    local = backend.lookup("Colorectal Cancer", "ncit")
    qualified = schema_qualified_store.lookup("Colorectal Cancer", "ncit")
    assert [(t.curie, t.scope) for t in local] == [(t.curie, t.scope) for t in qualified]
    assert qualified[0].curie == "NCIT:C2955"
    # Closure parity too.
    assert schema_qualified_store.reachable_from("NCIT:C2955", "NCIT:C2991", "ncit") is True
