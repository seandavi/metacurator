# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 0.1.0.

## [Unreleased]

### Added
- Curation targets (ADR-0010, SPEC 160): `targets/<name>/target.yaml` + schema;
  `load_target`; `--target` on `dictionary` and `run`; `target` on the MCP
  `dictionary_fields` tool.
- Readset ids (SPEC 170): refget seqcol digest over `insdc.sra:` run units, matching
  nextflow_telemetry ADR 0007 golden vectors.
- Decision clients (ADR-0011, SPEC 180): `DecisionClient` protocol and a Cloudflare
  Workers AI Clef client (`cloudflare:clef`, `cloudflare:clef-flash`).
- `metacurator discover` (SPEC 190): SRA parquet prefilter, per-study states, cached Clef
  screening, include/review/exclude rules, `studies.parquet` / `readsets.parquet` /
  `summary.md`.
- cmd target discovery config (human and mouse hosts, all body sites; study kind is a
  facet only) and `targets/cmd/eval_discovery.py`. Against the 2026-05-01 SRA snapshot:
  115/119 cMD studies pass the prefilter, 115/115 of those are kept (113 include), all
  six control studies behave as expected.
- Initial spec-first scaffold: SPEC framework, ADRs 0001–0006, design docs.
- LinkML schema starter: `metacurator_core` (framework contracts) and `cmd` (first
  concrete curation schema, lifted from the curatedMetagenomicData data dictionary).
- Module stubs for the deterministic spine, the agent boundary, and pluggable ontology
  grounding backends (DuckLake + standalone local-DuckDB).
- MIT license, packaging (`pyproject.toml`), contributor guide.

### Changed
- **Breaking:** no built-in default schema. `schema/cmd.yaml` moved to
  `targets/cmd/schema.yaml`; `Dictionary()` without a path needs `$METACURATOR_SCHEMA`,
  otherwise pass a path or use `load_target("cmd").schema_path` / `--target cmd`.
- `just gen` generates from `targets/*/schema.yaml`.

_Nothing is released yet; the implementation is being built from the specs._
