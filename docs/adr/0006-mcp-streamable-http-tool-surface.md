# 0006. MCP tool surface over streamable HTTP

- Status: accepted
- Date: 2026-06-26

## Context

The deterministic tools must be callable uniformly by three kinds of consumer: a human
(CLI), an in-process workflow (Python API), and an arbitrary agent (Claude Code, an SDK
agent, another orchestrator). We also want the agent-facing surface to be a **hostable,
maintainable service**, not a per-session subprocess.

## Decision

Expose the deterministic tools as an **MCP server running in streamable-HTTP transport**
(via FastMCP), in addition to the Python API and CLI — three faces over one
implementation. Streamable HTTP (not stdio) is required so the server can be deployed and
maintained as a long-running endpoint.

Design constraints:

- The server offers **only deterministic tools** (`resolve`, `archive`, `acquire`,
  `tables`, `ground`, `dictionary`, `diff`, `report`) and read access to the active
  schema. **No LLM runs inside the server** — `judge.py` calls belong to the consuming
  agent, which brings its own model. This keeps the server pure, cacheable, and cheap to
  host.
- Prefer **stateless** operation (state passed in/out as typed objects) so it scales and
  restarts cleanly; put authentication in front of it (it can fetch and execute against
  external services).

## Consequences

- One tool implementation, three interfaces; agents integrate uniformly and remotely.
- A hostable endpoint the maintainer controls; the no-hallucination contract holds at the
  boundary because IDs come from these tools, not the agent.
- Cost: an `mcp` extra (FastMCP) and the operational surface of a service (auth, deploy).
  The CLI and Python API remain fully usable with no server.

## Alternatives considered

- **stdio MCP only** — not independently hostable/maintainable; tied to a subprocess.
- **CLI-only for agents** — looser typing across the boundary, no streaming, awkward for
  remote/SDK agents.
- **Put `judge` in the server** — would bake a model + cost into the shared service and
  break the "server is pure tools" property. Rejected.
