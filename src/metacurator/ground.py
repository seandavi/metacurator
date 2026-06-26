"""ground — map a value to a verified ontology term. Implement to SPEC 070. [deterministic]

Backend-agnostic: depends on a GroundingBackend (default LocalDuckDBBackend). Enforces the
no-hallucination four-step discipline — lookup → round-trip → branch check → obsolete
check — and returns a GroundedTerm. A CURIE is only ever produced here, by lookup (ADR-0004).
"""

from __future__ import annotations

from .grounding.base import GroundingBackend
from .models import GroundedTerm


def ground(
    value: str,
    ontology: str,
    *,
    backend: GroundingBackend,
    branch_root: str | None = None,
) -> list[GroundedTerm]:
    """Lookup → round-trip → branch → obsolete; return tiered candidates. See SPEC 070."""
    raise NotImplementedError("SPEC 070 — implement the four-step grounding discipline")
