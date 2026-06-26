"""acquire — supplement retrieval ladder. Implement to SPEC 040. [deterministic]"""

from __future__ import annotations

from pathlib import Path

from .models import StudyRef


def acquire(study: StudyRef, *, dest: Path) -> list[Path]:
    """Fetch supplementary materials via the reliability ladder. See SPEC 040."""
    raise NotImplementedError("SPEC 040 — implement PMC→EuropePMC→Springer→browser ladder")
