# SPEC 070 — Ontology grounding & backends

- Status: drafted
- Determinism: deterministic (no LLM in the call path)
- Implements: `src/metacurator/ground.py`, `src/metacurator/grounding/`
- Related: ADR-0003 (LinkML), ADR-0004 (no-hallucination), ADR-0005 (backends)

## Purpose

Map a free-text value to a real ontology term — and prove it — so that curation never
emits a hallucinated identifier. Grounding produces a `GroundedTerm` (SPEC 010) and is
the deterministic counterpart to the agent's `disambiguate` (SPEC 100): the agent only
ever *chooses among* candidates this component returns.

## The no-hallucination contract

An ontology CURIE is **only** ever produced by this component, by lookup against an
ontology store. The four-step discipline for every grounding:

1. **Lookup** — normalize the value (casefold, trim, collapse whitespace/punct) and
   match against term labels and synonyms, *restricted to the ontology the schema binds
   to this field* (SPEC 060).
2. **Round-trip** — re-fetch the candidate CURIE and confirm its label/synonym actually
   matches the query and the prefix matches the expected ontology. A failed round-trip
   discards the candidate.
3. **Branch check** — confirm the term is `reachable_from` the schema's declared root
   for that field (e.g. disease ⊑ NCIT disease branch), via the closure query below.
4. **Obsolete check** — reject deprecated terms; surface `replaced_by` if present.

Confidence tiers: exact label/exact-synonym + branch-ok → `auto`; fuzzy/broad/narrow →
`review`; nothing valid → `none`. Only `auto` may be applied without human/agent review.

## Backend abstraction

`ground.py` is backend-agnostic; it depends on a `GroundingBackend` protocol implemented
in `grounding/`. All backends expose the **same ontology store shape** (the
semantic-sql-derived projection), so the grounding queries are identical across them:

```
terms(ontology, curie, label, definition, obsolete, replaced_by)
synonyms(ontology, curie, synonym, scope)        # scope: exact|broad|narrow|related
xrefs(ontology, curie, xref)
edges(ontology, subject, predicate, object)      # asserted direct edges (is_a, part_of, …)
```

`GroundingBackend` interface (normative):

- `lookup(value, ontology, *, scopes) -> list[GroundedTerm]`
- `get(curie, ontology) -> GroundedTerm | None`              # round-trip
- `reachable_from(curie, root, ontology, *, predicates) -> bool`   # branch check
- `is_obsolete(curie, ontology) -> bool` / `replaced_by(curie, ontology) -> str | None`
- `ensure(ontologies: list[str]) -> None`                   # make these available

### Closure is a query, not a table

Ancestors are computed on demand with a recursive CTE over `edges` (the materialized
`entailed_edge` closure is intentionally not stored — see cdsci-lake ADR-0006):

```sql
WITH RECURSIVE anc(start, node) AS (
    SELECT subject, object FROM edges
      WHERE ontology = :o AND predicate IN (:preds)
    UNION                                   -- UNION (not ALL): dedup + cycle guard
    SELECT a.start, e.object FROM anc a
      JOIN edges e ON e.ontology = :o AND e.predicate IN (:preds) AND e.subject = a.node
)
SELECT 1 FROM anc WHERE start = :curie AND node = :root LIMIT 1;
```

`:preds` defaults to `rdfs:subClassOf` plus any part-of relations the schema's
`reachable_from` declares. Use `UNION` so recursion terminates on cyclic graphs (DuckDB
has no SQL `CYCLE` clause).

## Backends (ADR-0005)

1. **`LocalDuckDBBackend` (default, no infrastructure).** `ensure()` downloads the
   needed `<onto>.db.gz` from semantic-sql's public `bbop-sqlite` bucket, projects the
   four tables into a local DuckDB file (cached under `data/`), and grounds against it.
   Only ontologies the active schema references are fetched. Semantic-sql encoding facts
   the projection relies on (validated against a real `hancestro.db`):
   - base `statements` table: literals in `value`, IRI objects in `object`, 8 cols incl.
     `graph`; `edge` is a **view** of asserted direct edges.
   - predicates: `rdfs:label`, `IAO:0000115` (definition), `oio:has{Exact,Broad,Narrow,
     Related}Synonym`, `oio:hasDbXref`, `owl:deprecated` (`value='true'`), `IAO:0100001`
     (replaced_by). Prefix is `oio:`, not `oboInOwl:`.
2. **`DuckLakeBackend` (opt-in).** Connects read-only to an existing DuckLake `ontology`
   schema (e.g. cdsci-lake) with the identical table shape; same queries.
3. *(future)* **`OlsBackend`** — live EBI OLS REST, for ad-hoc use; not reproducible, not
   the default.

Backend selection is by config (default = `LocalDuckDBBackend`). No backend requires
credentials except `DuckLakeBackend`.

## Errors

- Ontology not available and `ensure()` can't fetch it → explicit error naming the
  ontology and backend (never silently return `none`).
- Ambiguous lookup (multiple `auto`-tier hits) → return all, tier each `review`, let the
  caller/agent disambiguate; do not pick silently.

## Test cases (offline, against a tiny fixture store)

- Exact label hit, branch-ok, not obsolete → `GroundedTerm(confidence_tier="auto")`.
- Exact synonym hit → grounded with `scope="exact"`.
- A term outside the declared branch → `branch_ok=False`, not `auto`.
- A deprecated term → `obsolete=True`, `replaced_by` surfaced.
- Recursive-CTE ancestor walk returns the correct ancestor set on a small DAG.
- Same query returns identical results against `LocalDuckDBBackend` and a
  `DuckLakeBackend` pointed at an equivalent fixture (shape parity).

## Open questions

- Ship an optional **prebuilt parquet bundle** of common ontologies so first-run
  grounding is instant (vs. fetching `.db.gz` on demand)?
- Fuzzy matching method for the `review` tier (trigram / FTS / embedding) — keep behind
  the backend so it's swappable.
