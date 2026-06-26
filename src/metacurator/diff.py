"""diff — candidate-vs-reference & self-consistency QC. Implement to SPEC 080. [deterministic]

Generalizes the harness proven on the cMD reproduction: per-column match/mismatch/blank/
cand_adds + verdict, with normalizations (casefold, numeric tolerance, set-equal
multi-value, curated-blank=enrichment) to avoid false positives.
"""

from __future__ import annotations

from typing import Any

from .models import DiffResult


def diff(
    candidate: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    *,
    key: str,
) -> list[DiffResult]:
    """Join on key; per-column DiffResult with verdicts. See SPEC 080."""
    raise NotImplementedError("SPEC 080 — implement the QC diff with normalizations")
