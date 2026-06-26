"""tables — load supplements (xlsx/docx/pdf/csv) → SourceTable. SPEC 050. [deterministic]"""

from __future__ import annotations

from pathlib import Path

from .models import SourceTable


def load_tables(path: Path) -> list[SourceTable]:
    """Load every table in a supplement file, with provenance. See SPEC 050."""
    raise NotImplementedError("SPEC 050 — implement xlsx/docx/pdf/csv table loading")
