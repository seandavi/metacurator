"""pipeline + report tests (SPEC 110 / 090) — end-to-end offline, LLM mocked."""

from __future__ import annotations

from typing import Any

from metacurator.dictionary import Dictionary
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


STUDY = StudyRef(pmid="27171425", bioproject="PRJEB12449", title="Vogtmann 2016")

MAPPING = [
    {"source_col": "ID", "target_field": "sample_id", "confidence": 0.99},
    {"source_col": "Subject", "target_field": "subject_id", "confidence": 0.99},
    {"source_col": "Study", "target_field": "study_name", "confidence": 0.99},
    {"source_col": "Sex", "target_field": "sex", "confidence": 0.9},
    {"source_col": "Site", "target_field": "body_site", "confidence": 0.9},
]


def _source_table():
    return _table(
        ["ID", "Subject", "Study", "Sex", "Site"],
        [
            {"ID": "s1", "Subject": "p1", "Study": "VogtmannE_2016",
             "Sex": "Male", "Site": "feces"},
            {"ID": "s2", "Subject": "p2", "Study": "VogtmannE_2016",
             "Sex": "Female", "Site": "feces"},
        ],
        sheet="samples",
    )


def test_curate_study_clean_pass(backend):
    dictionary = Dictionary()
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    reference = [
        {"sample_id": "s1", "sex": "Male", "body_site": "feces"},
        {"sample_id": "s2", "sex": "Female", "body_site": "feces"},
    ]
    report = curate_study(
        STUDY, dictionary=dictionary, llm=llm, backend=backend,
        tables=[_source_table()], reference=reference,
    )
    assert report.provenance["overall_verdict"] == Verdict.PASS.value
    assert report.provenance["needs_review"] is False
    sex = next(d for d in report.diffs if d.column == "sex")
    assert sex.match == 2 and sex.verdict == Verdict.PASS
    assert report.provenance["chosen_source"] == "supp.xlsx#samples"


def test_curate_study_conflict_is_fail(backend):
    dictionary = Dictionary()
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    reference = [
        {"sample_id": "s1", "sex": "Female"},  # conflicts with candidate Male
        {"sample_id": "s2", "sex": "Female"},
    ]
    report = curate_study(
        STUDY, dictionary=dictionary, llm=llm, backend=backend,
        tables=[_source_table()], reference=reference,
    )
    assert report.provenance["overall_verdict"] == Verdict.FAIL.value
    assert report.provenance["needs_review"] is True
    md = render_markdown(report)
    assert "CONFLICT" in md and "**FAIL**" in md


def test_disambiguate_not_called_for_single_auto(backend):
    """Grounding 'feces' yields a single auto term -> no judgment call (SPEC 110)."""
    dictionary = Dictionary()
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    # body_site 'feces' grounds to a single auto UBERON term in the fixture store...
    # but body_site is a *static* enum here; use disease (dynamic) to exercise grounding.
    table = _table(
        ["ID", "Subject", "Study", "Disease"],
        [{"ID": "s1", "Subject": "p1", "Study": "X", "Disease": "Colorectal Carcinoma"}],
        sheet="s",
    )
    mapping = [
        {"source_col": "ID", "target_field": "sample_id", "confidence": 1.0},
        {"source_col": "Subject", "target_field": "subject_id", "confidence": 1.0},
        {"source_col": "Study", "target_field": "study_name", "confidence": 1.0},
        {"source_col": "Disease", "target_field": "disease", "confidence": 1.0},
    ]
    llm.mapping_items = mapping
    report = curate_study(STUDY, dictionary=dictionary, llm=llm, backend=backend, tables=[table])
    # 'Colorectal Carcinoma' is a single auto term under the disease branch -> grounded.
    assert report.provenance["grounded"].get("0.disease") == "NCIT:C2955"
    assert llm.disambiguate_calls == 0


def test_curate_many_isolates_failure(backend):
    dictionary = Dictionary()
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    good = _source_table()

    def acquire(study):
        if study.pmid == "boom":
            raise RuntimeError("acquire exploded")
        return ["ignored"]  # load_tables_fn replaced below

    reports = curate_many(
        [StudyRef(pmid="ok"), StudyRef(pmid="boom")],
        dictionary=dictionary, llm=llm, backend=backend,
        acquire_fn=acquire, load_tables_fn=lambda _p: [good],
    )
    assert len(reports) == 2
    ok, boom = reports
    assert ok.provenance.get("failed") is None
    assert boom.provenance["failed"] is True
    assert "acquire exploded" in boom.notes


def test_report_sidecar_roundtrip(backend):
    dictionary = Dictionary()
    llm = ScriptedLLM(table_index=0, mapping_items=MAPPING)
    report = curate_study(
        STUDY, dictionary=dictionary, llm=llm, backend=backend, tables=[_source_table()]
    )
    side = to_sidecar(report)
    assert side["study"]["pmid"] == "27171425"
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
