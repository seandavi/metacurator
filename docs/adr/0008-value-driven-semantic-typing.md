# 0008. Value-driven semantic typing (a discovery layer); bindings become priors

- Status: accepted
- Date: 2026-06-26

## Context

Today a curated column is bound to a schema field with one ontology
(`reachable_from`, SPEC 060/070): `disease → NCIT disease branch`, `body_site → UBERON`,
etc. This presupposes that a column is semantically **homogeneous** and that its **name**
carries its information content.

A grounding audit over the cMD corpus disproved both assumptions:

- **`target_condition`** holds at least four kinds of entity in one column — NCIT diseases
  (`Colorectal Carcinoma`), NCIT *non-disease* concepts (`Microbiome`, `Intestinal Flora`),
  drug classes (`Cephalosporin Antibiotic`), and **NCBITaxon** organisms
  (`Prevotella copri`). One ontology branch cannot bind it.
- **`age_group`** labels collide with generic NCIT terms (`Adult` is the primary label of
  `C17600` but the curator means the age-group-specific `C49685`), so reachability picked
  the wrong term 72% of the time.
- Multi-value cells (`Inflammatory Bowel Disease;Crohn Disease`) pack several entities into
  one string.

The information content lives in the **values**, not the column header. We want to discover
it from the data and route each value to the right ontology — without violating the
no-hallucination contract (ADR-0004) or spec-first source-of-truth (ADR-0002).

## Decision

We will add a **value-driven semantic typing layer** (SPEC 140) that:

1. **profiles** a column's values (deterministic statistics — numeric? accession-like?
   cardinality? shape),
2. **grounds the column's distinct values against a candidate ontology registry**
   (deterministic — `ground()` over several ontologies; the data reveals where values
   live), and
3. lets the **agent adjudicate** the semantic type / routing from that evidence — choosing
   `numeric` / `free_text` / `single_ontology` / **`multi_facet`** (split a heterogeneous
   column into typed sub-fields). The agent **proposes a routing, never a CURIE or value**.

**Schema ontology bindings (SPEC 060) become priors, not the sole mechanism.** A binding
that the evidence confirms short-circuits discovery (cheap, deterministic, no agent call).
Discovery runs only for **unbound or demonstrably heterogeneous** columns — which the audit
can flag automatically (high REVIEW + cross-ontology + multi-value ⇒ "needs discovery").

The pipeline (SPEC 110) gains a stage: `tables → [profile + type] → propose_mapping`.
Discovery output is a **per-study proposal overlay**, not an automatic schema mutation;
promoting a discovered facet into the schema stays a human / spec-first step (ADR-0002).

This **extends the judgment set of ADR-0004** from three calls to four (adds
`type_column`). The fourth call obeys the same invariants: it is the only place a model is
consulted for typing, it consumes deterministic evidence, and it cannot mint an identifier
— every CURIE still comes from `ground()`.

## Consequences

- Robust to heterogeneous and inconsistently-named columns; routes per value; **subsumes
  the multi-value problem** (tokenize → type each token) and surfaces the cross-ontology
  curation inconsistencies the audit found.
- "Discover or create new meanings" is **schema induction, not CURIE minting**: a column
  induces typed fields; identifiers remain real terms from `ground()`.
- The schema's role shifts from "the binding" to **"a domain ontology registry + optional
  binding hints"**. Bindings remain valid and *cheaper* where columns are homogeneous
  (`disease`/`body_site`/`country`/`ancestry` already hit ~100% — discovery there would
  only burn tokens), so we keep them as the fast path.
- Cost: grounding distinct values across N ontologies, some giant (NCBITaxon ~2 GB).
  Mitigations: profile-prune candidates, distinct-values-only, cache, and binding
  short-circuit. Documented in SPEC 140.
- A new agent surface to keep honest (no-mint, deterministic-first).

## Alternatives considered

- **Keep column→ontology binding only (status quo).** Brittle for heterogeneous columns;
  cannot model `target_condition`; forces a lossy single binding. Rejected as the *only*
  mechanism — kept as the prior/fast path.
- **Pure-LLM typing** ("ask the model which ontology/CURIE"). Violates the no-hallucination
  spirit (the model could assert an ontology or identifier without evidence) and is not
  reproducible. Rejected; the model only adjudicates over deterministic grounding evidence.
- **Hard schema induction** (auto-mutate the schema from data). Breaks spec-first
  source-of-truth and is risky at scale. Rejected; discovery emits a reviewed proposal.
