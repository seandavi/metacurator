"""target — curation target manifests. Implement to SPEC 160. [deterministic]

A curation target is a directory ``targets/<name>/`` holding everything specific to one
curated resource: ``target.yaml`` (the manifest), its LinkML schema, and optionally a
discovery configuration (SPEC 190). The toolkit itself names no target (ADR-0010).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

_QUESTION_TYPES = {"noul", "choice", "score"}
_QUESTION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_MAX_QUESTIONS = 64  # Clef's limit per request (SPEC 180)


class Rule(BaseModel):
    """One screening rule: a question's score must reach ``include_at`` to include."""

    model_config = ConfigDict(extra="forbid")

    question: str
    accept: list[str] = []
    include_at: float
    review_at: float


class Prefilter(BaseModel):
    """Exact SRA metadata values a study's experiments must match (SPEC 190)."""

    model_config = ConfigDict(extra="forbid")

    library_source: list[str]
    library_strategy: list[str]
    organisms: list[str]


class DiscoveryConfig(BaseModel):
    """A target's discovery block: prefilter, decision questions, rules, facets."""

    model_config = ConfigDict(extra="forbid")

    decision_model: str
    prefilter: Prefilter
    questions: dict[str, dict[str, Any]]
    rules: list[Rule]
    facets: list[str] = []

    @model_validator(mode="after")
    def _check(self) -> DiscoveryConfig:
        if len(self.questions) > _MAX_QUESTIONS:
            raise ValueError(f"questions: {len(self.questions)} > {_MAX_QUESTIONS} allowed")
        for qid, q in self.questions.items():
            if not _QUESTION_ID.match(qid):
                raise ValueError(f"questions: id {qid!r} must match {_QUESTION_ID.pattern}")
            if q.get("type") not in _QUESTION_TYPES:
                raise ValueError(
                    f"question {qid!r}: type {q.get('type')!r} not in {sorted(_QUESTION_TYPES)}"
                )
        for rule in self.rules:
            rq = self.questions.get(rule.question)
            if rq is None:
                raise ValueError(f"rule {rule.question!r}: no such question")
            qtype = rq["type"]
            if qtype == "choice":
                criteria = rq.get("criteria") or {}
                if not rule.accept:
                    raise ValueError(f"rule {rule.question!r}: choice rule needs accept options")
                bad = [o for o in rule.accept if o not in criteria]
                if bad:
                    raise ValueError(
                        f"rule {rule.question!r}: accept option(s) {bad} not in criteria"
                    )
            elif qtype == "noul":
                if rule.accept:
                    raise ValueError(f"rule {rule.question!r}: noul rule takes no accept list")
            else:
                raise ValueError(f"rule {rule.question!r}: rules on score questions unsupported")
            if not 0 <= rule.review_at <= rule.include_at <= 1:
                raise ValueError(
                    f"rule {rule.question!r}: need 0 <= review_at <= include_at <= 1, got "
                    f"review_at={rule.review_at} include_at={rule.include_at}"
                )
        for facet in self.facets:
            if self.questions.get(facet, {}).get("type") != "choice":
                raise ValueError(f"facets: {facet!r} is not a choice question")
        return self


class TargetManifest(BaseModel):
    """The parsed ``target.yaml``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    title: str
    schema_: str = Field(alias="schema")
    discovery: DiscoveryConfig | None = None


@dataclass(frozen=True)
class Target:
    """A loaded curation target (SPEC 160)."""

    name: str
    root: Path
    schema_path: Path
    discovery: DiscoveryConfig | None


def targets_dir() -> Path:
    """``$METACURATOR_TARGETS``, else the first ``targets/`` directory up-tree."""
    env = os.environ.get("METACURATOR_TARGETS")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "targets"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("no targets/ directory; set $METACURATOR_TARGETS")


def load_target(ref: str | Path) -> Target:
    """Load a target by name (``targets_dir()/<name>``) or by directory path."""
    as_path = Path(ref)
    if as_path.is_dir() and (as_path / "target.yaml").is_file():
        root = as_path
    else:
        base = targets_dir()
        root = base / str(ref)
        if not (root / "target.yaml").is_file():
            raise FileNotFoundError(f"unknown target {str(ref)!r}; looked in {base}")
    root = root.resolve()
    manifest = TargetManifest.model_validate(
        yaml.safe_load((root / "target.yaml").read_text(encoding="utf-8")) or {}
    )
    schema_path = root / manifest.schema_
    if not schema_path.is_file():
        raise FileNotFoundError(f"target {manifest.name!r}: schema not found: {schema_path}")
    return Target(
        name=manifest.name, root=root, schema_path=schema_path, discovery=manifest.discovery
    )
