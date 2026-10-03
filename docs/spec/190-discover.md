# SPEC 190 — discover: candidate studies from SRA metadata

- Status: drafted
- Determinism: **hybrid** — SQL selection, state building, rule scoring and readset
  construction are deterministic; screening is a decision-client call (SPEC 180)
- Implements: `src/metacurator/discover.py`, CLI `metacurator discover`
- Related: ADR-0010, ADR-0011, SPEC 010, SPEC 160, SPEC 170, SPEC 180

## Purpose

Find candidate studies for a curation target in public SRA metadata: prefilter
experiments by library source/strategy and sample organism, summarise each study into a
compact **state**, screen it with the target's question set through a decision client,
threshold the answers with the target's rules, and emit the included studies' samples as
**readsets** (SPEC 170) ready for processing.

## Contracts

Input: the OmicIDX SRA parquet export (default
`https://data-omicidx.cancerdatasci.org/sra/parquet/`, overridable by `--parquet-base` or
`$METACURATOR_SRA_PARQUET`), files `sra_studies.parquet`, `sra_experiments.parquet`,
`sra_samples.parquet`, `sra_runs.parquet`. Columns used:

- `sra_studies(accession, title, abstract, bioproject)`
- `sra_experiments(accession, study_accession, sample_accession, platform,
  library_strategy, library_source)`
- `sra_samples(accession, organism, biosample, attributes STRUCT(tag, value)[])`
- `sra_runs(accession, experiment_accession)`

```python
DEFAULT_SRA_PARQUET = "https://data-omicidx.cancerdatasci.org/sra/parquet/"
def open_sra(base: str) -> duckdb.DuckDBPyConnection
def select_studies(con, pf: Prefilter, *, studies=None, limit=None) -> list[str]
def build_states(con, pf, study_accessions, *, apply_organisms=True) -> dict[str, dict]
def score_rules(answers, rules, questions) -> tuple[Decision, dict[str, float]]
def build_readsets(con, pf, study_accessions, *, apply_organisms=True) -> list[ReadsetRow]
def run_discovery(target, *, out, base=DEFAULT_SRA_PARQUET, studies=None, limit=None,
                  model=None, workers=8, dry_run=False, client=None) -> dict[str, Any]
```

`StudyDecision` and `ReadsetRow` are defined in SPEC 010.

CLI:

```
metacurator discover --target TEXT [--out PATH] [--parquet-base URL] [--study ACC]...
                     [--limit INT] [--model provider:model] [--workers INT] [--dry-run]
```

Outputs in `--out` (default `./discovery/<target>`):

| file | content |
|---|---|
| `studies.parquet` | one row per screened study (`StudyDecision`; dict fields as canonical-JSON strings) |
| `readsets.parquet` | one row per sample of each `include` study (`ReadsetRow`; `units` as `VARCHAR[]`) |
| `decisions.duckdb` | answer cache, table `decisions` |
| `states.parquet` | `--dry-run` only: `study_accession, state_json, state_digest` |
| `summary.md` | snapshot, model, digests, counts, review queue, errors, omissions |

## Behavior

1. **Open.** In-memory DuckDB; `httpfs` loaded for `http(s)` bases; a trailing `/` is
   appended to the base; one view per file.
2. **Select.** With explicit `studies`: those accessions, sorted and deduplicated, and the
   organism allow-list is **not** applied (so named controls of any organism can be
   screened); source and strategy filters still apply. Otherwise, every
   `study_accession` with at least one experiment whose `library_source` and
   `library_strategy` are in the prefilter lists and whose sample `organism` is in the
   allow-list, ordered by accession, truncated to `limit`.
3. **State.** Built in bulk queries over the selected studies, counting only qualifying
   experiments (same filter as step 2). Keys, exactly:
   `study_accession, bioproject, title, abstract` (≤ 4,000 chars)`, n_experiments,
   organisms` (top 5 `{name: count}`), `library_strategies` (`{value: count}`),
   `platforms` (`{value: count}`), `sample_attributes` (top 20 `"tag: value (count)"`,
   ranked by count then tag then value; administrative tags matching
   `^(insdc|ena|sra|submitter|external id|biosamplemodel|sample.?name|title|description)`
   on the lower-cased tag are dropped). A requested study with no qualifying experiments is
   omitted and reported.
4. **Digests.** `question_set_digest = sha512t24u(canonical_json(questions))`;
   `state_digest = sha512t24u(canonical_json(state))` (SPEC 170 primitives).
5. **Dry run** writes `states.parquet` and `summary.md`, calls no model, and stops.
6. **Screen.** Client = injected, else `make_decision_client(model or
   discovery.decision_model)`. The cache key is `(study_accession, model,
   question_set_digest, state_digest)`; cached answers are reused without a call. Uncached
   studies run in a thread pool of `workers`; results are consumed on the main thread and
   each success is written to the cache immediately, so an interrupted run keeps its
   progress. A `DecisionError` marks the study `error` and is not cached.
7. **Score.** Per rule: `noul` → the yes probability; `choice` → the sum of the accepted
   options' probabilities. `include` if every score ≥ `include_at`; `exclude` if any score
   < `review_at`; else `review`. Facets: the argmax option of each facet question.
8. **Readsets.** For `include` studies only: qualifying experiments' runs grouped by
   `sample_accession`; units are `insdc_unit(run)`; runs whose accession is not an INSDC
   run accession are skipped and counted; `readset_id(units)`; `biosample` and `organism`
   from `sra_samples`.
9. **Write** `studies.parquet`, `readsets.parquet`, `summary.md` (snapshot = the
   `Last-Modified` header of `sra_studies.parquet` for http bases, else none; counts by
   decision and per facet; the 25 `review` studies with the lowest rule score; every
   error; omitted studies; skipped runs). Return the counts.

Invariants:

- Readset units come only from SRA run accessions in the parquet; the model never supplies
  an accession (ADR-0004).
- Re-running with the same snapshot, question set and model makes zero model calls.
- Changing a question's wording changes `question_set_digest` and invalidates the cache.

## Errors

- Target without `discovery` → `ValueError`; CLI exit 2.
- Any study ending `error` → CLI exit 1 (outputs are still written).
- Parquet read failures propagate from DuckDB.

## Test cases (offline; tiny parquet fixtures written with DuckDB)

Three studies: `STUDY_H` (human gut, WGS/METAGENOMIC, 2 samples × 2 runs), `STUDY_M`
(mouse gut), `STUDY_S` (soil; excluded by organism). A fake decision client answers from
the state title and counts calls.

- `select_studies` → `["STUDY_H", "STUDY_M"]`.
- State keys are exactly as specified; administrative attributes are dropped.
- `score_rules`: a score exactly `include_at` includes; just below `review_at` excludes.
- `readsets.parquet` ids equal `readset_id` of each sample's units.
- A second run on the same `out` makes zero client calls.
- `--study STUDY_S` bypasses the organism filter.
- A client raising `DecisionError` yields one `error` row and CLI exit 1.
- `--dry-run` writes `states.parquet` and makes no calls.

## Open questions

- A depth filter (bases/spots) once the parquet export carries counts.
- Screening from BioProject/publication text in addition to SRA metadata.
- Incremental runs keyed by snapshot date.
