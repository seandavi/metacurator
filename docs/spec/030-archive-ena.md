# SPEC 030 — archive: sequence-archive accessions & ID map

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/archive.py`
- Related: SPEC 010 (`AccessionMap`), ADR-0004

## Purpose

Build the `AccessionMap` for a study from ENA/BioSample: every run ↔ sample (BioSample) ↔
submitter alias/title. This is **authoritative for accessions** and is usually the best
key to join the publication's per-subject table to samples.

## Scope note for implementation

- Two-step ENA recipe (no auth): from one known sample derive the project, then a bulk
  `filereport` for the whole project (`run_accession, sample_accession,
  secondary_sample_accession, study_accession, sample_alias, sample_title`).
- DDBJ `PRJDB` projects are ENA-mirrored — same call. Capture `sample_alias`/`title`:
  they usually encode the paper's patient/sample ID (the join key for SPEC 100 mapping).
- Pure HTTP; no LLM. Save raw responses for reuse; offline tests use a snapshot.

## To complete

Fill the template. Cases: a project with multiple runs per BioSample (membership, not
equality); an ENA project; a DDBJ project; alias→paper-ID extraction.
