"""diff/QC tests (SPEC 080) — offline, hand-built candidate/reference rows."""

from __future__ import annotations

from metacurator.diff import diff
from metacurator.models import Verdict


def _by_col(results):
    return {r.column: r for r in results}


def test_clean_match_all_pass():
    rows = [
        {"sample_id": "s1", "disease": "Healthy", "age": "65.0"},
        {"sample_id": "s2", "disease": "Healthy", "age": "40.0"},
    ]
    results = diff(rows, rows, key="sample_id")  # self-diff
    assert all(r.verdict == Verdict.PASS for r in results)
    assert _by_col(results)["disease"].match == 2
    assert _by_col(results)["disease"].mismatch == 0


def test_real_value_conflict_is_fail():
    cand = [{"sample_id": "s1", "disease": "Crohn Disease"}]
    ref = [{"sample_id": "s1", "disease": "Healthy"}]
    r = _by_col(diff(cand, ref, key="sample_id"))["disease"]
    assert r.verdict == Verdict.FAIL
    assert r.mismatch == 1
    assert r.examples[0] == {"key": "s1", "candidate": "Crohn Disease", "reference": "Healthy"}


def test_float_precision_passes_via_tolerance():
    cand = [{"sample_id": "s1", "bmi": "23.4907552"}]
    ref = [{"sample_id": "s1", "bmi": "23.49075518"}]
    r = _by_col(diff(cand, ref, key="sample_id"))["bmi"]
    assert r.verdict == Verdict.PASS
    assert r.match == 1


def test_multivalue_accessions_set_equal():
    cand = [{"sample_id": "s1", "ncbi_accession": "ERR2;ERR1"}]
    ref = [{"sample_id": "s1", "ncbi_accession": "ERR1;ERR2"}]
    r = _by_col(diff(cand, ref, key="sample_id"))["ncbi_accession"]
    assert r.verdict == Verdict.PASS
    assert r.match == 1


def test_multivalue_accessions_set_unequal_is_fail():
    cand = [{"sample_id": "s1", "ncbi_accession": "ERR1;ERR3"}]
    ref = [{"sample_id": "s1", "ncbi_accession": "ERR1;ERR2"}]
    r = _by_col(diff(cand, ref, key="sample_id"))["ncbi_accession"]
    assert r.verdict == Verdict.FAIL


def test_candidate_enrichment_is_cand_adds_not_fail():
    cand = [{"sample_id": "s1", "bmi": "23.5"}]
    ref = [{"sample_id": "s1", "bmi": ""}]  # curated blank
    r = _by_col(diff(cand, ref, key="sample_id"))["bmi"]
    assert r.cand_adds == 1
    assert r.mismatch == 0
    assert r.verdict == Verdict.PASS


def test_candidate_blank_is_coverage_gap_partial():
    cand = [{"sample_id": "s1", "bmi": ""}]
    ref = [{"sample_id": "s1", "bmi": "23.5"}]
    r = _by_col(diff(cand, ref, key="sample_id"))["bmi"]
    assert r.blank == 1
    assert r.verdict == Verdict.PARTIAL


def test_unjoined_rows_reported():
    cand = [{"sample_id": "s1", "x": "a"}, {"sample_id": "s2", "x": "b"}]
    ref = [{"sample_id": "s1", "x": "a"}, {"sample_id": "s3", "x": "c"}]
    summary = _by_col(diff(cand, ref, key="sample_id"))["__rows__"]
    assert summary.compared == 1
    assert summary.cand_adds == 1  # s2 candidate-only
    assert summary.blank == 1  # s3 reference-only
    assert summary.verdict == Verdict.PARTIAL
    assert summary.examples[0]["candidate_only"] == ["s2"]
    assert summary.examples[0]["reference_only"] == ["s3"]


def test_synonym_fold_turns_mismatch_into_match():
    cand = [{"sample_id": "s1", "country": "USA"}]
    ref = [{"sample_id": "s1", "country": "United States"}]
    no_fold = _by_col(diff(cand, ref, key="sample_id"))["country"]
    assert no_fold.verdict == Verdict.FAIL
    folded = _by_col(
        diff(cand, ref, key="sample_id", synonyms={"USA": "United States"})
    )["country"]
    assert folded.verdict == Verdict.PASS


def test_secondary_key_fallback():
    cand = [{"sample_id": "", "biosample": "SAMN1", "x": "a"}]
    ref = [{"sample_id": "", "biosample": "SAMN1", "x": "a"}]
    summary = _by_col(
        diff(cand, ref, key="sample_id", secondary_key="biosample")
    )["__rows__"]
    assert summary.compared == 1


def test_casefold_match():
    cand = [{"sample_id": "s1", "sex": "male"}]
    ref = [{"sample_id": "s1", "sex": "Male"}]
    r = _by_col(diff(cand, ref, key="sample_id"))["sex"]
    assert r.verdict == Verdict.PASS
