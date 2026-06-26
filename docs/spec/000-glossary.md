# SPEC 000 — Glossary & conventions

- Status: stub

## Terms

- **Curation** — producing a tidy, schema-conforming, ontology-grounded sample/record
  table from a publication and its supplements.
- **Determinism gradient** — the spectrum from mechanical (deterministic code) to
  judgment (agent) work; the organizing principle of the toolkit (ADR-0004).
- **Grounding** — mapping a free-text value to a verified ontology term (SPEC 070).
- **No-hallucination contract** — identifiers (accessions, CURIEs) are produced only by
  deterministic tools, never by a model (ADR-0004).
- **semantic-sql / semsql** — OBO ontologies distributed as SQLite; the ontology source.
- **DuckLake** — DuckDB lakehouse format; one (optional) grounding backend.
- **Schema** — the LinkML description of the target standard (ADR-0003).

## Conventions

- Spec files: `NNN-name.md`, numbered by pipeline stage.
- ADRs: immutable once accepted; supersede, don't edit (ADR-0001).
- Generated code lives in `_generated/` and is never hand-edited (ADR-0003).

## To complete

Expand as terms accrue; cross-link to the spec/ADR that defines each.
