"""CLI — thin adapter over the deterministic API. Implement to SPEC 120. [deterministic]

``metacurator <command>`` mirrors the tools (resolve, dictionary, ground, diff, archive,
acquire) plus ``serve`` for the MCP endpoint. The same functions underlie the Python API
and the MCP server — three faces, one implementation. ``--json`` emits the typed object.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(
    help="metacurator — reproduce curated, ontology-grounded sample metadata from papers.",
    add_completion=False,
)


def _emit(obj: Any, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(obj, indent=2, default=str))
    else:
        typer.echo(obj)


@app.command()
def version() -> None:
    """Print the metacurator version."""
    from . import __version__

    typer.echo(__version__)


@app.command()
def resolve(
    pmid: str = typer.Argument(None, help="PubMed ID"),
    doi: str = typer.Option(None, "--doi", help="DOI (instead of a PMID)"),
    json_out: bool = typer.Option(False, "--json", help="Emit the StudyRef as JSON"),
) -> None:
    """Resolve a PMID/DOI to a StudyRef (PMCID, DOI, OA status). SPEC 020."""
    from .resolve import resolve as _resolve

    study = asyncio.run(_resolve(pmid, doi=doi))
    if json_out:
        _emit(study.model_dump(mode="json"), True)
    else:
        typer.echo(
            f"pmid={study.pmid} pmcid={study.pmcid} doi={study.doi} oa={study.oa_status}"
        )


@app.command()
def dictionary(
    schema: str = typer.Option(None, "--schema", help="Path to a LinkML schema (default cmd)"),
    json_out: bool = typer.Option(False, "--json", help="Emit fields as JSON"),
) -> None:
    """Introspect the active curation schema: fields, enums, ontology bindings. SPEC 060."""
    from .dictionary import Dictionary

    d = Dictionary(schema)
    if json_out:
        _emit(
            {
                name: {
                    "range": fs.range,
                    "required": fs.required,
                    "multivalued": fs.multivalued,
                    "enum": fs.enum_name,
                    "binding": fs.binding.branch_root if fs.binding else None,
                }
                for name, fs in d.fields().items()
            },
            True,
        )
        return
    typer.echo(f"class={d.class_name} identifier={d.identifier}")
    for name, fs in d.fields().items():
        flags = "".join(c for c, on in (("R", fs.required), ("M", fs.multivalued)) if on)
        kind = fs.enum_name or fs.range
        typer.echo(f"  {name}: {kind} {flags}")


@app.command()
def ground(
    value: str = typer.Argument(..., help="The value to ground"),
    ontology: str = typer.Argument(..., help="Ontology key, e.g. ncit / uberon"),
    branch_root: str = typer.Option(None, "--branch-root", help="Required ancestor CURIE"),
    cache_dir: str = typer.Option(None, "--cache-dir", help="Ontology store cache dir"),
    json_out: bool = typer.Option(False, "--json", help="Emit GroundedTerms as JSON"),
) -> None:
    """Ground a value to verified ontology term(s); never mints a CURIE. SPEC 070."""
    from .ground import ground as _ground
    from .grounding.local_duckdb import LocalDuckDBBackend

    base = Path(cache_dir).expanduser() if cache_dir else Path.home() / ".cache" / "metacurator"
    backend = LocalDuckDBBackend(cache_dir=base / "ontology")
    backend.ensure([ontology])
    terms = _ground(value, ontology, backend=backend, branch_root=branch_root)
    if json_out:
        _emit([t.model_dump(mode="json") for t in terms], True)
        return
    if not terms:
        typer.echo("(no grounding)")
    for t in terms:
        typer.echo(f"  {t.curie}\t{t.label}\t{t.confidence_tier}\tbranch_ok={t.branch_ok}")


@app.command()
def diff(
    candidate: Path = typer.Argument(..., help="Candidate table (csv/tsv/xlsx/…)"),
    reference: Path = typer.Argument(..., help="Reference table"),
    key: str = typer.Option(..., "--key", help="Join column"),
    secondary_key: str = typer.Option(None, "--secondary-key", help="Fallback join column"),
    json_out: bool = typer.Option(False, "--json", help="Emit DiffResults as JSON"),
) -> None:
    """QC diff a candidate table against a reference. SPEC 080."""
    from .diff import diff as _diff
    from .tables import load_tables

    cand = load_tables(candidate)[0].frame.records
    ref = load_tables(reference)[0].frame.records
    results = _diff(cand, ref, key=key, secondary_key=secondary_key)
    if json_out:
        _emit([r.model_dump(mode="json") for r in results], True)
        return
    for r in results:
        typer.echo(
            f"  {r.column}: {r.verdict} (compared={r.compared} match={r.match} "
            f"mismatch={r.mismatch} blank={r.blank} cand_adds={r.cand_adds})"
        )


@app.command()
def archive(
    bioproject: str = typer.Option(None, "--bioproject", help="ENA/DDBJ project accession"),
    seed: str = typer.Option(None, "--seed", help="A known run/sample accession"),
    pmid: str = typer.Option("0", "--pmid", help="PMID for the StudyRef"),
    json_out: bool = typer.Option(False, "--json", help="Emit the AccessionMap as JSON"),
) -> None:
    """Build the authoritative ENA AccessionMap for a study/project. SPEC 030."""
    from .archive import build_accession_map
    from .models import StudyRef

    amap = asyncio.run(
        build_accession_map(StudyRef(pmid=pmid, bioproject=bioproject), seed_accession=seed)
    )
    if json_out:
        _emit(amap.model_dump(mode="json"), True)
        return
    typer.echo(f"project={amap.project} rows={len(amap.rows)} source={amap.source}")


@app.command()
def run(
    pmid: str = typer.Argument(..., help="PubMed ID of the study to curate"),
    model: str = typer.Option("vertex:gemini-3.1-flash-lite", "--model", help="provider:model"),
    dest: str = typer.Option("./bronze", "--dest", help="where to save fetched supplements"),
    cache: str = typer.Option(None, "--cache-dir", help="ontology store cache dir"),
    schema: str = typer.Option(None, "--schema", help="LinkML schema (default cmd)"),
    no_ground: bool = typer.Option(False, "--no-ground", help="skip ontology grounding"),
    json_out: bool = typer.Option(False, "--json", help="emit the report JSON sidecar"),
) -> None:
    """Curate one study end-to-end with a real model judge (SPEC 110/130). [live]

    Resolves the PMID, acquires open supplements, loads tables, and runs the pipeline with
    the chosen model performing the three judgment calls. Grounds dynamic-enum fields
    against the ontologies the schema binds (downloaded on first use).
    """
    from .acquire import acquire
    from .dictionary import Dictionary
    from .grounding.local_duckdb import LocalDuckDBBackend
    from .llm import make_client
    from .pipeline import curate_study
    from .report import render_markdown, to_sidecar
    from .resolve import resolve as _resolve
    from .tables import load_tables

    study = asyncio.run(_resolve(pmid))
    typer.echo(f"resolved: pmid={study.pmid} pmcid={study.pmcid} oa={study.oa_status}")

    result = asyncio.run(acquire(study, dest=Path(dest)))
    if result.gap:
        typer.echo(f"acquire: gap — {result.note}", err=True)
        raise typer.Exit(code=2)
    tables = [t for f in result.files for t in load_tables(f)]
    typer.echo(
        f"acquired {len(result.files)} file(s) via {result.method}; {len(tables)} table(s)"
    )

    dictionary = Dictionary(schema)
    backend = None
    if not no_ground:
        base = Path(cache).expanduser() if cache else Path.home() / ".cache" / "metacurator"
        backend = LocalDuckDBBackend(cache_dir=base / "ontology")
        onts = sorted({b.ontology for b in dictionary.bindings().values()})
        if onts:
            typer.echo(f"ensuring ontologies for grounding: {onts}")
            backend.ensure(onts)

    report = curate_study(
        study, dictionary=dictionary, llm=make_client(model), backend=backend
    )
    if json_out:
        _emit(to_sidecar(report), True)
    else:
        typer.echo(render_markdown(report))


@app.command()
def serve() -> None:
    """Run the MCP server (streamable HTTP); deterministic tools only (ADR-0006). SPEC 120."""
    from .mcp_server import main

    main()


if __name__ == "__main__":
    app()
