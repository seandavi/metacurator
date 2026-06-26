# SPEC 020 — resolve: identifiers & open-access triage

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/resolve.py`
- Related: SPEC 010, 040

## Purpose

From a PMID (or DOI), produce a `StudyRef`: resolve PMCID + DOI and determine
open-access status, so downstream `acquire` (SPEC 040) knows whether the supplement is
reachable from open sources or needs a browser/institutional path.

## Scope note for implementation

- ID conversion via NCBI idconv / PMC ID converter; OA status via the PMC OA service
  (`idIsNotOpenAccess` ⇒ not OA). Do this in one batch (triage before chasing files).
- Pure HTTP + parse; no LLM. Return `StudyRef` (SPEC 010).
- Cache responses; offline tests use saved fixtures.

## To complete

Fill Contracts/Behavior/Errors/Test-cases per `_TEMPLATE.md`. Cases: a known OA PMC
article; a non-OA (paywalled) article; a DOI-only input; an unresolvable PMID.
