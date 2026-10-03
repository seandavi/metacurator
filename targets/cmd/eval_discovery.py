"""Evaluate SRA discovery for the cmd target against curatedMetagenomicData. [cmd-specific]

    uv run python targets/cmd/eval_discovery.py --discovery DIR --controls DIR \
        --curated PATH [--parquet-base URL]

Gold standard: the hand-curated cMD studies (``PATH/<study>/<study>_sample.tsv``, column
``ncbi_accession``), mapped run → SRA study through the same SRA parquet discovery used.

Criteria (each printed PASS/FAIL; written to ``DIR/eval.md``; exit 1 on any FAIL):

- C1 prefilter recall: ≥ 115 cMD studies have ≥ 1 mapped SRA study in ``studies.parquet``.
- C2 screening recall: of the C1-covered cMD studies, ≥ 90% have ≥ 1 mapped SRA study
  decided include or review.
- C3 controls (from the ``--controls`` run): three mouse studies are include/review with
  host = mouse; soil, marine and pig-farm studies are exclude.
- C4 readset: ZellerG_2014 sample ERS436796 / SAMEA2467039 in ERP005534 has readset id
  ``RS.l29A5uBFtCKLgc-EPvUhj0hD6Q02Z7qj`` and its runs match a curated cMD sample.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb

from metacurator.discover import DEFAULT_SRA_PARQUET, open_sra

RUN = re.compile(r"[SED]RR\d+")
C1_MIN = 115
C2_MIN = 0.90
MOUSE_CONTROLS = {"SRP313292": "PRJNA719426", "ERP123538": "PRJEB39960", "ERP115481": "PRJEB32767"}
NEGATIVE_CONTROLS = {"ERP128471": "PRJEB44414 soil", "ERP015773": "PRJEB14154 marine",
                     "ERP153147": "PRJEB68161 pig farm"}
C4 = {
    "sra_sample": "ERS436796",
    "biosample": "SAMEA2467039",
    "study_accession": "ERP005534",
    "readset_id": "RS.l29A5uBFtCKLgc-EPvUhj0hD6Q02Z7qj",
    "cmd_study": "ZellerG_2014",
}


def load_gold(curated: Path) -> tuple[dict[str, set[str]], dict[str, list[frozenset[str]]]]:
    """cMD study → runs, and cMD study → per-sample run sets."""
    runs: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, list[frozenset[str]]] = defaultdict(list)
    for path in sorted(curated.glob("*/*_sample.tsv")):
        study = path.parent.name
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            if "ncbi_accession" not in (reader.fieldnames or []):
                continue
            for row in reader:
                found = frozenset(RUN.findall(row.get("ncbi_accession") or ""))
                if found:
                    runs[study] |= found
                    samples[study].append(found)
    return dict(runs), dict(samples)


def map_runs(con: duckdb.DuckDBPyConnection, runs: set[str]) -> dict[str, set[str]]:
    """Run accession → SRA study accessions (via sra_runs → sra_experiments)."""
    con.execute("CREATE OR REPLACE TEMP TABLE _gold AS SELECT unnest($r::VARCHAR[]) AS run",
                {"r": sorted(runs)})
    out: dict[str, set[str]] = defaultdict(set)
    for run, study in con.execute(
        """
        SELECT DISTINCT r.accession, e.study_accession
        FROM sra_runs r JOIN sra_experiments e ON e.accession = r.experiment_accession
        WHERE r.accession IN (SELECT run FROM _gold) AND e.study_accession IS NOT NULL
        """
    ).fetchall():
        out[run].add(study)
    return dict(out)


def rows(path: Path) -> list[dict[str, Any]]:
    rel = duckdb.sql(f"SELECT * FROM read_parquet('{str(path).replace(chr(39), chr(39) * 2)}')")
    return [dict(zip(rel.columns, r, strict=True)) for r in rel.fetchall()]


def summary_count(path: Path, key: str) -> str:
    m = re.search(rf"^- {re.escape(key)}: (\S+)$", path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--discovery", type=Path, required=True, help="full discovery output dir")
    ap.add_argument("--controls", type=Path, required=True, help="controls discovery output dir")
    ap.add_argument("--curated", type=Path, required=True, help="cMD inst/curated directory")
    ap.add_argument("--parquet-base", default=os.environ.get("METACURATOR_SRA_PARQUET")
                    or DEFAULT_SRA_PARQUET)
    args = ap.parse_args()

    report: list[str] = ["# cmd discovery evaluation", ""]
    failures: list[str] = []

    def say(line: str = "") -> None:
        print(line)
        report.append(line)

    def verdict(name: str, ok: bool, detail: str) -> None:
        say(f"- **{name}: {'PASS' if ok else 'FAIL'}** — {detail}")
        if not ok:
            failures.append(name)

    # 1-2. gold standard and its SRA studies
    gold_runs, gold_samples = load_gold(args.curated)
    all_runs = set().union(*gold_runs.values())
    n_pairs = sum(len(v) for v in gold_runs.values())
    run_to_study = map_runs(open_sra(args.parquet_base), all_runs)
    cmd_to_sra = {s: set().union(*(run_to_study.get(r, set()) for r in rs))
                  for s, rs in gold_runs.items()}
    sra_studies = set().union(*cmd_to_sra.values())
    say("## Gold standard")
    say()
    say(f"- cMD studies with run accessions: {len(gold_runs)}")
    say(f"- (study, run) pairs: {n_pairs}; distinct runs: {len(all_runs)}")
    say(f"- runs found in SRA parquet: {len(run_to_study)}/{len(all_runs)}")
    say(f"- distinct SRA studies: {len(sra_studies)}")
    say()

    # 3. discovery outputs
    full = {r["study_accession"]: r for r in rows(args.discovery / "studies.parquet")}
    controls = {r["study_accession"]: r for r in rows(args.controls / "studies.parquet")}
    readsets = rows(args.discovery / "readsets.parquet")

    say("## Criteria")
    say()
    # C1
    covered = sorted(s for s, sra in cmd_to_sra.items() if sra & full.keys())
    missed = sorted(set(cmd_to_sra) - set(covered))
    verdict("C1 prefilter recall", len(covered) >= C1_MIN,
            f"{len(covered)}/{len(cmd_to_sra)} cMD studies screened (need ≥ {C1_MIN}); "
            f"missed: {', '.join(f'{s} ({sorted(cmd_to_sra[s])})' for s in missed) or 'none'}")

    # C2
    def best(cmd_study: str, accept: set[str]) -> bool:
        return any(full[a]["decision"] in accept for a in cmd_to_sra[cmd_study] if a in full)

    kept = [s for s in covered if best(s, {"include", "review"})]
    included = [s for s in covered if best(s, {"include"})]
    frac = len(kept) / len(covered) if covered else 0.0
    verdict("C2 screening recall", frac >= C2_MIN,
            f"{len(kept)}/{len(covered)} = {frac:.3f} include|review (need ≥ {C2_MIN}); "
            f"include only: {len(included)}/{len(covered)} = "
            f"{(len(included) / len(covered) if covered else 0):.3f}")
    for s in sorted(set(covered) - set(kept)):
        for acc in sorted(a for a in cmd_to_sra[s] if a in full):
            r = full[acc]
            ans = json.loads(r["answers"] or "{}")
            host = ans.get("host", {}).get("probabilities")
            shotgun = ans.get("shotgun_microbiome", {}).get("noul")
            say(f"  - miss {s} / {acc}: {r['decision']} scores={r['rule_scores']} "
                f"host={host} shotgun={shotgun} error={r['error']}")

    # C3
    c3_notes: list[str] = []
    c3_ok = True
    for acc, proj in MOUSE_CONTROLS.items():
        r = controls.get(acc)
        host = json.loads(r["facets"] or "{}").get("host") if r else None
        ok = r is not None and r["decision"] in {"include", "review"} and host == "mouse"
        c3_ok &= ok
        c3_notes.append(f"{acc} ({proj}, mouse): {r['decision'] if r else 'absent'} "
                        f"host={host} {'ok' if ok else 'BAD'}")
    for acc, what in NEGATIVE_CONTROLS.items():
        r = controls.get(acc)
        ok = r is not None and r["decision"] == "exclude"
        c3_ok &= ok
        c3_notes.append(f"{acc} ({what}): {r['decision'] if r else 'absent'} "
                        f"{'ok' if ok else 'BAD'}")
    verdict("C3 controls", c3_ok, "; ".join(c3_notes))

    # C4
    hit = next((r for r in readsets if r["sra_sample"] == C4["sra_sample"]), None)
    c4_ok = hit is not None and all(hit[k] == C4[k] for k in
                                    ("biosample", "study_accession", "readset_id"))
    runs = frozenset(u.split(":", 1)[1] for u in hit["units"]) if hit else frozenset()
    matches_cmd = runs in set(gold_samples.get(C4["cmd_study"], []))
    verdict("C4 readset", c4_ok and matches_cmd,
            (f"{hit['readset_id']} biosample={hit['biosample']} study={hit['study_accession']} "
             f"runs={sorted(runs)} matches cMD {C4['cmd_study']} sample: {matches_cmd}")
            if hit else f"no readset for {C4['sra_sample']}")

    # report only
    say()
    say("## Report")
    say()
    by_decision = Counter(r["decision"] for r in full.values())
    say(f"- studies screened: {len(full)}")
    say(f"- by decision: {dict(sorted(by_decision.items()))}")
    for facet in ("host", "body_site", "study_kind"):
        c = Counter(json.loads(r["facets"] or "{}").get(facet, "?") for r in full.values())
        say(f"- by {facet}: {dict(c.most_common())}")
    calls = summary_count(args.discovery / "summary.md", "calls")
    say(f"- Clef calls (cache misses, last run): {calls}")
    say(f"- errors: {by_decision.get('error', 0)}")
    say(f"- readsets: {len(readsets)}")

    (args.discovery / "eval.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nwrote {args.discovery / 'eval.md'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
