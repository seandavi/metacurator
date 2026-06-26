# SPEC NNN — <component>

- Status: stub | drafted | stable
- Determinism: deterministic | agent
- Implements: `src/metacurator/<module>.py`
- Related: ADR-XXXX, SPEC-YYY

## Purpose

One or two sentences: what this component is for.

## Contracts

Inputs and outputs as typed objects from [SPEC 010](010-data-model.md). Give the
function signature(s) the implementation must expose.

## Behavior

What it must do, step by step. State the invariants it guarantees (e.g. idempotency,
"never emits an identifier not returned by a tool").

## Errors

Failure conditions and how they surface (exceptions, typed error results, partial
results + warnings).

## Test cases

Representative cases an implementation must pass, runnable offline against fixtures.

## Open questions

Anything deliberately unresolved.
