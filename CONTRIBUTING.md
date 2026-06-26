# Contributing to metacurator

Thanks for your interest. metacurator is **spec-first**: please read this and
[`docs/spec/README.md`](docs/spec/README.md) before writing code.

## The golden rule: specs lead, code follows

1. **Behavior changes start as a spec change.** Update (or add) the spec in
   `docs/spec/` first; implement to satisfy it. A PR that changes behavior without a
   corresponding spec delta will be asked to add one.
2. **Decisions are recorded.** Anything architectural goes in an ADR
   (`docs/adr/`, see the template). Don't relitigate an accepted ADR in code review —
   supersede it with a new ADR.
3. **The determinism gradient is law** (ADR-0004). New mechanical capability →
   deterministic, unit-tested module. Only the three `judge.py` calls may invoke an LLM,
   and they must return validated typed objects, never raw IDs/values.

## Development

```bash
uv sync --extra dev --extra schema --extra mcp --extra tables
uv run ruff check .
uv run pytest
```

- **Generated code is not edited.** `src/metacurator/_generated/` (Pydantic models, JSON
  Schema) is regenerated from `schema/*.yaml`; change the LinkML, then regenerate
  (`just gen`). See ADR-0003.
- **Tests are offline by default.** Use fixtures in `tests/fixtures/` (a tiny ontology
  store, saved supplement files, an ENA snapshot). Live network tests are opt-in via
  `RUN_INTEGRATION=1`.
- **No hallucinated identifiers, ever.** Accessions and ontology CURIEs come from tools,
  not models. A test that asserts an ID was produced by a model is a bug.

## Commit & PR

- Small, well-described commits; branch for non-trivial work (no force-push to `main`).
- PRs explain the spec/ADR they satisfy and include tests.
- Be kind. This is research infrastructure; clarity beats cleverness.
