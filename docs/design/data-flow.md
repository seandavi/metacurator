# Data flow (per study)

How one study moves through the pipeline (SPEC 110). `[D]` = deterministic tool,
`[A]` = agent judgment (SPEC 100). Every arrow carries a typed object (SPEC 010).

```
 PMID
  │
  ▼  [D] resolve (SPEC 020)
 StudyRef ───────────────────────────────────────────────┐
  │                                                        │
  ▼  [D] archive (SPEC 030)                                │
 AccessionMap  (runs↔samples↔aliases; authoritative IDs)  │
  │                                                        │
  ▼  [D] acquire (SPEC 040)                                │
 supplement files (bronze)                                 │
  │                                                        │
  ▼  [D] tables (SPEC 050)                                 │
 [SourceTable, …]                                          │
  │                                                        │
  ▼  [A] classify_tables (SPEC 100)                        │
 chosen SourceTable (the patient table)                    │
  │                                                        │
  ▼  [A] propose_mapping (SPEC 100)                        │
 ColumnMapping  ──[D] validate vs schema (SPEC 060)        │
  │                                                        │
  ▼  [D] apply mapping → raw candidate values              │
  │        join to AccessionMap on alias/sample  ◀─────────┘
  │
  ▼  [D] ground (SPEC 070)  → GroundedTerm per ontology-bound value
  │        (lookup → round-trip → branch → obsolete; backend: local DuckDB or DuckLake)
  │
  ▼  [A] disambiguate (SPEC 100)  — only for review-tier values
  │
  ▼  [D] assemble CandidateRows (conform to generated record model)
  │
  ▼  [D] diff / QC (SPEC 080)  → DiffResult per column
  │
  ▼  [D] report (SPEC 090)  → CurationReport (+ provenance sidecar)
```

Fan-out: the same per-study chain runs across a study list; per-study failures are
isolated. QC gates (low-confidence classify/propose, or a FAIL diff) route a study to
human review rather than emitting silently.

Note the two authoritative, model-free sources of identifiers: **`archive`** for
accessions and **`ground`** for ontology CURIEs. The agent steps shape and choose; they
never mint an identifier (ADR-0004).
