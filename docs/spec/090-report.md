# SPEC 090 — report & provenance

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/report.py`
- Related: SPEC 010 (`CurationReport`), 080

## Purpose

Emit the human-facing `CurationReport`: sources used (with exact file/table/accession
provenance), per-column verdicts (from SPEC 080), ID-map notes, confidence, and a
provenance trail sufficient to reproduce the run.

## Scope note for implementation

- Markdown report + a machine-readable sidecar (JSON) of the same content.
- Every reproduced value traces to its source (file+sheet+cell, or accession, or grounded
  CURIE). Distinguish: REPRODUCED / PARTIAL / CONFLICT / NOT-FOUND and **curation gap vs
  curation error** (a paywalled-only field is a gap, not an error).
- No LLM (templating only).

## To complete

Fill the template. Cases: a report over a clean study; a study with a real conflict; a
study with paywalled gaps clearly marked as gaps.
