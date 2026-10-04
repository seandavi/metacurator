"""Decision-client tests (SPEC 180). Offline via httpx.MockTransport; one gated live call."""

from __future__ import annotations

import json
import os

import httpx
import pytest

from metacurator.decision import DecisionError, make_decision_client
from metacurator.decision import cloudflare as cf
from metacurator.decision.cloudflare import ClefClient

QUESTIONS = {
    "host": {
        "type": "choice",
        "instructions": "What host were the sequenced samples taken from?",
        "criteria": {
            "human": "Living humans: stool, body sites, tissues, or body fluids",
            "mouse": "Laboratory or wild mice, including germ-free or humanized mice",
            "environment": "Environmental samples: soil, water, air, wastewater, food",
        },
    },
    "shotgun": {"type": "noul", "instructions": "Is this shotgun metagenomics?"},
}

ANSWERS = {
    "host": {
        "type": "choice",
        "choice": "human",
        "probabilities": {"human": 0.9, "mouse": 0.08, "environment": 0.02},
        "confidence": 0.85,
    },
    "shotgun": {"type": "noul", "noul": 0.97},
}


def _client(handler, **kw) -> ClefClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ClefClient("clef", account_id="acct", token="tok", http=http, **kw)


def _ok(answers=ANSWERS) -> httpx.Response:
    return httpx.Response(
        200, json={"success": True, "errors": [], "result": {"model": "clef", "answers": answers}}
    )


def test_success_envelope_parsed_and_request_shape():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok({**ANSWERS, "extra": {"type": "noul", "noul": 0.1}})

    answers = _client(handler).decide(state={"title": "t"}, questions=QUESTIONS)
    assert set(answers) == {"host", "shotgun"}  # extra ids dropped
    assert answers["host"]["choice"] == "human"
    assert answers["shotgun"]["noul"] == 0.97
    req = seen[0]
    assert str(req.url).endswith("/accounts/acct/ai/run/@cf/cloudflare/clef")
    assert req.headers["authorization"] == "Bearer tok"
    assert json.loads(req.content) == {
        "model": "clef", "state": {"title": "t"}, "questions": QUESTIONS
    }


def test_bare_result_body_accepted():
    answers = _client(lambda r: httpx.Response(200, json={"answers": ANSWERS})).decide(
        state="s", questions=QUESTIONS
    )
    assert answers["host"]["probabilities"]["mouse"] == 0.08


def test_retry_on_429_then_success(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(cf.time, "sleep", sleeps.append)
    responses = iter([httpx.Response(429, text="slow down"), _ok()])
    answers = _client(lambda r: next(responses)).decide(state="s", questions=QUESTIONS)
    assert answers["host"]["choice"] == "human"
    assert sleeps == [1]


def test_retries_exhausted(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(cf.time, "sleep", sleeps.append)
    with pytest.raises(DecisionError, match="after 4 attempts.*HTTP 503"):
        _client(lambda r: httpx.Response(503, text="down")).decide(state="s", questions=QUESTIONS)
    assert sleeps == [1, 2, 4]


def test_client_error_not_retried(monkeypatch):
    calls: list[int] = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text='{"errors":[{"code":10000}]}')

    monkeypatch.setattr(cf.time, "sleep", lambda s: pytest.fail("must not sleep"))
    with pytest.raises(DecisionError, match="HTTP 401"):
        _client(handler).decide(state="s", questions=QUESTIONS)
    assert calls == [1]


def test_success_false_is_error():
    body = {"success": False, "errors": [{"code": 5006, "message": "bad input"}], "result": None}
    with pytest.raises(DecisionError, match="clef error.*bad input"):
        _client(lambda r: httpx.Response(200, json=body)).decide(state="s", questions=QUESTIONS)


@pytest.mark.parametrize(
    ("answers", "message"),
    [
        ({"host": ANSWERS["host"]}, "'shotgun': no answer"),
        ({**ANSWERS, "shotgun": {"type": "choice", "choice": "x"}}, "answer type"),
        ({**ANSWERS, "shotgun": {"type": "noul", "noul": 1.5}}, r"not in \[0, 1\]"),
        (
            {**ANSWERS, "host": {**ANSWERS["host"], "probabilities": {"human": 1.0}}},
            "probabilities keys",
        ),
        ({**ANSWERS, "host": {**ANSWERS["host"], "choice": "cat"}}, "not an option"),
    ],
)
def test_invalid_answers_rejected(answers, message):
    with pytest.raises(DecisionError, match=message):
        _client(lambda r: _ok(answers)).decide(state="s", questions=QUESTIONS)


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_AUTH_TOKEN", raising=False)
    client = ClefClient("clef", http=httpx.Client(transport=httpx.MockTransport(lambda r: _ok())))
    with pytest.raises(DecisionError, match="CLOUDFLARE_ACCOUNT_ID"):
        client.decide(state="s", questions=QUESTIONS)


def test_factory():
    client = make_decision_client("cloudflare:clef-flash")
    assert client.describe() == {
        "provider": "cloudflare", "model": "clef-flash", "endpoint": "workers-ai", "params": {}
    }
    with pytest.raises(ValueError, match="unknown decision provider"):
        make_decision_client("openai:gpt")
    with pytest.raises(ValueError, match="unknown Clef model"):
        make_decision_client("cloudflare:clef-max")
    with pytest.raises(ValueError, match="provider:model"):
        make_decision_client("clef")


@pytest.mark.skipif(
    not (
        os.environ.get("RUN_INTEGRATION")
        and os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        and os.environ.get("CLOUDFLARE_AUTH_TOKEN")
    ),
    reason="live Clef call: set RUN_INTEGRATION=1, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_AUTH_TOKEN",
)
def test_live_clef_host_human():
    state = {
        "title": "Potential of fecal microbiota for early stage detection of colorectal cancer",
        "organisms": {"Homo sapiens": 199},
    }
    answers = ClefClient("clef").decide(state=state, questions={"host": QUESTIONS["host"]})
    assert answers["host"]["choice"] == "human"
