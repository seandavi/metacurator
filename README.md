# metacurator

**Reproduce curated, sample-level metadata from publications — deterministically where
possible, with an LLM only where judgment is irreducible, and never a hallucinated
identifier.**

`metacurator` turns the ad-hoc work of reading a paper + its supplements and producing
a tidy, ontology-grounded sample table into a **spec-first toolkit**: a library of
deterministic tools, a pluggable LinkML schema describing the target standard, and a
narrow agent boundary for the few genuinely ambiguous steps.

> Status: **alpha.** The full deterministic spine is implemented to its specs
> (resolve · archive · acquire · tables · dictionary · ground · diff · report · pipeline),
> along with the agent boundary (`judge`) and the three faces — Python API, CLI, and the
> streamable-HTTP MCP server. Tests run offline (`uv run pytest`); set `RUN_INTEGRATION=1`
> for the live-network cases. The schema and curation coverage are still illustrative
> (one curation target, `targets/cmd/`). This repo is built *from its specs* — see below.

## Why it exists

Hand-curating sample phenotype metadata from publications is slow and error-prone, and
naively handing it to an LLM produces confident, wrong identifiers. We learned (the hard
way, across 10 metagenomics studies) that the work sits on a **determinism gradient**:

- **Mechanical** (lookups, downloads, table loads, ontology grounding, diffing) → these
  must be deterministic, testable code. An LLM here only adds cost and hallucination.
- **Judgment** (which table is the patient table? how do its columns map to the schema?
  which ontology candidate is right?) → these need a model, but constrained to emit
  *typed objects* the deterministic code validates and applies.

metacurator encodes that split. See [ADR-0004](docs/adr/0004-deterministic-spine-agent-judgment.md).

## Spec-first

Code is a build artifact of a spec, not the source of truth. Every component has a
spec in [`docs/spec/`](docs/spec/) defining its contract, behavior, invariants, errors,
and test cases. Agents (and humans) **implement and customize from the specs** rather
than refactoring existing code. The *why* lives in [ADRs](docs/adr/); the *how it fits*
in [design docs](docs/design/); the *what each piece must do* in specs.

Start here: [`docs/spec/README.md`](docs/spec/README.md).

## Architecture at a glance

```
LinkML schema (targets/*/schema.yaml)  ──gen──▶  Pydantic models + JSON Schema   (ADR-0003)
        │ declares slots, enums, ontology bindings
        ▼
Deterministic spine (src/metacurator/*)          Agent boundary (judge.py)
  resolve · archive · acquire · tables ·            classify_tables
  dictionary · ground · diff · report               propose_mapping
        │  pure, testable, no LLM                    disambiguate
        ▼                                                 │ emits typed objects only
Ontology grounding backends (grounding/)  ◀───────────────┘
  DuckLake (cdsci-lake)  |  local DuckDB (standalone helper)   (ADR-0005)
        │
Tool surface: Python API · CLI · streamable-HTTP MCP   (ADR-0006)
```

## Install (once implemented)

```bash
uv add metacurator                 # core (deterministic spine + schema runtime)
uv add "metacurator[mcp]"          # + streamable-HTTP tool server
uv add "metacurator[tables]"       # + xlsx/docx/pdf supplement parsers
uv add "metacurator[schema,dev]"   # + LinkML codegen + test tooling
```

Ontology grounding works **without** any data-lake access via the bundled local-DuckDB
backend (it builds a small ontology store from public semantic-sql files); a DuckLake
backend is available for teams that have one. See [SPEC 070](docs/spec/070-ontology-grounding.md).

## Curation targets and SRA discovery

Everything specific to one curated resource lives in `targets/<name>/` (ADR-0010,
[SPEC 160](docs/spec/160-targets.md)); `cmd` (curatedMetagenomicData) is the first. Commands
that need a schema take `--target NAME` or `--schema PATH`:

```bash
uv run metacurator dictionary --target cmd
```

`discover` ([SPEC 190](docs/spec/190-discover.md)) prefilters the public OmicIDX SRA parquet
export by the target's library and organism criteria, screens each study with a decision
model (Cloudflare Workers AI Clef, [SPEC 180](docs/spec/180-decision-clients.md); needs
`CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AUTH_TOKEN`), and writes `studies.parquet`,
`readsets.parquet` (one row per sample, keyed by readset id,
[SPEC 170](docs/spec/170-readset.md)) and `summary.md`. Answers are cached, so reruns only
call the model for new or changed studies.

```bash
uv run metacurator discover --target cmd --dry-run          # states only, no model calls
uv run metacurator discover --target cmd --out discovery/cmd
uv run metacurator discover --target cmd --study ERP005534  # named studies, any organism
```

## License

MIT © 2026 Sean Davis. See [LICENSE](LICENSE). Contributions welcome —
see [CONTRIBUTING.md](CONTRIBUTING.md).
