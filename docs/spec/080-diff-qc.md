# SPEC 080 — diff & QC

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/diff.py`
- Related: SPEC 010 (`DiffResult`), 090

## Purpose

Compare a reconstructed candidate table against a reference (existing curation) or against
itself for self-consistency, producing per-column `DiffResult`s and an overall verdict —
the QC gate that catches both reproduction errors and existing-curation errors. No LLM;
deterministic and fully testable.

## Contract

`diff(candidate, reference, *, key, secondary_key=None, columns=None, synonyms=None,
blank_values=None, max_examples=5) -> list[DiffResult]`

- `candidate`, `reference`: lists of row dicts.
- `key`: the join column (the sample/record key). `secondary_key`: fallback when a row's
  primary key is blank.
- `columns`: restrict the compared columns (default: union of non-key columns).
- `synonyms`: optional `{value: canonical}` folds (casefolded), ideally sourced from the
  schema/ontology (e.g. country-name variants).
- `blank_values`: casefolded strings treated as blank (default `{""}`).

Returns one `DiffResult` per column plus a leading **`__rows__`** summary row whose
`compared` = joined keys, `cand_adds` = candidate-only keys, `blank` = reference-only
keys, with the unjoined keys in `examples`.

## Behavior

Join candidate↔reference on `key` (then `secondary_key`). Per joined row and column,
classify the (candidate, reference) cell pair:

- both blank → `blank`;
- reference blank, candidate filled → `cand_adds` (enrichment, **not** a mismatch);
- candidate blank, reference filled → `blank` (a coverage gap, not a value conflict);
- both filled → `compared`, then `match` or `mismatch` by the equality rule.

**Equality rule (normalizations to avoid false positives):**

- numeric: if both sides parse as numbers, compare with tolerance `1e-6`;
- multi-value (a list, or a string containing `;`): compare as **sets** of casefolded,
  trimmed tokens (order-independent) — e.g. semicolon-joined run accessions;
- otherwise: casefold + trim, then apply `synonyms` folds, then string-equal.

**Verdict** per column: any `mismatch` → `FAIL`; else any `blank` (coverage gap) →
`PARTIAL`; else `PASS`. Candidate enrichment alone keeps a column `PASS`.

## Invariants

- Symmetric joining: keys present on only one side are reported (`__rows__`), never
  silently dropped.
- A pure float-precision or set-order difference is never a `mismatch`.
- Self-diff (`reference is candidate`) yields all `PASS` and no mismatches.

## Errors

- Duplicate keys on a side: last row wins (documented); callers needing strictness can
  pre-check. A missing `key` column on a row makes that row unjoinable (reported).

## Test cases

- Clean match → all `PASS`.
- A real value conflict → `FAIL` with an example `{key, candidate, reference}`.
- Float precision (`65.0` vs `65.0000001`) → `PASS` via tolerance.
- Set-equal multi-value accessions (`A;B` vs `B;A`) → `PASS`.
- Candidate enrichment (reference blank, candidate filled) → `cand_adds`, verdict not
  `FAIL`.
- Unjoined rows reported in `__rows__` (candidate-only and reference-only keys).
- A `synonyms` fold (`USA` → `United States`) turns a would-be mismatch into a `match`.

## Open questions

- Source the `synonyms` folds automatically from enum permissible values / ontology
  synonyms (SPEC 060/070) instead of passing them in.
- Whether candidate-blank/reference-filled deserves its own counter distinct from
  `blank` (currently folded into `blank`).
