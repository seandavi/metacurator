# 0002. Spec-first development

- Status: accepted
- Date: 2026-06-26

## Context

The toolkit will be implemented and customized repeatedly, often by agents. When code is
the source of truth, customization means refactoring — agents fork, drift, and lose the
original intent. We want downstream users to be able to **build on top of** a stable
contract instead of rewriting it.

## Decision

**Specifications are the source of truth; code is a build artifact of a spec.** Every
component has a spec in `docs/spec/` defining: purpose, inputs/outputs (referencing the
typed contracts in the data-model spec), behavior, invariants, error conditions, and
representative test cases. Implementation exists to satisfy a spec.

Workflow for any behavior change: **edit the spec first, then implement to it.** New
capability = new spec (or spec section) + implementation + tests. Agents are pointed at
the relevant spec and asked to implement/extend *to the spec*, not to mutate unrelated
code.

Specs are versioned with the repo and numbered (`NNN-name.md`) by pipeline stage.

## Consequences

- An agent can be handed a single spec file and produce a conforming implementation or a
  customization layered on top, with no need to reverse-engineer code.
- Contracts (the typed models, the LinkML schema) are stable seams; implementations
  behind them can be swapped (e.g. a new supplement parser) without breaking callers.
- Cost: specs and code can drift. Mitigation — PRs that change behavior must change the
  spec; tests assert the spec's stated cases; CI can later check spec/code coherence.

## Alternatives considered

- **Code-first with good docstrings** — docs lag code; customization still means
  refactoring; intent is implicit.
- **Spec only in a wiki / external doc** — not versioned with the code, drifts faster,
  not in the agent's working tree.
