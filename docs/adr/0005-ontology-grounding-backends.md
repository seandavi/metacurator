# 0005. Pluggable ontology grounding backends (no DuckLake required)

- Status: accepted
- Date: 2026-06-26

## Context

Grounding a free-text value to a real ontology term (lookup → verify round-trip → check
it sits under the expected branch → check not obsolete) needs an ontology store. One
such store is a shared DuckLake (the `cdsci-lake` `ontology` schema built from
semantic-sql). But this is open-source software: **most users will not have DuckLake
access**, and grounding must still work for them out of the box.

## Decision

Define a `GroundingBackend` protocol (see SPEC 070) with a stable interface
(`lookup`, `round_trip`, `is_a_descendant`/`reachable_from`, `is_obsolete`,
`replaced_by`) and ship at least two implementations:

1. **`LocalDuckDBBackend` (default, zero-infrastructure).** A bundled helper builds a
   small local ontology store from public **semantic-sql** files (`bbop-sqlite`):
   download the needed `<onto>.db.gz`, project the same `terms / synonyms / xrefs /
   edges` tables into a local DuckDB/parquet, and ground against it. Closure is computed
   on demand with a recursive CTE over `edges` (the `entailed_edge` table is not
   materialized). Only the ontologies a schema references are fetched.
2. **`DuckLakeBackend` (opt-in).** Connects read-only to an existing DuckLake `ontology`
   schema (e.g. cdsci-lake) for teams that maintain one.

The two share the projection contract (identical table shapes), so the same grounding
queries run against either. A backend is selected by config; the default requires no
credentials and no lake.

The projection logic and the semantic-sql facts (predicate CURIEs, `value`/`object`
encoding, `edge` view, the recursive-CTE closure) are shared with — and were validated
in — the cdsci-lake ontology source; SPEC 070 restates them so this repo is
self-contained.

## Consequences

- Works for everyone with `pip install metacurator` and a network connection; scales up
  to a shared lake when one exists, with identical query logic.
- A prebuilt parquet bundle (optional, future) can make first-run grounding instant.
- Cost: the local backend duplicates a little of cdsci-lake's projection logic; the
  shared table contract keeps them in lockstep. Large ontologies (NCBITaxon) are only
  fetched if a schema actually binds to them.

## Alternatives considered

- **Require DuckLake** — unacceptable for OSS; excludes most users.
- **Call OAK directly per value** — row-at-a-time, slower for batch curation, and pulls
  the same `.db` files anyway; we want columnar batch grounding and one closure method.
- **Hit the EBI OLS REST API live** — network round-trip per term, rate limits, not
  reproducible/pinnable. Useful as a possible third backend, not the default.
