"""diff — candidate-vs-reference & self-consistency QC. Implement to SPEC 080. [deterministic]

Generalizes the harness proven on the cMD reproduction: per-column match/mismatch/blank/
cand_adds + verdict, with normalizations (casefold, numeric tolerance, set-equal
multi-value, curated-blank=enrichment, synonym folds) to avoid false positives.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import DiffResult, Verdict

NUMERIC_TOL = 1e-6
_DEFAULT_BLANKS = frozenset({""})


def _is_blank(value: Any, blanks: frozenset[str]) -> bool:
    if value is None:
        return True
    return str(value).strip().casefold() in blanks


def _as_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _looks_multivalue(value: Any) -> bool:
    return isinstance(value, list | tuple | set) or (isinstance(value, str) and ";" in value)


def _tokens(value: Any) -> frozenset[str]:
    items: Iterable[Any] = value if isinstance(value, list | tuple | set) else str(value).split(";")
    return frozenset(str(t).strip().casefold() for t in items if str(t).strip())


def _canon(value: Any, synonyms: Mapping[str, str]) -> str:
    s = str(value).strip().casefold()
    return synonyms.get(s, s)


def _equal(a: Any, b: Any, synonyms: Mapping[str, str]) -> bool:
    fa, fb = _as_float(a), _as_float(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= NUMERIC_TOL
    if _looks_multivalue(a) or _looks_multivalue(b):
        return _tokens(a) == _tokens(b)
    return _canon(a, synonyms) == _canon(b, synonyms)


def _index(
    rows: list[dict[str, Any]], key: str, secondary_key: str | None
) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for row in rows:
        k = row.get(key)
        if (k is None or str(k).strip() == "") and secondary_key:
            k = row.get(secondary_key)
        if k is None or str(k).strip() == "":
            continue
        idx[str(k)] = row  # last row wins on duplicate keys (SPEC 080)
    return idx


def _columns(
    candidate: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    key: str,
    secondary_key: str | None,
) -> list[str]:
    cols: list[str] = []
    seen = {key, secondary_key}
    for row in [*candidate, *reference]:
        for c in row:
            if c not in seen:
                seen.add(c)
                cols.append(c)
    return cols


def diff(
    candidate: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    *,
    key: str,
    secondary_key: str | None = None,
    columns: Iterable[str] | None = None,
    synonyms: Mapping[str, str] | None = None,
    blank_values: Iterable[str] | None = None,
    max_examples: int = 5,
) -> list[DiffResult]:
    """Join on key; per-column DiffResult with verdicts + a __rows__ summary. See SPEC 080."""
    folds = {k.casefold(): v.casefold() for k, v in (synonyms or {}).items()}
    blanks = frozenset(b.casefold() for b in (blank_values or _DEFAULT_BLANKS))

    cand_idx = _index(candidate, key, secondary_key)
    ref_idx = _index(reference, key, secondary_key)
    cand_keys, ref_keys = set(cand_idx), set(ref_idx)
    joined = cand_keys & ref_keys
    cand_only = sorted(cand_keys - ref_keys)
    ref_only = sorted(ref_keys - cand_keys)

    cols = list(columns) if columns is not None else _columns(
        candidate, reference, key, secondary_key
    )

    results: list[DiffResult] = []

    # Leading row-join summary: unjoined keys are reported, never silently dropped.
    join_examples: list[dict[str, Any]] = []
    if cand_only or ref_only:
        join_examples.append(
            {
                "candidate_only": cand_only[:max_examples],
                "reference_only": ref_only[:max_examples],
            }
        )
    results.append(
        DiffResult(
            column="__rows__",
            compared=len(joined),
            cand_adds=len(cand_only),
            blank=len(ref_only),
            verdict=Verdict.PASS if not (cand_only or ref_only) else Verdict.PARTIAL,
            examples=join_examples,
        )
    )

    for col in cols:
        compared = match = mismatch = blank = cand_adds = 0
        examples: list[dict[str, Any]] = []
        for k in sorted(joined):
            cv = cand_idx[k].get(col)
            rv = ref_idx[k].get(col)
            cb, rb = _is_blank(cv, blanks), _is_blank(rv, blanks)
            if rb and not cb:
                cand_adds += 1
                continue
            if cb:  # candidate blank (reference blank or filled) -> coverage, not conflict
                blank += 1
                continue
            compared += 1
            if _equal(cv, rv, folds):
                match += 1
            else:
                mismatch += 1
                if len(examples) < max_examples:
                    examples.append({"key": k, "candidate": cv, "reference": rv})
        verdict = (
            Verdict.FAIL if mismatch else Verdict.PARTIAL if blank else Verdict.PASS
        )
        results.append(
            DiffResult(
                column=col,
                compared=compared,
                match=match,
                mismatch=mismatch,
                blank=blank,
                cand_adds=cand_adds,
                verdict=verdict,
                examples=examples,
            )
        )
    return results
