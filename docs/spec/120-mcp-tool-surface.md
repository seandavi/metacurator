# SPEC 120 — Tool surface: MCP (streamable HTTP), CLI, Python API

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/mcp_server.py`, `src/metacurator/cli.py`,
  `src/metacurator/__init__.py` (the Python API surface)
- Related: ADR-0006, ADR-0004

## Purpose

Expose the deterministic spine through three faces over one implementation: a Python API
(import-and-call), a CLI (`metacurator …`), and an **MCP server over streamable HTTP**
for agents. The Python functions are the single implementation; CLI and MCP are thin
adapters.

## MCP server

- **Transport: streamable HTTP** (FastMCP), so it is hostable and maintainable as a
  long-running endpoint — not a stdio subprocess (ADR-0006).
- **Tools exposed (deterministic only):** `resolve`, `archive`, `acquire`, `tables`,
  `dictionary` (introspect the active schema: fields, enums, ontology bindings),
  `ground`, `diff`, `report`. Plus resources for the active schema document.
- **No `judge` tools.** The server hosts no LLM; the consuming agent runs `judge` calls
  with its own model (ADR-0006). This keeps the server pure, cacheable, hostable.
- **Stateless preferred:** inputs/outputs are the SPEC 010 typed objects (JSON); the
  server holds no per-session mutable state beyond caches (e.g. the local ontology
  store). Authentication is provided in front of the server by the operator.

## CLI

`metacurator <command>` mirrors the tools (`resolve`, `archive`, `acquire`, `ground`,
`diff`, `run` …) for human/offline use; `run` drives the pipeline (SPEC 110). Output is
human-readable; `--json` emits the typed object.

## Python API

`from metacurator import resolve, acquire, ground, diff, load_tables, Dictionary,
build_accession_map, build_report, curate_study, curate_many` — the canonical entry points
the CLI and MCP wrap. This is the interface the deterministic `pipeline` (SPEC 110) uses.
The four verb tools (`resolve`/`acquire`/`ground`/`diff`) are bound eagerly (their names
shadow their submodules); the rest resolve lazily so `import metacurator` stays light.

## Invariants

- A tool's behavior is identical across all three faces (same function underneath).
- The MCP surface exposes only deterministic tools; exposing a `judge` call here is a
  contract violation (ADR-0006).
- Every tool's response is a SPEC 010 typed object (or a clear typed error).

## Errors

- Tool errors are returned as structured error results (code + message + context), not
  opaque stack traces, so an agent can react.

## Test cases

- The MCP tool list contains the deterministic tools and **no** `judge*` tool.
- A tool invoked via CLI `--json` and via the Python API returns equivalent objects.
- Server runs in streamable-HTTP mode and a tool call round-trips a typed object.

## Open questions

- Auth model for the hosted server (token / mTLS / gateway) — operator's choice; document
  a recommended default.
- Whether `acquire` (which fetches external files) should be allowed on the hosted server
  or restricted to the CLI/local API for safety.
