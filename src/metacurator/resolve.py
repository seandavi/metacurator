"""resolve — identifiers & open-access triage. Implement to SPEC 020. [deterministic]"""

from __future__ import annotations

from .models import StudyRef


def resolve(pmid: str | None = None, *, doi: str | None = None) -> StudyRef:
    """PMID/DOI → StudyRef (PMCID, DOI, OA status, bioproject). See SPEC 020."""
    raise NotImplementedError("SPEC 020 — implement PMID→PMCID/DOI + OA triage")
