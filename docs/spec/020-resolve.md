# SPEC 020 — resolve: identifiers & open-access triage

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/resolve.py`
- Related: SPEC 010, 040

## Purpose

From a PMID (or DOI), produce a `StudyRef`: resolve PMCID + DOI and determine open-access
status, so downstream `acquire` (SPEC 040) knows whether the supplement is reachable from
open sources or needs a browser/institutional path.

## Contract

- `async resolve(pmid=None, *, doi=None, client=None, email=...) -> StudyRef`
- `async oa_package_url(pmcid, *, client) -> str | None` — the OA package (`tgz`) href if
  the article is in the PMC OA subset (used by `acquire`).

The `httpx.AsyncClient` is injectable — the offline test seam.

## Behavior

1. **ID conversion** via the NCBI PMC ID Converter
   (`/pmc/utils/idconv/v1.0/?ids=<id>&format=json`): one record giving `pmcid`, `pmid`,
   `doi`. A record with `status="error"` (or no records) is unresolvable.
2. **OA status** via the PMC OA service (`/pmc/utils/oa/oa.fcgi?id=<PMCID>`): an
   `<error code="idIsNotOpenAccess">` ⇒ `not_oa`; a `<record>` with links ⇒ `oa`; anything
   else ⇒ `unknown`. Only queried when a PMCID exists (no PMCID ⇒ `unknown`).

Returns `StudyRef(pmid, pmcid, doi, oa_status)`. Triage first (one batch), then chase files.

## Invariants

- Pure HTTP + parse; no LLM. Identifiers are copied verbatim from the services.
- OA status is conservative: only `oa` when the OA service actually lists a package.

## Errors

- Neither `pmid` nor `doi` → `ValueError`.
- An unresolvable identifier (error record / no records) → `LookupError` naming it.
- HTTP errors propagate.

## Test cases (offline against saved responses)

- A known OA PMC article → `pmcid` set, `oa_status == oa`.
- A non-OA (paywalled) article → `oa_status == not_oa`.
- A DOI-only input → resolves `pmid`/`pmcid` from the DOI.
- An unresolvable PMID → `LookupError`.

## Open questions

- Whether to also resolve the BioProject here (from a linked SRA/ENA record) or leave it to
  `archive` (currently `archive` owns project resolution).
- Caching policy for idconv/OA responses.
