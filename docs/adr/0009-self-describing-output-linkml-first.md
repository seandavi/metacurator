# 0009. Curated output is a self-describing dataset, LinkML-first, layered minimum + discovered

- Status: accepted
- Date: 2026-06-26

## Context

Once value-driven typing (ADR-0008) gives each column a semantic type — free text /
numeric / controlled-vocabulary-bound-to-an-ontology / a multi-facet split — a flat CSV can
no longer carry the model's richness. A consumer of the curated output needs to know, per
column: its description, whether it is free text or a controlled vocabulary, which ontology
backs a controlled column, the per-cell CURIE for grounded values, and any **discovered**
columns the typing layer produced.

We also need the relationship between the stable curated schema and the per-study discovered
columns to be **coherent**: discovered columns should use the *same* semantic tooling as the
base schema (same ontology bindings, validation, generation), not be bolted on as untyped
extras.

## Decision

The curated output is a **self-describing dataset**, not a flat CSV, and **LinkML is the
descriptor source-of-truth** (ADR-0003) — the only layer that natively expresses a
controlled-vocabulary→ontology binding.

The output schema is **layered**:

- the shipped/base LinkML schema (e.g. `cmd`) is the **minimum** contract;
- per-study **discovered** types/columns (ADR-0008) are a LinkML **overlay** that
  `imports` the base and extends it (a subclass that adds the discovered slots/enums), so
  discovered columns get the **same semantic tooling** as base columns — ontology binding,
  validation, and downstream generation — while carrying discovery provenance (LinkML
  `annotations`: `discovered`, `evidence`, `confidence`, `source_column`).
- **Promotion** graduates a reviewed discovered slot from the overlay into the base
  (spec-first, ADR-0002); the base grows deliberately, it is never auto-mutated.

We emit, by default, **(1)** a tidy TSV with companion `<field>_ontology_term_id` columns
(cMD-compatible cell values) and **(2)** the LinkML schema = base + discovered overlay. We
optionally generate **(3)** a Frictionless `datapackage.json` for the broad data ecosystem
and **(4)** JSON-LD / RDF for fully-semantic downstream. **TSV + LinkML is the default; RDF
is offered, not imposed.** Frictionless and JSON-LD are *generated views* of the LinkML
source-of-truth (like `gen-pydantic`), never separate sources.

## Consequences

- The output declares each column's meaning and type; consumers can tell free text from a
  controlled vocabulary and see the ontology behind every grounded field.
- Base and discovered columns are uniform under one substrate — no second-class discovered
  columns; identical validation/generation; discovery provenance preserved.
- The base schema stays a stable minimum; discovery extends it without mutation; promotion
  is explicit and reviewable.
- One model, many renderings: TSV / Frictionless / JSON-LD are regenerated from LinkML and
  cannot drift from it (cf ADR-0003 "generated artifacts are not hand-edited").
- Cost: a serialization component (SPEC 150) and a base+overlay LinkML merge. Per-cell
  CURIEs still live in the *data* (companion columns or JSON-LD); the schema documents which
  columns have them.

## Alternatives considered

- **Flat CSV/TSV only.** Cannot carry column meaning, types, bindings, or discovered
  facets. Rejected as the *only* output (kept as the data layer, enriched with companion
  CURIE columns).
- **Frictionless as the primary descriptor.** Lightweight and ubiquitous, but cannot
  natively express ontology bindings or dynamic/open controlled vocabularies. Kept as a
  *generated* interop view, not the source of truth.
- **Discovered columns as a separate, non-LinkML side artifact.** Would split the semantic
  substrate and deny discovered fields the same tooling/validation. Rejected — the
  LinkML overlay keeps one substrate.
- **Auto-merge discovered columns into the base schema.** Breaks spec-first
  source-of-truth. Rejected — base stays minimal; overlay stays separate until promotion.
