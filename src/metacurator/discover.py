"""discover — candidate studies from SRA metadata, screened by a decision client. SPEC 190.

[hybrid] Selection, state building, rule scoring and readset construction are deterministic
SQL/Python over the OmicIDX SRA parquet export; screening is one decision-client call per
study (SPEC 180), cached by (study, model, question-set digest, state digest). Readset
units come only from SRA run accessions — a model never supplies an accession (ADR-0004).
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import httpx

from .decision import DecisionClient, DecisionError, make_decision_client
from .models import Decision, ReadsetRow, StudyDecision
from .readset import RUN_ACCESSION, canonical_json, insdc_unit, readset_id, sha512t24u
from .target import Prefilter, Rule, Target

log = logging.getLogger(__name__)

DEFAULT_SRA_PARQUET = "https://data-omicidx.cancerdatasci.org/sra/parquet/"
_TABLES = ("sra_studies", "sra_experiments", "sra_samples", "sra_runs")
_ABSTRACT_MAX = 4000
_TOP_ORGANISMS = 5
_TOP_ATTRIBUTES = 20
_ADMIN_TAGS = (
    r"^(insdc|ena|sra|submitter|external id|biosamplemodel|sample.?name|title|description)"
)
_REVIEW_QUEUE = 25


# -- source ------------------------------------------------------------------------------


def open_sra(base: str) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with one view per SRA parquet file under ``base``."""
    if not base.endswith("/"):
        base += "/"
    con = duckdb.connect()
    if base.startswith("http"):
        con.execute("INSTALL httpfs; LOAD httpfs;")
    for name in _TABLES:
        path = (base + f"{name}.parquet").replace("'", "''")
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    return con


def select_studies(
    con: duckdb.DuckDBPyConnection,
    pf: Prefilter,
    *,
    studies: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    """Studies with ≥1 experiment passing the prefilter; explicit ``studies`` bypass it."""
    if studies is not None:
        return sorted(set(studies))
    rows = con.execute(
        """
        SELECT e.study_accession
        FROM sra_experiments e JOIN sra_samples s ON s.accession = e.sample_accession
        WHERE list_contains($sources, e.library_source)
          AND list_contains($strategies, e.library_strategy)
          AND list_contains($organisms, s.organism)
        GROUP BY 1 ORDER BY 1
        """,
        {
            "sources": pf.library_source,
            "strategies": pf.library_strategy,
            "organisms": pf.organisms,
        },
    ).fetchall()
    accs = [r[0] for r in rows if r[0]]
    return accs[:limit] if limit else accs


def _qualify(
    con: duckdb.DuckDBPyConnection, pf: Prefilter, studies: list[str], apply_organisms: bool
) -> None:
    """Materialise ``_qexp`` (qualifying experiments) and ``_qsamp`` (their samples).

    Duplicate accessions in the export are collapsed with ``min()`` so the result, and
    hence every state digest, is deterministic.
    """
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _sel AS SELECT DISTINCT unnest($s::VARCHAR[]) AS acc",
        {"s": studies},
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _qexp AS
        SELECT e.accession AS experiment_accession,
               min(e.study_accession) AS study_accession,
               min(e.sample_accession) AS sample_accession,
               min(e.platform) AS platform,
               min(e.library_strategy) AS library_strategy
        FROM sra_experiments e
        WHERE e.study_accession IN (SELECT acc FROM _sel)
          AND list_contains($sources, e.library_source)
          AND list_contains($strategies, e.library_strategy)
        GROUP BY e.accession
        """,
        {"sources": pf.library_source, "strategies": pf.library_strategy},
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _qsamp AS
        SELECT s.accession, min(s.organism) AS organism, min(s.biosample) AS biosample,
               min(s.attributes) AS attributes
        FROM sra_samples s
        WHERE s.accession IN (SELECT sample_accession FROM _qexp)
        GROUP BY s.accession
        """
    )
    if apply_organisms:
        con.execute(
            """
            DELETE FROM _qexp WHERE sample_accession IS NULL OR sample_accession NOT IN (
                SELECT accession FROM _qsamp WHERE list_contains($organisms, organism))
            """,
            {"organisms": pf.organisms},
        )


def _counts(rows: list[tuple[Any, ...]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for study, key, n in rows:
        out.setdefault(study, {})[key] = n
    return out


def build_states(
    con: duckdb.DuckDBPyConnection,
    pf: Prefilter,
    study_accessions: list[str],
    *,
    apply_organisms: bool = True,
) -> dict[str, dict[str, Any]]:
    """Summarise each study's qualifying experiments into a decision state (SPEC 190)."""
    if not study_accessions:
        return {}
    _qualify(con, pf, study_accessions, apply_organisms)
    n_exp = dict(
        con.execute("SELECT study_accession, count(*) FROM _qexp GROUP BY 1").fetchall()
    )
    organisms = _counts(
        con.execute(
            """
            SELECT study_accession, organism, n FROM (
                SELECT q.study_accession, s.organism, count(DISTINCT q.sample_accession) AS n,
                       row_number() OVER (PARTITION BY q.study_accession
                                          ORDER BY count(DISTINCT q.sample_accession) DESC,
                                                   s.organism) AS rn
                FROM _qexp q JOIN _qsamp s ON s.accession = q.sample_accession
                WHERE s.organism IS NOT NULL
                GROUP BY 1, 2)
            WHERE rn <= $top
            """,
            {"top": _TOP_ORGANISMS},
        ).fetchall()
    )
    strategies = _counts(
        con.execute(
            "SELECT study_accession, library_strategy, count(*) FROM _qexp "
            "WHERE library_strategy IS NOT NULL GROUP BY 1, 2"
        ).fetchall()
    )
    platforms = _counts(
        con.execute(
            "SELECT study_accession, platform, count(*) FROM _qexp "
            "WHERE platform IS NOT NULL GROUP BY 1, 2"
        ).fetchall()
    )
    attributes: dict[str, list[str]] = {}
    for study, line in con.execute(
        """
        WITH flat AS (
            SELECT q.study_accession, q.sample_accession, unnest(s.attributes) AS kv
            FROM _qexp q JOIN _qsamp s ON s.accession = q.sample_accession
        ), kv AS (
            SELECT DISTINCT study_accession, sample_accession, kv.tag AS tag, kv.value AS value
            FROM flat
        ), ranked AS (
            SELECT study_accession, tag, value, count(*) AS n,
                   row_number() OVER (PARTITION BY study_accession
                                      ORDER BY count(*) DESC, tag, value) AS rn
            FROM kv
            WHERE tag IS NOT NULL AND value IS NOT NULL
              AND NOT regexp_matches(lower(tag), $admin)
            GROUP BY 1, 2, 3
        )
        SELECT study_accession, tag || ': ' || value || ' (' || n || ')'
        FROM ranked WHERE rn <= $top ORDER BY study_accession, rn
        """,
        {"admin": _ADMIN_TAGS, "top": _TOP_ATTRIBUTES},
    ).fetchall():
        attributes.setdefault(study, []).append(line)
    meta = {
        acc: (title, bioproject, abstract)
        for acc, title, bioproject, abstract in con.execute(
            """
            SELECT accession, min(title), min(bioproject), min(left(abstract, $max))
            FROM sra_studies WHERE accession IN (SELECT acc FROM _sel) GROUP BY 1
            """,
            {"max": _ABSTRACT_MAX},
        ).fetchall()
    }
    states: dict[str, dict[str, Any]] = {}
    for acc in sorted(set(study_accessions)):
        if acc not in n_exp:
            continue
        title, bioproject, abstract = meta.get(acc, (None, None, None))
        states[acc] = {
            "study_accession": acc,
            "bioproject": bioproject,
            "title": title,
            "abstract": abstract,
            "n_experiments": n_exp[acc],
            "organisms": organisms.get(acc, {}),
            "library_strategies": strategies.get(acc, {}),
            "platforms": platforms.get(acc, {}),
            "sample_attributes": attributes.get(acc, []),
        }
    return states


# -- scoring -----------------------------------------------------------------------------


def score_rules(
    answers: dict[str, dict[str, Any]], rules: list[Rule], questions: dict[str, dict[str, Any]]
) -> tuple[Decision, dict[str, float]]:
    """Every rule ≥ include_at → include; any < review_at → exclude; else review."""
    scores: dict[str, float] = {}
    decision: Decision = "include"
    for rule in rules:
        a = answers[rule.question]
        if questions[rule.question]["type"] == "noul":
            score = float(a["noul"])
        else:
            score = float(sum(a["probabilities"][o] for o in rule.accept))
        scores[rule.question] = score
        if score < rule.review_at:
            decision = "exclude"
        elif score < rule.include_at and decision == "include":
            decision = "review"
    return decision, scores


# -- readsets ----------------------------------------------------------------------------


def _readsets(
    con: duckdb.DuckDBPyConnection,
    pf: Prefilter,
    study_accessions: list[str],
    apply_organisms: bool,
) -> tuple[list[ReadsetRow], int]:
    if not study_accessions:
        return [], 0
    _qualify(con, pf, study_accessions, apply_organisms)
    rows = con.execute(
        """
        WITH runs AS (
            SELECT DISTINCT accession, experiment_accession FROM sra_runs
            WHERE experiment_accession IN (SELECT experiment_accession FROM _qexp)
        ), proj AS (
            SELECT accession, min(bioproject) AS bioproject FROM sra_studies
            WHERE accession IN (SELECT acc FROM _sel) GROUP BY 1
        )
        SELECT q.study_accession, p.bioproject, q.sample_accession, s.biosample, s.organism,
               list(DISTINCT r.accession ORDER BY r.accession) AS runs
        FROM _qexp q
        JOIN runs r ON r.experiment_accession = q.experiment_accession
        LEFT JOIN _qsamp s ON s.accession = q.sample_accession
        LEFT JOIN proj p ON p.accession = q.study_accession
        WHERE q.sample_accession IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5
        ORDER BY 1, 3
        """
    ).fetchall()
    out: list[ReadsetRow] = []
    skipped = 0
    for study, bioproject, sample, biosample, organism, runs in rows:
        units = [insdc_unit(r) for r in runs if RUN_ACCESSION.match(r)]
        skipped += len(runs) - len(units)
        if not units:
            continue
        out.append(
            ReadsetRow(
                readset_id=readset_id(units),
                units=sorted(units),
                study_accession=study,
                bioproject=bioproject,
                sra_sample=sample,
                biosample=biosample,
                organism=organism,
                n_runs=len(units),
            )
        )
    return out, skipped


def build_readsets(
    con: duckdb.DuckDBPyConnection,
    pf: Prefilter,
    study_accessions: list[str],
    *,
    apply_organisms: bool = True,
) -> list[ReadsetRow]:
    """One readset per sample of the given studies' qualifying experiments (SPEC 170)."""
    return _readsets(con, pf, study_accessions, apply_organisms)[0]


# -- outputs -----------------------------------------------------------------------------


def _write_parquet(path: Path, rows: list[dict[str, Any]], columns: dict[str, str]) -> None:
    """Write ``rows`` to parquet with explicit column types (via NDJSON + DuckDB)."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".ndjson", dir=path.parent, delete=False, encoding="utf-8"
    ) as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
        tmp = Path(fh.name)
    try:
        cols = ", ".join(f"'{k}': '{v}'" for k, v in columns.items())
        select = ", ".join(columns)
        src = str(tmp).replace("'", "''")
        dst = str(path).replace("'", "''")
        duckdb.execute(
            f"COPY (SELECT {select} FROM read_json('{src}', format='newline_delimited', "
            f"columns={{{cols}}})) TO '{dst}' (FORMAT parquet)"
        )
    finally:
        tmp.unlink(missing_ok=True)


_STUDY_COLUMNS = {
    "study_accession": "VARCHAR",
    "bioproject": "VARCHAR",
    "title": "VARCHAR",
    "n_experiments": "BIGINT",
    "decision": "VARCHAR",
    "rule_scores": "VARCHAR",
    "facets": "VARCHAR",
    "answers": "VARCHAR",
    "error": "VARCHAR",
    "model": "VARCHAR",
    "question_set_digest": "VARCHAR",
    "state_digest": "VARCHAR",
    "snapshot": "VARCHAR",
    "decided_at": "TIMESTAMP",
}
_READSET_COLUMNS = {
    "readset_id": "VARCHAR",
    "units": "VARCHAR[]",
    "study_accession": "VARCHAR",
    "bioproject": "VARCHAR",
    "sra_sample": "VARCHAR",
    "biosample": "VARCHAR",
    "organism": "VARCHAR",
    "n_runs": "BIGINT",
}
_STATE_COLUMNS = {"study_accession": "VARCHAR", "state_json": "VARCHAR", "state_digest": "VARCHAR"}


def _study_row(d: StudyDecision) -> dict[str, Any]:
    row = d.model_dump(mode="json")
    for key in ("rule_scores", "facets", "answers"):
        row[key] = canonical_json(row[key]).decode("utf-8")
    return row


def _snapshot(base: str) -> str | None:
    if not base.startswith("http"):
        return None
    try:
        resp = httpx.head(base + "sra_studies.parquet", timeout=30.0, follow_redirects=True)
    except httpx.HTTPError:
        return None
    return resp.headers.get("last-modified") if resp.is_success else None


def _summary(
    *,
    target: Target,
    snapshot: str | None,
    model: str | None,
    qdigest: str,
    counts: dict[str, Any],
    decisions: list[StudyDecision],
    omitted: list[str],
    facets: list[str],
) -> str:
    lines = [
        f"# Discovery: {target.name}",
        "",
        f"- snapshot: {snapshot or 'unknown'}",
        f"- model: {model or 'none (dry run)'}",
        f"- question set digest: `{qdigest}`",
        "",
        "## Counts",
        "",
        *(f"- {k}: {v}" for k, v in counts.items()),
    ]
    if decisions:
        by_decision: Counter[str] = Counter(d.decision for d in decisions)
        lines += ["", "## By decision", "", "| decision | studies |", "|---|---|"]
        lines += [f"| {k} | {by_decision[k]} |" for k in ("include", "review", "exclude", "error")]
        for facet in facets:
            lines += ["", f"## By {facet} (include / review / exclude)", "",
                      f"| {facet} | include | review | exclude |", "|---|---|---|---|"]
            table: dict[str, Counter[str]] = {}
            for d in decisions:
                if d.decision != "error":
                    table.setdefault(d.facets.get(facet, "?"), Counter())[d.decision] += 1
            for value, c in sorted(table.items(), key=lambda kv: -sum(kv[1].values())):
                lines.append(f"| {value} | {c['include']} | {c['review']} | {c['exclude']} |")
        review = sorted(
            (d for d in decisions if d.decision == "review"),
            key=lambda d: (min(d.rule_scores.values(), default=0.0), d.study_accession),
        )[:_REVIEW_QUEUE]
        if review:
            lines += ["", f"## Review queue (lowest rule score, top {_REVIEW_QUEUE})", "",
                      "| study | bioproject | scores | title |", "|---|---|---|---|"]
            for d in review:
                scores = ", ".join(f"{k}={v:.2f}" for k, v in d.rule_scores.items())
                title = (d.title or "").replace("|", "/")[:100]
                lines.append(f"| {d.study_accession} | {d.bioproject or ''} | {scores} | {title} |")
        errors = [d for d in decisions if d.decision == "error"]
        if errors:
            lines += ["", "## Errors", ""]
            lines += [f"- {d.study_accession}: {d.error}" for d in errors]
    if omitted:
        lines += ["", "## Omitted (no qualifying experiments)", ""]
        lines += [f"- {acc}" for acc in omitted]
    return "\n".join(lines) + "\n"


# -- cache -------------------------------------------------------------------------------

_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS decisions (
    study_accession VARCHAR, model VARCHAR, question_set_digest VARCHAR,
    state_digest VARCHAR, answers VARCHAR, decided_at TIMESTAMP,
    PRIMARY KEY (study_accession, model, question_set_digest, state_digest))
"""


# -- orchestration -----------------------------------------------------------------------


def run_discovery(
    target: Target,
    *,
    out: Path,
    base: str = DEFAULT_SRA_PARQUET,
    studies: list[str] | None = None,
    limit: int | None = None,
    model: str | None = None,
    workers: int = 8,
    dry_run: bool = False,
    client: DecisionClient | None = None,
) -> dict[str, Any]:
    """Select → state → screen (cached) → score → readsets → outputs. SPEC 190."""
    disc = target.discovery
    if disc is None:
        raise ValueError(f"target {target.name!r} has no discovery config")
    if not base.endswith("/"):
        base += "/"
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot(base)
    con = open_sra(base)
    apply_organisms = studies is None

    selected = select_studies(con, disc.prefilter, studies=studies, limit=limit)
    log.info("selected %d studies", len(selected))
    states = build_states(con, disc.prefilter, selected, apply_organisms=apply_organisms)
    omitted = [acc for acc in selected if acc not in states]
    log.info("built %d states (%d omitted)", len(states), len(omitted))
    qdigest = sha512t24u(canonical_json(disc.questions))
    sdigests = {acc: sha512t24u(canonical_json(s)) for acc, s in states.items()}

    if dry_run:
        _write_parquet(
            out / "states.parquet",
            [
                {"study_accession": acc, "state_json": canonical_json(s).decode("utf-8"),
                 "state_digest": sdigests[acc]}
                for acc, s in states.items()
            ],
            _STATE_COLUMNS,
        )
        counts: dict[str, Any] = {"selected": len(selected), "states": len(states),
                                  "omitted": len(omitted)}
        (out / "summary.md").write_text(
            _summary(target=target, snapshot=snapshot, model=None, qdigest=qdigest,
                     counts=counts, decisions=[], omitted=omitted, facets=disc.facets),
            encoding="utf-8",
        )
        return counts

    client = client or make_decision_client(model or disc.decision_model)
    model_name = str(client.describe()["model"])

    cache = duckdb.connect(str(out / "decisions.duckdb"))
    try:
        cache.execute(_CACHE_DDL)
        cached: dict[tuple[str, str], tuple[dict[str, dict[str, Any]], datetime]] = {
            (acc, sd): (json.loads(ans), at)
            for acc, sd, ans, at in cache.execute(
                "SELECT study_accession, state_digest, answers, decided_at FROM decisions "
                "WHERE model = ? AND question_set_digest = ?",
                [model_name, qdigest],
            ).fetchall()
        }
        results: dict[str, tuple[dict[str, dict[str, Any]] | None, str | None, datetime]] = {}
        todo = []
        for acc in states:
            hit = cached.get((acc, sdigests[acc]))
            if hit is not None:
                results[acc] = (hit[0], None, hit[1])
            else:
                todo.append(acc)
        log.info("screening %d studies (%d cached)", len(todo), len(results))
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(client.decide, state=states[acc], questions=disc.questions): acc
                for acc in todo
            }
            for i, fut in enumerate(as_completed(futures), 1):
                acc = futures[fut]
                now = datetime.now(UTC).replace(tzinfo=None)
                try:
                    answers = fut.result()
                except DecisionError as exc:
                    results[acc] = (None, str(exc), now)
                    log.warning("%s: %s", acc, exc)
                else:
                    results[acc] = (answers, None, now)
                    cache.execute(
                        "INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
                        [acc, model_name, qdigest, sdigests[acc],
                         canonical_json(answers).decode("utf-8"), now],
                    )
                if i % 100 == 0 or i == len(todo):
                    log.info("screened %d/%d", i, len(todo))
    finally:
        cache.close()

    decisions: list[StudyDecision] = []
    for acc, state in states.items():
        found, error, at = results[acc]
        if found is None:
            decision: Decision = "error"
            scores: dict[str, float] = {}
            facets: dict[str, str] = {}
        else:
            decision, scores = score_rules(found, disc.rules, disc.questions)
            facets = {f: found[f]["choice"] for f in disc.facets}
        decisions.append(
            StudyDecision(
                study_accession=acc, bioproject=state["bioproject"], title=state["title"],
                n_experiments=state["n_experiments"], decision=decision, rule_scores=scores,
                facets=facets, answers=found or {}, error=error, model=model_name,
                question_set_digest=qdigest, state_digest=sdigests[acc], snapshot=snapshot,
                decided_at=at,
            )
        )

    included = [d.study_accession for d in decisions if d.decision == "include"]
    readsets, skipped = _readsets(con, disc.prefilter, included, apply_organisms)
    _write_parquet(out / "studies.parquet", [_study_row(d) for d in decisions], _STUDY_COLUMNS)
    _write_parquet(
        out / "readsets.parquet", [r.model_dump(mode="json") for r in readsets], _READSET_COLUMNS
    )
    by = Counter(d.decision for d in decisions)
    counts = {
        "selected": len(selected),
        "screened": len(decisions),
        "omitted": len(omitted),
        "calls": len(todo),
        "cached": len(decisions) - len(todo),
        "include": by["include"],
        "review": by["review"],
        "exclude": by["exclude"],
        "error": by["error"],
        "readsets": len(readsets),
        "skipped_runs": skipped,
    }
    (out / "summary.md").write_text(
        _summary(target=target, snapshot=snapshot, model=model_name, qdigest=qdigest,
                 counts=counts, decisions=decisions, omitted=omitted, facets=disc.facets),
        encoding="utf-8",
    )
    return counts
