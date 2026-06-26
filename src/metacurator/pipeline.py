"""pipeline — per-study orchestration & fan-out. Implement to SPEC 110. [deterministic]

Deterministic control flow that calls the pure tools and delegates only the three
judgment steps (SPEC 100) at fixed joints, with QC gating (SPEC 080). External stages
(acquire / resolve / archive) and the LLM + grounding backend are injected, so the
orchestration is fully testable offline. See docs/design/data-flow.md for the sequence.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import judge as judge_mod
from .dictionary import Dictionary
from .diff import diff as diff_tables
from .ground import ground
from .grounding.base import GroundingBackend
from .judge import LLMClient
from .models import (
    CandidateRow,
    ColumnMapping,
    ConfidenceTier,
    CurationReport,
    SourceTable,
    StudyRef,
    Verdict,
)
from .report import build_report
from .tables import load_tables


def _as_study(study: StudyRef | str) -> StudyRef:
    return study if isinstance(study, StudyRef) else StudyRef(pmid=study)


def _source_label(table: SourceTable) -> str:
    p = table.provenance
    if p.sheet:
        return f"{p.file}#{p.sheet}"
    if p.table_index is not None:
        return f"{p.file}#table{p.table_index}"
    return p.file


def apply_mapping(table: SourceTable, mapping: ColumnMapping) -> list[dict[str, Any]]:
    """Project source rows to target fields per the mapping (no values invented)."""
    rows: list[dict[str, Any]] = []
    for record in getattr(table.frame, "records", []):
        projected: dict[str, Any] = {}
        for item in mapping.items:
            if item.source_col in record:
                projected[item.target_field] = record[item.source_col]
        rows.append(projected)
    return rows


def ground_rows(
    rows: list[dict[str, Any]],
    dictionary: Dictionary,
    *,
    backend: GroundingBackend,
    llm: LLMClient | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Ground dynamic-enum values; disambiguate only when not a single auto. SPEC 110."""
    grounded: dict[str, str] = {}
    notes: list[str] = []
    bindings = dictionary.bindings()
    for i, row in enumerate(rows):
        for field, binding in bindings.items():
            value = row.get(field)
            if value in (None, ""):
                continue
            if value in dictionary.field(field).permissible_values:
                continue  # explicit permissible value (e.g. Healthy)
            terms = ground(
                str(value), binding.ontology, backend=backend, branch_root=binding.branch_root
            )
            # Count *distinct* auto CURIEs: a value can hit one term via both its label and
            # an exact synonym (common in NCIT), yielding two auto rows for one CURIE.
            auto_curies = {t.curie for t in terms if t.confidence_tier == ConfidenceTier.auto}
            if len(auto_curies) == 1:
                grounded[f"{i}.{field}"] = next(iter(auto_curies))  # single auto: no judgment
                continue
            reviews = [t for t in terms if t.confidence_tier == ConfidenceTier.review]
            if llm is not None and reviews:
                choice = judge_mod.disambiguate(str(value), reviews, llm=llm)
                if choice.curie:
                    grounded[f"{i}.{field}"] = choice.curie
                else:
                    notes.append(f"row{i}.{field}={value!r}: no grounding chosen")
            else:
                notes.append(
                    f"row{i}.{field}={value!r}: needs review ({len(reviews)} candidate(s))"
                )
    return grounded, notes


def curate_study(
    study: StudyRef | str,
    *,
    dictionary: Dictionary,
    llm: LLMClient,
    backend: GroundingBackend | None = None,
    tables: list[SourceTable] | None = None,
    reference: list[dict[str, Any]] | None = None,
    acquire_fn: Callable[[StudyRef], list[Any]] | None = None,
    load_tables_fn: Callable[..., list[SourceTable]] = load_tables,
    key: str | None = None,
) -> CurationReport:
    """Run one study: (acquire→)tables→classify→map→apply→ground→diff→report. SPEC 110."""
    study = _as_study(study)

    if tables is None:
        if acquire_fn is None:
            raise ValueError("provide tables=... or an acquire_fn to fetch supplements")
        tables = []
        for path in acquire_fn(study):
            tables.extend(load_tables_fn(path))
    if not tables:
        raise ValueError("no tables to curate")

    sources = [_source_label(t) for t in tables]

    choice = judge_mod.classify_tables(tables, dictionary, llm=llm)
    chosen = tables[choice.table_index]
    mapping = judge_mod.propose_mapping(chosen, dictionary, llm=llm)
    rows = apply_mapping(chosen, mapping)

    val_errors: list[str] = []
    for i, row in enumerate(rows):
        errs = dictionary.validate_row(CandidateRow(key=str(i), values=row), backend=backend)
        val_errors += [f"row{i}: {e}" for e in errs]

    grounded: dict[str, str] = {}
    ground_notes: list[str] = []
    if backend is not None:
        grounded, ground_notes = ground_rows(rows, dictionary, backend=backend, llm=llm)

    join_key = key or dictionary.identifier or "sample_id"
    diffs = diff_tables(rows, reference, key=join_key) if reference is not None else []

    needs_review = (
        choice.needs_review
        or mapping.needs_review
        or bool(val_errors)
        or any(d.verdict == Verdict.FAIL for d in diffs)
    )
    provenance = {
        "classify": {"table_index": choice.table_index, "confidence": choice.confidence},
        "chosen_source": _source_label(chosen),
        "mapping_fields": [i.target_field for i in mapping.items],
        "grounded": grounded,
        "n_candidate_rows": len(rows),
        "needs_review": needs_review,
    }
    note_parts: list[str] = []
    if val_errors:
        note_parts.append("Validation issues: " + "; ".join(val_errors[:10]))
    if ground_notes:
        note_parts.append("Grounding review: " + "; ".join(ground_notes[:10]))
    notes = "\n\n".join(note_parts) or None

    return build_report(
        study, sources=sources, diffs=diffs, notes=notes, provenance=provenance
    )


def curate_many(
    studies: list[StudyRef | str],
    *,
    dictionary: Dictionary,
    llm: LLMClient,
    backend: GroundingBackend | None = None,
    acquire_fn: Callable[[StudyRef], list[Any]] | None = None,
    reference_fn: Callable[[StudyRef], list[dict[str, Any]] | None] | None = None,
    **kwargs: Any,
) -> list[CurationReport]:
    """Fan-out across studies; per-study failures are isolated, not fatal. SPEC 110."""
    reports: list[CurationReport] = []
    for raw in studies:
        study = _as_study(raw)
        try:
            reference = reference_fn(study) if reference_fn else None
            reports.append(
                curate_study(
                    study,
                    dictionary=dictionary,
                    llm=llm,
                    backend=backend,
                    reference=reference,
                    acquire_fn=acquire_fn,
                    **kwargs,
                )
            )
        except Exception as exc:  # isolate per-study failure (SPEC 110)
            reports.append(
                build_report(
                    study,
                    sources=[],
                    diffs=[],
                    notes=f"FAILED: {type(exc).__name__}: {exc}",
                    provenance={"failed": True, "needs_review": True},
                )
            )
    return reports
