"""CLI tests (SPEC 120) — offline; the same functions back the Python API."""

from __future__ import annotations

import json

from typer.testing import CliRunner

import metacurator
from metacurator.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == metacurator.__version__


def test_dictionary_json():
    result = runner.invoke(app, ["dictionary", "--json"])
    assert result.exit_code == 0
    fields = json.loads(result.stdout)
    assert "sample_id" in fields
    assert fields["age"]["range"] == "float"
    assert fields["disease"]["binding"] == "NCIT:C2991"


def test_dictionary_human():
    result = runner.invoke(app, ["dictionary"])
    assert result.exit_code == 0
    assert "identifier=sample_id" in result.stdout


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_diff_cli_matches_python_api(tmp_path):
    cand = _write(tmp_path, "cand.csv", "sample_id,sex\ns1,Male\ns2,Female\n")
    ref = _write(tmp_path, "ref.csv", "sample_id,sex\ns1,Male\ns2,Male\n")

    result = runner.invoke(
        app, ["diff", str(cand), str(ref), "--key", "sample_id", "--json"]
    )
    assert result.exit_code == 0
    cli_results = json.loads(result.stdout)

    # Same computation via the Python API -> equivalent objects (SPEC 120 invariant).
    from metacurator.tables import load_tables

    api_results = [
        r.model_dump(mode="json")
        for r in metacurator.diff(
            load_tables(cand)[0].frame.records,
            load_tables(ref)[0].frame.records,
            key="sample_id",
        )
    ]
    assert cli_results == api_results
    sex = next(r for r in cli_results if r["column"] == "sex")
    assert sex["verdict"] == "FAIL"  # s2 Female vs Male


def test_diff_cli_human_output(tmp_path):
    cand = _write(tmp_path, "cand.csv", "sample_id,sex\ns1,Male\n")
    ref = _write(tmp_path, "ref.csv", "sample_id,sex\ns1,Male\n")
    result = runner.invoke(app, ["diff", str(cand), str(ref), "--key", "sample_id"])
    assert result.exit_code == 0
    assert "sex: PASS" in result.stdout


def test_lazy_public_api():
    # PEP 562 lazy access: names resolve to the real callables.
    from metacurator.diff import diff as diff_impl

    assert metacurator.diff is diff_impl
    assert "ground" in dir(metacurator)
