# SPEC 030 — archive: sequence-archive accessions & ID map

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/archive.py`
- Related: SPEC 010 (`AccessionMap`), ADR-0004

## Purpose

Build the `AccessionMap` for a study from ENA/BioSample: every run ↔ sample (BioSample) ↔
submitter alias/title. This is **authoritative for accessions** (no other stage may invent
them, ADR-0004) and is usually the best key to join the publication's per-subject table to
samples.

## Contract

- `async build_accession_map(study, *, seed_accession=None, client=None) -> AccessionMap`
  — resolve the project (from `study.bioproject`, else derive it from `seed_accession`),
  then bulk-fetch the project's runs into an `AccessionMap`.
- `async project_for_accession(accession, *, client) -> str | None` — step 1: the
  `study_accession` a run/sample belongs to.
- Helpers (deterministic, no I/O): `runs_for_sample(amap) -> dict[str, set[str]]`,
  `by_alias(amap) -> dict[str, list[AccessionRow]]`.

The injectable `client` (an `httpx.AsyncClient`) is the test seam: offline tests pass a
client backed by a saved ENA response; in production it is created internally.

## Behavior — the two-step ENA recipe (no auth)

1. **Derive the project** from one known accession (when `study.bioproject` is unknown):
   `filereport?accession=<acc>&result=read_run&fields=study_accession`.
2. **Bulk filereport** for the whole project, requesting
   `run_accession, sample_accession, secondary_sample_accession, study_accession,
   sample_alias, sample_title` as TSV.

Map each row → `AccessionRow(run, sample=BioSample, secondary_sample, alias, title)`;
the `AccessionMap` carries `project` and `source="ena"`. DDBJ `PRJDB` projects are
ENA-mirrored, so the identical call works. `sample_alias`/`sample_title` usually encode
the paper's patient/sample ID — the join key for SPEC 100 mapping — so they are preserved
verbatim. Empty TSV cells become `None`.

## Invariants

- A sample maps to a **set** of runs (membership, not equality): multiple runs per
  BioSample produce multiple rows sharing one `sample`.
- Accessions are copied verbatim from ENA; nothing is synthesized or reformatted.

## Errors

- Neither `study.bioproject` nor a resolvable `seed_accession` → explicit `ValueError`.
- A project that returns no rows → `LookupError` naming the project (never a silent empty
  map).
- HTTP errors propagate (surfaced by the caller / MCP as a structured error).

## Test cases (offline against a saved ENA snapshot)

- A project with multiple runs per BioSample → `runs_for_sample` returns the membership
  set, not a single run.
- An ENA project (`PRJEB…`) and a DDBJ project (`PRJDB…`) both parse via the same call.
- The two-step path: no `bioproject`, a `seed_accession` resolves the project first.
- `by_alias` recovers the paper sample IDs from `sample_alias`.

## Open questions

- Whether to also fetch BioSample attributes (host, collection date) here or leave that to
  a later enrichment stage.
- Caching policy for raw ENA responses (on-disk snapshot keyed by project) for
  reproducibility.
