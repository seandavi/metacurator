"""pipeline + report tests (SPEC 110 / 090) — end-to-end offline, LLM mocked.

Runs against the synthetic test schema (the ``tdict`` fixture), so it doesn't depend on the
shipped cmd schema's field names or bindings.
"""

from __future__ import annotations

from typing import Any

from metacurator.models import SourceProvenance, SourceTable, StudyRef, Verdict
from metacurator.pipeline import curate_many, curate_study
from metacurator.report import column_status, render_markdown, to_sidecar
from metacurator.tables import Frame


class ScriptedLLM:
    """Routes each judge call to a canned response by the system prompt's intent."""

    def __init__(self, *, table_index=0, mapping_items=None, disambiguate=None) -> None:
        self.table_index = table_index
        self.mapping_items = mapping_items or []
        self.disambiguate = disambiguate
        self.disambiguate_calls = 0

    def complete(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if "select which loaded supplement table" in system:
            return {"table_index": self.table_index, "confidence": 0.95}
        if "map source table columns" in system:
            return {"items": self.mapping_items}
        if "choose the single best ontology term" in system:
            self.disambiguate_calls += 1
            return {"curie": self.disambiguate}
        raise AssertionError(f"unexpected judge call: {system[:40]}")


def _table(columns, records, **prov) -> SourceTable:
    return SourceTable(
        frame=Frame(columns=columns, records=records),
        provenance=SourceProvenance(file="supp.xlsx", **prov),
        n_rows=len(records),
        n_cols=len(columns),
    )


STUDY = StudyRef(pmid="1", title="Synthetic study")

MAPPING = [
    {"source_col": "ID", "target_field": "record_id", "confidence": 0.99},
    {"source_col": "Grp", "target_field": "group", "confidence": 0.99},
    {"source_col": "Status", "target_field": "status", "confidence": 0.9},
    {"source_col": "Site", "target_field": "site", "confidence": 0.9},
    {"source_col": "Cond", "target_field": "condition", "confidence": 0.9},
]


def _source_table():
    return _table(
        ["ID", "Grp", "Status", "Site", "Cond"],
        [
            {"ID": "r1", "Grp": "g1", "Status": "Case",
             "Site": "feces", "Cond": "Colorectal Carcinoma"},
            {"ID": "r2", "Grp": "g2", "Status": "Control",
             "Site": "feces", "Cond": "Healthy"},
        ],
        sheet="samples",
    )


def test_curate_study_clean_pass(tdict, backend):
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    reference = [
        {"record_id": "r1", "status": "Case", "site": "feces"},
        {"record_id": "r2", "status": "Control", "site": "feces"},
    ]
    report = curate_study(
        STUDY, dictionary=tdict, llm=llm, backend=backend,
        tables=[_source_table()], reference=reference, key="record_id",
    )
    assert report.provenance["overall_verdict"] == Verdict.PASS.value
    assert report.provenance["needs_review"] is False
    status = next(d for d in report.diffs if d.column == "status")
    assert status.match == 2 and status.verdict == Verdict.PASS
    assert report.provenance["chosen_source"] == "supp.xlsx#samples"
    # condition grounded against NCIT (Colorectal Carcinoma -> C2955; Healthy is permissible).
    assert report.provenance["grounded"].get("0.condition") == "NCIT:C2955"


def test_curate_study_conflict_is_fail(tdict, backend):
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    reference = [
        {"record_id": "r1", "status": "Control"},  # conflicts with candidate Case
        {"record_id": "r2", "status": "Control"},
    ]
    report = curate_study(
        STUDY, dictionary=tdict, llm=llm, backend=backend,
        tables=[_source_table()], reference=reference, key="record_id",
    )
    assert report.provenance["overall_verdict"] == Verdict.FAIL.value
    assert report.provenance["needs_review"] is True
    md = render_markdown(report)
    assert "CONFLICT" in md and "**FAIL**" in md


def test_disambiguate_not_called_for_single_auto(tdict, backend):
    """'Colorectal Carcinoma' is a single auto NCIT term -> no judgment call (SPEC 110)."""
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    report = curate_study(
        STUDY, dictionary=tdict, llm=llm, backend=backend, tables=[_source_table()]
    )
    assert report.provenance["grounded"].get("0.condition") == "NCIT:C2955"
    assert llm.disambiguate_calls == 0


def test_curate_many_isolates_failure(tdict, backend):
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    good = _source_table()

    def acquire(study):
        if study.pmid == "boom":
            raise RuntimeError("acquire exploded")
        return ["ignored"]

    reports = curate_many(
        [StudyRef(pmid="ok"), StudyRef(pmid="boom")],
        dictionary=tdict, llm=llm, backend=backend,
        acquire_fn=acquire, load_tables_fn=lambda _p: [good], key="record_id",
    )
    assert len(reports) == 2
    ok, boom = reports
    assert ok.provenance.get("failed") is None
    assert boom.provenance["failed"] is True
    assert "acquire exploded" in boom.notes


def test_report_sidecar_roundtrip(tdict, backend):
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    report = curate_study(
        STUDY, dictionary=tdict, llm=llm, backend=backend, tables=[_source_table()]
    )
    side = to_sidecar(report)
    assert side["study"]["pmid"] == "1"
    assert side["provenance"]["overall_verdict"] in {"PASS", "PARTIAL", "FAIL"}


def test_column_status_mapping():
    from metacurator.models import DiffResult

    reproduced = DiffResult(column="x", compared=2, match=2, verdict=Verdict.PASS)
    conflict = DiffResult(column="x", mismatch=1, verdict=Verdict.FAIL)
    partial = DiffResult(column="x", blank=1, verdict=Verdict.PARTIAL)
    not_found = DiffResult(column="x", verdict=Verdict.PASS)
    assert column_status(reproduced) == "REPRODUCED"
    assert column_status(conflict) == "CONFLICT"
    assert column_status(partial) == "PARTIAL"
    assert column_status(not_found) == "NOT-FOUND"
