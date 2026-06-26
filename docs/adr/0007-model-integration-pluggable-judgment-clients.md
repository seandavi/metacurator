# 0007. Model integration: pluggable judgment clients, Vertex default

- Status: accepted
- Date: 2026-06-26

## Context

`judge.py` is the only place a model runs (ADR-0004) and it already depends on an injected
`LLMClient` Protocol — `complete(*, system, prompt, schema) -> dict` returning a
schema-shaped object. The MCP server does not host a model (ADR-0006), so the CLI `run`
path and library users need *concrete* clients.

We want three things that pull in different directions: (1) flexibility across providers
(Gemini, Claude, open models like Gemma); (2) a light core (the base install is
deliberately minimal — heavy capabilities live behind extras); (3) reproducibility (a run
should record exactly which model produced each judgment). A single cloud also tempts us:
Vertex AI gives one auth (ADC) that reaches Gemini and Claude.

## Decision

We will integrate models as **thin, first-party adapters behind the existing `LLMClient`
Protocol**, each shipped as an **optional extra** — not via a universal LLM library in the
core, and not by hard-locking to one cloud.

- The **Protocol is the flexibility seam**: swapping providers is configuration, never a
  refactor. A `make_client("provider:model")` factory (SPEC 130) resolves clients.
- The **default deployment target is Vertex AI (GCP)**: one ADC auth covering **Gemini**
  (native `response_schema` structured output) and **Claude-on-Vertex**. The first adapter
  we ship is Vertex/Gemini.
- **Structured output is the adapter's responsibility** (Gemini `response_schema`, Claude
  forced tool-use, open models via constrained decoding). A shared **validate-and-retry**
  wrapper in the judgment layer enforces the schema contract provider-agnostically.
- Each judgment client exposes `describe()` (provider, model, version, params); the
  pipeline records it in the `CurationReport` provenance, so a run is reproducible.
- Judgment is run at **temperature 0** by default (stable choices), overridable.

## Consequences

- Flexibility is preserved structurally; Vertex is a default, not a lock-in. A collaborator
  without GCP can pass an Anthropic, OpenAI, or local (Ollama) client to the same seam.
- The core stays light: model SDKs land behind extras (`[vertex]`, later `[anthropic]`,
  `[ollama]`), never in the base dependency set.
- We accept maintaining N small adapters and that **structured-output technique differs per
  provider** (handled inside each adapter). We accept that **Gemma is not turnkey on
  Vertex** (self-managed Model Garden endpoint) — open/local Gemma is better served by an
  Ollama adapter, so "GCP gives us Gemma for free" is explicitly *not* relied upon.
- Runs are reproducible at the model level (id + version + params in provenance).

## Alternatives considered

- **A universal LLM library (LiteLLM / any-llm) in the core** — one adapter, ~100
  providers, but a heavyweight dependency with its own quirks and inconsistent
  structured-output normalization; against the light-core ethos. A user may still wrap one
  and pass it as an `LLMClient` — we just don't depend on it. Rejected for the core.
- **Hard-lock to Vertex/GCP only** — simplest auth and billing, but discards the
  model-agnostic design (ADR-0004/0006) and portability for non-GCP collaborators.
  Rejected.
- **`instructor` / `pydantic-ai` for structured output** — convenient, but another
  opinionated dependency; our schema contract is simple enough for a thin
  validate-and-retry wrapper. Kept optional, not required.
