# 0004. Deterministic spine, agent judgment only at the joints

- Status: accepted
- Date: 2026-06-26

## Context

Curating metadata from a paper spans steps that need very different amounts of judgment.
Treating it all as "an agent task" wastes tokens, isn't reproducible, and — worst —
invites hallucinated accessions and ontology IDs. Treating it all as deterministic code
is impossible: every supplement is a different shape, and "which table is the patient
table" can't be hardcoded.

## Decision

Organize the toolkit along a **determinism gradient**. Mechanical steps are deterministic,
individually testable functions with no LLM in the call path; only irreducibly ambiguous
steps invoke a model, and those are confined to one module (`judge.py`) with exactly
three calls:

| step | nature | home |
|---|---|---|
| resolve (PMID→PMCID/DOI, OA triage) | lookup | deterministic |
| archive (ENA/BioSample accession + ID map) | lookup | deterministic |
| acquire (supplement download ladder) | mechanical | deterministic |
| tables (load xlsx/docx/pdf/csv) | mechanical | deterministic |
| ground (ontology lookup → round-trip → branch check) | mechanical | deterministic |
| diff / QC | mechanical | deterministic |
| report | mechanical | deterministic |
| `classify_tables` (which is the patient table) | judgment | **agent** |
| `propose_mapping` (source cols → schema fields) | judgment | **agent** |
| `disambiguate` (choose among real candidates) | judgment | **agent** |
| pipeline / fan-out / QC gating | control flow | deterministic |

**The no-hallucination contract:** agent calls return *validated typed objects*
(`ColumnMapping`, a choice among `GroundedTerm`s) — never a raw identifier or value. IDs
and accessions are produced only by deterministic tools. This is enforced structurally
(the agent literally cannot emit an accession the pipeline will trust) and by tests.

## Consequences

- Reproducibility, auditability, and low cost where it matters; flexibility exactly
  where inputs are messy.
- The skill (agent-facing knowledge) governs only `judge.py`; the spine stays code.
- Drawing the line is an ongoing judgment: as tools mature, more moves into the
  deterministic half. ADRs/specs record where the line currently sits.

## Alternatives considered

- **All-agent + skills** — flexible but non-reproducible, expensive, hallucination-prone
  on exact data. Rejected as the spine; retained as an *interaction mode* over the tools.
- **All-deterministic workflow** — brittle on heterogeneous supplements; over-fits to the
  studies seen so far. Rejected as the whole; adopted for the spine + orchestration.
