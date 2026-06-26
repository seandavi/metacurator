# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 0.1.0.

## [Unreleased]

### Added
- Initial spec-first scaffold: SPEC framework, ADRs 0001–0006, design docs.
- LinkML schema starter: `metacurator_core` (framework contracts) and `cmd` (first
  concrete curation schema, lifted from the curatedMetagenomicData data dictionary).
- Module stubs for the deterministic spine, the agent boundary, and pluggable ontology
  grounding backends (DuckLake + standalone local-DuckDB).
- MIT license, packaging (`pyproject.toml`), contributor guide.

_Nothing is released yet; the implementation is being built from the specs._
