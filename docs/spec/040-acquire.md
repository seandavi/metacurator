# SPEC 040 — acquire: supplement retrieval ladder

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/acquire.py`
- Related: SPEC 020, 050

## Purpose

Given a `StudyRef`, fetch the supplementary materials (where the per-subject phenotype
table almost always lives), trying retrieval methods in a reliability order and reporting
which worked.

## Scope note for implementation

Ladder (observed to work in practice):
1. PMC OA `bin/` files when OA.
2. EuropePMC `supplementaryFiles` zip (works where the PMC `bin/` URL hits a bot wall).
3. Nature/Springer: scrape the article HTML with a browser User-Agent for real `MOESM`
   names, then download from `static-content.springer.com` with **UA + `Referer`**
   (UA-only → 403; **check file size, not just HTTP status**).
4. Cookie-gated files: a real browser session (out of scope for the core; expose a hook).
5. Paywalled Science/Cell supplements: not retrievable from open sources — report as a
   gap, fall back to `archive` (SPEC 030) + study portals.

Save everything verbatim to a raw/bronze dir (idempotent). No LLM.

## To complete

Fill the template. Cases: OA PMC supplement; EuropePMC zip fallback; Springer CDN with
UA+Referer (size check); a paywalled gap reported cleanly.
