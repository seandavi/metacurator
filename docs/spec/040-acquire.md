# SPEC 040 — acquire: supplement retrieval ladder

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/acquire.py`
- Related: SPEC 020, 050

## Purpose

Given a `StudyRef`, fetch the supplementary materials (where the per-subject phenotype
table almost always lives), trying retrieval methods in a reliability order and reporting
which worked — saving everything verbatim to a raw/bronze dir (idempotent).

## Contract

- `async acquire(study, *, dest, client=None) -> AcquireResult` —
  `AcquireResult(files: list[Path], method: str, gap: bool, note: str)`. `gap=True` means
  the supplement was not retrievable from open sources (a curation gap, not an error).
- `acquire_files(study, *, dest, client=None) -> list[Path]` — convenience wrapper
  returning just the paths (suitable as the pipeline's `acquire_fn`).

The `httpx.AsyncClient` is injectable — the offline test seam.

## Behavior — the reliability ladder

1. **EuropePMC `supplementaryFiles`** zip (`/europepmc/webservices/rest/PMC<n>/
   supplementaryFiles`) — the most reliable single open endpoint; extract each member into
   `dest`. (Implemented as the deterministic core rung.)
2. **PMC OA package** (`tgz` from the OA service, SPEC 020) when EuropePMC has nothing.
3. **Nature/Springer CDN** (`static-content.springer.com`, needs UA + `Referer`; verify by
   **file size**, not just HTTP status) — a hook; not attempted by the core.
4. **Cookie-gated / browser session** — out of scope for the core; exposed as a hook.
5. **Paywalled Science/Cell** — not retrievable from open sources → reported as a `gap`,
   falling back to `archive` (SPEC 030) + study portals.

A non-OA study with no EuropePMC files yields `gap=True` rather than an error, so the
pipeline records a curation gap and continues.

## Invariants

- Files are saved verbatim (no transformation); re-running is idempotent (same `dest`).
- The method that succeeded is reported; an empty result is always an explicit `gap`.

## Errors

- A study with no PMCID and no other open handle → `gap=True` (not an exception).
- HTTP/zip corruption errors propagate.

## Test cases (offline)

- An EuropePMC zip with two members → both extracted to `dest`, `method="europepmc"`,
  `gap=False`.
- EuropePMC 404 / empty → `gap=True`, `files=[]`.
- The extracted files load via SPEC 050 (`tables.load_tables`).

## Open questions

- Whether to implement the Springer CDN rung in-core (UA + Referer + size check) or keep it
  a hook to avoid brittle scraping in the deterministic spine.
- Bronze-layer manifest (what was fetched, when, from where) for full reproducibility.
