"""Freeze the demo approvals and golden artifacts.

Run once at build time (and again only when specs, fixtures, or the engine
version change -- any golden churn outside those events is a determinism
regression by definition, which is exactly what the golden tests exist to
catch):

  1. approve the three demo specs into registry/approved.json,
  2. build the frozen-time snapshot into tests/golden/state/,
  3. evaluate and write the golden attestation + drift report.

Approval timestamps here are fixed, not wall-clock: the registry is a
committed fixture and must not churn on re-freeze.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from attest.collect import collect_for_specs
from attest.engine import (
    ENGINE_VERSION,
    ObjectStore,
    approve_spec,
    build_attestation,
    build_manifest,
    diff_attestations,
    empty_registry,
    ensure_valid,
    evaluate_specs,
    hash_obj,
    read_json,
    save_registry,
    write_attestation,
    write_canonical,
    write_snapshot,
)

APPROVER = "drew.poole"
APPROVED_AT = "2026-07-17T00:00:00Z"


def main() -> int:
    demo_config = read_json(ROOT / "fixtures" / "demo_config.json")
    spec_paths = sorted((ROOT / "specs").glob("*.json"))
    specs = [ensure_valid(read_json(p)) for p in spec_paths]

    registry = empty_registry()
    for spec in specs:
        registry, digest = approve_spec(registry, spec, APPROVER, APPROVED_AT)
        print(f"approved {spec['control_id']}: {digest}")
    save_registry(ROOT / "registry" / "approved.json", registry)

    golden_state = ROOT / "tests" / "golden" / "state"
    store = ObjectStore(golden_state)

    records, stamp = collect_for_specs(specs, ROOT / "fixtures" / "target_system",
                                       demo_config["frozen_collected_at"])
    manifest = build_manifest(records, stamp, store)
    snapshot_id = write_snapshot(golden_state, manifest, store)
    results = evaluate_specs(specs, manifest, store, registry)
    att_id, body = build_attestation(results, manifest, ENGINE_VERSION)
    att_path = write_attestation(golden_state, att_id, body)
    print(f"golden snapshot {snapshot_id}, attestation {att_id} ({body['rollup']['verdict']})")

    records2, stamp2 = collect_for_specs(specs, ROOT / "fixtures" / "target_system_remediated",
                                         demo_config["remediated_collected_at"])
    manifest2 = build_manifest(records2, stamp2, store)
    write_snapshot(golden_state, manifest2, store)
    results2 = evaluate_specs(specs, manifest2, store, registry)
    att_id2, body2 = build_attestation(results2, manifest2, ENGINE_VERSION)
    write_attestation(golden_state, att_id2, body2)
    print(f"golden remediated attestation {att_id2} ({body2['rollup']['verdict']})")

    drift = diff_attestations(body, body2)
    write_canonical(ROOT / "tests" / "golden" / "drift_report.json", drift)

    meta = {
        "engine_version": ENGINE_VERSION,
        "snapshot_id": snapshot_id,
        "manifest_sha256": hash_obj(manifest),
        "attestation_id": att_id,
        "attestation_path": f"state/attestations/{att_id}.json",
        "remediated_attestation_id": att_id2,
        "rollup_before": body["rollup"],
        "rollup_after": body2["rollup"],
    }
    write_canonical(ROOT / "tests" / "golden" / "meta.json", meta)
    print(f"golden meta written; attestation file: {att_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
