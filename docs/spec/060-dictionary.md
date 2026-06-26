# SPEC 060 — dictionary: schema load & validation

- Status: stub
- Determinism: deterministic
- Implements: `src/metacurator/dictionary.py`
- Related: ADR-0003 (LinkML), SPEC 010, 070

## Purpose

Load the active LinkML curation schema and expose it to the rest of the toolkit:
enumerate fields (slots), their types, permissible values (enums with ontology
`meaning`s), and **ontology bindings** (which ontology + which `reachable_from` root a
field's values must satisfy). Validate a `ColumnMapping` (targets exist) and a
`CandidateRow` (types, permissible values, ontology-branch constraints via SPEC 070).

## Scope note for implementation

- Read via `linkml-runtime`; do not depend on full `linkml` at runtime (codegen is a
  build step, ADR-0003). Generated Pydantic record models come from `_generated/`.
- Surface, per field: range/type, `required`, `multivalued`, enum permissible values +
  their `meaning` CURIEs, and any dynamic-enum (`reachable_from`) binding → hand the
  branch root to SPEC 070 for validation.
- Pluggable: the schema path is configuration; `cmd` is schema #1.

## To complete

Fill the template. Cases: load `cmd.yaml`; reject a mapping to an unknown field; reject a
value outside an enum; accept a value whose ontology term is under the bound branch and
reject one that is not.
