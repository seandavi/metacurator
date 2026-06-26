# SPEC 050 — tables: load supplements into tables

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/tables.py`
- Related: SPEC 040, 010 (`SourceTable`)

## Purpose

Turn a downloaded supplement file (xlsx, csv/tsv, docx, pdf) into one or more
`SourceTable`s with provenance (file, sheet, table index, detected header row), so the
agent's `classify_tables` (SPEC 100) can pick the patient table and `propose_mapping` can
map it. Loading is **mechanical only** — no interpretation of meaning (that is SPEC 100).

## Contract

- `load_tables(path, *, url=None) -> list[SourceTable]` — dispatch by file extension.
- `Frame` — the loaded representation kept behind `SourceTable.frame`: `columns:
  list[str]` and `records: list[dict]` (one dict per data row, keyed by column). Downstream
  (`diff`, mapping application) consumes `frame.records`.

Each `SourceTable` carries `provenance` (`file`, `sheet`, `table_index`, `header_row`,
`url`) and `n_rows`/`n_cols`.

## Behavior

- **Header detection** is shared across formats: the header is the first row whose
  filled-cell count matches the widest row seen, so a sparse title/caption line above the
  real header is skipped; its 0-based index is recorded as `header_row`. Blank or duplicate
  header cells are filled/disambiguated (`col1`, `col2`, …) so records have stable keys.
- **csv/tsv** → one table; delimiter from the extension (`.tsv` → tab, else comma).
- **xlsx** → one table per non-empty sheet (`sheet` set; header may not be row 0).
- **docx** → one table per document table (`table_index` set).
- **pdf** → one table per extracted table per page (`table_index` a running counter).
- Parsers live behind the `tables` extra (openpyxl, python-docx, pdfplumber).

## Invariants

- No cell values are coerced or reinterpreted beyond string normalization of headers;
  data cells are preserved verbatim (typing/cleaning is downstream).
- Provenance is mandatory and sufficient to locate the table again (file + sheet/index +
  header row).

## Errors

- Unknown extension → `ValueError` naming the suffix.
- A file yielding zero tables (all sheets/pages empty) → `ValueError` (clean error, never
  a silent empty list).

## Test cases

- Multi-sheet xlsx → one `SourceTable` per sheet, `sheet` recorded.
- Header not on the first row (a title/blank line precedes it) → `header_row > 0` and the
  correct columns.
- A docx table → records keyed by the header row.
- A pdf table → rows extracted (conversion covered offline via the shared row→table
  helper; live pdf parsing under integration).
- A file with no tables → `ValueError`.
- csv and tsv round-trip to the same records.

## Open questions

- Frame representation (records vs Arrow/pandas) — kept behind `SourceTable.frame`;
  records chosen for zero heavy deps and direct `diff` interop.
- Multi-table-per-sheet xlsx (several tables stacked on one sheet) — out of scope until a
  real supplement needs it; current behavior is one table per sheet.
