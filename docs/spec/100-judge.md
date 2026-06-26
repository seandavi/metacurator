# SPEC 100 — Judge: the agent boundary

- Status: drafted
- Determinism: **agent** (the only module that invokes an LLM)
- Implements: `src/metacurator/judge.py`
- Related: ADR-0004 (determinism gradient + no-hallucination contract), SPEC 010, 060, 070

## Purpose

Contain *all* LLM-dependent judgment in exactly three calls, each consuming and producing
typed objects (SPEC 010). Everything else in the toolkit is deterministic. This module is
where a **skill** plugs in: the skill is the system prompt + technique notes + tool-access
policy for these calls. Nothing here produces an identifier or a curated value directly —
agents choose among / describe over deterministic results.

## The three calls

1. **`classify_tables(tables: list[SourceTable], schema) -> TableChoice`**
   Pick which loaded supplement table is the per-subject characteristics table (and why).
   Output: chosen `table_index`, rationale, confidence. No data extraction here.

2. **`propose_mapping(table: SourceTable, schema) -> ColumnMapping`**
   Map source columns to target-schema fields, proposing a transform per column. Output
   is a `ColumnMapping` (SPEC 010) — a *description of how to project*, never values.
   The deterministic spine validates it against the schema (SPEC 060) and applies it.

3. **`disambiguate(value: str, candidates: list[GroundedTerm]) -> DisambiguationChoice`**
   Choose among **real** grounded candidates produced by SPEC 070 (or decline). The
   agent may only return one of the provided `curie`s or `None` — it cannot mint a CURIE;
   a returned CURIE outside the candidate set raises `JudgeContractError`.

## Invariants (the contract)

- **No invented identifiers or values.** Accessions come from `archive`; CURIEs from
  `ground`; the agent selects/labels, it does not assert data. Enforced by types (the
  return shapes carry no free identifier field the spine will trust) and by tests.
- **Deterministic-first.** A judgment call is made only when the deterministic path is
  ambiguous (e.g. a value that grounded to multiple `review`-tier terms). If grounding
  returned a single `auto` term, `disambiguate` is not called.
- **Model-agnostic & swappable.** The LLM client is injected; `judge.py` defines the
  contract and prompt assembly, not a hardwired vendor. The MCP server (SPEC 120) does
  **not** host these calls — the consuming agent brings its own model (ADR-0006).
- **Auditable.** Each call records its inputs, the prompt, and the typed output into the
  `CurationReport` provenance.

## Errors

- Low-confidence `classify_tables`/`propose_mapping` → return the result *with* a
  `needs_review` flag rather than proceeding silently; the pipeline (SPEC 110) gates on it.
- `disambiguate` returning a CURIE not in the candidate set → rejected by validation (a
  bug in the implementation or prompt), surfaced loudly.

## Test cases

- With the LLM client mocked, `propose_mapping` output is validated against a schema and
  a mapping to a non-existent field is rejected.
- `disambiguate` constrained to candidate CURIEs: a response outside the set raises.
- When grounding yields a single `auto` term, the pipeline does not call `disambiguate`
  (spied).

## Open questions

- Whether `propose_mapping` should be one call or per-column (token vs. context tradeoff).
- How much of the skill's technique corpus to inline per call vs. reference.
