"""report — CurationReport + provenance. Implement to SPEC 090. [deterministic]"""

from __future__ import annotations

from .models import CurationReport


def render_markdown(report: CurationReport) -> str:
    """Render a CurationReport as markdown (machine-readable sidecar alongside). SPEC 090."""
    raise NotImplementedError("SPEC 090 — render report + provenance (markdown + json)")
