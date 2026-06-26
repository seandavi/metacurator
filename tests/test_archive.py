"""archive tests (SPEC 030) — offline against a saved ENA filereport snapshot."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from metacurator.archive import build_accession_map, by_alias, runs_for_sample
from metacurator.models import StudyRef

FIXTURE = Path(__file__).parent / "fixtures" / "ena_filereport_PRJEB12449.tsv"
SNAPSHOT = FIXTURE.read_text()


def _mock_client() -> httpx.AsyncClient:
    """An AsyncClient whose ENA portal responses come from the snapshot.

    A ``fields=study_accession`` request (step 1) returns just the project; any other
    request returns the full bulk filereport.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        fields = request.url.params.get("fields", "")
        if fields == "study_accession":
            return httpx.Response(200, text="study_accession\nPRJEB12449\n")
        return httpx.Response(200, text=SNAPSHOT)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_build_from_bioproject():
    study = StudyRef(pmid="27171425", bioproject="PRJEB12449")
    async with _mock_client() as client:
        amap = await build_accession_map(study, client=client)
    assert amap.project == "PRJEB12449"
    assert amap.source == "ena"
    assert len(amap.rows) == 3
    assert amap.rows[0].sample == "SAMEA3879595"
    assert amap.rows[0].secondary_sample == "ERS1066729"


async def test_runs_for_sample_is_membership():
    study = StudyRef(pmid="27171425", bioproject="PRJEB12449")
    async with _mock_client() as client:
        amap = await build_accession_map(study, client=client)
    rfs = runs_for_sample(amap)
    assert rfs["SAMEA3879595"] == {"ERR1293500", "ERR1293499"}
    assert rfs["SAMEA3879596"] == {"ERR1293861"}


async def test_two_step_resolves_project_from_seed():
    study = StudyRef(pmid="27171425")  # no bioproject
    async with _mock_client() as client:
        amap = await build_accession_map(study, seed_accession="ERR1293500", client=client)
    assert amap.project == "PRJEB12449"
    assert len(amap.rows) == 3


async def test_by_alias_recovers_paper_ids():
    study = StudyRef(pmid="27171425", bioproject="PRJEB12449")
    async with _mock_client() as client:
        amap = await build_accession_map(study, client=client)
    aliases = by_alias(amap)
    assert "MMRS11288076ST-27-0-0" in aliases
    assert len(aliases["MMRS11288076ST-27-0-0"]) == 2  # two runs share the alias


async def test_ddbj_project_uses_same_call():
    study = StudyRef(pmid="0", bioproject="PRJDB1234")
    async with _mock_client() as client:
        amap = await build_accession_map(study, client=client)
    assert amap.project == "PRJDB1234"  # project echoes the requested accession
    assert len(amap.rows) == 3


async def test_missing_project_and_seed_raises():
    with pytest.raises(ValueError, match="bioproject or a seed_accession"):
        await build_accession_map(StudyRef(pmid="0"))


@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"), reason="set RUN_INTEGRATION=1 for live ENA"
)
async def test_live_ena_project():
    study = StudyRef(pmid="27171425", bioproject="PRJEB12449")
    amap = await build_accession_map(study)
    assert amap.project == "PRJEB12449"
    assert len(amap.rows) > 100
    assert all(r.run and r.run.startswith("ERR") for r in amap.rows if r.run)
