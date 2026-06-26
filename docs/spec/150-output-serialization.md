# SPEC 150 — output serialization (self-describing curated dataset)

- Status: drafted
- Determinism: deterministic (templating / serialization; no LLM)
- Implements: `src/metacurator/emit.py`
- Related: ADR-0002, ADR-0003, ADR-0008, ADR-0009; SPEC 010, 060, 090, 140.

## Purpose

Serialize curated records together with their schema as a **self-describing dataset**: a
data table whose every column declares its meaning and semantic type (free text / numeric /
controlled-vocabulary-bound-to-an-ontology), with per-cell ontology CURIEs, and with
**discovered** columns expressed in the *same* LinkML substrate as the base schema (ADR-0009).

## Contracts

- `emit_dataset(records, dictionary, *, discovered=None, dest, formats=("tsv", "linkml"))
  -> EmitResult`
  - `records`: `CandidateRow`s (SPEC 010).
  - `dictionary`: the base schema (SPEC 060) — the **minimum** contract.
  - `discovered`: the SPEC 140 typing overlay (facets / `TypeDecision`s) or `None`.
  - `formats`: any of `tsv`, `linkml`, `frictionless`, `jsonld`.
- `EmitResult` — the written paths + the **effective schema** (base + overlay).

## Behavior

- **Effective schema** = base LinkML (minimum) **+** discovered overlay. The overlay is a
  LinkML document that `imports` the base and adds the discovered slots/enums to a subclass
  (e.g. `SampleEnriched is_a Sample`). Discovered slots carry `annotations`:
  `{discovered: true, evidence, confidence, source_column}`. `SchemaView` merges the import
  closure, so base and discovered columns are handled identically.
- **Tidy TSV** (default): one column per field; for each **grounded / ontology-bound** field
  a companion `<field>_ontology_term_id` column carries the per-cell CURIE (cMD convention).
  free-text and numeric fields get **no** companion column. A `multi_facet` source column
  expands to its facet columns. **Multi-value** cells use the curated join convention
  (order-aligned `;`-joined values and `;`-joined CURIEs).
- **LinkML descriptor** (default): write the effective schema alongside the TSV. This *is*
  the column-description layer (descriptions, ranges, enums, bindings) and the source for
  every other format.
- **Frictionless** (optional): generate `datapackage.json` from the effective LinkML —
  fields (types from ranges, `enum` constraints from permissible values, title/description),
  `rdfType` / custom keys referencing the ontology binding, bundling the TSV + dataset
  metadata from the `CurationReport` provenance (SPEC 090).
- **JSON-LD / RDF** (optional): instances with per-value `{label, id: CURIE}` and an
  `@context` mapping fields/bindings to ontology URIs (LinkML can emit the context).

The pipeline (SPEC 110) calls `emit_dataset` after assembling records + the report.

## Invariants

- **One semantic substrate.** Base and discovered columns are both LinkML; nothing is a
  second-class untyped extra (ADR-0009).
- **Generated, not hand-edited.** TSV / Frictionless / JSON-LD are rendered from the LinkML
  source-of-truth and never diverge from it (cf ADR-0003).
- **No minting in serialization.** Per-cell CURIEs come only from grounding (ADR-0004) and
  are echoed verbatim into companion columns / JSON-LD; `emit` invents nothing.
- **Base is not mutated.** Discovered facets live in the overlay with provenance; promotion
  to the base is a separate spec-first step.
- **Type is explicit per column.** free-text vs controlled-vocabulary is visible in the
  LinkML range (`string` vs `Enum`/dynamic enum), so a consumer knows which columns are
  grounded.

## Errors

- A discovered facet whose ontology can't be resolved → emit it as `string` (free text) with
  a `needs_review` annotation; never fabricate a binding.
- A grounded field whose value did not reach `auto` → emit the value with a blank companion
  CURIE and a review flag (never a guessed CURIE).

## Test cases (offline)

- Records + base dictionary → TSV with companion `_ontology_term_id` columns for bound
  fields; the LinkML descriptor round-trips through `SchemaView`.
- A discovered overlay with one `multi_facet` split → the effective schema has the facet
  slots (subclass, `discovered: true`); the TSV has the facet columns; base slots unchanged.
- A free-text column → no companion CURIE column; LinkML range `string`.
- A Frictionless `datapackage.json` generated from the effective schema lists fields with
  types + enum constraints and loads via the `frictionless` lib (gated/optional).
- `emit` mints no identifier (every CURIE traces to grounding).

## Open questions

- Multi-value encoding: companion `;`-joined columns vs a normalized **long** table — and
  how Frictionless / JSON-LD represent each.
- Discovered overlay scope (per-study vs per-corpus) and how overlays merge.
- Promotion tooling (overlay slot → base schema) and carrying discovery provenance through
  promotion.
- Exact LinkML `annotations` keys for discovery provenance; aligning with SPEC 140
  `OntologyEvidence`.
- Generating the JSON-LD `@context` from LinkML prefixes/bindings (leverage LinkML's
  context generator).
