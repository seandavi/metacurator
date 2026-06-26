"""metacurator — spec-first toolkit for reproducing curated, ontology-grounded,
sample-level metadata from publications.

This package is built **from its specs** (`docs/spec/`), under the decisions recorded in
`docs/adr/`. The organizing principle is the determinism gradient (ADR-0004): the public
surface here is the deterministic spine; the single LLM-dependent module is `judge`.

Most functions are stubs at this scaffold stage — implement to the matching SPEC.
"""

from __future__ import annotations

__version__ = "0.0.1"

# Public deterministic API (implemented to SPEC 020–090). Imported lazily by consumers;
# kept as names here to document the intended surface.
__all__ = [
    "resolve",
    "archive",
    "acquire",
    "tables",
    "dictionary",
    "ground",
    "diff",
    "report",
]
