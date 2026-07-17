"""Operational audit log: one JSONL line per CLI action.

This is the operational record (who ran what, when, on which hashes), not
the attestation itself -- so unlike the engine, wall-clock timestamps
belong here. Same discipline as RIA's logs/ria.log: structured, one line
per decision, plain JSONL so a SIEM ingests it without conversion.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("logs") / "attest.log"


def audit(action: str, **fields: object) -> None:
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        **fields,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
