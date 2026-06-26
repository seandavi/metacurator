# SPEC 080 — diff & QC

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/diff.py`
- Related: SPEC 010 (`DiffResult`), 090

## Purpose

Compare a reconstructed candidate table against a reference (existing curation) or against
itself for self-consistency, producing per-column `DiffResult`s and an overall verdict —
the QC gate that catches both reproduction errors and existing-curation errors.

## Scope note for implementation

Generalize the harness proven on the cMD reproduction:
- Join on the sample/record key (fallback to a secondary key); report per column
  `compared / match / mismatch / blank / cand_adds` + examples + verdict.
- **Normalizations to avoid false positives:** casefold, trim; numeric compare with
  tolerance (~1e-6); multi-value fields compared as **sets** (order-independent);
  curated-blank/candidate-filled counted as enrichment (`cand_adds`), not mismatch;
  known synonym folds (e.g. country names) — ideally sourced from the schema/ontology.
- No LLM. Deterministic and fully testable.

## To complete

Fill the template. Cases: clean match; a real value conflict (FAIL); float-precision
(PASS via tolerance); set-equal multi-value accessions (PASS); candidate enrichment
(cand_adds, not FAIL); unjoined rows reported.
