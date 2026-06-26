"""MCP server tests (SPEC 120 / ADR-0006) — tool surface + a round-trip, offline."""

from __future__ import annotations

from metacurator.mcp_server import build_server

DETERMINISTIC_TOOLS = {
    "resolve_study",
    "archive_accessions",
    "acquire_supplements",
    "load_supplement_tables",
    "dictionary_fields",
    "ground_value",
    "diff_tables",
    "render_report",
}
_JUDGE_MARKERS = ("judge", "classify", "propose", "disambiguate")


async def test_tool_surface_is_deterministic_only():
    server = build_server()
    names = {t.name for t in await server.list_tools()}
    assert names >= DETERMINISTIC_TOOLS
    # ADR-0006: the server hosts NO judgment tools.
    assert not any(marker in n for n in names for marker in _JUDGE_MARKERS)


async def test_diff_tool_roundtrips_typed_object():
    server = build_server()
    res = await server.call_tool(
        "diff_tables",
        {
            "candidate": [{"sample_id": "s1", "sex": "Male"}],
            "reference": [{"sample_id": "s1", "sex": "Female"}],
            "key": "sample_id",
        },
    )
    results = res.structured_content["results"]
    sex = next(r for r in results if r["column"] == "sex")
    assert sex["verdict"] == "FAIL"
    assert sex["mismatch"] == 1


async def test_dictionary_tool():
    server = build_server()
    res = await server.call_tool("dictionary_fields", {})
    data = res.structured_content
    assert data["identifier"] == "sample_id"
    assert data["fields"]["disease"]["binding"]["branch_root"] == "NCIT:C7057"


async def test_render_report_tool():
    server = build_server()
    res = await server.call_tool(
        "render_report",
        {
            "pmid": "27171425",
            "sources": ["supp.xlsx#samples"],
            "diffs": [
                {"column": "sex", "compared": 2, "match": 2, "verdict": "PASS"}
            ],
        },
    )
    data = res.structured_content
    assert "27171425" in data["markdown"]
    assert data["sidecar"]["provenance"]["overall_verdict"] == "PASS"
