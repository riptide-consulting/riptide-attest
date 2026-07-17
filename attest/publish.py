"""The gated publisher: Attest's one external side effect.

Producing an attestation is reversible (a local file). Publishing it to a
tracker or mailing it to an auditor is not. So publishing carries the same
two-layer gate as RIA's writers, with the identical placement argument: the
human key is checked INSIDE the function that performs the write, at the
moment of the write, so no refactor of calling code can forget it.

The key is ATTEST_PUBLISH_APPROVED, read from the environment at the moment
of use, deliberately never stored in any configuration file.
"""

from __future__ import annotations

import os
from pathlib import Path

from .audit import audit
from .engine import load_attestation


def _require_approval() -> None:
    if os.environ.get("ATTEST_PUBLISH_APPROVED", "").strip().lower() not in ("1", "true"):
        raise PermissionError(
            "ATTEST_PUBLISH_APPROVED is not set -- refusing to publish the attestation externally. "
            "Set ATTEST_PUBLISH_APPROVED=1 to explicitly approve this external side effect."
        )


def publish_attestation(attestation_path: Path | str) -> dict:
    """Publish an attestation record to the configured tracker.

    Gate order matters: the approval check runs first, so the demo (no key
    set) exercises and displays the refusal. With the key set, the tracker
    integration (mcp_servers/attest_tracker) performs the write; without
    credentials configured it reports exactly what it would have written.
    """
    attestation_id, body = load_attestation(attestation_path)  # self-check before any external reach
    _require_approval()  # the human key, at the point of effect

    notion_key = os.environ.get("NOTION_API_KEY", "").strip()
    if not notion_key:
        audit("publish.skipped", attestation_id=attestation_id, reason="no tracker credentials")
        return {
            "published": False,
            "attestation_id": attestation_id,
            "reason": "approved, but no tracker credentials configured (NOTION_API_KEY); nothing was sent",
        }

    from mcp_servers.attest_tracker.writer import publish_record  # point-of-use import

    result = publish_record(attestation_id, body)
    audit("publish.sent", attestation_id=attestation_id, target=result.get("target"))
    return {"published": True, "attestation_id": attestation_id, **result}
