"""pipeline — per-study orchestration & fan-out. Implement to SPEC 110. [deterministic]

Deterministic control flow that calls the pure tools and delegates only the three
judgment steps (SPEC 100) at fixed joints, with QC gating (SPEC 080) and resumability.
See docs/design/data-flow.md for the sequence.
"""

from __future__ import annotations

from .models import CurationReport


def curate_study(pmid: str, **kwargs) -> CurationReport:
    """Run one study end-to-end: resolve→…→report. See SPEC 110 / data-flow.md."""
    raise NotImplementedError("SPEC 110 — implement the per-study pipeline")


def curate_many(pmids: list[str], **kwargs) -> list[CurationReport]:
    """Fan-out across studies; per-study failures isolated. See SPEC 110."""
    raise NotImplementedError("SPEC 110 — implement fan-out orchestration")
