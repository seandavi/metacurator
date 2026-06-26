"""GroundingBackend protocol + shared ontology-store shape. See SPEC 070, ADR-0005.

All backends expose the same store shape so grounding queries are identical:

    terms(ontology, curie, label, definition, obsolete, replaced_by)
    synonyms(ontology, curie, synonym, scope)
    xrefs(ontology, curie, xref)
    edges(ontology, subject, predicate, object)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import GroundedTerm

DEFAULT_PREDICATES = ("rdfs:subClassOf",)


@runtime_checkable
class GroundingBackend(Protocol):
    """Stable interface every grounding backend implements (SPEC 070)."""

    def ensure(self, ontologies: list[str]) -> None:
        """Make the named ontologies available locally (download/build/attach)."""
        ...

    def lookup(
        self, value: str, ontology: str, *, scopes: tuple[str, ...] = ("exact", "label")
    ) -> list[GroundedTerm]:
        """Normalized match against labels + synonyms, restricted to one ontology."""
        ...

    def get(self, curie: str, ontology: str) -> GroundedTerm | None:
        """Round-trip a CURIE: re-fetch and confirm it exists in the ontology."""
        ...

    def reachable_from(
        self,
        curie: str,
        root: str,
        ontology: str,
        *,
        predicates: tuple[str, ...] = DEFAULT_PREDICATES,
    ) -> bool:
        """True if ``curie`` is under ``root`` via the recursive-CTE closure (SPEC 070)."""
        ...

    def is_obsolete(self, curie: str, ontology: str) -> bool: ...
    def replaced_by(self, curie: str, ontology: str) -> str | None: ...
