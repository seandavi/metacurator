# SPEC 180 — decision clients (DecisionClient + Clef)

- Status: drafted
- Determinism: **agent-support** (validation is deterministic; the model call is not)
- Implements: `src/metacurator/decision/` (`base.py`, `cloudflare.py`)
- Related: ADR-0007, ADR-0011, SPEC 130, SPEC 160, SPEC 190

## Purpose

Answer bounded screening questions (yes/no, pick-one, ordinal) about a state object with a
**probability for every option**, through a provider-agnostic protocol, so discovery
(SPEC 190) can threshold those probabilities into include/review/exclude (ADR-0011).

## Contracts

```python
class DecisionError(RuntimeError): ...

class DecisionClient(Protocol):
    def decide(self, *, state: dict[str, Any] | str,
               questions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]: ...
    def describe(self) -> dict[str, Any]: ...   # {provider, model, endpoint, params}

def validate_answers(questions, answers) -> dict[str, dict[str, Any]]
def make_decision_client(spec: str, **opts) -> DecisionClient   # "provider:model"
```

Questions use Clef's schema (Workers AI `@cf/cloudflare/clef` input schema):
`{"type": "noul", "instructions": ..., "criteria"?: {"true": ..., "false": ...}}`,
`{"type": "choice", "instructions": ..., "criteria": {option: description, ...}}`,
`{"type": "score", "instructions": ..., "criteria": [level0, level1, ...]}`.

Answers, keyed by question id:
`{"type": "noul", "noul": p_yes}`,
`{"type": "choice", "choice": argmax, "probabilities": {option: p}, "confidence": c}`,
`{"type": "score", "score": s, "probabilities": {...}, "legend": {...}, "confidence": c}`.

`ClefClient(model, *, account_id=None, token=None, timeout=60.0, max_retries=3, http=None)`,
`model ∈ {clef, clef-flash}`; endpoint
`https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{model}`.

## Behavior

- `make_decision_client("cloudflare:clef")` / `("cloudflare:clef-flash")` → `ClefClient`.
- `validate_answers` checks every question id has an answer, the answer `type` equals the
  question `type`, a `noul` value is a number in [0, 1], and a `choice` answer's `choice`
  is a criteria key and its `probabilities` keys equal the criteria keys. It returns the
  answers restricted to the question ids (extra answer ids are dropped).
- `ClefClient.decide`:
  1. Resolve `account_id`/`token` lazily (first call) from arguments, else
     `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_AUTH_TOKEN`.
  2. `POST` the endpoint with `Authorization: Bearer <token>` and JSON
     `{"model": model, "state": state, "questions": questions}`.
  3. HTTP 429, 5xx or a transport error: sleep `2 ** attempt` seconds (1, 2, 4) and retry,
     up to `max_retries` retries.
  4. Other 4xx: fail immediately.
  5. 2xx: parse JSON; `success: false` is a failure; the payload is `body["result"]` when
     present (REST envelope), else the body; return `validate_answers(questions,
     payload["answers"])`.
- `describe()` → `{"provider": "cloudflare", "model": model, "endpoint": "workers-ai",
  "params": {}}`.
- The client is synchronous (`httpx.Client`) and thread-safe for concurrent `decide`
  calls; callers parallelise with threads.
- No secrets in code or logs: the token is never included in error messages.

## Errors

- Malformed spec → `ValueError("decision client spec must be 'provider:model', got '<s>'")`.
- Unknown provider → `ValueError("unknown decision provider '<p>'; known: ['cloudflare']")`.
- Unknown Clef model → `ValueError`.
- Missing credentials → `DecisionError("set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AUTH_TOKEN")`.
- Retries exhausted → `DecisionError` with the last status and body (or transport error).
- Non-retryable 4xx → `DecisionError` with status and body.
- `success: false` → `DecisionError("clef error: <errors>")`.
- Answers failing validation → `DecisionError` naming the question id.

## Test cases (offline, `httpx.MockTransport`)

- A REST envelope with noul + choice answers parses and validates.
- 429 then 200 succeeds (sleep patched out); the request carried the bearer token and the
  `{model, state, questions}` body.
- `{"success": false, "errors": [...]}` → `DecisionError`.
- An answer missing for a question id → `DecisionError`.
- No credentials in env → `DecisionError`.
- Unknown provider / unknown Clef model / malformed spec → `ValueError`.
- Live (gated by `RUN_INTEGRATION=1` and both env vars): Clef answers `host = human` for the
  ZellerG_2014 colorectal-cancer study title.

## Open questions

- Async client if discovery outgrows threads.
- Recording Clef's `usage` (token counts) for cost reporting.
