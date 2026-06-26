"""resolve tests (SPEC 020) — offline against saved idconv + OA responses."""

from __future__ import annotations

import httpx
import pytest

from metacurator.models import OAStatus
from metacurator.resolve import resolve

_OA_RECORD = (
    "<OA><records><record id='PMC4940234'>"
    "<link format='tgz' href='ftp://ftp.ncbi.nlm.nih.gov/x/x.tar.gz'/>"
    "</record></records></OA>"
)
_OA_NOT = "<OA><error code='idIsNotOpenAccess'>not open access</error></OA>"


def _client(*, idconv: dict, oa_xml: str = _OA_RECORD) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "idconv" in path:
            return httpx.Response(200, json=idconv)
        if "oa.fcgi" in path:
            return httpx.Response(200, text=oa_xml)
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


_OK = {"records": [{"pmid": "27171425", "pmcid": "PMC4940234", "doi": "10.1158/x"}]}


async def test_resolve_oa_article():
    async with _client(idconv=_OK, oa_xml=_OA_RECORD) as c:
        study = await resolve("27171425", client=c)
    assert study.pmcid == "PMC4940234"
    assert study.doi == "10.1158/x"
    assert study.oa_status == OAStatus.oa


async def test_resolve_non_oa_article():
    async with _client(idconv=_OK, oa_xml=_OA_NOT) as c:
        study = await resolve("27171425", client=c)
    assert study.oa_status == OAStatus.not_oa


async def test_resolve_from_doi():
    async with _client(idconv=_OK) as c:
        study = await resolve(doi="10.1158/x", client=c)
    assert study.pmid == "27171425"
    assert study.pmcid == "PMC4940234"


async def test_resolve_no_pmcid_is_unknown_oa():
    idconv = {"records": [{"pmid": "123", "doi": "10.1/y"}]}  # no pmcid
    async with _client(idconv=idconv) as c:
        study = await resolve("123", client=c)
    assert study.pmcid is None
    assert study.oa_status == OAStatus.unknown


async def test_resolve_unresolvable_raises():
    idconv = {"records": [{"pmid": "999", "status": "error", "errmsg": "invalid id"}]}
    async with _client(idconv=idconv) as c:
        with pytest.raises(LookupError, match="could not resolve"):
            await resolve("999", client=c)


async def test_resolve_requires_an_identifier():
    with pytest.raises(ValueError, match="needs a pmid or a doi"):
        await resolve()
