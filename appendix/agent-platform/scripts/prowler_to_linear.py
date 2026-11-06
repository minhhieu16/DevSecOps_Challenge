"""Placeholder: open/update Linear issues (team SEC) for NEW Prowler FAIL findings (DET-012).

TODO: parse *.ocsf.json in PROWLER_OUTPUT_DIR, dedupe by (check id, resource uid, account) against open
Linear issues labelled `prowler`, create issues via the Linear GraphQL API (LINEAR_API_KEY), set priority by
severity (critical/high -> urgent/high). Never log the API key.
"""
import json
import os
import pathlib


def main() -> None:
    out = pathlib.Path(os.environ.get("PROWLER_OUTPUT_DIR", "out"))
    fails = 0
    for f in out.glob("*.ocsf.json"):
        for item in json.loads(f.read_text()):
            if item.get("status_code") == "FAIL":
                fails += 1
    print(f"[placeholder] {fails} FAIL findings found; Linear sync not implemented")


if __name__ == "__main__":
    main()
