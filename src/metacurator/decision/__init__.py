"""Decision clients — bounded screening judgments with per-option probabilities.

SPEC 180, ADR-0011. Separate from ``llm`` (SPEC 130): requests are ``{state, questions}``
and answers carry a probability for every option. First provider: Cloudflare Clef.
"""

from __future__ import annotations

from .base import DecisionClient, DecisionError, make_decision_client, validate_answers

__all__ = ["DecisionClient", "DecisionError", "make_decision_client", "validate_answers"]
