"""Attestation assembly: the byte-stable artifact.

An attestation body contains, in full: the engine version, the snapshot
identity (id, manifest hash, collected_at), and per-control results with
spec hashes and evidence hashes. It contains no wall-clock timestamp of its
own -- the snapshot's collected_at is the attestation's notion of time, so
producing the report twice, or in five years, yields identical bytes.

The attestation id is the canonical hash of the body. The id is therefore a
claim anyone can check by rehashing, which is what --replay does.

Controls are sorted by control_id so the order specs were listed on a
command line cannot produce two different attestations of the same facts.
"""

from __future__ import annotations

from pathlib import Path

from .canonical import hash_obj, read_json, write_canonical
from .snapshot import snapshot_id_for

ATTEST_VERSION = "1.0"
_ID_PREFIX_LEN = 16


class ReportError(ValueError):
    """An attestation file is malformed or fails its self-check."""


def build_attestation(spec_results: list[dict], manifest: dict, engine_version: str) -> tuple[str, dict]:
    controls = sorted(spec_results, key=lambda r: r["control_id"])
    tally = {"pass": 0, "fail": 0, "unknown": 0}
    for result in controls:
        tally[result["verdict"]] += 1
    if tally["fail"]:
        rollup = "fail"
    elif tally["unknown"]:
        rollup = "unknown"
    else:
        rollup = "pass"
    body = {
        "attest_version": ATTEST_VERSION,
        "engine_version": engine_version,
        "snapshot": {
            "id": snapshot_id_for(manifest),
            "manifest_sha256": hash_obj(manifest),
            "collected_at": manifest["collected_at"],
        },
        "controls": controls,
        "rollup": {"verdict": rollup, "counts": tally, "total": len(controls)},
    }
    attestation_id = "att-" + hash_obj(body)[:_ID_PREFIX_LEN]
    return attestation_id, body


def write_attestation(state_root: Path | str, attestation_id: str, body: dict) -> Path:
    directory = Path(state_root) / "attestations"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{attestation_id}.json"
    write_canonical(path, {"attestation_id": attestation_id, "body": body})
    return path


def load_attestation(path: Path | str) -> tuple[str, dict]:
    """Load and self-check: the stored id must be the body's hash."""
    wrapper = read_json(path)
    if not isinstance(wrapper, dict) or "attestation_id" not in wrapper or "body" not in wrapper:
        raise ReportError(f"attestation file {path} is malformed")
    attestation_id, body = wrapper["attestation_id"], wrapper["body"]
    expected = "att-" + hash_obj(body)[:_ID_PREFIX_LEN]
    if attestation_id != expected:
        raise ReportError(
            f"attestation {attestation_id} fails its self-check: body hashes to {expected} -- "
            "the report has been modified after it was written"
        )
    return attestation_id, body
