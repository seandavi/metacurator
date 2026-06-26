# SPEC 130 — judgment clients (LLMClient adapters)

- Status: drafted
- Determinism: **agent-support** (the wrapper is deterministic; the model call is the one
  non-deterministic step, confined to `judge`, ADR-0004)
- Implements: `src/metacurator/llm/` (`base.py`, `vertex.py`), consumed by `judge.py`
- Related: ADR-0004, ADR-0006, ADR-0007, SPEC 100

## Purpose

Provide concrete `LLMClient` implementations for the three judgment calls (SPEC 100) and a
factory to select one, without committing the core to any single provider or to a universal
LLM library (ADR-0007). Make every model call return a **schema-valid object** and make
every run **reproducible** (the model is recorded in provenance).

## Contracts

- **`LLMClient`** (Protocol, defined in `judge.py`): `complete(*, system, prompt, schema:
  dict) -> dict`. An adapter additionally exposes:
  - `describe() -> dict` — `{provider, model, version|None, params}` for provenance.
- **`make_client(spec: str, **opts) -> LLMClient`** — `spec` is `"provider:model"`, e.g.
  `"vertex:gemini-2.5-pro"`. Unknown provider → `ValueError`; a missing provider extra →
  an `ImportError` naming the extra to install.
- **`structured(call, schema, *, retries=2) -> dict`** — the shared validate-and-retry
  wrapper: run `call()`, parse JSON, check it against `schema`; on failure re-ask with the
  error appended, up to `retries`; raise `LLMContractError` after exhausting them.

## Behavior

- **Structured output is provider-native where possible.** The Vertex/Gemini adapter sets
  `response_mime_type="application/json"` and passes the call's JSON `schema` as
  `response_schema` (converted to the OpenAPI subset Gemini accepts), so the model is
  constrained to the shape. Other adapters (future) use their best fit (Claude forced
  tool-use; open models via grammar/JSON-schema constrained decoding).
- **The wrapper is the provider-agnostic safety net**: JSON-parse + schema-shape check with
  bounded retries. `judge.py` remains the final gate (it `pydantic`-validates `complete`'s
  dict into `TableChoice` / `ColumnMapping` / `DisambiguationChoice` and enforces the
  no-mint rules — SPEC 100).
- **Determinism knobs**: judgment defaults to `temperature=0`; `make_client` accepts
  overrides. Auth is out-of-band: Vertex uses ADC (`GOOGLE_CLOUD_PROJECT` /
  `GOOGLE_CLOUD_LOCATION`); no secrets in code or the schema.
- **Provenance**: the pipeline records `llm.describe()` in the `CurationReport` provenance
  so a run names the exact model.

## Invariants

- An adapter never alters the judgment contract: it only transports `system`/`prompt`/
  `schema` to a model and returns a dict. No identifier/value minting happens here — that is
  structurally prevented in `judge` (SPEC 100).
- The base install pulls **no** model SDK; each provider is an extra (`[vertex]`, …).

## Errors

- Provider SDK missing → `ImportError` naming the extra (`pip install metacurator[vertex]`).
- Model returns non-JSON or schema-invalid output after `retries` → `LLMContractError`
  carrying the last raw output.
- Auth/quota errors propagate from the provider SDK (surfaced by the CLI/MCP as structured
  errors).

## Test cases (offline; the provider SDK call is mocked)

- `make_client("vertex:gemini-2.5-pro")` returns a client whose `describe()` reports the
  provider + model; an unknown provider raises `ValueError`.
- `structured()` retries on a first invalid (non-JSON) response and succeeds on a valid
  retry; raises `LLMContractError` after exhausting retries.
- A mocked Vertex client drives `judge.propose_mapping` end-to-end and a schema-invalid
  field is still rejected by `judge` (the two layers compose).
- Live Vertex/Gemini call is gated behind `RUN_INTEGRATION=1` + GCP credentials.

## Open questions

- Whether to convert our JSON-schema dicts to provider schemas generically or keep a small
  per-adapter converter (currently per-adapter, since the subsets differ).
- Caching identical judgment calls (same inputs) for cost/repro — likely a thin on-disk
  cache keyed by (model, system, prompt, schema).
- Claude-on-Vertex vs Anthropic-direct as one adapter with two auth paths, or two adapters
  (deferred until the Anthropic adapter lands).
