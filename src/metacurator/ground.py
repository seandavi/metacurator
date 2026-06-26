"""ground — map a value to a verified ontology term. Implement to SPEC 070. [deterministic]

Backend-agnostic: depends on a GroundingBackend (default LocalDuckDBBackend). Enforces the
no-hallucination four-step discipline — lookup -> round-trip -> branch check -> obsolete
check — and returns tiered GroundedTerms. A CURIE is only ever produced here, by lookup
against a real ontology store (ADR-0004); a model never mints one.
"""

from __future__ import annotations

from .grounding.base import GroundingBackend
from .models import ConfidenceTier, GroundedTerm, Scope

# Scopes that count as an "exact" hit for auto-tier eligibility.
_EXACT_SCOPES = (Scope.label, Scope.exact)


def ground(
    value: str,
    ontology: str,
    *,
    backend: GroundingBackend,
    branch_root: str | None = None,
    scopes: tuple[str, ...] = ("exact", "label"),
) -> list[GroundedTerm]:
    """Lookup -> round-trip -> branch -> obsolete; return tiered candidates. See SPEC 070.

    Tiering:
    - exactly one exact, in-branch, non-obsolete candidate -> that one is ``auto``;
    - multiple such candidates (ambiguous) -> all ``review`` (never pick silently);
    - fuzzy/broad/narrow, out-of-branch, or obsolete -> ``review``/``none``;
    - no surviving candidate -> ``[]``.

    ``branch_root`` is the schema-declared root the term must be reachable from (SPEC 060);
    when ``None`` there is no branch constraint and ``branch_ok`` is treated as satisfied.
    """
    candidates = backend.lookup(value, ontology, scopes=scopes)

    survivors: list[GroundedTerm] = []
    for cand in candidates:
        if cand.curie is None:
            continue
        # Step 2 — round-trip: the candidate must really exist in this ontology.
        confirmed = backend.get(cand.curie, ontology)
        if confirmed is None or confirmed.ontology != ontology:
            continue

        # Step 4 — obsolete check (authoritative from the round-tripped term).
        obsolete = confirmed.obsolete
        replaced = confirmed.replaced_by if obsolete else None

        # Step 3 — branch check.
        branch_ok = (
            True if branch_root is None
            else backend.reachable_from(cand.curie, branch_root, ontology)
        )

        survivors.append(
            cand.model_copy(
                update={
                    "label": confirmed.label or cand.label,
                    "branch_ok": branch_ok,
                    "obsolete": obsolete,
                    "replaced_by": replaced,
                }
            )
        )

    # Identify auto-eligible: exact scope, in branch, not obsolete.
    auto_eligible = [
        t for t in survivors
        if t.scope in _EXACT_SCOPES and t.branch_ok and not t.obsolete
    ]
    unique_auto = {t.curie for t in auto_eligible}

    results: list[GroundedTerm] = []
    for t in survivors:
        is_auto = (
            t in auto_eligible
            and len(unique_auto) == 1  # ambiguity (>1 distinct auto) demotes to review
        )
        if is_auto:
            tier = ConfidenceTier.auto
        elif t.obsolete:
            tier = ConfidenceTier.none  # deprecated terms are rejected; replaced_by surfaced
        else:
            tier = ConfidenceTier.review
        results.append(t.model_copy(update={"confidence_tier": tier}))

    # auto first, then review, then none — stable within tier.
    order = {ConfidenceTier.auto: 0, ConfidenceTier.review: 1, ConfidenceTier.none: 2}
    results.sort(key=lambda t: order[t.confidence_tier])
    return results
