"""judge — THE AGENT BOUNDARY (the only module that invokes an LLM). SPEC 100, ADR-0004.

Exactly three judgment calls, each returning a validated typed object — never an
identifier or curated value. The LLM client is injected (model-agnostic). A skill
supplies the prompts/technique corpus for these calls. The MCP server does NOT host
these (ADR-0006): the consuming agent brings its own model.
"""

from __future__ import annotations

from typing import Any, Protocol

from .models import ColumnMapping, GroundedTerm, SourceTable


class LLMClient(Protocol):
    """Minimal injected LLM interface; implementations live outside the deterministic core."""

    def complete(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


def classify_tables(tables: list[SourceTable], schema: Any, *, llm: LLMClient) -> int:
    """Pick the index of the per-subject characteristics table (+ rationale). SPEC 100."""
    raise NotImplementedError("SPEC 100 — classify_tables (agent)")


def propose_mapping(table: SourceTable, schema: Any, *, llm: LLMClient) -> ColumnMapping:
    """Map source columns → schema fields; returns a ColumnMapping (no values). SPEC 100."""
    raise NotImplementedError("SPEC 100 — propose_mapping (agent)")


def disambiguate(value: str, candidates: list[GroundedTerm], *, llm: LLMClient) -> str | None:
    """Choose among REAL grounded candidates (or None). Cannot mint a CURIE. SPEC 100."""
    raise NotImplementedError("SPEC 100 — disambiguate (agent)")
