"""Framework contracts — the typed objects every stage passes around (SPEC 010).

These are the *process* models (they describe curation work). The *record* models (the
target standard's row types, e.g. a cMD Sample) are generated from the LinkML schema into
``metacurator._generated`` (ADR-0003) and are referenced, not defined here.

Invariant (ADR-0004): ``AccessionMap`` and ``GroundedTerm`` are producible only by
deterministic tools. ``ColumnMapping`` (agent output) describes a projection; it carries
no curated values. No identifier is ever minted by a model.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class OAStatus(StrEnum):
    oa = "oa"
    not_oa = "not_oa"
    unknown = "unknown"


class StudyRef(BaseModel):
    """Identity + access of one study (SPEC 020)."""

    pmid: str
    pmcid: str | None = None
    doi: str | None = None
    oa_status: OAStatus = OAStatus.unknown
    bioproject: str | None = None
    title: str | None = None


class AccessionRow(BaseModel):
    run: str | None = None
    sample: str | None = None  # BioSample (SAMN/SAMEA/SAMD)
    secondary_sample: str | None = None  # ERS/SRS/DRS
    alias: str | None = None
    title: str | None = None


class AccessionMap(BaseModel):
    """Per-sample sequence-archive identifiers (SPEC 030). Authoritative for accessions."""

    project: str | None = None
    source: str = "ena"
    rows: list[AccessionRow] = Field(default_factory=list)


class SourceProvenance(BaseModel):
    file: str
    sheet: str | None = None
    table_index: int | None = None
    header_row: int | None = None
    url: str | None = None


class SourceTable(BaseModel):
    """A loaded supplement table + provenance (SPEC 050). ``frame`` type is kept opaque."""

    model_config = {"arbitrary_types_allowed": True}

    frame: Any
    provenance: SourceProvenance
    n_rows: int
    n_cols: int


class MappingItem(BaseModel):
    source_col: str
    target_field: str
    transform: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None


class ColumnMapping(BaseModel):
    """Agent output (SPEC 100): how to project source columns → schema fields. No values."""

    items: list[MappingItem] = Field(default_factory=list)
    needs_review: bool = False


class Scope(StrEnum):
    exact = "exact"
    broad = "broad"
    narrow = "narrow"
    related = "related"
    label = "label"


class ConfidenceTier(StrEnum):
    auto = "auto"
    review = "review"
    none = "none"


class GroundedTerm(BaseModel):
    """A verified ontology grounding (SPEC 070). Produced only by deterministic tools."""

    query: str
    ontology: str
    curie: str | None = None
    label: str | None = None
    scope: Scope | None = None
    branch_ok: bool = False
    obsolete: bool = False
    replaced_by: str | None = None
    confidence_tier: ConfidenceTier = ConfidenceTier.none


class CandidateRow(BaseModel):
    """One reconstructed record + per-field provenance (SPEC 010). Conforms to the active
    generated record model; kept loose here so the framework is schema-agnostic."""

    model_config = {"arbitrary_types_allowed": True}

    key: str
    values: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)


class Verdict(StrEnum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


class DiffResult(BaseModel):
    column: str
    compared: int = 0
    match: int = 0
    mismatch: int = 0
    blank: int = 0
    cand_adds: int = 0
    verdict: Verdict = Verdict.PASS
    examples: list[dict[str, Any]] = Field(default_factory=list)


class CurationReport(BaseModel):
    """The human-facing artifact + provenance trail (SPEC 090)."""

    study: StudyRef
    sources: list[str] = Field(default_factory=list)
    diffs: list[DiffResult] = Field(default_factory=list)
    notes: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
