"""target tests (SPEC 160) — manifest resolution and discovery-config validation.

Uses throwaway target directories under tmp_path; the shipped cmd target is asserted only in
test_cmd_target.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from metacurator.dictionary import Dictionary
from metacurator.target import load_target

TEST_SCHEMA = Path(__file__).parent / "fixtures" / "test_schema.yaml"


def _discovery(**over):
    d = {
        "decision_model": "cloudflare:clef",
        "prefilter": {
            "library_source": ["METAGENOMIC"],
            "library_strategy": ["WGS"],
            "organisms": ["human gut metagenome"],
        },
        "questions": {
            "host": {
                "type": "choice",
                "instructions": "Host?",
                "criteria": {"human": "h", "mouse": "m", "soil": "s"},
            },
            "shotgun": {"type": "noul", "instructions": "Shotgun?"},
            "depth": {"type": "score", "instructions": "Depth?", "criteria": ["lo", "hi"]},
        },
        "rules": [
            {"question": "host", "accept": ["human"], "include_at": 0.8, "review_at": 0.5},
            {"question": "shotgun", "include_at": 0.8, "review_at": 0.5},
        ],
        "facets": ["host"],
    }
    d.update(over)
    return d


def _make(tmp_path: Path, name: str = "demo", **manifest) -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / "schema.yaml").write_text(TEST_SCHEMA.read_text())
    data = {"name": name, "title": "Demo", "schema": "schema.yaml", **manifest}
    (root / "target.yaml").write_text(yaml.safe_dump(data))
    return root


def test_load_by_directory_and_name(tmp_path, monkeypatch):
    root = _make(tmp_path, discovery=_discovery())
    by_dir = load_target(root)
    assert by_dir.name == "demo"
    assert by_dir.schema_path == (root / "schema.yaml").resolve()
    assert by_dir.discovery is not None and len(by_dir.discovery.rules) == 2
    monkeypatch.setenv("METACURATOR_TARGETS", str(tmp_path))
    assert load_target("demo").schema_path == by_dir.schema_path
    # the target's schema is a loadable dictionary schema
    assert Dictionary(by_dir.schema_path, class_name="TestRecord").identifier == "record_id"


def test_unknown_target_names_searched_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("METACURATOR_TARGETS", str(tmp_path))
    searched = re.escape(str(tmp_path))
    with pytest.raises(FileNotFoundError, match=rf"unknown target 'nope'.*{searched}"):
        load_target("nope")


def test_missing_schema_file(tmp_path):
    root = _make(tmp_path)
    (root / "schema.yaml").unlink()
    with pytest.raises(FileNotFoundError, match="schema not found"):
        load_target(root)


def test_unknown_manifest_key_rejected(tmp_path):
    with pytest.raises(ValidationError, match="colour"):
        load_target(_make(tmp_path, colour="red"))


def _rule(question: str, accept: list[str] | None = None, inc: float = 0.8, rev: float = 0.5):
    return {"rules": [{"question": question, "accept": accept or [], "include_at": inc,
                       "review_at": rev}]}


def _only(qid: str, qtype: str):
    return {"questions": {qid: {"type": qtype, "instructions": "x"}}, "rules": [], "facets": []}


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (_rule("nope"), "no such"),
        (_rule("host"), "needs accept"),
        (_rule("host", ["cat"]), "not in criteria"),
        (_rule("shotgun", ["x"]), "no accept"),
        (_rule("depth"), "score"),
        (_rule("shotgun", inc=0.4), "review_at"),
        (_rule("shotgun", inc=1.2), "include_at"),
        ({"facets": ["shotgun"]}, "not a choice"),
        (_only("bad id!", "noul"), "must match"),
        (_only("q", "essay"), "type"),
        (
            {"questions": {f"q{i}": {"type": "noul", "instructions": "x"} for i in range(65)},
             "rules": [], "facets": []},
            "> 64",
        ),
    ],
)
def test_discovery_validation(tmp_path, override, message):
    with pytest.raises(ValidationError, match=message):
        load_target(_make(tmp_path, discovery=_discovery(**override)))


def test_dictionary_without_schema_errors(monkeypatch):
    monkeypatch.delenv("METACURATOR_SCHEMA", raising=False)
    with pytest.raises(FileNotFoundError, match="no schema given"):
        Dictionary()
