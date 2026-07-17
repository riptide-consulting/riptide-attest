"""PostToolUse observer: one JSONL line per tool event.

Same discipline as attest/audit.py's operational log: structured, one
line per event, append-only, plain JSONL. The record is deliberately
small -- ts, tool, file_path when present -- an audit trail of which
files the session's tools touched, not a transcript.

This hook observes; it never blocks. It exits 0 no matter what, including
on malformed stdin.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT / "logs" / "hook_audit.jsonl"


def main() -> None:
    event = json.load(sys.stdin)
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": event.get("tool_name") or "unknown",
    }
    file_path = (event.get("tool_input") or {}).get("file_path")
    if file_path:
        record["file_path"] = str(file_path)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_PATH, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # an observer must never block the tool pipeline
    sys.exit(0)
