"""judge tests (SPEC 100) — the agent boundary, with the LLM client mocked."""

from __future__ import annotations

from typing import Any

import pytest

from metacurator import judge
from metacurator.dictionary import Dictionary
from metacurator.models import (
    ConfidenceTier,
    GroundedTerm,
    Scope,
    SourceProvenance,
    SourceTable,
)
from metacurator.tables import Frame


class MockLLM:
    """Returns a canned response (dict or callable) and records the calls it received."""

    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        return self.response(prompt) if callable(self.response) else self.response


def _table(columns, records, **prov) -> SourceTable:
    return SourceTable(
        frame=Frame(columns=columns, records=records),
        provenance=SourceProvenance(file="supp.xlsx", **prov),
        n_rows=len(records),
        n_cols=len(columns),
    )


@pytest.fixture
def cmd() -> Dictionary:
    return Dictionary()


# -- classify_tables ---------------------------------------------------------


def test_classify_tables_returns_choice(cmd):
    tables = [
        _table(["gene", "fold_change"], [{"gene": "TP53"}], sheet="deg"),
        _table(["subject_id", "disease"], [{"subject_id": "s1"}], sheet="samples"),
    ]
    llm = MockLLM({"table_index": 1, "rationale": "per-subject", "confidence": 0.9})
    choice = judge.classify_tables(tables, cmd, llm=llm)
    assert choice.table_index == 1
    assert choice.needs_review is False


def test_classify_low_confidence_flags_review(cmd):
    tables = [_table(["a"], [{"a": "1"}])]
    llm = MockLLM({"table_index": 0, "confidence": 0.2})
    assert judge.classify_tables(tables, cmd, llm=llm).needs_review is True


def test_classify_out_of_range_index_clamps_and_reviews(cmd):
    tables = [_table(["a"], [{"a": "1"}])]
    llm = MockLLM({"table_index": 9, "confidence": 0.99})
    choice = judge.classify_tables(tables, cmd, llm=llm)
    assert choice.table_index == 0
    assert choice.needs_review is True


# -- propose_mapping ---------------------------------------------------------


def test_propose_mapping_valid(cmd):
    table = _table(["Sex", "BMI"], [{"Sex": "Male", "BMI": "23.5"}])
    llm = MockLLM(
        {
            "items": [
                {"source_col": "Sex", "target_field": "sex", "confidence": 0.9},
                {"source_col": "BMI", "target_field": "bmi", "confidence": 0.9},
            ]
        }
    )
    mapping = judge.propose_mapping(table, cmd, llm=llm)
    assert {i.target_field for i in mapping.items} == {"sex", "bmi"}


def test_propose_mapping_unknown_field_rejected(cmd):
    table = _table(["Sex"], [{"Sex": "Male"}])
    llm = MockLLM(
        {"items": [{"source_col": "Sex", "target_field": "not_a_field", "confidence": 0.9}]}
    )
    with pytest.raises(judge.JudgeContractError, match="not_a_field"):
        judge.propose_mapping(table, cmd, llm=llm)


# -- disambiguate ------------------------------------------------------------


def _cand(curie: str) -> GroundedTerm:
    return GroundedTerm(
        query="x", ontology="ncit", curie=curie, label=curie,
        scope=Scope.label, confidence_tier=ConfidenceTier.review,
    )


def test_disambiguate_picks_a_candidate():
    cands = [_cand("NCIT:C2955"), _cand("NCIT:C9305")]
    llm = MockLLM({"curie": "NCIT:C2955", "rationale": "best"})
    assert judge.disambiguate("colorectal cancer", cands, llm=llm).curie == "NCIT:C2955"


def test_disambiguate_none_is_allowed():
    cands = [_cand("NCIT:C2955")]
    llm = MockLLM({"curie": None})
    assert judge.disambiguate("x", cands, llm=llm).curie is None


def test_disambiguate_out_of_set_raises():
    cands = [_cand("NCIT:C2955")]
    llm = MockLLM({"curie": "NCIT:C0000"})  # not a candidate -> minting attempt
    with pytest.raises(judge.JudgeContractError, match="not in candidate set"):
        judge.disambiguate("x", cands, llm=llm)


def test_disambiguate_no_candidates_short_circuits():
    llm = MockLLM({"curie": "NCIT:C2955"})
    choice = judge.disambiguate("x", [], llm=llm)
    assert choice.curie is None
    assert llm.calls == []  # the model is not consulted when there is nothing to choose
