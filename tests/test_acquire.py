"""acquire tests (SPEC 040) — offline; EuropePMC zip served by MockTransport."""

from __future__ import annotations

import io
import zipfile

import httpx

from metacurator.acquire import acquire, acquire_files
from metacurator.models import StudyRef
from metacurator.tables import load_tables

STUDY = StudyRef(pmid="27171425", pmcid="PMC4940234")


def _zip_bytes(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _client(*, status: int = 200, members: dict[str, str] | None = None) -> httpx.AsyncClient:
    content = _zip_bytes(members) if members else b""

    def handler(request: httpx.Request) -> httpx.Response:
        if "supplementaryFiles" in request.url.path:
            return httpx.Response(
                status, content=content, headers={"content-type": "application/zip"}
            )
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_acquire_europepmc_zip(tmp_path):
    members = {
        "supp/table1.csv": "subject_id,disease\ns1,Healthy\n",
        "readme.txt": "notes",
    }
    async with _client(members=members) as c:
        result = await acquire(STUDY, dest=tmp_path, client=c)
    assert result.gap is False
    assert result.method == "europepmc"
    assert {p.name for p in result.files} == {"table1.csv", "readme.txt"}
    # Extracted file is real and loadable via SPEC 050.
    csv = next(p for p in result.files if p.suffix == ".csv")
    assert load_tables(csv)[0].frame.records[0] == {"subject_id": "s1", "disease": "Healthy"}


async def test_acquire_empty_is_gap(tmp_path):
    async with _client(status=404) as c:
        result = await acquire(STUDY, dest=tmp_path, client=c)
    assert result.gap is True
    assert result.files == []


async def test_acquire_no_pmcid_is_gap_without_network(tmp_path):
    result = await acquire(StudyRef(pmid="x"), dest=tmp_path)  # no client needed
    assert result.gap is True
    assert "no PMCID" in result.note


async def test_acquire_files_wrapper(tmp_path):
    members = {"t.csv": "a,b\n1,2\n"}
    async with _client(members=members) as c:
        files = await acquire_files(STUDY, dest=tmp_path, client=c)
    assert [p.name for p in files] == ["t.csv"]
