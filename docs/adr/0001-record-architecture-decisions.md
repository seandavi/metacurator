# 0001. Record architecture decisions

- Status: accepted
- Date: 2026-06-26

## Context

metacurator is intended to be built and extended largely by agents working from written
artifacts. Decisions that are only implicit in code get relitigated, reversed by
accident, and are invisible to a fresh contributor (human or agent).

## Decision

We will keep **Architecture Decision Records** in `docs/adr/`, one file per decision,
numbered and immutable once accepted. To change an accepted decision, add a new ADR that
supersedes it (and mark the old one superseded) — we do not edit history.

Use `docs/adr/0000-template.md`. Every ADR states context, the decision, consequences
(including accepted downsides), and rejected alternatives.

## Consequences

- The "why" is durable and greppable; a new session can catch up by reading the ADRs.
- A small discipline tax on each substantive change.
- ADRs pair with two other artifact classes: **specs** (`docs/spec/`, what each
  component must do) and **design docs** (`docs/design/`, how the pieces fit).

## Alternatives considered

- **Decisions in code comments / commit messages** — not discoverable, not durable.
- **A single design doc** — becomes a stale monolith; ADRs localize and date decisions.
