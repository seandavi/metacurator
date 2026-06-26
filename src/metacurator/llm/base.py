"""Judgment-client plumbing: factory + provider-agnostic validate-and-retry. SPEC 130.

The model call is the one non-deterministic step (confined to `judge`, ADR-0004). These
helpers make every adapter's output JSON-parseable and schema-shaped before it reaches
`judge`, which then does the strict pydantic validation + no-mint enforcement (SPEC 100).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


class LLMContractError(RuntimeError):
    """A model failed to return schema-valid JSON within the retry budget (SPEC 130)."""


def _matches_schema(data: Any, schema: dict[str, Any]) -> tuple[bool, str]:
    """Light shape check: an object with its required keys present.

    Intentionally minimal — provider-native structured output enforces the full shape and
    `judge` does the strict pydantic validation. This only catches gross violations so the
    retry can re-ask.
    """
    if schema.get("type") == "object" and not isinstance(data, dict):
        return False, "expected a JSON object"
    missing = [k for k in schema.get("required", []) if k not in (data or {})]
    if missing:
        return False, f"missing required keys: {missing}"
    return True, ""


def structured(
    call: Callable[[str | None], str], schema: dict[str, Any], *, retries: int = 2
) -> dict[str, Any]:
    """Run ``call(feedback)`` -> raw text; parse + shape-check JSON; retry with a nudge.

    ``call`` receives ``None`` on the first attempt and an error string on each retry (so
    the adapter can append it to the prompt). Raises ``LLMContractError`` after
    ``retries`` extra attempts.
    """
    feedback: str | None = None
    last = ""
    for _ in range(retries + 1):
        last = call(feedback)
        try:
            data = json.loads(last)
        except (json.JSONDecodeError, TypeError) as exc:
            feedback = f"Your previous output was not valid JSON ({exc}). Return ONLY JSON."
            continue
        ok, err = _matches_schema(data, schema)
        if ok:
            return data
        feedback = f"Your JSON did not match the schema: {err}. Return ONLY matching JSON."
    raise LLMContractError(
        f"model did not return schema-valid JSON after {retries + 1} attempts; last={last!r}"
    )


def make_client(spec: str, **opts: Any):
    """Resolve a ``"provider:model"`` spec to an LLMClient (SPEC 130).

    Known providers: ``vertex``. Unknown provider -> ValueError; a missing provider extra
    surfaces as an ImportError naming the extra to install.
    """
    provider, _, model = spec.partition(":")
    if not provider or not model:
        raise ValueError(f"client spec must be 'provider:model', got {spec!r}")
    if provider == "vertex":
        from .vertex import VertexClient

        return VertexClient(model, **opts)
    raise ValueError(f"unknown model provider {provider!r}; known: ['vertex']")
