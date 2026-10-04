# 0010. General toolkit; curation targets live in `targets/<name>/`

- Status: accepted
- Date: 2026-10-03

## Context

ADR-0003 made the LinkML schema the substrate and named curatedMetagenomicData (cMD) "the
first concrete curation target". The code still treated cMD as the default: the
dictionary located `schema/cmd.yaml` by walking up from the package, and several commands
documented "default cmd". New work adds a discovery engine that screens public SRA
metadata for candidate studies. Its inclusion criteria (hosts, library strategies,
organism allow-lists, screening questions and thresholds) are cMD-specific and change for
scientific reasons, not for code reasons.

Two forces pull apart: the spine (resolve, archive, tables, dictionary, ground, diff,
discover) is generic and should stay testable without any one target; each target's
criteria should be reviewable as data, next to its schema.

## Decision

We will keep metacurator domain-agnostic and put every domain-specific artifact in a
**curation target** directory `targets/<name>/`:

- `target.yaml` — the manifest (name, title, schema path, optional discovery config;
  SPEC 160).
- `schema.yaml` — the target's LinkML schema (imports `schema/metacurator_core.yaml`).
- Target-specific scripts, such as an evaluation of discovery against the target's gold
  standard.

Rules:

- `src/` must not reference any target by name. There is no built-in default schema:
  schema resolution is explicit path → `$METACURATOR_SCHEMA` → error (SPEC 060).
- Commands that need a schema accept `--schema PATH` or `--target NAME|DIR`.
- The test suite must pass against the synthetic test schema alone. Target-specific
  assertions live only in `tests/test_cmd_target.py`.

cMD is the first target: `targets/cmd/`.

## Consequences

- Adding a target is adding a directory; no code change. Changing cMD's inclusion criteria
  is a reviewable YAML diff.
- Callers that relied on the implicit cMD default must now say `--target cmd` (CLI) or
  `Dictionary(load_target("cmd").schema_path)` (Python). This is a breaking change for
  library users, accepted at version 0.0.x.
- A wheel install has no `targets/` directory; users point `$METACURATOR_TARGETS` at one,
  or pass a target directory path. Packaging targets as data is deferred.
- The word "profile" stays with SPEC 140 (column profiling); the concept here is a
  "target".

## Alternatives considered

- **cMD-only repository.** Rejected: the spine is already target-agnostic (ADR-0003), and
  cMD criteria change for scientific reasons and belong in reviewable config rather than
  in code paths.
- **Separate deployment repository for cMD** (config, secrets, schedules, outputs).
  Deferred until secrets, schedules and outputs accumulate; today a directory suffices.
- **Keep a default schema, just move it.** Rejected: an implicit default lets target
  assumptions leak back into `src/` and its tests.
