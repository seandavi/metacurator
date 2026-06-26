"""archive — ENA/BioSample accessions & ID map. Implement to SPEC 030. [deterministic]

Authoritative for accessions (ADR-0004): no other stage may invent these.
"""

from __future__ import annotations

from .models import AccessionMap, StudyRef


def build_accession_map(study: StudyRef) -> AccessionMap:
    """ENA two-step (derive project → bulk filereport) → AccessionMap. See SPEC 030."""
    raise NotImplementedError("SPEC 030 — implement ENA bulk filereport accession+ID map")
