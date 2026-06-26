# SPEC 110 — pipeline: per-study orchestration & fan-out

- Status: drafted
- Determinism: deterministic (orchestration; delegates judgment to SPEC 100)
- Implements: `src/metacurator/pipeline.py`
- Related: ADR-0004, SPEC 020–100

## Purpose

Wire the stages into a per-study pipeline and a fan-out across many studies — the
deterministic spine that calls the pure tools and delegates only the three judgment steps
(SPEC 100) at fixed joints, with QC gating (SPEC 080).

## Contract

- `curate_study(study, *, dictionary, llm, backend=None, tables=None, reference=None,
  acquire_fn=None, load_tables_fn=load_tables, key=None) -> CurationReport`
- `curate_many(studies, *, dictionary, llm, backend=None, acquire_fn=None,
  reference_fn=None, **kw) -> list[CurationReport]`
- Helpers: `apply_mapping(table, mapping) -> list[dict]`, `ground_rows(rows, dictionary,
  *, backend, llm=None) -> (grounded, notes)`.

The external stages (`acquire`, and later `resolve`/`archive`) are **injected callables**,
so the orchestration is testable offline with fixtures and a mocked LLM; the `llm` and
`backend` are likewise injected.

## Behavior — per-study flow

`acquire → tables → classify_tables(agent) → propose_mapping(agent) → apply +
validate(dictionary) → ground(values) → [disambiguate(agent) only for review-tier]
→ assemble rows → diff/QC → report`.

- Tables come from `tables=` or from `acquire_fn(study)` loaded via `load_tables_fn`.
- `classify_tables` picks the per-subject table; `propose_mapping` is applied by
  `apply_mapping` (projection only — no values invented).
- Each projected row is validated by the dictionary (types, enums, branch via SPEC 070).
- Dynamic-enum values are grounded: a single `auto` term is used directly; otherwise
  `disambiguate` is consulted **only** when there are review-tier candidates (a single
  `auto` never triggers a judgment call).
- With a `reference`, `diff` produces per-column verdicts; the report is assembled.

**QC gating**: `needs_review` is set when classify/propose flag it, validation produces
errors, or any column diffs `FAIL`. The flag is recorded in the report provenance.

## Fan-out

`curate_many` runs each study independently; a per-study exception is **isolated** into a
failed `CurationReport` (notes = the error) rather than aborting the batch — the "scout
one, then pipeline the rest" pattern.

## Invariants

- Control flow is deterministic; the only judgment is the three SPEC 100 calls.
- No stage invents an accession or CURIE; grounding/archive remain authoritative.

## Errors

- Neither `tables` nor `acquire_fn` provided → `ValueError`.
- A study acquiring zero tables → `ValueError` (isolated by `curate_many`).

## Test cases

- One study end-to-end against fixtures (LLM mocked, fixture grounding backend) → a
  `CurationReport` with per-column verdicts.
- A clean reproduction → overall `PASS`; an injected conflict → `FAIL`.
- `disambiguate` is **not** called when grounding yields a single `auto` term (spied).
- A batch where one study raises → that study isolated as a failed report, others succeed.

## Open questions

- Bronze-layer caching / resumability (idempotent re-runs) — deferred to a storage layer.
- Choosing the join key when the identifier field is not in the mapping (currently falls
  back to the dictionary identifier / `key=`).
