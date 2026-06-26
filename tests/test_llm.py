"""Judgment-client tests (SPEC 130) — offline; the provider SDK is mocked."""

from __future__ import annotations

import json
from typing import Any

import pytest

from metacurator import judge
from metacurator.dictionary import Dictionary
from metacurator.llm import LLMContractError, make_client, structured
from metacurator.llm.vertex import VertexClient, to_gemini_schema

# -- make_client factory -----------------------------------------------------


def test_make_client_vertex():
    client = make_client("vertex:gemini-2.5-pro")
    assert isinstance(client, VertexClient)
    desc = client.describe()
    assert desc["provider"] == "vertex"
    assert desc["model"] == "gemini-2.5-pro"


def test_make_client_unknown_provider():
    with pytest.raises(ValueError, match="unknown model provider"):
        make_client("acme:model-x")


def test_make_client_bad_spec():
    with pytest.raises(ValueError, match="provider:model"):
        make_client("justamodel")


# -- validate-and-retry wrapper ----------------------------------------------


def test_structured_succeeds_first_try():
    out = structured(lambda fb: '{"a": 1}', {"type": "object", "required": ["a"]})
    assert out == {"a": 1}


def test_structured_retries_then_succeeds():
    calls = {"n": 0}

    def call(feedback):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json"  # first attempt invalid
        assert feedback is not None  # the retry gets the error nudge
        return '{"a": 1}'

    out = structured(call, {"type": "object", "required": ["a"]})
    assert out == {"a": 1}
    assert calls["n"] == 2


def test_structured_raises_after_retries():
    with pytest.raises(LLMContractError, match="schema-valid JSON"):
        structured(lambda fb: "still not json", {"type": "object"}, retries=1)


def test_structured_retries_on_missing_required_key():
    seq = iter(['{"b": 1}', '{"a": 1}'])
    out = structured(lambda fb: next(seq), {"type": "object", "required": ["a"]})
    assert out == {"a": 1}


# -- gemini schema conversion ------------------------------------------------


def test_to_gemini_schema_nullable_and_nesting():
    schema = {
        "type": "object",
        "properties": {
            "curie": {"type": ["string", "null"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}},
                    "required": ["x"],
                },
            },
        },
        "required": ["curie"],
    }
    g = to_gemini_schema(schema)
    assert g["type"] == "object"
    assert g["required"] == ["curie"]
    assert g["properties"]["curie"] == {"type": "string", "nullable": True}
    assert g["properties"]["items"]["type"] == "array"
    assert g["properties"]["items"]["items"]["properties"]["x"] == {"type": "number"}


# -- VertexClient.complete with a mocked genai client ------------------------


class _FakeGenai:
    """Mimics google-genai: ``client.models.generate_content(...).text``."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.last_config: dict[str, Any] | None = None
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.last_config = config
        return type("Resp", (), {"text": self.response_text})()


def test_vertex_complete_returns_dict_and_sets_json_config():
    fake = _FakeGenai('{"table_index": 1, "confidence": 0.9}')
    client = VertexClient("gemini-2.5-pro", client=fake)
    out = client.complete(
        system="sys", prompt="p", schema={"type": "object", "required": ["table_index"]}
    )
    assert out == {"table_index": 1, "confidence": 0.9}
    assert fake.last_config["response_mime_type"] == "application/json"
    assert fake.last_config["system_instruction"] == "sys"
    assert fake.last_config["temperature"] == 0.0


def test_vertex_drives_judge_and_still_enforces_no_mint():
    """The adapter + judge compose: an out-of-set disambiguate CURIE is still rejected."""
    fake = _FakeGenai(json.dumps({"curie": "NCIT:C0000", "rationale": "made up"}))
    client = VertexClient("gemini-2.5-pro", client=fake)
    from metacurator.models import ConfidenceTier, GroundedTerm, Scope

    cands = [
        GroundedTerm(
            query="x", ontology="ncit", curie="NCIT:C2955", label="CRC",
            scope=Scope.label, confidence_tier=ConfidenceTier.review,
        )
    ]
    with pytest.raises(judge.JudgeContractError, match="not in candidate set"):
        judge.disambiguate("x", cands, llm=client)


def test_vertex_propose_mapping_via_model(monkeypatch):
    fake = _FakeGenai(
        json.dumps({"items": [{"source_col": "Sex", "target_field": "sex", "confidence": 0.9}]})
    )
    client = VertexClient("gemini-2.5-pro", client=fake)
    from metacurator.models import SourceProvenance, SourceTable
    from metacurator.tables import Frame

    table = SourceTable(
        frame=Frame(columns=["Sex"], records=[{"Sex": "Male"}]),
        provenance=SourceProvenance(file="s.xlsx"),
        n_rows=1,
        n_cols=1,
    )
    mapping = judge.propose_mapping(table, Dictionary(), llm=client)
    assert mapping.items[0].target_field == "sex"
