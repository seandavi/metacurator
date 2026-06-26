# Design overview

metacurator reproduces curated, sample-level metadata from publications. This document
explains how the pieces fit; the *why* is in the [ADRs](../adr/), the *what each piece
must do* is in the [specs](../spec/).

## Layers

1. **Schema (LinkML).** `schema/*.yaml` declares the target standard: fields, types,
   enums with ontology `meaning`s, and dynamic-enum ontology bindings. Compiles to
   Pydantic record models + JSON Schema (ADR-0003). Pluggable — `cmd` is the first.

2. **Typed contracts (SPEC 010).** Framework process-objects (`StudyRef`,
   `AccessionMap`, `SourceTable`, `ColumnMapping`, `GroundedTerm`, `CandidateRow`,
   `DiffResult`, `CurationReport`). Every stage speaks only these.

3. **Deterministic spine.** `resolve · archive · acquire · tables · dictionary · ground ·
   diff · report` — pure, tested, no LLM (ADR-0004).

4. **Agent boundary (SPEC 100).** `judge.py`: `classify_tables`, `propose_mapping`,
   `disambiguate`. The only LLM in the system; returns typed objects, never identifiers.

5. **Grounding backends (ADR-0005).** `LocalDuckDBBackend` (default, no infra) and
   `DuckLakeBackend` (opt-in), sharing one ontology-store shape.

6. **Orchestration (SPEC 110)** and **tool surface (SPEC 120):** the pipeline + fan-out,
   exposed as Python API, CLI, and a streamable-HTTP MCP server.

## The central idea

The determinism gradient (ADR-0004): push everything mechanical into deterministic tools
(cheap, reproducible, auditable, hallucination-proof), and reserve the model for the
three irreducibly ambiguous steps — which return typed objects the deterministic code
validates and applies. Identifiers (accessions, ontology CURIEs) are produced only by
tools. That single rule is what makes automated curation trustworthy.

## Maturity path

1. **Tools** (this scaffold → implementation): the deterministic library + grounding.
2. **Skill**: package the technique corpus to drive the tools interactively (the agent
   boundary).
3. **Workflow**: the deterministic pipeline + fan-out for reproducible bulk runs.

See [data-flow.md](data-flow.md) for the per-study sequence.
