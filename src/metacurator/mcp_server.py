"""MCP server (streamable HTTP) — deterministic tools only. Implement to SPEC 120/ADR-0006.

Exposes resolve / archive / acquire / tables / dictionary / ground / diff / report as MCP
tools over streamable-HTTP transport (FastMCP, ``[mcp]`` extra), so it is hostable and
maintainable as a long-running endpoint. NO ``judge`` tools and NO LLM run here — the
consuming agent brings its own model (ADR-0006). Prefer stateless operation; put auth in
front of the server.
"""

from __future__ import annotations


def build_server():
    """Construct the FastMCP server with the deterministic tool surface. See SPEC 120."""
    raise NotImplementedError("SPEC 120 — register deterministic tools on a FastMCP server")


def main() -> None:
    """Run the server in streamable-HTTP transport (ADR-0006)."""
    raise NotImplementedError("SPEC 120 — serve build_server() over streamable-http")


if __name__ == "__main__":
    main()
