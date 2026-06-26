# SPEC 060 — dictionary: schema load & validation

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/dictionary.py`
- Related: ADR-0003 (LinkML), SPEC 010, 070

## Purpose

Load the active LinkML curation schema and expose it to the rest of the toolkit:
enumerate fields (slots), their types, permissible values (enums with ontology
`meaning`s), and **ontology bindings** (which ontology + which `reachable_from` root a
field's values must satisfy). Validate a `ColumnMapping` (targets exist) and a
`CandidateRow` (types, permissible values, ontology-branch constraints via SPEC 070).

## Contracts

- **`OntologyBinding`** — a field's dynamic-enum binding: `ontology` (the grounding
  backend's lowercase key, e.g. `ncit`), `branch_root` (the CURIE values must be reachable
  from, e.g. `NCIT:C2991`), `predicates` (closure relations, default `rdfs:subClassOf`).
- **`FieldSpec`** — one slot: `name`, `range`, `required`, `multivalued`, `enum_name |
  None`, `permissible_values` (value → `meaning` CURIE or `None`), `binding | None`.
  `is_enum` ⇔ `enum_name is not None`; `is_dynamic_enum` ⇔ `binding is not None`.
- **`Dictionary`** — the loaded schema for one record class (default `Sample` in `cmd`):
  `fields()`, `field(name)`, `identifier`, `bindings()`, `ontologies_needed()`,
  `validate_mapping(mapping) -> list[str]`, `validate_row(row, *, backend=None) ->
  list[str]`. Validators return a list of human-readable error strings (empty ⇒ valid).

## Behavior

- Read via `linkml-runtime`'s `SchemaView`; do **not** depend on full `linkml` at runtime
  (codegen is a build step, ADR-0003). Generated Pydantic record models come from
  `_generated/`. The schema path is configuration; `cmd` is schema #1 (located relative to
  the repo or via `$METACURATOR_SCHEMA`).
- Per field, surface range/`required`/`multivalued`; for enum ranges, the permissible
  values and their `meaning` CURIEs; for a dynamic enum (`include: [{reachable_from}]`),
  the branch binding — `source_ontology` → `ontology`, `source_nodes[0]` → `branch_root`,
  `relationship_types` → `predicates`.
- `ontologies_needed()` unions the dynamic bindings' ontologies with the prefixes of all
  static enum `meaning` CURIEs, so a caller can `backend.ensure(...)` exactly those.
- **`validate_mapping`**: every `target_field` must be a slot of the active class.
- **`validate_row`**: per value (each element of a multivalued field):
  - numeric range (`float`/`integer`/…) → must coerce to a number;
  - static enum → value must be a permissible value;
  - dynamic enum → an explicit permissible value (e.g. `Healthy`) passes; otherwise, if a
    grounding `backend` is supplied, the value must `ground` (SPEC 070) to an in-branch,
    non-obsolete term; with no backend the dynamic check is skipped (reported as
    unverifiable only when asked to be strict).

## Invariants

- The dictionary never grounds or mints a CURIE itself — branch checks delegate to SPEC
  070. It only *reports* what the schema requires (ADR-0004).
- Static enum permissible sets come verbatim from the schema; dictionary does not extend
  them by memory.

## Errors

- Schema file not found / unreadable → explicit error naming the path searched.
- Validation never raises on bad *data*; it returns errors. It may raise on a bad *schema*
  reference (e.g. unknown class).

## Test cases

- Load `cmd.yaml`: `Sample` has the expected slots; `sample_id` is the identifier; `age`
  is `float`; `ncbi_accession` is multivalued.
- A `ColumnMapping` to an unknown field → non-empty errors; a valid one → `[]`.
- A static-enum value outside the permissible set (e.g. `body_site = "spleen"`) → error;
  a permissible one (`feces`) → ok.
- A dynamic-enum value whose ontology term is **under** the bound branch grounds clean
  (with a backend); one **not** under the branch → error. `Healthy` passes via the
  explicit permissible value.
- A non-numeric value for a `float` field → error.

## Open questions

- Packaging the schema files as package data so a wheel install can locate `cmd.yaml`
  without the source tree (currently resolved relative to the repo / `$METACURATOR_SCHEMA`).
- Whether to validate cross-field constraints (e.g. `age_unit` required when `age` set) —
  out of scope until a schema declares them as rules.
