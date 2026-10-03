# SPEC 160 — targets: curation target manifests

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/target.py`
- Related: ADR-0003, ADR-0010, ADR-0011, SPEC 060, SPEC 190

## Purpose

Locate and validate a **curation target** — the directory that holds everything specific to
one curated resource (its LinkML schema and its discovery configuration), so the toolkit
itself names no target (ADR-0010).

## Contracts

Directory layout:

```
targets/<name>/
  target.yaml    # manifest (required)
  schema.yaml    # LinkML schema, path given by the manifest
  ...            # target-specific scripts (not loaded by the toolkit)
```

`target.yaml`:

```yaml
name: cmd                     # required
title: curatedMetagenomicData # required
schema: schema.yaml           # required; relative to the target directory
discovery:                    # optional; required by `discover` (SPEC 190)
  decision_model: "cloudflare:clef"     # provider:model (SPEC 180)
  prefilter:
    library_source: [METAGENOMIC]       # exact sra_experiments.library_source values
    library_strategy: [WGS, OTHER]      # exact sra_experiments.library_strategy values
    organisms: [human gut metagenome]   # exact sra_samples.organism values
  questions:                  # Clef question set, sent verbatim (SPEC 180)
    host: {type: choice, instructions: "...", criteria: {human: "...", mouse: "..."}}
    shotgun: {type: noul, instructions: "..."}
  rules:                      # every rule must pass for `include`
    - {question: host, accept: [human, mouse], include_at: 0.8, review_at: 0.5}
    - {question: shotgun, include_at: 0.8, review_at: 0.5}
  facets: [host]              # choice questions whose argmax is recorded per study
```

Python API (pydantic models forbid unknown keys):

```python
class Rule(BaseModel):         question: str; accept: list[str] = []; include_at: float; review_at: float
class Prefilter(BaseModel):    library_source: list[str]; library_strategy: list[str]; organisms: list[str]
class DiscoveryConfig(BaseModel):
    decision_model: str; prefilter: Prefilter
    questions: dict[str, dict[str, Any]]; rules: list[Rule]; facets: list[str] = []
class TargetManifest(BaseModel):
    name: str; title: str; schema_: str (alias "schema"); discovery: DiscoveryConfig | None = None

@dataclass(frozen=True)
class Target: name: str; root: Path; schema_path: Path; discovery: DiscoveryConfig | None

def targets_dir() -> Path
def load_target(ref: str | Path) -> Target
```

## Behavior

- `targets_dir()`: `$METACURATOR_TARGETS` if set; else the first `targets/` directory found
  walking up from the installed module's parents; else `FileNotFoundError`.
- `load_target(ref)`:
  1. If `Path(ref)` is a directory containing `target.yaml`, that directory is the root.
  2. Else the root is `targets_dir() / ref`, and `target.yaml` must exist there.
  3. Parse with `yaml.safe_load`; validate with `TargetManifest`.
  4. `schema_path = root / manifest.schema` must exist.
  5. Return `Target(name=manifest.name, root, schema_path, manifest.discovery)`.
- `DiscoveryConfig` validation (after field parsing):
  - at most 64 questions; ids match `^[A-Za-z0-9_.-]{1,100}$` (Clef's limits);
  - each question's `type` is one of `noul`, `choice`, `score`;
  - each rule names a defined question;
  - a rule on a `choice` question has non-empty `accept`, each a key of that question's
    `criteria`;
  - a rule on a `noul` question has empty `accept`;
  - rules on `score` questions are not supported;
  - `0 <= review_at <= include_at <= 1`;
  - each facet is a `choice` question.
- Loading is pure: no network, no model calls.

## Errors

- No targets directory → `FileNotFoundError("no targets/ directory; set $METACURATOR_TARGETS")`.
- Unknown target → `FileNotFoundError("unknown target '<ref>'; looked in <dir>")`.
- Schema file missing → `FileNotFoundError` naming the path.
- Invalid manifest or discovery config → `pydantic.ValidationError` whose message names the
  offending field (e.g. `rule 'host': accept option 'cat' not in criteria`).

## Test cases

- `load_target("cmd")` resolves `targets/cmd/schema.yaml`; `load_target(<dir>)` accepts a
  directory path; `$METACURATOR_TARGETS` overrides the search.
- Unknown name → `FileNotFoundError` mentioning the searched directory.
- Unknown manifest key → validation error.
- Each discovery validation rule above rejects a minimal bad config.
- The cmd target's discovery config validates with 4 questions and 2 rules
  (`tests/test_cmd_target.py`).

## Open questions

- Packaging targets as package data for wheel installs (today: repo checkout or
  `$METACURATOR_TARGETS`).
- Rules over `score` questions (a threshold on the weighted level) if a target needs one.
