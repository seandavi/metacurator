"""Cloudflare Workers AI Clef decision client. SPEC 180, ADR-0011.

Calls ``@cf/cloudflare/{clef,clef-flash}`` over the Workers AI REST API with ``httpx``; no
SDK. Credentials come from arguments or ``CLOUDFLARE_ACCOUNT_ID`` / ``CLOUDFLARE_AUTH_TOKEN``
and are never echoed in errors.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import httpx

from .base import DecisionError, validate_answers

ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{model}"
MODELS = ("clef", "clef-flash")
_BODY_EXCERPT = 500


class ClefClient:
    """A DecisionClient backed by Clef on Workers AI. Thread-safe for concurrent ``decide``."""

    def __init__(
        self,
        model: str,
        *,
        account_id: str | None = None,
        token: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        http: httpx.Client | None = None,
    ) -> None:
        if model not in MODELS:
            raise ValueError(f"unknown Clef model {model!r}; known: {list(MODELS)}")
        self.model = model
        self._account_id = account_id
        self._token = token
        self._max_retries = max_retries
        self._http = http or httpx.Client(timeout=timeout)
        self._lock = threading.Lock()

    def _credentials(self) -> tuple[str, str]:
        with self._lock:
            self._account_id = self._account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
            self._token = self._token or os.environ.get("CLOUDFLARE_AUTH_TOKEN")
            if not self._account_id or not self._token:
                raise DecisionError("set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AUTH_TOKEN")
            return self._account_id, self._token

    def decide(
        self, *, state: dict[str, Any] | str, questions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        account, token = self._credentials()
        url = ENDPOINT.format(account=account, model=self.model)
        payload = {"model": self.model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {token}"}
        last = ""
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._http.post(url, json=payload, headers=headers)
            except httpx.TransportError as exc:
                last = f"transport error: {exc!r}"
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    last = f"HTTP {resp.status_code}: {resp.text[:_BODY_EXCERPT]}"
                elif resp.status_code >= 400:
                    raise DecisionError(
                        f"clef HTTP {resp.status_code}: {resp.text[:_BODY_EXCERPT]}"
                    )
                else:
                    return self._parse(resp, questions)
            if attempt < self._max_retries:
                time.sleep(2**attempt)
        raise DecisionError(f"clef failed after {self._max_retries + 1} attempts; last {last}")

    @staticmethod
    def _parse(
        resp: httpx.Response, questions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        try:
            body = resp.json()
        except ValueError as exc:
            raise DecisionError(f"clef returned non-JSON: {resp.text[:_BODY_EXCERPT]}") from exc
        if not isinstance(body, dict):
            raise DecisionError(f"clef returned {type(body).__name__}, expected an object")
        if body.get("success") is False:
            raise DecisionError(f"clef error: {body.get('errors')}")
        result = body.get("result", body)
        if not isinstance(result, dict) or "answers" not in result:
            raise DecisionError(f"clef response has no answers: {str(body)[:_BODY_EXCERPT]}")
        return validate_answers(questions, result["answers"])

    def describe(self) -> dict[str, Any]:
        return {"provider": "cloudflare", "model": self.model, "endpoint": "workers-ai",
                "params": {}}
