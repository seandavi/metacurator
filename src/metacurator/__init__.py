"""metacurator — spec-first toolkit for reproducing curated, ontology-grounded,
sample-level metadata from publications.

This package is built **from its specs** (`docs/spec/`), under the decisions recorded in
`docs/adr/`. The organizing principle is the determinism gradient (ADR-0004): the public
surface here is the deterministic spine; the single LLM-dependent module is `judge`.

The names below are the canonical entry points the CLI (SPEC 120) and MCP server wrap —
three faces over one implementation. The four verb tools (`resolve`/`acquire`/`ground`/
`diff`) are bound eagerly because their names collide with their submodules and they are
lightweight; the heavier entry points (linkml/pipeline) are resolved lazily (PEP 562) so
``import metacurator`` stays cheap.
"""

from __future__ import annotations

# Eager: verb tools whose names shadow the same-named submodule (lazy __getattr__ would
# never fire for them). These modules are light (no linkml/duckdb at import time).
from .acquire import acquire
from .diff import diff
from .ground import ground
from .resolve import resolve

__version__ = "0.0.1"

# Lazy: heavier / non-colliding entry points. name -> "module:attr".
_LAZY = {
    "build_accession_map": "archive:build_accession_map",
    "load_tables": "tables:load_tables",
    "Dictionary": "dictionary:Dictionary",
    "build_report": "report:build_report",
    "render_markdown": "report:render_markdown",
    "curate_study": "pipeline:curate_study",
    "curate_many": "pipeline:curate_many",
}

__all__ = ["__version__", "acquire", "diff", "ground", "resolve", *_LAZY]


def __getattr__(name: str):  # PEP 562 lazy attribute access
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module_name, attr = target.split(":")
    module = importlib.import_module(f".{module_name}", __name__)
    return getattr(module, attr)


def __dir__() -> list[str]:
    return sorted(__all__)
