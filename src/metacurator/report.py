"""report — CurationReport + provenance. Implement to SPEC 090. [deterministic]

Templating only — no LLM. Assembles the typed CurationReport, computes the overall
verdict, and renders a human-facing markdown plus a machine-readable JSON sidecar.
"""

from __future__ import annotations

from typing import Any

from .models import CurationReport, DiffResult, StudyRef, Verdict

# Per-column report status (distinct from the raw diff verdict).
REPRODUCED = "REPRODUCED"
CONFLICT = "CONFLICT"  # a real value disagreement = curation error
PARTIAL = "PARTIAL"  # coverage gaps, no conflict = curation gap (not an error)
NOT_FOUND = "NOT-FOUND"


def column_status(diff: DiffResult) -> str:
    """Map a DiffResult to a report status (SPEC 090)."""
    if diff.column == "__rows__":
        return PARTIAL if diff.verdict == Verdict.PARTIAL else REPRODUCED
    if diff.verdict == Verdict.FAIL:
        return CONFLICT
    if diff.verdict == Verdict.PARTIAL:
        return PARTIAL
    if diff.compared > 0:
        return REPRODUCED
    return NOT_FOUND


def overall_verdict(diffs: list[DiffResult]) -> Verdict:
    real = [d for d in diffs if d.column != "__rows__"]
    if any(d.verdict == Verdict.FAIL for d in real):
        return Verdict.FAIL
    if any(d.verdict == Verdict.PARTIAL for d in real):
        return Verdict.PARTIAL
    return Verdict.PASS


def build_report(
    study: StudyRef,
    *,
    sources: list[str],
    diffs: list[DiffResult],
    notes: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> CurationReport:
    """Assemble the typed CurationReport and record the overall verdict (SPEC 090)."""
    prov = dict(provenance or {})
    prov["overall_verdict"] = overall_verdict(diffs).value
    return CurationReport(
        study=study, sources=sources, diffs=diffs, notes=notes, provenance=prov
    )


def to_sidecar(report: CurationReport) -> dict[str, Any]:
    """The machine-readable JSON of the report content (SPEC 090)."""
    return report.model_dump(mode="json")


def render_markdown(report: CurationReport) -> str:
    """Render a CurationReport as markdown (JSON sidecar alongside). SPEC 090."""
    s = report.study
    ident = s.title or s.pmid
    verdict = report.provenance.get("overall_verdict", overall_verdict(report.diffs).value)

    lines: list[str] = [
        f"# Curation report — {ident}",
        "",
        f"- PMID: {s.pmid}",
    ]
    if s.pmcid:
        lines.append(f"- PMCID: {s.pmcid}")
    if s.bioproject:
        lines.append(f"- BioProject: {s.bioproject}")
    lines += [f"- Overall verdict: **{verdict}**", ""]

    lines += ["## Sources", ""]
    lines += [f"- {src}" for src in report.sources] or ["- (none recorded)"]
    lines.append("")

    real = [d for d in report.diffs if d.column != "__rows__"]
    if real:
        lines += [
            "## Per-column verdicts",
            "",
            "| column | status | compared | match | mismatch | blank | cand_adds |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for d in real:
            lines.append(
                f"| {d.column} | {column_status(d)} | {d.compared} | {d.match} "
                f"| {d.mismatch} | {d.blank} | {d.cand_adds} |"
            )
        lines.append("")

        conflicts = [d for d in real if d.verdict == Verdict.FAIL]
        if conflicts:
            lines += ["## Conflicts (curation errors)", ""]
            for d in conflicts:
                for ex in d.examples:
                    lines.append(
                        f"- `{d.column}` @ {ex.get('key')}: "
                        f"candidate={ex.get('candidate')!r} vs reference={ex.get('reference')!r}"
                    )
            lines.append("")

    if report.notes:
        lines += ["## Notes", "", report.notes, ""]

    return "\n".join(lines)
