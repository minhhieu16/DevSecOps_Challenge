"""athena_scheduler.py - run a named Athena query file on a schedule and forward rows to detection_router.

Triggered by EventBridge Scheduler (hourly DET-007/008, daily DET-010) or manually for weekly reports.
Controls: ISO 27001 A.8.16; HIPAA 164.312(b).

Event shape:
  {"query_name": "DET-007-agent-access-denied",   # file name without .sql, from QUERY_DIR (default ./queries)
   "detection_id": "DET-007",                       # required for mode "detect"
   "mode": "detect",                                # "detect" (default): forward rows to the router; "report": no alerting
   "params": {"week_start": "2026-11-02", "week_end": "2026-11-09"}}   # optional {{placeholder}} values (ISO dates only)

Packaging: copy ../athena/*.sql into the Lambda zip under queries/. Only files there can run (name must match
^[A-Za-z0-9._-]+$, so no path traversal). Environment: ATHENA_DATABASE (audit), ATHENA_WORKGROUP (audit-detections),
ROUTER_FUNCTION_NAME (detection-router), QUERY_DIR, MAX_WAIT_SECONDS (840). The workgroup must define the
result location (enforced) and the Lambda role needs athena:*Query* on that workgroup, glue read on db audit,
S3 read on the audit prefixes and write on the results prefix, kms on alias/audit-logs, lambda:InvokeFunction on the router.
Python 3.12, stdlib + boto3 only.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import boto3

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

DATABASE = os.environ.get("ATHENA_DATABASE", "audit")
WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "audit-detections")
ROUTER = os.environ.get("ROUTER_FUNCTION_NAME", "detection-router")
QUERY_DIR = Path(os.environ.get("QUERY_DIR", Path(__file__).parent / "queries"))
MAX_WAIT = int(os.environ.get("MAX_WAIT_SECONDS", "840"))
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_FORWARD_ROWS = 100   # async Lambda payload limit is 256 KB; full results stay in Athena
PARAM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_athena = boto3.client("athena")
_lambda = boto3.client("lambda")


def load_query(name: str, params: dict[str, str]) -> str:
    """Read queries/<name>.sql and substitute {{key}} placeholders (values must be ISO dates)."""
    if not NAME_RE.match(name):
        raise ValueError(f"invalid query_name {name!r}")
    sql = (QUERY_DIR / f"{name}.sql").read_text(encoding="utf-8")
    for key, value in params.items():
        if not re.match(r"^[a-z_]+$", key) or not PARAM_RE.match(str(value)):
            raise ValueError(f"invalid param {key!r}={value!r}")
        sql = sql.replace("{{" + key + "}}", str(value))
    if "{{" in sql:
        raise ValueError("unresolved placeholders in query")
    return sql


def run_query(sql: str) -> str:
    """Start the query and block until it finishes; returns QueryExecutionId or raises."""
    qid = _athena.start_query_execution(QueryString=sql, QueryExecutionContext={"Database": DATABASE}, WorkGroup=WORKGROUP)["QueryExecutionId"]
    deadline = time.time() + MAX_WAIT
    delay = 1.0
    while time.time() < deadline:
        status = _athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            return qid
        if state in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"athena query {qid} {state}: {status.get('StateChangeReason', '')}")
        time.sleep(delay)
        delay = min(delay * 1.5, 10)
    _athena.stop_query_execution(QueryExecutionId=qid)
    raise TimeoutError(f"athena query {qid} exceeded {MAX_WAIT}s")


def fetch_rows(qid: str) -> list[dict[str, Any]]:
    """Return result rows as dicts (header row removed). Paginated."""
    rows: list[dict[str, Any]] = []
    header: list[str] | None = None
    for page in _athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for r in page["ResultSet"]["Rows"]:
            vals = [c.get("VarCharValue") for c in r["Data"]]
            if header is None:
                header = vals
            else:
                rows.append(dict(zip(header, vals)))
    return rows


def handler(event: dict, context: Any = None) -> dict:
    """Lambda entrypoint; see module docstring."""
    name = event["query_name"]
    mode = event.get("mode", "detect")
    sql = load_query(name, event.get("params", {}))
    qid = run_query(sql)
    rows = fetch_rows(qid)
    LOG.info("query %s -> %d rows (execution %s)", name, len(rows), qid)
    out = {"query_name": name, "query_execution_id": qid, "rows": len(rows)}
    if mode == "detect" and rows:
        payload = {"source": "athena", "detection_id": event["detection_id"], "query_name": name,
                   "query_execution_id": qid, "rows": rows[:MAX_FORWARD_ROWS], "total_rows": len(rows)}
        _lambda.invoke(FunctionName=ROUTER, InvocationType="Event", Payload=json.dumps(payload).encode())
        out["forwarded"] = True
    return out
