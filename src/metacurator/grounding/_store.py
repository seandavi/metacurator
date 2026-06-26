"""Shared DuckDB ontology-store layer for grounding backends. SPEC 070, ADR-0005.

Every backend exposes the same four-table store shape, so the grounding SQL is
identical across them:

    terms(ontology, curie, label, definition, obsolete, replaced_by)
    synonyms(ontology, curie, synonym, scope)
    xrefs(ontology, curie, xref)
    edges(ontology, subject, predicate, object)

``DuckStore`` wraps a DuckDB connection whose tables live under ``qualifier`` (empty for a
local file, ``"ontology."`` for an attached DuckLake schema) and implements the
``GroundingBackend`` query primitives. Matching normalizes *both* sides of every
comparison with one SQL expression (``_norm_sql``) so casefold/trim/punct-collapse is
identical across backends — the shape-parity invariant — and needs no Python UDF.
"""

from __future__ import annotations

import re

import duckdb

from ..models import GroundedTerm, Scope
from .base import DEFAULT_PREDICATES

# The four-table store shape (SPEC 070). Shared by the local-store builder and the test
# fixtures, so both agree on one definition.
STORE_DDL = """
CREATE TABLE IF NOT EXISTS terms (
    ontology    VARCHAR NOT NULL,
    curie       VARCHAR NOT NULL,
    label       VARCHAR,
    definition  VARCHAR,
    obsolete    BOOLEAN DEFAULT FALSE,
    replaced_by VARCHAR
);
CREATE TABLE IF NOT EXISTS synonyms (
    ontology VARCHAR NOT NULL,
    curie    VARCHAR NOT NULL,
    synonym  VARCHAR,
    scope    VARCHAR   -- exact | broad | narrow | related
);
CREATE TABLE IF NOT EXISTS xrefs (
    ontology VARCHAR NOT NULL,
    curie    VARCHAR NOT NULL,
    xref     VARCHAR
);
CREATE TABLE IF NOT EXISTS edges (
    ontology  VARCHAR NOT NULL,
    subject   VARCHAR NOT NULL,
    predicate VARCHAR NOT NULL,
    object    VARCHAR NOT NULL
);
"""

_NONALNUM = re.compile(r"[^0-9a-z]+")


def normalize(value: str | None) -> str:
    """Python mirror of the SQL normalization (casefold, trim, collapse non-alphanumerics).

    Kept for callers that need to normalize outside SQL; the SQL path (``_norm_sql``) is
    the one used inside lookups and is the authority for matching.
    """
    if value is None:
        return ""
    return _NONALNUM.sub(" ", value.casefold()).strip()


def _norm_sql(expr: str) -> str:
    """SQL fragment normalizing ``expr`` the same way as ``normalize`` (ASCII)."""
    return f"trim(regexp_replace(lower({expr}), '[^0-9a-z]+', ' ', 'g'))"


class DuckStore:
    """Grounding query primitives over a DuckDB connection with the four-table shape."""

    def __init__(self, con: duckdb.DuckDBPyConnection, *, qualifier: str = "") -> None:
        self.con = con
        self.q = qualifier  # e.g. "" or "ontology."

    # -- lookup -----------------------------------------------------------------
    def lookup(
        self, value: str, ontology: str, *, scopes: tuple[str, ...] = ("exact", "label")
    ) -> list[GroundedTerm]:
        """Normalized match against labels (scope ``label``) + synonyms, one ontology."""
        out: list[GroundedTerm] = []
        seen: set[tuple[str, Scope]] = set()

        if "label" in scopes:
            rows = self.con.execute(
                f"SELECT ontology, curie, label, obsolete, replaced_by "  # noqa: S608
                f"FROM {self.q}terms "
                f"WHERE ontology = ? AND {_norm_sql('label')} = {_norm_sql('?')}",
                [ontology, value],
            ).fetchall()
            for onto, curie, label, obsolete, replaced in rows:
                key = (curie, Scope.label)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    GroundedTerm(
                        query=value, ontology=onto, curie=curie, label=label,
                        scope=Scope.label, obsolete=bool(obsolete), replaced_by=replaced,
                    )
                )

        syn_scopes = tuple(s for s in scopes if s != "label")
        if syn_scopes:
            placeholders = ", ".join("?" for _ in syn_scopes)
            rows = self.con.execute(
                f"SELECT t.ontology, t.curie, t.label, s.scope, t.obsolete, t.replaced_by "  # noqa: S608
                f"FROM {self.q}synonyms s "
                f"JOIN {self.q}terms t ON t.ontology = s.ontology AND t.curie = s.curie "
                f"WHERE s.ontology = ? AND s.scope IN ({placeholders}) "
                f"AND {_norm_sql('s.synonym')} = {_norm_sql('?')}",
                [ontology, *syn_scopes, value],
            ).fetchall()
            for onto, curie, label, scope, obsolete, replaced in rows:
                sc = Scope(scope)
                key = (curie, sc)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    GroundedTerm(
                        query=value, ontology=onto, curie=curie, label=label,
                        scope=sc, obsolete=bool(obsolete), replaced_by=replaced,
                    )
                )
        return out

    # -- round-trip -------------------------------------------------------------
    def get(self, curie: str, ontology: str) -> GroundedTerm | None:
        """Re-fetch a CURIE within an ontology; ``None`` if it does not exist."""
        row = self.con.execute(
            f"SELECT ontology, curie, label, obsolete, replaced_by "  # noqa: S608
            f"FROM {self.q}terms WHERE ontology = ? AND curie = ?",
            [ontology, curie],
        ).fetchone()
        if row is None:
            return None
        onto, curie, label, obsolete, replaced = row
        return GroundedTerm(
            query=curie, ontology=onto, curie=curie, label=label,
            obsolete=bool(obsolete), replaced_by=replaced,
        )

    # -- branch check (recursive-CTE closure, SPEC 070) -------------------------
    def reachable_from(
        self,
        curie: str,
        root: str,
        ontology: str,
        *,
        predicates: tuple[str, ...] = DEFAULT_PREDICATES,
    ) -> bool:
        """True if ``curie`` is under ``root`` via asserted edges. ``curie == root`` is True."""
        if curie == root:
            return True
        placeholders = ", ".join("?" for _ in predicates)
        # UNION (not ALL) dedups and guards against cyclic graphs (DuckDB has no CYCLE).
        sql = (
            f"WITH RECURSIVE anc(start, node) AS ("  # noqa: S608
            f"  SELECT subject, object FROM {self.q}edges "
            f"    WHERE ontology = ? AND predicate IN ({placeholders}) "
            f"  UNION "
            f"  SELECT a.start, e.object FROM anc a "
            f"    JOIN {self.q}edges e ON e.ontology = ? AND e.predicate IN ({placeholders}) "
            f"      AND e.subject = a.node "
            f") SELECT 1 FROM anc WHERE start = ? AND node = ? LIMIT 1"
        )
        params = [ontology, *predicates, ontology, *predicates, curie, root]
        return self.con.execute(sql, params).fetchone() is not None

    def is_obsolete(self, curie: str, ontology: str) -> bool:
        row = self.con.execute(
            f"SELECT obsolete FROM {self.q}terms WHERE ontology = ? AND curie = ?",  # noqa: S608
            [ontology, curie],
        ).fetchone()
        return bool(row[0]) if row else False

    def replaced_by(self, curie: str, ontology: str) -> str | None:
        row = self.con.execute(
            f"SELECT replaced_by FROM {self.q}terms WHERE ontology = ? AND curie = ?",  # noqa: S608
            [ontology, curie],
        ).fetchone()
        return row[0] if row else None

    def loaded_ontologies(self) -> set[str]:
        rows = self.con.execute(f"SELECT DISTINCT ontology FROM {self.q}terms").fetchall()  # noqa: S608
        return {r[0] for r in rows}


__all__ = ["STORE_DDL", "DuckStore", "normalize"]
