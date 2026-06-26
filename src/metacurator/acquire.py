"""acquire — supplement retrieval ladder. Implement to SPEC 040. [deterministic]

Fetch supplementary materials in a reliability order, saving everything verbatim to a
bronze dir (idempotent), and report which method worked. The EuropePMC zip rung is
implemented in-core; brittle CDN/browser rungs are hooks (SPEC 040). No LLM. The
httpx.AsyncClient is injectable for offline tests.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .models import StudyRef

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_TIMEOUT = httpx.Timeout(120.0)


@dataclass
class AcquireResult:
    """What `acquire` retrieved, how, and whether it hit a gap (SPEC 040)."""

    files: list[Path] = field(default_factory=list)
    method: str = "none"
    gap: bool = True
    note: str = ""


def _looks_like_zip(content: bytes) -> bool:
    return content[:2] == b"PK"


async def _europepmc_supplement(
    pmcid: str, dest: Path, client: httpx.AsyncClient
) -> list[Path]:
    """Download + extract the EuropePMC supplementaryFiles zip into ``dest``."""
    num = pmcid.replace("PMC", "")
    resp = await client.get(f"{EUROPEPMC}/PMC{num}/supplementaryFiles")
    if resp.status_code != 200 or not _looks_like_zip(resp.content):
        return []
    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            target = dest / Path(name).name  # flatten; verbatim bytes
            target.write_bytes(zf.read(name))
            extracted.append(target)
    return extracted


async def acquire(
    study: StudyRef, *, dest: Path, client: httpx.AsyncClient | None = None
) -> AcquireResult:
    """Fetch supplementary materials via the reliability ladder. See SPEC 040."""
    if not study.pmcid:
        return AcquireResult(gap=True, note="no PMCID; not retrievable from open sources")

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True)
    try:
        files = await _europepmc_supplement(study.pmcid, Path(dest), client)
        if files:
            return AcquireResult(files=files, method="europepmc", gap=False)
        return AcquireResult(
            gap=True, note="no open supplement found (EuropePMC empty); see SPEC 040 ladder"
        )
    finally:
        if own_client:
            await client.aclose()


async def acquire_files(
    study: StudyRef, *, dest: Path, client: httpx.AsyncClient | None = None
) -> list[Path]:
    """Convenience wrapper returning just the file paths (pipeline acquire_fn). SPEC 040."""
    result = await acquire(study, dest=dest, client=client)
    return result.files
