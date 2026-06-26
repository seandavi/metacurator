# SPEC 090 — report & provenance

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/report.py`
- Related: SPEC 010 (`CurationReport`), 080

## Purpose

Emit the human-facing `CurationReport`: sources used (with provenance), per-column
verdicts (from SPEC 080), ID-map notes, confidence, and a provenance trail sufficient to
reproduce the run. Templating only — no LLM.

## Contract

- `build_report(study, *, sources, diffs, notes=None, provenance=None) -> CurationReport`
  — assemble the typed artifact; computes the overall verdict.
- `render_markdown(report) -> str` — the human-facing markdown.
- `to_sidecar(report) -> dict` — the machine-readable JSON of the same content.
- `column_status(diff) -> str` — map a `DiffResult` to a report status.

## Behavior

- **Overall verdict**: `FAIL` if any column `FAIL`; else `PARTIAL` if any `PARTIAL`; else
  `PASS`. Stored in `provenance["overall_verdict"]`.
- **Per-column status** (distinct from the raw diff verdict): `REPRODUCED` (PASS with
  `compared > 0`), `CONFLICT` (FAIL — a real value disagreement = curation error),
  `PARTIAL` (coverage gaps, no conflict), `NOT-FOUND` (nothing compared and no enrichment).
  A coverage gap is a **curation gap** (e.g. a paywalled-only field), not an error; a
  `CONFLICT` is an error — the report labels them differently.
- Markdown sections: study identity, overall verdict, sources, a per-column table
  (status, compared/match/mismatch/blank/cand_adds), conflict examples, notes, and a
  provenance block. The JSON sidecar carries the same `CurationReport` content.

## Invariants

- Every reproduced value is traceable to its source via the provenance carried on
  `SourceTable` / `AccessionMap` / grounded CURIEs (the report surfaces, does not
  re-derive, that provenance).
- Rendering is pure: the same `CurationReport` always renders identically.

## Errors

- None expected (templating). An empty `diffs` list renders a report with no per-column
  rows and an overall `PASS` (nothing failed).

## Test cases

- A clean study → overall `PASS`, columns `REPRODUCED`.
- A study with a real conflict → overall `FAIL`, the column `CONFLICT` with an example.
- A study with coverage gaps → `PARTIAL`, columns marked as gaps (not errors).
- `to_sidecar` round-trips the report content; markdown contains the study id and verdict.

## Open questions

- Whether to embed full per-cell provenance inline or reference it by id (large studies).
- A stable on-disk layout (one dir per study: `report.md` + `report.json` + bronze cache).
