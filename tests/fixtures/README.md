# Test fixtures

Offline fixtures for the test suite (no network; live tests are opt-in via
`RUN_INTEGRATION=1`). Add as specs are implemented:

- `ontology_mini.db` — a tiny semantic-sql-shaped SQLite (statements + edge + prefix) for
  grounding tests (SPEC 070). Build it in-test like cdsci-lake's `test_ontology.py`.
- `ena_filereport.tsv` — a saved ENA bulk filereport snapshot (SPEC 030).
- `supplement_sample.xlsx` / `.docx` — small supplement files (SPEC 050).
- `cmd_curated_sample.tsv` — a reference slice to diff against (SPEC 080).

Keep fixtures tiny and hand-built where possible.
