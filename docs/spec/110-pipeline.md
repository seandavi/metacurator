# SPEC 110 — pipeline: per-study orchestration & fan-out

- Status: stub
- Determinism: deterministic (orchestration; delegates judgment to SPEC 100)
- Implements: `src/metacurator/pipeline.py`
- Related: ADR-0004, SPEC 020–100

## Purpose

Wire the stages into a per-study pipeline and a fan-out across many studies — the
deterministic spine that calls the pure tools and delegates only the three judgment steps
(SPEC 100) at fixed joints, with QC gating (SPEC 080) and resumability.

## Scope note for implementation

Per-study flow:
`resolve → archive → acquire → tables → classify_tables(agent) → propose_mapping(agent)
→ apply+validate(dictionary) → ground(values) → [disambiguate(agent) for review-tier]
→ assemble CandidateRows → diff/QC → report`.

- Deterministic control flow; idempotent and resumable (bronze cached; re-runs cheap).
- Fan-out across a study list (the "scout one, then pipeline the rest" pattern from the
  reproduction run); per-study failure is isolated, not fatal to the batch.
- QC gates: a low-confidence `classify`/`propose` or a FAIL diff routes to human review.

## To complete

Fill the template. Cases: one study end-to-end against fixtures (LLM mocked); a batch
with one failing study isolated; resume from a cached bronze layer.
