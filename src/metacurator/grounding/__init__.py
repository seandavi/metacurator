"""Ontology grounding backends (SPEC 070, ADR-0005).

Default is the zero-infrastructure ``LocalDuckDBBackend`` (builds a local store from
public semantic-sql files); ``DuckLakeBackend`` is opt-in for teams with a lake. Both
share one store shape, so grounding logic is identical across them.
"""

from .base import GroundingBackend
from .ducklake import DuckLakeBackend
from .local_duckdb import LocalDuckDBBackend

__all__ = ["GroundingBackend", "LocalDuckDBBackend", "DuckLakeBackend"]
