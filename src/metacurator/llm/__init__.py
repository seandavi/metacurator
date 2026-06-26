"""Judgment clients — concrete LLMClient adapters + factory (SPEC 130, ADR-0007).

``judge`` (SPEC 100) defines the ``LLMClient`` Protocol and stays the final validation gate;
this package provides models behind it. Base install pulls no model SDK — each provider is
an optional extra (``[vertex]`` today).
"""

from __future__ import annotations

from .base import LLMContractError, make_client, structured

__all__ = ["LLMContractError", "make_client", "structured"]
