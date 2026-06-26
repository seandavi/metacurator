# SPEC 140 — profile & type (value-driven semantic typing)

- Status: drafted
- Determinism: **hybrid** — profiling + candidate grounding are deterministic; the
  type/route decision is an agent call (a fourth judgment, ADR-0008), no-mint.
- Implements: `src/metacurator/profile.py` + a `type_column` judgment call (judge boundary,
  SPEC 100 contract).
- Related: ADR-0002, ADR-0004, ADR-0005, ADR-0008; SPEC 050, 060, 070, 100, 110.

## Purpose

Determine the semantic type(s) and ontology routing of a source column **from its values**,
not its header — so a heterogeneous column is split into typed facets and each value grounds
against the right ontology. Schema bindings (SPEC 060) act as **priors** that short-circuit
discovery when present and confirmed by the evidence.

## Contracts

- **`ColumnProfile`** (deterministic) — `name`, `n`, `n_distinct`, `n_blank`,
  `numeric_fraction`, `looks_like` (∈ `curie`/`accession`/`numeric`/`free`),
  `cardinality` (`controlled`/`open`), `examples`. No interpretation of meaning.
- **`OntologyEvidence`** (deterministic) — for the column's distinct values, where each
  grounds: `landings` = `{value: {ontology: best GroundedTerm | None}}`, plus an aggregate
  `distribution` = `{ontology: fraction grounded}` and a per-ontology branch breakdown.
- **`TypeDecision`** (agent output, **carries no CURIEs/values**) — one of:
  - `numeric` | `free_text`
  - `single_ontology{ontology, branch_root?}`
  - `multi_facet{facets: [{name, ontology, branch_root?}]}`
  plus `rationale`, `confidence`, `needs_review`.

## Behavior

- **`profile(values) -> ColumnProfile`** — deterministic statistics.
- **`gather_evidence(distinct_values, candidates) -> OntologyEvidence`** — ground each
  distinct value (SPEC 070) against each candidate ontology (no branch constraint, or each
  ontology's natural root), recording the best landing. Candidates come from the **ontology
  registry** (below), optionally pruned by the profile (e.g. skip grounding a numeric
  column; restrict to taxonomy ontologies when values look like binomials).
- **`type_column(profile, evidence, binding_hint) -> TypeDecision`** — the agent
  adjudicates over the deterministic evidence (judge boundary, SPEC 100 no-mint rules). If a
  schema **binding exists and the evidence confirms it** (≥ threshold of distinct values
  land in the bound ontology/branch), **short-circuit to that binding without calling the
  model**. Heterogeneous evidence (several ontologies/branches above threshold) → a
  `multi_facet` proposal or `needs_review`.
- **Apply (deterministic).** Facets become *proposed* fields; each value routes to its
  facet's ontology and grounds via SPEC 070. **Multi-value cells are tokenized** (split on
  `;`/`,`) and each token is typed + grounded independently.

The pipeline (SPEC 110) inserts this between `tables` and `propose_mapping`:
`tables → [profile + type] → map`. A confirmed binding makes it a no-op fast path.

## Ontology registry

The **candidate ontology set** is configuration (per domain). A schema may declare it; the
default is the union of ontologies its bindings reference (e.g. cmd → NCIT, UBERON,
HANCESTRO) plus optional additions (NCBITaxon, ENVO, CHEBI, OBI). A live `OlsBackend`
(SPEC 070 future) could widen the set beyond locally-built stores; it is not the default.

## Invariants

- **No identifier minted.** `type_column` returns a *routing*, never a CURIE/value; every
  identifier still comes from `ground()` (ADR-0004). A routing to an ontology outside the
  candidate set is rejected.
- **Bindings are priors.** A confirmed binding short-circuits discovery — cheaper,
  deterministic, no agent call. Discovery runs only for unbound / unconfirmed columns.
- **Deterministic-first.** The agent is consulted only when the deterministic evidence is
  ambiguous or heterogeneous.
- **Proposal, not mutation.** Discovery emits a per-study overlay; promoting a facet into
  the schema is an explicit spec-first step (ADR-0002).

## Errors

- No candidate ontology available → empty evidence → the agent must return `free_text` or
  `needs_review` (never invent).
- A required ontology not cached → explicit `ensure` / error (SPEC 070), never a silent
  miss.

## Cost controls

Distinct-values-only; profile-prune candidates; cache evidence keyed by `(value,
ontology)`; binding short-circuit. Any sampling cap (e.g. evidence over the top-K
most-frequent distinct values) is **logged** — no silent truncation.

## Test cases (offline, against a small multi-ontology fixture store)

- A homogeneous column with a **confirmed binding** → short-circuits to the binding; the
  model is **not** consulted (spied).
- A **heterogeneous** column (values landing in two ontologies/branches) → `multi_facet`
  (or `needs_review`) with the correct facets.
- A **numeric** column → profile prunes ontology grounding → `numeric`, no grounding.
- A **multi-value** cell → tokenized; each token typed/grounded independently.
- `type_column` never returns a CURIE; a routing to an ontology not in the candidate set is
  rejected.

## Open questions

- One `type_column` call per column vs batched; how much evidence to inline per call.
- Thresholds for "binding confirmed" and for "heterogeneous → split".
- How discovered facets are named (agent-proposed vs templated from the dominant ontology).
- Adding `OlsBackend` so the candidate set isn't limited to locally-built ontologies.
- The promotion workflow: discovered overlay → schema (human-in-the-loop), and whether a
  promoted facet carries its discovery provenance.
