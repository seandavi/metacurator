"""dictionary — LinkML schema load & validation. Implement to SPEC 060. [deterministic]

Loads the active LinkML curation schema (default: cmd) via linkml-runtime; exposes
fields, enums (with ontology `meaning`s), and dynamic-enum (`reachable_from`) bindings;
validates ColumnMapping and CandidateRow (ontology-branch checks delegate to SPEC 070).
"""

from __future__ import annotations

from pathlib import Path

from .models import CandidateRow, ColumnMapping


class Schema:
    """Loaded curation schema. See SPEC 060."""

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("SPEC 060 — load LinkML schema via linkml-runtime")

    def fields(self) -> list[str]: ...
    def validate_mapping(self, mapping: ColumnMapping) -> list[str]: ...
    def validate_row(self, row: CandidateRow) -> list[str]: ...
