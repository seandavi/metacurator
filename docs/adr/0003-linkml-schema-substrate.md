# 0003. LinkML as the schema substrate

- Status: accepted
- Date: 2026-06-26

## Context

The target metadata standard (which fields exist, their types, allowed values, and the
ontology each value must come from) has to be **pluggable** — metacurator should curate
to curatedMetagenomicData today and another standard tomorrow — and it must express
**ontology bindings**, because half of curation is grounding values to ontology terms.

JSON Schema gives structure and enums but has no native notion of "this value is an
ontology term" or "must be a descendant of this class."

## Decision

Author the target standard as a **LinkML** schema (`schema/*.yaml`). LinkML is chosen
because it:

- expresses **enums with `meaning:` CURIEs** — directly matching how the cMD dictionary
  already pairs each allowed value with an ontology term id;
- supports **dynamic enums** (`reachable_from` an ontology node) — so "disease ∈
  descendants of the NCIT disease branch" is declared *in the schema*, not buried in code;
- **compiles to** Pydantic models *and* JSON Schema (and SQL DDL, SHACL, …) — so we get
  JSON Schema and typed models as build artifacts, losing nothing by choosing LinkML;
- is the **same ecosystem** as semantic-sql / OAK, which the ontology layer already uses.

Generated artifacts (`gen-pydantic`, `gen-json-schema`) land in
`src/metacurator/_generated/` and are **never hand-edited** (regenerated via `make
schema`). Two schemas ship: `metacurator_core` (the framework's own contracts) and `cmd`
(the first concrete curation target). Pluggability = supply a different LinkML schema.

LinkML dynamic-enum (`reachable_from`) constraints are evaluated by the ontology
grounding backend (ADR-0005) — e.g. via a recursive closure query — rather than only by
OAK, so there is one source of ontology truth.

## Consequences

- The codebook *is* the schema; the cMD `*_ontology_term_id` columns become enum
  `meaning`s; branch rules are declarative and machine-checkable.
- One authoring format yields models + JSON Schema + validation.
- Cost: a LinkML dependency and YAML authoring; LinkML tooling has rough edges. The
  runtime needs only `linkml-runtime`; full `linkml` (codegen) is a dev/build extra.

## Alternatives considered

- **JSON Schema directly** — no ontology semantics; we'd re-invent enum-meaning and
  branch constraints in ad-hoc code. Rejected (but produced as a generated artifact).
- **Pydantic models hand-written as the source** — no ontology binding, not a portable
  standard, couples the schema to Python. Rejected; Pydantic is generated downstream.
