"""Decision-client protocol, answer validation and factory. SPEC 180, ADR-0011.

A decision client answers bounded questions (``noul`` yes/no, ``choice`` pick-one, ``score``
ordinal) about a state with a probability per option. It is separate from ``LLMClient``
(SPEC 130): the request is ``{state, questions}`` and the answer carries probabilities.
"""

from __future__ import annotations

import math
from typing import Any, Protocol


class DecisionError(RuntimeError):
    """A decision call failed or returned answers that do not fit the questions."""


class DecisionClient(Protocol):
    def decide(
        self, *, state: dict[str, Any] | str, questions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]: ...

    def describe(self) -> dict[str, Any]: ...


def _is_prob(x: Any) -> bool:
    return (
        isinstance(x, int | float)
        and not isinstance(x, bool)
        and math.isfinite(x)
        and 0 <= x <= 1
    )


def validate_answers(
    questions: dict[str, dict[str, Any]], answers: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Check ``answers`` fit ``questions``; return them restricted to the question ids."""
    if not isinstance(answers, dict):
        raise DecisionError(f"answers must be an object, got {type(answers).__name__}")
    out: dict[str, dict[str, Any]] = {}
    for qid, q in questions.items():
        a = answers.get(qid)
        if not isinstance(a, dict):
            raise DecisionError(f"question {qid!r}: no answer")
        if a.get("type") != q.get("type"):
            raise DecisionError(
                f"question {qid!r}: answer type {a.get('type')!r} != {q.get('type')!r}"
            )
        if q["type"] == "noul" and not _is_prob(a.get("noul")):
            raise DecisionError(f"question {qid!r}: noul {a.get('noul')!r} not in [0, 1]")
        if q["type"] == "choice":
            options = set(q.get("criteria") or {})
            probs = a.get("probabilities")
            if a.get("choice") not in options:
                raise DecisionError(f"question {qid!r}: choice {a.get('choice')!r} not an option")
            if not isinstance(probs, dict) or set(probs) != options:
                raise DecisionError(
                    f"question {qid!r}: probabilities keys "
                    f"{sorted(probs) if isinstance(probs, dict) else probs!r} != {sorted(options)}"
                )
            bad = {k: v for k, v in probs.items() if not _is_prob(v)}
            if bad:
                raise DecisionError(f"question {qid!r}: probabilities not in [0, 1]: {bad}")
        out[qid] = a
    return out


def make_decision_client(spec: str, **opts: Any) -> DecisionClient:
    """Resolve a ``"provider:model"`` spec to a DecisionClient (SPEC 180).

    Known providers: ``cloudflare`` (models ``clef``, ``clef-flash``).
    """
    provider, _, model = spec.partition(":")
    if not provider or not model:
        raise ValueError(f"decision client spec must be 'provider:model', got {spec!r}")
    if provider == "cloudflare":
        from .cloudflare import ClefClient

        return ClefClient(model, **opts)
    raise ValueError(f"unknown decision provider {provider!r}; known: ['cloudflare']")
