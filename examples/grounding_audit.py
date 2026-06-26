"""Grounding-breadth audit: every distinct curated disease label vs real NCIT.

The honest, high-signal test of the no-hallucination core (SPEC 070) across the whole
curatedMetagenomicData corpus. For every *single*-disease curated value (label ->
ontology term id), we ground the label against real NCIT under the schema's disease branch
(NCIT:C2991) and compare metacurator's CURIE to the curator's. Categories:

- AGREE        : metacurator's auto CURIE == the curator's CURIE.
- DISAGREE     : both NCIT, but different CURIEs (a real discrepancy to investigate).
- REVIEW       : grounded but not auto (out-of-branch or ambiguous) — often a schema
                 branch-root gap (e.g. procedures/findings outside NCIT:C2991).
- NO-MATCH     : no NCIT grounding for the label at all.
- CROSS-ONTO   : the curator used a non-NCIT ontology (EFO/MP/...), which the cmd schema's
                 NCIT binding cannot match by construction.
- SCHEMA-PV    : the label is an explicit permissible value (e.g. Healthy); compared to the
                 schema's asserted meaning.

Multi-disease rows (a value with several CURIEs) are skipped and counted separately — the
point here is breadth of single-term grounding, not compound parsing.

Usage:
    uv run python examples/grounding_audit.py \
        --curated ../curatedMetagenomicDataCuration/inst/curated --cache /path/to/cache
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

from metacurator.dictionary import Dictionary
from metacurator.ground import ground
from metacurator.grounding.local_duckdb import LocalDuckDBBackend
from metacurator.models import ConfidenceTier

_MULTI = re.compile(r"[;,]")
_SENTINELS = {"", "not applicable", "na", "n/a", "unknown", "control"}


def collect_pairs(curated_dir: Path) -> tuple[Counter, int]:
    """Counter of (label, curated_curie) for single-disease rows; + #multi rows skipped."""
    pairs: Counter = Counter()
    multi = 0
    for sub in sorted(p for p in curated_dir.iterdir() if p.is_dir()):
        tsv = sub / f"{sub.name}_sample.tsv"
        if not tsv.exists():
            continue
        with open(tsv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                label = (row.get("disease") or "").strip()
                curie = (row.get("disease_ontology_term_id") or "").strip()
                if not label or label.casefold() in _SENTINELS:
                    continue
                curies = [c for c in _MULTI.split(curie) if c.strip()]
                if len(curies) != 1:
                    multi += 1
                    continue
                pairs[(label, curies[0].strip())] += 1
    return pairs, multi


def classify(label, curie, *, dictionary, backend, branch_root):
    pv = dictionary.field("disease").permissible_values
    if label in pv:
        return "SCHEMA-PV", pv[label]
    if not curie.startswith("NCIT:"):
        return "CROSS-ONTO", ""
    terms = ground(label, "ncit", backend=backend, branch_root=branch_root)
    autos = [t for t in terms if t.confidence_tier == ConfidenceTier.auto]
    if autos:
        mc = autos[0].curie
        return ("AGREE" if mc == curie else "DISAGREE"), mc
    if terms:
        return "REVIEW", terms[0].curie or ""
    return "NO-MATCH", ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--curated", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--examples", type=int, default=12, help="examples to show per category")
    args = ap.parse_args()

    dictionary = Dictionary()
    branch_root = dictionary.field("disease").binding.branch_root
    backend = LocalDuckDBBackend(cache_dir=Path(args.cache))
    print("ensuring NCIT ...")
    backend.ensure(["ncit"])

    pairs, multi = collect_pairs(Path(args.curated))
    print(f"\n{len(pairs)} distinct single-disease (label, curie) pairs; "
          f"{multi} multi-disease rows skipped\n")

    categories = ("AGREE", "DISAGREE", "REVIEW", "NO-MATCH", "CROSS-ONTO", "SCHEMA-PV")
    buckets: dict[str, list] = {k: [] for k in categories}
    row_coverage: Counter = Counter()
    for (label, curie), n in pairs.most_common():
        cat, mc = classify(
            label, curie, dictionary=dictionary, backend=backend, branch_root=branch_root
        )
        buckets[cat].append((label, curie, mc, n))
        row_coverage[cat] += n

    total_rows = sum(row_coverage.values())
    print("== summary (distinct labels / sample rows) ==")
    for cat in buckets:
        print(f"  {cat:11s} {len(buckets[cat]):4d} labels   {row_coverage[cat]:6d} rows "
              f"({100 * row_coverage[cat] / total_rows:4.1f}%)")

    agree_rows = row_coverage["AGREE"] + row_coverage["SCHEMA-PV"]
    print(f"\n  agreement (AGREE+SCHEMA-PV): {agree_rows}/{total_rows} rows "
          f"({100 * agree_rows / total_rows:.1f}%)\n")

    for cat in ("DISAGREE", "REVIEW", "NO-MATCH", "CROSS-ONTO"):
        rows = buckets[cat]
        if not rows:
            continue
        print(f"== {cat} ({len(rows)} labels) ==")
        for label, curie, mc, n in rows[: args.examples]:
            extra = f" -> metacurator={mc}" if mc else ""
            print(f"  [{n:5d}] {label!r}  curated={curie}{extra}")
        if len(rows) > args.examples:
            print(f"  ... and {len(rows) - args.examples} more")
        print()


if __name__ == "__main__":
    main()
