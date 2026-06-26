"""resolve — identifiers & open-access triage. Implement to SPEC 020. [deterministic]

Pure HTTP + parse; no LLM. PMID/DOI -> StudyRef via the NCBI PMC ID Converter, then OA
status via the PMC OA service. The httpx.AsyncClient is injectable for offline tests.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import httpx

from .models import OAStatus, StudyRef

IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
DEFAULT_EMAIL = "metacurator@example.org"
_TIMEOUT = httpx.Timeout(30.0)


async def _idconv(ident: str, *, client: httpx.AsyncClient, email: str) -> dict[str, str] | None:
    resp = await client.get(
        IDCONV_URL,
        params={"ids": ident, "format": "json", "tool": "metacurator", "email": email},
    )
    resp.raise_for_status()
    records = resp.json().get("records") or []
    return records[0] if records else None


async def _oa_status(pmcid: str, *, client: httpx.AsyncClient) -> OAStatus:
    resp = await client.get(OA_URL, params={"id": pmcid})
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    error = root.find(".//error")
    if error is not None:
        return OAStatus.not_oa if error.get("code") == "idIsNotOpenAccess" else OAStatus.unknown
    return OAStatus.oa if root.find(".//record") is not None else OAStatus.unknown


async def oa_package_url(pmcid: str, *, client: httpx.AsyncClient) -> str | None:
    """The OA package (tgz) href if the article is in the PMC OA subset (SPEC 020)."""
    resp = await client.get(OA_URL, params={"id": pmcid})
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    for link in root.findall(".//link"):
        if link.get("format") == "tgz":
            return link.get("href")
    return None


async def resolve(
    pmid: str | None = None,
    *,
    doi: str | None = None,
    client: httpx.AsyncClient | None = None,
    email: str = DEFAULT_EMAIL,
) -> StudyRef:
    """PMID/DOI -> StudyRef (PMCID, DOI, OA status). See SPEC 020."""
    ident = pmid or doi
    if not ident:
        raise ValueError("resolve needs a pmid or a doi")

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        record = await _idconv(ident, client=client, email=email)
        if record is None or record.get("status") == "error":
            raise LookupError(f"could not resolve identifier {ident!r}")

        pmcid = record.get("pmcid") or None
        oa = await _oa_status(pmcid, client=client) if pmcid else OAStatus.unknown
        return StudyRef(
            pmid=record.get("pmid") or (pmid or ""),
            pmcid=pmcid,
            doi=record.get("doi") or doi,
            oa_status=oa,
        )
    finally:
        if own_client:
            await client.aclose()
