"""discover tests (SPEC 190) — tiny SRA parquet fixtures, a fake decision client, no network."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import duckdb
import pytest
import yaml
from typer.testing import CliRunner

from metacurator import discover as disc_mod
from metacurator.cli import app
from metacurator.decision import DecisionError
from metacurator.discover import (
    build_states,
    open_sra,
    run_discovery,
    score_rules,
    select_studies,
)
from metacurator.readset import readset_id
from metacurator.target import Rule, load_target

TEST_SCHEMA = Path(__file__).parent / "fixtures" / "test_schema.yaml"

QUESTIONS = {
    "host": {
        "type": "choice",
        "instructions": "Host?",
        "criteria": {"human": "h", "mouse": "m", "environment": "e"},
    },
    "shotgun": {"type": "noul", "instructions": "Shotgun?"},
}
DISCOVERY = {
    "decision_model": "cloudflare:clef",
    "prefilter": {
        "library_source": ["METAGENOMIC"],
        "library_strategy": ["WGS"],
        "organisms": ["human gut metagenome", "mouse gut metagenome"],
    },
    "questions": QUESTIONS,
    "rules": [
        {"question": "host", "accept": ["human", "mouse"], "include_at": 0.8, "review_at": 0.5},
        {"question": "shotgun", "include_at": 0.8, "review_at": 0.5},
    ],
    "facets": ["host"],
}

STUDIES = [
    ("STUDY_H", "Human gut shotgun", "PRJ_H", "Stool from people."),
    ("STUDY_M", "Mouse gut shotgun", "PRJ_M", None),
    ("STUDY_S", "Soil shotgun", "PRJ_S", None),
]
# (experiment, study, sample, strategy); EXP_H1 is duplicated as in the real export.
EXPERIMENTS = [
    ("EXP_H1", "STUDY_H", "SAMP_H1", "WGS"),
    ("EXP_H1", "STUDY_H", "SAMP_H1", "WGS"),
    ("EXP_H2", "STUDY_H", "SAMP_H2", "WGS"),
    ("EXP_H3", "STUDY_H", "SAMP_H3", "AMPLICON"),
    ("EXP_M1", "STUDY_M", "SAMP_M1", "WGS"),
    ("EXP_S1", "STUDY_S", "SAMP_S1", "WGS"),
]
HUMAN_ATTRS = [("host", "Homo sapiens"), ("env", "stool"), ("INSDC center name", "X"),
               ("submitter id", "s1"), ("Sample Name", "n1")]
SAMPLES = [
    ("SAMP_H1", "human gut metagenome", "SAMN_H1", HUMAN_ATTRS),
    ("SAMP_H2", "human gut metagenome", "SAMN_H2", HUMAN_ATTRS),
    ("SAMP_H3", "human gut metagenome", "SAMN_H3", HUMAN_ATTRS),
    ("SAMP_M1", "mouse gut metagenome", "SAMN_M1", [("host", "Mus musculus")]),
    ("SAMP_S1", "soil metagenome", "SAMN_S1", [("env", "soil")]),
]
RUNS = [
    ("SRR1", "EXP_H1"), ("SRR2", "EXP_H1"), ("SRR3", "EXP_H2"), ("SRR4", "EXP_H2"),
    ("XRR9", "EXP_H2"),  # not an INSDC run accession: skipped
    ("SRR5", "EXP_H3"), ("SRR6", "EXP_M1"), ("SRR7", "EXP_S1"),
]


@pytest.fixture
def sra(tmp_path) -> Path:
    base = tmp_path / "sra"
    base.mkdir()
    con = duckdb.connect()
    con.execute("CREATE TABLE s(accession VARCHAR, title VARCHAR, bioproject VARCHAR, "
                "abstract VARCHAR)")
    con.executemany("INSERT INTO s VALUES (?, ?, ?, ?)", STUDIES)
    con.execute("CREATE TABLE e(accession VARCHAR, study_accession VARCHAR, "
                "sample_accession VARCHAR, platform VARCHAR, library_strategy VARCHAR, "
                "library_source VARCHAR)")
    con.executemany("INSERT INTO e VALUES (?, ?, ?, 'ILLUMINA', ?, 'METAGENOMIC')", EXPERIMENTS)
    con.execute("CREATE TABLE sa(accession VARCHAR, organism VARCHAR, biosample VARCHAR, "
                "attributes STRUCT(tag VARCHAR, value VARCHAR)[])")
    for acc, org, bs, attrs in SAMPLES:
        con.execute(
            "INSERT INTO sa VALUES (?, ?, ?, ?::STRUCT(tag VARCHAR, value VARCHAR)[])",
            [acc, org, bs, [{"tag": t, "value": v} for t, v in attrs]],
        )
    con.execute("CREATE TABLE r(accession VARCHAR, experiment_accession VARCHAR)")
    con.executemany("INSERT INTO r VALUES (?, ?)", RUNS)
    for table, name in (("s", "sra_studies"), ("e", "sra_experiments"),
                        ("sa", "sra_samples"), ("r", "sra_runs")):
        con.execute(f"COPY {table} TO '{base / name}.parquet' (FORMAT parquet)")
    return base


@pytest.fixture
def target_dir(tmp_path) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    (root / "schema.yaml").write_text(TEST_SCHEMA.read_text())
    (root / "target.yaml").write_text(
        yaml.safe_dump({"name": "demo", "title": "Demo", "schema": "schema.yaml",
                        "discovery": DISCOVERY})
    )
    return root


class FakeClient:
    """Answers from the state title; optionally fails one study; counts calls."""

    def __init__(self, fail: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail
        self._lock = threading.Lock()

    def decide(self, *, state, questions):
        with self._lock:
            self.calls.append(state["study_accession"])
        if state["study_accession"] == self.fail:
            raise DecisionError("boom")
        title = state["title"].lower()
        host = "human" if "human" in title else "mouse" if "mouse" in title else "environment"
        probs = {k: (0.9 if k == host else 0.05) for k in ("human", "mouse", "environment")}
        return {
            "host": {"type": "choice", "choice": host, "probabilities": probs,
                     "confidence": 0.9},
            "shotgun": {"type": "noul", "noul": 0.95},
        }

    def describe(self):
        return {"provider": "fake", "model": "fake-1", "endpoint": "test", "params": {}}


def _rows(path: Path) -> list[dict]:
    rel = duckdb.sql(f"SELECT * FROM '{path}'")
    return [dict(zip(rel.columns, row, strict=True)) for row in rel.fetchall()]


def test_select_studies(sra, target_dir):
    pf = load_target(target_dir).discovery.prefilter
    con = open_sra(str(sra))
    assert select_studies(con, pf) == ["STUDY_H", "STUDY_M"]
    assert select_studies(con, pf, limit=1) == ["STUDY_H"]
    assert select_studies(con, pf, studies=["STUDY_S", "STUDY_S"]) == ["STUDY_S"]


def test_build_states_shape_and_attribute_filter(sra, target_dir):
    pf = load_target(target_dir).discovery.prefilter
    states = build_states(open_sra(str(sra)), pf, ["STUDY_H", "STUDY_M", "STUDY_S"])
    assert sorted(states) == ["STUDY_H", "STUDY_M"]  # soil fails the organism allow-list
    h = states["STUDY_H"]
    assert set(h) == {
        "study_accession", "bioproject", "title", "abstract", "n_experiments", "organisms",
        "library_strategies", "platforms", "sample_attributes",
    }
    assert h["n_experiments"] == 2  # AMPLICON dropped, duplicate experiment collapsed
    assert h["organisms"] == {"human gut metagenome": 2}
    assert h["library_strategies"] == {"WGS": 2}
    assert h["platforms"] == {"ILLUMINA": 2}
    # admin tags (INSDC…, submitter…, Sample Name) dropped; ranked by count then tag
    assert h["sample_attributes"] == ["env: stool (2)", "host: Homo sapiens (2)"]
    assert h["bioproject"] == "PRJ_H" and h["abstract"] == "Stool from people."


def test_score_rules_boundaries():
    rules = [Rule(question="host", accept=["human", "mouse"], include_at=0.8, review_at=0.5),
             Rule(question="shotgun", include_at=0.8, review_at=0.5)]

    def answers(human: float, shotgun: float):
        return {
            "host": {"type": "choice", "choice": "human",
                     "probabilities": {"human": human, "mouse": 0.0, "environment": 1 - human}},
            "shotgun": {"type": "noul", "noul": shotgun},
        }

    assert score_rules(answers(0.8, 0.8), rules, QUESTIONS) == (
        "include", {"host": 0.8, "shotgun": 0.8}
    )
    assert score_rules(answers(0.79, 0.9), rules, QUESTIONS)[0] == "review"
    assert score_rules(answers(0.5, 0.9), rules, QUESTIONS)[0] == "review"
    assert score_rules(answers(0.4999, 0.9), rules, QUESTIONS)[0] == "exclude"
    # exclude wins over review regardless of rule order
    assert score_rules(answers(0.6, 0.1), rules, QUESTIONS)[0] == "exclude"


def test_run_discovery_outputs_and_cache(sra, target_dir, tmp_path):
    target = load_target(target_dir)
    out = tmp_path / "out"
    client = FakeClient()
    counts = run_discovery(target, out=out, base=str(sra), client=client)
    assert sorted(client.calls) == ["STUDY_H", "STUDY_M"]
    assert counts["include"] == 2 and counts["error"] == 0
    assert counts["skipped_runs"] == 1

    studies = {r["study_accession"]: r for r in _rows(out / "studies.parquet")}
    assert studies["STUDY_H"]["decision"] == "include"
    assert json.loads(studies["STUDY_M"]["facets"]) == {"host": "mouse"}
    assert studies["STUDY_H"]["model"] == "fake-1"

    readsets = _rows(out / "readsets.parquet")
    by_sample = {r["sra_sample"]: r for r in readsets}
    assert set(by_sample) == {"SAMP_H1", "SAMP_H2", "SAMP_M1"}
    assert by_sample["SAMP_H2"]["units"] == ["insdc.sra:SRR3", "insdc.sra:SRR4"]
    assert by_sample["SAMP_H1"]["biosample"] == "SAMN_H1"
    assert by_sample["SAMP_H1"]["bioproject"] == "PRJ_H"
    for r in readsets:
        assert r["readset_id"] == readset_id(r["units"])
        assert r["n_runs"] == len(r["units"])
    assert "include | 2" in (out / "summary.md").read_text()

    again = FakeClient()
    counts2 = run_discovery(target, out=out, base=str(sra), client=again)
    assert again.calls == []
    assert counts2["calls"] == 0 and counts2["cached"] == 2


def test_dry_run_writes_states_without_calls(sra, target_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(disc_mod, "make_decision_client",
                        lambda spec: pytest.fail("dry run must not build a client"))
    out = tmp_path / "dry"
    counts = run_discovery(load_target(target_dir), out=out, base=str(sra), dry_run=True)
    assert counts == {"selected": 2, "states": 2, "omitted": 0}
    rows = _rows(out / "states.parquet")
    assert [r["study_accession"] for r in rows] == ["STUDY_H", "STUDY_M"]
    assert json.loads(rows[0]["state_json"])["n_experiments"] == 2
    assert not (out / "studies.parquet").exists()


def _cli(monkeypatch, client, *args):
    monkeypatch.setattr(disc_mod, "make_decision_client", lambda spec: client)
    return CliRunner().invoke(app, ["discover", *args])


def test_cli_study_bypasses_organism_filter(sra, target_dir, tmp_path, monkeypatch):
    client = FakeClient()
    out = tmp_path / "ctl"
    result = _cli(monkeypatch, client, "--target", str(target_dir), "--parquet-base", str(sra),
                  "--out", str(out), "--study", "STUDY_S")
    assert result.exit_code == 0, result.output
    assert client.calls == ["STUDY_S"]
    (row,) = _rows(out / "studies.parquet")
    assert row["decision"] == "exclude"
    assert json.loads(row["facets"]) == {"host": "environment"}
    assert _rows(out / "readsets.parquet") == []


def test_cli_error_row_exits_1(sra, target_dir, tmp_path, monkeypatch):
    out = tmp_path / "err"
    result = _cli(monkeypatch, FakeClient(fail="STUDY_M"), "--target", str(target_dir),
                  "--parquet-base", str(sra), "--out", str(out))
    assert result.exit_code == 1, result.output
    decisions = {r["study_accession"]: r for r in _rows(out / "studies.parquet")}
    assert decisions["STUDY_M"]["decision"] == "error"
    assert decisions["STUDY_M"]["error"] == "boom"
    assert decisions["STUDY_H"]["decision"] == "include"
    # errors are not cached: a rerun retries only the failed study
    retry = FakeClient()
    assert _cli(monkeypatch, retry, "--target", str(target_dir), "--parquet-base", str(sra),
                "--out", str(out)).exit_code == 0
    assert retry.calls == ["STUDY_M"]


def test_cli_target_without_discovery_exits_2(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "schema.yaml").write_text(TEST_SCHEMA.read_text())
    (root / "target.yaml").write_text("name: plain\ntitle: Plain\nschema: schema.yaml\n")
    result = CliRunner().invoke(app, ["discover", "--target", str(root)])
    assert result.exit_code == 2
