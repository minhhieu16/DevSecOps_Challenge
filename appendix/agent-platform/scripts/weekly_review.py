#!/usr/bin/env python3
"""Weekly review report generator (stdlib + boto3, Python 3.12).

Purpose: run the Athena weekly-review queries in detections/athena/weekly-review-*.sql against the
`audit` database, poll for completion, and render evidence/weekly/YYYY-Www.md for sign-off via PR.
Controls: HIPAA 164.308(a)(1)(ii)(D) information system activity review; ISO 27001 A.8.15/A.8.16.

SQL files may use the placeholders {{week_start}} and {{week_end}} (ISO dates, UTC, end exclusive).
Section routing is by keyword in the file name (weekly-review-<topic>.sql):
  debug -> debug sessions | breakglass/break-glass -> break-glass | runbook -> runbook runs |
  critical/alert -> critical alerts | denied/accessdenied -> AccessDenied trend | other -> extra sections.
Read-only: only SELECT statements are allowed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys
import time

SECTIONS = [
    ("debug", "Debug sessions (prod-debug / prod-debug-agent)", ["debug"]),
    ("breakglass", "Break-glass usage and reconciliation", ["breakglass", "break-glass", "break_glass"]),
    ("runbook", "Runbook runs (production-ops)", ["runbook", "ops"]),
    ("critical", "Critical alerts and handling", ["critical", "alert"]),
    ("denied", "AccessDenied trend", ["denied", "accessdenied"]),
]
POLL_SECONDS = 2
TIMEOUT_SECONDS = 600


def iso_week_bounds(today: dt.date) -> tuple[str, dt.date, dt.date]:
    """Previous full ISO week (Mon..Sun) relative to today; end is exclusive."""
    this_monday = today - dt.timedelta(days=today.weekday())
    start = this_monday - dt.timedelta(days=7)
    iso = start.isocalendar()
    return f"{iso.year}-W{iso.week:02d}", start, this_monday


def route(filename: str) -> str:
    name = filename.lower()
    for key, _title, words in SECTIONS:
        if any(w in name for w in words):
            return key
    return "other"


def run_query(athena, sql: str, database: str, workgroup: str, results_location: str | None) -> list[list[str]]:
    # Strip leading SQL comments (-- line and /* block */) before the read-only check.
    body = re.sub(r"^(\s*(--[^\n]*\n|/\*.*?\*/))*", "", sql, flags=re.DOTALL)
    if not re.match(r"^\s*(with|select)\b", body, re.IGNORECASE) or ";" in body.strip().rstrip(";"):
        raise ValueError("only a single SELECT/WITH query is allowed")
    kwargs: dict = {
        "QueryString": sql,
        "QueryExecutionContext": {"Database": database},
        "WorkGroup": workgroup,
    }
    if results_location:
        kwargs["ResultConfiguration"] = {"OutputLocation": results_location}
    qid = athena.start_query_execution(**kwargs)["QueryExecutionId"]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        status = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"query {qid} {state}: {status.get('StateChangeReason', '')}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"query {qid} timed out")
        time.sleep(POLL_SECONDS)
    rows: list[list[str]] = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for row in page["ResultSet"]["Rows"]:
            rows.append([c.get("VarCharValue", "") for c in row["Data"]])
    return rows  # first row is the header


def md_table(rows: list[list[str]], limit: int = 200) -> str:
    if not rows:
        return "_No rows._"
    header, body = rows[0], rows[1:]
    if not body:
        return "_No rows._"
    esc = lambda s: s.replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(esc(h) for h in header) + " |", "|" + "---|" * len(header)]
    for r in body[:limit]:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    if len(body) > limit:
        lines.append(f"\n_{len(body) - limit} more rows truncated; see Athena query results._")
    return "\n".join(lines)


def render(week: str, start: dt.date, end: dt.date, results: dict[str, list[tuple[str, str]]]) -> str:
    out = [
        f"# Weekly review {week}",
        "",
        f"Period (UTC): {start.isoformat()} to {(end - dt.timedelta(days=1)).isoformat()}",
        f"Generated: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by scripts/weekly_review.py",
        "",
        "Controls: HIPAA 164.308(a)(1)(ii)(D), ISO 27001 A.8.15 / A.8.16",
        "",
    ]
    for key, title, _ in SECTIONS:
        out += [f"## {title}", ""]
        items = results.get(key, [])
        if not items:
            out += ["_No query file found for this section (detections/athena/weekly-review-*.sql)._", ""]
        for fname, body in items:
            out += [f"Query: `{fname}`", "", body, ""]
    for fname, body in results.get("other", []):
        out += [f"## Additional: {fname}", "", body, ""]
    out += [
        "## Prowler new fails",
        "",
        "_Placeholder: list new FAIL findings since last week from "
        "s3://papaya-audit-logs/evidence/prowler/ (see prowler-weekly workflow / Linear SEC issues)._",
        "",
        "## Reviewer checks",
        "",
        "- [ ] Every prod-debug* session has a ticket and duration < 1h (target >= 98% with ticket)",
        "- [ ] Every runbook run has a named approver different from the requester",
        "- [ ] Every break-glass use is reconciled (PR merged) within 48h",
        "- [ ] Critical alerts were acknowledged < 15 minutes; follow-ups tracked in Linear",
        "- [ ] AccessDenied trend explained (no unexplained spikes after governance releases)",
        "- [ ] Out-of-pipeline prod changes = 0 (DET-001/002/003 silent)",
        "",
        "## Sign-off",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Reviewer (platform) | |",
        "| Reviewer (security) | |",
        "| Date | |",
        "| Exceptions / follow-up tickets | |",
        "| Decision | [ ] Signed off  [ ] Signed off with exceptions |",
        "",
        "Sign-off = approving the PR that adds this file.",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queries-dir", default="detections/athena")
    ap.add_argument("--database", default="audit")
    ap.add_argument("--workgroup", default="audit-weekly")
    ap.add_argument("--output-dir", default="evidence/weekly")
    ap.add_argument("--results-location", default=None, help="s3:// output location if the workgroup has none")
    ap.add_argument("--region", default="ap-southeast-1")
    ap.add_argument("--today", default=None, help="override date YYYY-MM-DD (testing)")
    ap.add_argument("--dry-run", action="store_true", help="list queries and render with empty results; no AWS calls")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    week, start, end = iso_week_bounds(today)
    files = sorted(pathlib.Path(args.queries_dir).glob("weekly-review-*.sql"))
    if not files:
        print(f"no weekly-review-*.sql found in {args.queries_dir}", file=sys.stderr)
        return 1

    athena = None
    if not args.dry_run:
        import boto3  # imported lazily so --dry-run works without boto3

        athena = boto3.client("athena", region_name=args.region)
    results: dict[str, list[tuple[str, str]]] = {}
    for f in files:
        sql = f.read_text().replace("{{week_start}}", start.isoformat()).replace("{{week_end}}", end.isoformat())
        print(f"running {f.name}")
        if athena is None:
            body = "_dry run_"
        else:
            try:
                body = md_table(run_query(athena, sql, args.database, args.workgroup, args.results_location))
            except Exception as exc:  # report, do not hide: reviewer must see failed queries
                body = f"**QUERY FAILED:** `{type(exc).__name__}: {exc}`"
                print(body, file=sys.stderr)
        results.setdefault(route(f.name), []).append((f.name, body))

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{week}.md"
    target.write_text(render(week, start, end, results))
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
