"""Vertex/Gemini judgment client (the default, ADR-0007). SPEC 130.

Uses Google's google-genai SDK in Vertex mode (ADC auth). Structured output is
provider-native: the call's JSON schema becomes Gemini's ``response_schema`` with
``response_mime_type=application/json``; the shared validate-and-retry wrapper is the
backstop. The SDK is imported lazily so the base package needs no model dependency — install
the ``[vertex]`` extra. The underlying genai client is injectable for offline tests.
"""

from __future__ import annotations

import os
from typing import Any

from .base import structured

_DEFAULT_LOCATION = "us-central1"


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert our JSON-schema dicts to the OpenAPI subset Gemini accepts.

    Handles the shapes the judge uses: object/array/properties/required, scalar types, and
    nullable unions (``["string", "null"]`` -> type ``string`` + ``nullable: true``).
    Constraint keywords (minimum/maximum) are dropped — the validate-retry wrapper and
    `judge`'s pydantic models enforce those.
    """
    out: dict[str, Any] = {}
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        non_null = [t for t in raw_type if t != "null"]
        out["type"] = non_null[0] if non_null else "string"
        if "null" in raw_type:
            out["nullable"] = True
    elif raw_type is not None:
        out["type"] = raw_type

    if out.get("type") == "object":
        props = schema.get("properties", {})
        out["properties"] = {k: to_gemini_schema(v) for k, v in props.items()}
        if schema.get("required"):
            out["required"] = list(schema["required"])
    elif out.get("type") == "array" and "items" in schema:
        out["items"] = to_gemini_schema(schema["items"])
    return out


class VertexClient:
    """LLMClient backed by Vertex AI Gemini (ADR-0007, SPEC 130)."""

    def __init__(
        self,
        model: str,
        *,
        project: str | None = None,
        location: str | None = None,
        temperature: float = 0.0,
        retries: int = 2,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.retries = retries
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_LOCATION)
        self._client = client  # injectable for tests; built lazily otherwise

    def _genai(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise ImportError(
                    "the Vertex client needs the [vertex] extra: "
                    "uv add 'metacurator[vertex]' (or pip install 'metacurator[vertex]')"
                ) from exc
            self._client = genai.Client(
                vertexai=True, project=self.project, location=self.location
            )
        return self._client

    def describe(self) -> dict[str, Any]:
        """Model provenance for the CurationReport (SPEC 130)."""
        return {
            "provider": "vertex",
            "model": self.model,
            "version": None,
            "params": {"temperature": self.temperature, "location": self.location},
        }

    def complete(
        self, *, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        client = self._genai()
        gemini_schema = to_gemini_schema(schema)

        def call(feedback: str | None) -> str:
            contents = prompt if feedback is None else f"{prompt}\n\n{feedback}"
            resp = client.models.generate_content(
                model=self.model,
                contents=contents,
                config={
                    "system_instruction": system,
                    "response_mime_type": "application/json",
                    "response_schema": gemini_schema,
                    "temperature": self.temperature,
                },
            )
            return resp.text

        return structured(call, schema, retries=self.retries)
