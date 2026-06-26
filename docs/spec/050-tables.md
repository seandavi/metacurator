# SPEC 050 — tables: load supplements into tables

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/tables.py`
- Related: SPEC 040, 010 (`SourceTable`)

## Purpose

Turn a downloaded supplement file (xlsx, csv/tsv, docx, pdf) into one or more
`SourceTable`s with provenance (file, sheet, table index), so the agent's
`classify_tables` (SPEC 100) can pick the patient table and `propose_mapping` can map it.

## Scope note for implementation

- xlsx: every sheet → a table (header detection is fiddly; a real header may not be row
  0 — record the detected header row in provenance). Parsers behind the `tables` extra
  (openpyxl, python-docx, pdfplumber).
- Loading is mechanical only — no interpretation of meaning (that's SPEC 100).
- Prefer DuckDB readers where possible for csv/xlsx; keep the frame type behind
  `SourceTable`.

## To complete

Fill the template. Cases: multi-sheet xlsx; header not on first row; docx table; a
table-bearing pdf; a file with no tables (clean error).
