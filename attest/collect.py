"""Evidence collection: the boundary where the nondeterministic world is
frozen into a snapshot.

This module is deliberately OUTSIDE attest/engine/ because it does the two
things the engine may never do: look at a clock (once, to stamp the
collection) and touch systems whose contents change. Everything downstream
of the manifest it produces is deterministic.

Collection is spec-driven and need-to-know: the collector reads exactly the
selectors the approved specs cite, in sorted order, and nothing else. An
adapter that cannot read a selector records an error for it; absence
becomes an unknown verdict downstream (then fail-closed), never a crash and
never a silent pass.

The only adapter in this build is `fs`, which resolves fs://relative/path
against a target root -- the demo's simulated target system. Real target
systems (cloud config APIs, IAM exports, SIEM queries) attach here as new
schemes with the same contract; see mcp_servers/ for the MCP-served form.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import spec_selectors


class CollectorError(RuntimeError):
    """A selector cannot be dispatched to any adapter (config error, not
    evidence absence -- absence is data, a missing adapter is a mistake)."""


def utc_now_stamp() -> str:
    """The single sanctioned clock read: one second-precision UTC stamp per
    collection pass. Everything downstream treats it as data."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _collect_fs(rel_path: str, target_root: Path) -> dict:
    candidate = (target_root / rel_path).resolve()
    root = target_root.resolve()
    if root not in candidate.parents and candidate != root:
        return {"error": f"selector escapes the target root: {rel_path}"}
    if not candidate.is_file():
        return {"error": f"no such file under target root: {rel_path}"}
    raw = candidate.read_bytes()
    if rel_path.endswith(".json"):
        try:
            return {"body": json.loads(raw.decode("utf-8")), "content_type": "application/json"}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {"error": f"unparseable JSON evidence at {rel_path}: {exc}"}
    try:
        return {"body": {"raw_text": raw.decode("utf-8")}, "content_type": "text/plain"}
    except UnicodeDecodeError as exc:
        return {"error": f"undecodable text evidence at {rel_path}: {exc}"}


def collect_for_specs(specs: list[dict], target_root: Path | str, collected_at: str | None = None) -> tuple[list[dict], str]:
    """Collect every selector the given specs cite. Returns (records,
    collected_at). Pass collected_at explicitly for reproducible fixtures;
    omit it for a live collection stamped once, here, now."""
    target_root = Path(target_root)
    stamp = collected_at if collected_at is not None else utc_now_stamp()

    selectors: set[str] = set()
    for spec in specs:
        selectors.update(spec_selectors(spec))

    records = []
    for selector in sorted(selectors):
        scheme, _, rest = selector.partition("://")
        if scheme == "fs":
            result = _collect_fs(rest, target_root)
        else:
            raise CollectorError(f"no adapter for scheme {scheme!r} (selector {selector})")
        records.append({"selector": selector, **result})
    return records, stamp
