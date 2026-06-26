# metacurator

**Reproduce curated, sample-level metadata from publications — deterministically where
possible, with an LLM only where judgment is irreducible, and never a hallucinated
identifier.**

`metacurator` turns the ad-hoc work of reading a paper + its supplements and producing
a tidy, ontology-grounded sample table into a **spec-first toolkit**: a library of
deterministic tools, a pluggable LinkML schema describing the target standard, and a
narrow agent boundary for the few genuinely ambiguous steps.

> Status: **scaffold / pre-alpha.** The specs and decisions are in place; most modules
> are stubs. This repo is designed to be *built from its specs* — see below.

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
LinkML schema (schema/*.yaml)  ──gen──▶  Pydantic models + JSON Schema   (ADR-0003)
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

## License

MIT © 2026 Sean Davis. See [LICENSE](LICENSE). Contributions welcome —
see [CONTRIBUTING.md](CONTRIBUTING.md).
