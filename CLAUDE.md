# CLAUDE.md — working in metacurator

Orientation for an agent picking up this repo. Read this, then
[`docs/spec/README.md`](docs/spec/README.md) and the ADRs in `docs/adr/`.

## What this is

A spec-first toolkit to reproduce curated, ontology-grounded, sample-level metadata from
publications. Status: **scaffold** — specs + decisions are in place; most modules are
stubs that raise `NotImplementedError` pointing at their spec.

## The rules (non-negotiable)

1. **Spec-first (ADR-0002).** Specs in `docs/spec/` are the source of truth. To change
   behavior, change the spec first, then implement to it. Don't refactor unrelated code;
   layer customizations on the typed contracts (SPEC 010).
2. **Determinism gradient (ADR-0004).** Mechanical work = deterministic, tested code with
   no LLM. Only `judge.py` invokes a model, via exactly three calls, returning typed
   objects.
3. **No hallucinated identifiers (ADR-0004).** Accessions come only from `archive`,
   ontology CURIEs only from `ground`. A model never mints an ID or value. Even the
   starter schema (`schema/cmd.yaml`) only asserts CURIEs verified against real data.
4. **Decisions are ADRs (ADR-0001).** Architectural changes get a new ADR; supersede,
   don't edit accepted ones.
5. **Generated code is not edited (ADR-0003).** `src/metacurator/_generated/` is built
   from `schema/*.yaml` via `make -C schema all`.

## Layout

- `docs/spec/` — what each component must do (start at `README.md`; 010, 070, 100, 120
  are drafted exemplars; the rest are stubs to complete).
- `docs/adr/` — why (0001–0006).
- `docs/design/` — how it fits (`overview.md`, `data-flow.md`).
- `schema/` — LinkML (`metacurator_core.yaml`, `cmd.yaml`) → Pydantic + JSON Schema.
- `src/metacurator/` — `models.py` (real contracts) + deterministic spine stubs +
  `judge.py` (agent boundary) + `grounding/` (backends) + `cli.py`, `mcp_server.py`.
- `tests/` — offline; `RUN_INTEGRATION=1` for live.

## Dev

```bash
uv sync --extra dev --extra schema --extra mcp --extra tables
uv run ruff check . && uv run pytest
make -C schema all   # regenerate models/json-schema from LinkML
```

## Suggested first implementation order

`grounding/local_duckdb.py` + `ground.py` (SPEC 070, default backend, the no-hallucination
core) → `dictionary.py` (SPEC 060, load `cmd.yaml`) → `archive.py` (SPEC 030) →
`diff.py` (SPEC 080, port the cMD harness) → outward to `resolve/acquire/tables`, then
`judge`, `pipeline`, and the MCP/CLI surface.
