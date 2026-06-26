"""MCP server (streamable HTTP) — deterministic tools only. Implement to SPEC 120/ADR-0006.

Exposes resolve / archive / acquire / tables / dictionary / ground / diff / report as MCP
tools over streamable-HTTP transport (FastMCP, ``[mcp]`` extra), so it is hostable and
maintainable as a long-running endpoint. NO ``judge`` tools and NO LLM run here — the
consuming agent brings its own model (ADR-0006). Prefer stateless operation; put auth in
front of the server.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _cache_dir(cache_dir: str | None) -> Path:
    base = cache_dir or os.environ.get("METACURATOR_CACHE") or "~/.cache/metacurator"
    return Path(base).expanduser() / "ontology"


def build_server():
    """Construct the FastMCP server with the deterministic tool surface. See SPEC 120."""
    from fastmcp import FastMCP

    mcp = FastMCP(
        "metacurator",
        instructions=(
            "Deterministic curation tools (no LLM runs here; ADR-0006). The consuming "
            "agent performs the three judgment steps (SPEC 100) with its own model."
        ),
    )

    @mcp.tool
    async def resolve_study(pmid: str | None = None, doi: str | None = None) -> dict[str, Any]:
        """Resolve a PMID/DOI to a StudyRef (PMCID, DOI, OA status). SPEC 020."""
        from .resolve import resolve

        study = await resolve(pmid, doi=doi)
        return study.model_dump(mode="json")

    @mcp.tool
    async def archive_accessions(
        bioproject: str | None = None, seed_accession: str | None = None, pmid: str = "0"
    ) -> dict[str, Any]:
        """Build the authoritative ENA AccessionMap for a study/project. SPEC 030."""
        from .archive import build_accession_map
        from .models import StudyRef

        amap = await build_accession_map(
            StudyRef(pmid=pmid, bioproject=bioproject), seed_accession=seed_accession
        )
        return amap.model_dump(mode="json")

    @mcp.tool
    async def acquire_supplements(
        pmid: str, pmcid: str | None = None, dest: str = "./bronze"
    ) -> dict[str, Any]:
        """Fetch supplementary materials via the open-source ladder. SPEC 040."""
        from .acquire import acquire
        from .models import StudyRef

        result = await acquire(StudyRef(pmid=pmid, pmcid=pmcid), dest=Path(dest))
        return {
            "files": [str(p) for p in result.files],
            "method": result.method,
            "gap": result.gap,
            "note": result.note,
        }

    @mcp.tool
    def load_supplement_tables(path: str) -> dict[str, Any]:
        """Load every table in a supplement file into rows + provenance. SPEC 050."""
        from .tables import load_tables

        tables = load_tables(path)
        return {
            "tables": [
                {
                    "provenance": t.provenance.model_dump(),
                    "columns": t.frame.columns,
                    "n_rows": t.n_rows,
                    "records": t.frame.records,
                }
                for t in tables
            ]
        }

    @mcp.tool
    def dictionary_fields(schema_path: str | None = None) -> dict[str, Any]:
        """Introspect the active schema: fields, enums, ontology bindings. SPEC 060."""
        from .dictionary import Dictionary

        d = Dictionary(schema_path)
        fields = {
            name: {
                "range": fs.range,
                "required": fs.required,
                "multivalued": fs.multivalued,
                "enum": fs.enum_name,
                "permissible_values": fs.permissible_values,
                "binding": (
                    {"ontology": fs.binding.ontology, "branch_root": fs.binding.branch_root}
                    if fs.binding
                    else None
                ),
            }
            for name, fs in d.fields().items()
        }
        return {"class": d.class_name, "identifier": d.identifier, "fields": fields}

    @mcp.tool
    def ground_value(
        value: str, ontology: str, branch_root: str | None = None, cache_dir: str | None = None
    ) -> dict[str, Any]:
        """Ground a value to verified ontology term(s); never mints a CURIE. SPEC 070."""
        from .ground import ground
        from .grounding.local_duckdb import LocalDuckDBBackend

        backend = LocalDuckDBBackend(cache_dir=_cache_dir(cache_dir))
        backend.ensure([ontology])
        terms = ground(value, ontology, backend=backend, branch_root=branch_root)
        return {"terms": [t.model_dump(mode="json") for t in terms]}

    @mcp.tool
    def diff_tables(
        candidate: list[dict[str, Any]],
        reference: list[dict[str, Any]],
        key: str,
        secondary_key: str | None = None,
    ) -> dict[str, Any]:
        """QC diff candidate vs reference rows; per-column verdicts. SPEC 080."""
        from .diff import diff

        results = diff(candidate, reference, key=key, secondary_key=secondary_key)
        return {"results": [r.model_dump(mode="json") for r in results]}

    @mcp.tool
    def render_report(
        pmid: str, diffs: list[dict[str, Any]], sources: list[str] | None = None
    ) -> dict[str, Any]:
        """Assemble + render a CurationReport (markdown + JSON sidecar). SPEC 090."""
        from .models import DiffResult, StudyRef
        from .report import build_report, render_markdown, to_sidecar

        report = build_report(
            StudyRef(pmid=pmid),
            sources=sources or [],
            diffs=[DiffResult.model_validate(d) for d in diffs],
        )
        return {"markdown": render_markdown(report), "sidecar": to_sidecar(report)}

    return mcp


def main() -> None:
    """Run the server in streamable-HTTP transport (ADR-0006)."""
    server = build_server()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))
    server.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
