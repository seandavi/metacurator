"""archive — ENA/BioSample accessions & ID map. Implement to SPEC 030. [deterministic]

Authoritative for accessions (ADR-0004): no other stage may invent these. Uses the ENA
portal ``filereport`` API (no auth); DDBJ ``PRJDB`` projects are ENA-mirrored, so the same
call serves them. The ``httpx.AsyncClient`` is injectable so offline tests run against a
saved ENA snapshot.
"""

from __future__ import annotations

from collections import defaultdict

import httpx

from .models import AccessionMap, AccessionRow, StudyRef

ENA_PORTAL = "https://www.ebi.ac.uk/ena/portal/api/filereport"
RUN_FIELDS = (
    "run_accession",
    "sample_accession",
    "secondary_sample_accession",
    "study_accession",
    "sample_alias",
    "sample_title",
)
_TIMEOUT = httpx.Timeout(60.0)


def _parse_tsv(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    out: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        out.append(dict(zip(header, line.split("\t"), strict=False)))
    return out


def _clean(value: str | None) -> str | None:
    """Empty ENA cells -> None; everything else verbatim."""
    if value is None:
        return None
    v = value.strip()
    return v or None


async def _filereport(
    accession: str,
    *,
    fields: tuple[str, ...],
    client: httpx.AsyncClient,
    result: str = "read_run",
) -> list[dict[str, str]]:
    resp = await client.get(
        ENA_PORTAL,
        params={
            "accession": accession,
            "result": result,
            "fields": ",".join(fields),
            "format": "tsv",
        },
    )
    resp.raise_for_status()
    return _parse_tsv(resp.text)


async def project_for_accession(accession: str, *, client: httpx.AsyncClient) -> str | None:
    """Step 1: the study/project accession a run or sample belongs to (SPEC 030)."""
    rows = await _filereport(accession, fields=("study_accession",), client=client)
    return _clean(rows[0].get("study_accession")) if rows else None


async def build_accession_map(
    study: StudyRef,
    *,
    seed_accession: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> AccessionMap:
    """Resolve the project, then bulk-fetch its runs into an AccessionMap. See SPEC 030."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        project = study.bioproject
        if not project:
            if not seed_accession:
                raise ValueError(
                    "need study.bioproject or a seed_accession to resolve the project"
                )
            project = await project_for_accession(seed_accession, client=client)
        if not project:
            raise LookupError(f"could not resolve a project (seed={seed_accession!r})")

        rows = await _filereport(project, fields=RUN_FIELDS, client=client)
        if not rows:
            raise LookupError(f"ENA returned no runs for project {project!r}")

        acc_rows = [
            AccessionRow(
                run=_clean(r.get("run_accession")),
                sample=_clean(r.get("sample_accession")),
                secondary_sample=_clean(r.get("secondary_sample_accession")),
                alias=_clean(r.get("sample_alias")),
                title=_clean(r.get("sample_title")),
            )
            for r in rows
        ]
        return AccessionMap(project=project, source="ena", rows=acc_rows)
    finally:
        if own_client:
            await client.aclose()


# -- deterministic helpers (no I/O) ------------------------------------------


def runs_for_sample(amap: AccessionMap) -> dict[str, set[str]]:
    """BioSample -> the set of run accessions it maps to (membership, not equality)."""
    out: dict[str, set[str]] = defaultdict(set)
    for row in amap.rows:
        if row.sample and row.run:
            out[row.sample].add(row.run)
    return dict(out)


def by_alias(amap: AccessionMap) -> dict[str, list[AccessionRow]]:
    """Submitter alias (often the paper's sample ID) -> its AccessionRows."""
    out: dict[str, list[AccessionRow]] = defaultdict(list)
    for row in amap.rows:
        if row.alias:
            out[row.alias].append(row)
    return dict(out)
