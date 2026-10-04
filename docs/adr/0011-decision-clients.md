# 0011. Decision clients for bounded screening judgments

- Status: accepted
- Date: 2026-10-03

## Context

Discovery (SPEC 190) screens thousands of SRA studies with a handful of bounded questions:
is the host human or mouse, is this shotgun sequencing of a microbial community, which body
site. Each answer is a yes/no, a pick-one, or an ordinal level.

The existing model seam is `judge.LLMClient.complete(*, system, prompt, schema) -> dict`
(ADR-0007, SPEC 130): free-form structured JSON from a generative model. Decision models
such as Cloudflare's Clef take a different request — `{state, questions}` with typed
questions (`noul`, `choice`, `score`) — and return a **probability per option** rather
than a single generated value. Thresholding on those probabilities is what lets discovery
route studies to include, review or exclude.

## Decision

We will add a separate **`DecisionClient`** protocol (SPEC 180):
`decide(*, state, questions) -> answers` plus `describe()` for provenance, resolved by a
`make_decision_client("provider:model")` factory that mirrors `llm.make_client`.

- The first provider is Cloudflare Workers AI Clef (`cloudflare:clef`,
  `cloudflare:clef-flash`), called over HTTPS with `httpx`; no SDK dependency.
- Answers are validated against the question set before use (every question answered,
  types match, choice options are exactly the question's criteria keys).
- Thresholds that turn probabilities into include/review/exclude live in target config
  (SPEC 160), not code.
- `LLMClient` is unchanged; the three judgment calls in `judge` keep using it.

## Consequences

- Screening returns calibrated-looking numbers that can be thresholded and audited per
  study; a review band falls out naturally.
- Two model seams exist. They answer different kinds of question and are not
  interchangeable; that is the point.
- A decision provider must return probabilities for every option. Generative LLMs could be
  adapted later (e.g. by sampling) but are not in scope.

## Alternatives considered

- **Route Clef through `LLMClient.complete`.** Rejected: the `complete` contract returns one
  JSON object shaped by a JSON Schema, so option probabilities would be lost or smuggled
  through an ad-hoc schema, and the `{system, prompt, schema}` request does not map onto
  `{state, questions}`.
- **Use a generative LLM for screening.** Rejected for v1: no per-option probabilities,
  higher cost per study, and free text needs extra validation.
