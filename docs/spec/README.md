# Specifications

**Specs are the source of truth. Code implements a spec.** (See
[ADR-0002](../adr/0002-spec-first-development.md).)

If you are an agent or contributor: find the spec for the component you're working on,
implement or extend **to that spec**, and add tests for the cases it lists. Do not
refactor unrelated modules — customizations layer on top of the contracts, they don't
rewrite them.

## How to read a spec

Each spec is self-contained and follows the template in [`_TEMPLATE.md`](_TEMPLATE.md):

- **Purpose** — what this component is for, in one or two sentences.
- **Determinism** — `deterministic` (no LLM, ADR-0004) or `agent` (judgment).
- **Contracts** — the typed inputs/outputs, referencing the data-model spec (010).
- **Behavior** — what it must do, step by step; the invariants it guarantees.
- **Errors** — failure conditions and how they surface.
- **Test cases** — representative cases an implementation must pass (offline).
- **Open questions** — anything deliberately unresolved.

## Index (by pipeline stage)

| spec | component | determinism | status |
|---|---|---|---|
| [000](000-glossary.md) | Glossary & conventions | — | stub |
| [010](010-data-model.md) | Typed contracts (the objects every stage passes) | — | **drafted** ✓ |
| [020](020-resolve.md) | `resolve`: PMID→PMCID/DOI, OA triage | deterministic | **drafted** ✓ |
| [030](030-archive-ena.md) | `archive`: ENA/BioSample accession + ID map | deterministic | **drafted** ✓ |
| [040](040-acquire.md) | `acquire`: supplement retrieval ladder | deterministic | **drafted** ✓ |
| [050](050-tables.md) | `tables`: load xlsx/docx/pdf/csv → table | deterministic | **drafted** ✓ |
| [060](060-dictionary.md) | `dictionary`: LinkML schema load + validation | deterministic | **drafted** ✓ |
| [070](070-ontology-grounding.md) | `ground` + grounding backends | deterministic | **drafted** ✓ |
| [080](080-diff-qc.md) | `diff`: candidate-vs-curated & self-consistency QC | deterministic | **drafted** ✓ |
| [090](090-report.md) | `report`: verdict report + provenance | deterministic | **drafted** ✓ |
| [100](100-judge.md) | `judge`: the agent boundary (3 calls) | agent | **drafted** ✓ |
| [110](110-pipeline.md) | `pipeline`: per-study orchestration + fan-out | deterministic | **drafted** ✓ |
| [120](120-mcp-tool-surface.md) | MCP (streamable HTTP) + CLI + Python API | deterministic | **drafted** ✓ |
| [130](130-judgment-clients.md) | `llm`: judgment clients (LLMClient adapters) + factory | agent-support | **drafted** |
| [140](140-profile-and-type.md) | `profile`: value-driven semantic typing + ontology routing | hybrid | **drafted** |

Status: **drafted** = spec written to template depth; **✓** = implemented to that spec with
offline tests. Only the glossary (000) remains a template stub.
