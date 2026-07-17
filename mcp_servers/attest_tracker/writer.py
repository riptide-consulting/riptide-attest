"""The tracker port, instantiated as Notion: one page per published
attestation.

publish_record() is the only export and it is deliberately dumb: it holds
no authority, applies no verdict logic, and re-reads its credentials from
the environment at the moment of use. Every check that matters happens
upstream in attest/publish.py -- the attestation self-check
(load_attestation re-hashes the body against the id, attest/engine/
report.py) and the human key (_require_approval reads
ATTEST_PUBLISH_APPROVED at the point of the write). Swapping this file's
Notion calls for ServiceNow or Jira changes nothing upstream; the argument
is laid out in mcp_servers/README.md.

notion-client is imported lazily inside the function, so this module (and
attest/publish.py, which imports it at point of use) stays importable on
machines without the tracker integration installed.
"""

from __future__ import annotations

import os


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set -- the tracker integration is unconfigured; "
            "set it in the environment (never in a committed file) to publish"
        )
    return value


def publish_record(attestation_id: str, body: dict) -> dict:
    """Create one Notion page titled with the attestation id.

    The page carries the rollup verdict, the pass/fail/unknown counts,
    the snapshot id and its collected_at, and the engine version --
    nothing else leaves the machine. Returns {target, page_id, url} for
    the audit log in attest/publish.py.
    """
    # This function is only ever reached AFTER attest/publish.py's
    # _require_approval() human-key check: by the time control arrives
    # here, a human has set ATTEST_PUBLISH_APPROVED for this invocation.
    # It must never grow a second entry point that skips that gate.
    api_key = _require_env("NOTION_API_KEY")  # read at point of use, never cached
    database_id = _require_env("NOTION_DATABASE_ID")

    from notion_client import Client  # lazy: only the approved, configured path pays this import

    rollup = body["rollup"]
    counts = rollup["counts"]
    snapshot = body["snapshot"]

    def _paragraph(text: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    client = Client(auth=api_key)
    page = client.pages.create(
        parent={"database_id": database_id},
        # The key "title" addresses the database's title property whatever
        # its display name is, so this works against any database schema.
        properties={"title": {"title": [{"type": "text", "text": {"content": attestation_id}}]}},
        children=[
            _paragraph(
                f"rollup: {rollup['verdict']} "
                f"(pass {counts['pass']}, fail {counts['fail']}, "
                f"unknown {counts['unknown']} of {rollup['total']})"
            ),
            _paragraph(f"snapshot: {snapshot['id']} (collected_at {snapshot['collected_at']})"),
            _paragraph(f"engine {body['engine_version']}, attestation schema {body['attest_version']}"),
            _paragraph(
                "The canonical artifact is the local attestation JSON; "
                "this page is a pointer, not a proof."
            ),
        ],
    )
    return {"target": "notion", "page_id": page["id"], "url": page.get("url")}
