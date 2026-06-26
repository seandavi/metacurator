# SPEC 010 — Data model (the typed contracts)

- Status: drafted
- Determinism: —
- Implements: `src/metacurator/models.py` (hand-written framework contracts) +
  `src/metacurator/_generated/` (record models generated from the LinkML curation schema)
- Related: ADR-0002, ADR-0003, ADR-0004

## Purpose

Define the typed objects that flow between stages. These contracts are the stable seams
of the toolkit: deterministic tools and the agent boundary interoperate only through
them, which is what lets implementations be swapped and lets the no-hallucination
contract be enforced structurally.

## Two kinds of model

1. **Framework contracts** (`models.py`, hand-written Pydantic): the *process* objects
   below — they describe curation work, not the target standard.
2. **Record contracts** (`_generated/`, from LinkML via `gen-pydantic`, ADR-0003): the
   *target standard's* row/record types (e.g. a cMD sample row). Never hand-edited.

## Framework contracts (normative shapes)

> Field lists are the required contract; an implementation may add optional fields.

- **`StudyRef`** — identity & access of one study.
  `pmid`, `pmcid | None`, `doi | None`, `oa_status` (enum: `oa` / `not_oa` / `unknown`),
  `bioproject | None`, `title | None`.

- **`AccessionMap`** — per-sample sequence-archive identifiers (from `archive`).
  rows of `{ run, sample (biosample), secondary_sample, alias, title }`; plus
  `project` and a `source` provenance tag. **Authoritative for accessions** — no other
  stage may invent these.

- **`SourceTable`** — a loaded supplement table + provenance.
  `frame` (Arrow/DataFrame), `provenance` (`file`, `sheet | None`, `table_index | None`,
  `url | None`), `n_rows`, `n_cols`.

- **`ColumnMapping`** — *agent output* from `propose_mapping`. A list of
  `{ source_col, target_field, transform | None, confidence (0–1), evidence }`.
  Validated against the active schema (SPEC 060) before use. **Carries no values** — it
  describes how to project, it does not assert curated data.

- **`GroundedTerm`** — result of grounding one value (from `ground`, never from a model).
  `query`, `ontology`, `curie`, `label`, `scope` (`exact`/`broad`/`narrow`/`related`/
  `label`), `branch_ok (bool)`, `obsolete (bool)`, `replaced_by | None`,
  `confidence_tier` (`auto` / `review` / `none`).

- **`CandidateRow`** — one reconstructed record keyed to the source, conforming to the
  generated record model for the active schema, plus `provenance` per field.

- **`DiffResult`** — per-column comparison (candidate vs reference, or self-consistency):
  `column`, `compared`, `match`, `mismatch`, `blank`, `cand_adds`, `verdict`
  (`PASS`/`PARTIAL`/`FAIL`), `examples`.

- **`CurationReport`** — the human-facing artifact: sources used, per-column verdicts,
  ID-map notes, confidence, and a provenance trail sufficient to reproduce the run.

## Invariants

- Every stage consumes and produces these types — **no free-text hand-off** between
  deterministic stages and the agent boundary.
- `AccessionMap` and `GroundedTerm` are producible only by deterministic tools. Any code
  path that lets an agent populate a CURIE or accession is a contract violation
  (ADR-0004).
- Provenance is mandatory on `SourceTable`, `CandidateRow` (per field), and
  `CurationReport`.

## Test cases

- Round-trip each model through JSON (Pydantic) without loss.
- A `ColumnMapping` referencing a field absent from the active schema fails validation.
- A `CandidateRow` with a value outside an enum's permissible values (SPEC 060) is
  rejected with a clear error.

## Open questions

- Frame representation: Arrow table vs pandas vs polars — pick in implementation; keep it
  behind `SourceTable` so callers don't depend on it.
- Whether `CandidateRow` provenance should reference the exact `SourceTable` cell
  (row/col) — likely yes for full auditability.
