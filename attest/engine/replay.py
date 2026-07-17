"""Replay: re-derive a past verdict from stored artifacts and prove the
stored attestation is what this engine, on these inputs, produces.

The chain of custody a replay walks:

    attestation file -> self-check (id == hash(body))
      -> manifest, fetched from the object store by the hash the body cites
      -> each spec, fetched from the object store by the hash each control cites
      -> approval registry check for each spec (an approval revoked since
         the original run makes the replay fail loudly -- by design: a
         verdict whose authority was withdrawn should not re-verify)
      -> full re-evaluation, re-assembly, byte comparison

Anything short of an exact hash match is a failure with a named reason.
There is no fuzzy 'close enough' outcome, because the entire value of the
artifact is that there is nothing to argue about.
"""

from __future__ import annotations

from pathlib import Path

from .canonical import hash_obj
from .evaluator import evaluate_specs
from .report import build_attestation, load_attestation
from .snapshot import ObjectStore, TamperError


def replay(attestation_path: Path | str, state_root: Path | str, registry: dict, engine_version: str) -> dict:
    """Returns {"ok": bool, "attestation_id": ..., "reason": ...}."""
    attestation_id, body = load_attestation(attestation_path)  # raises ReportError if edited
    store = ObjectStore(state_root)

    manifest = store.get(body["snapshot"]["manifest_sha256"])  # TamperError if modified

    specs = []
    for control in body["controls"]:
        specs.append(store.get(control["spec_sha256"]))

    try:
        results = evaluate_specs(specs, manifest, store, registry)
    except TamperError as exc:
        return {"ok": False, "attestation_id": attestation_id, "reason": f"evidence integrity: {exc}"}

    replay_id, replay_body = build_attestation(results, manifest, engine_version)

    if hash_obj(replay_body) != hash_obj(body):
        return {
            "ok": False,
            "attestation_id": attestation_id,
            "reason": (
                f"re-derived attestation {replay_id} differs from stored {attestation_id}; "
                "inputs, engine version, or approvals have changed since the original run"
            ),
        }
    return {"ok": True, "attestation_id": attestation_id, "reason": "re-derived byte-for-byte"}
