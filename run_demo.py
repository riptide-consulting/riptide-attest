"""The one-command demo: the full Attest arc, offline, zero API spend,
self-verifying. Every determinism claim in the README is asserted here with
an exit code, not narrated. If any assertion fails, the demo says so and
exits nonzero -- the demo is itself a test.

The arc:
  1. Triage: which RIA remediation actions are machine-attestable at all
  2. The approval gate: an edited spec is refused; approval is a hash pin
  3. Snapshot: evidence frozen, content-addressed
  4. Evaluate: 3 controls -> 2 pass, 1 fail, with the failing predicate named
  5. Determinism: evaluate again -> byte-identical attestation
  6. Tamper: modify one stored evidence object -> refused at point of use
  7. Remediation drift: fix retention, re-attest -> exactly one transition
  8. Replay: re-derive attestation #1 from stored artifacts, hashes match
  9. The publish gate: external send refused without the human key

Frozen time: by default the demo stamps snapshots with the fixture time so
your attestation ids match the ones printed in the README, byte for byte.
Run with --live-clock for a wall-clock collection (ids will differ; the
within-run determinism assertions still hold -- that distinction is the
honest shape of the claim: same snapshot -> same bytes).
"""

from __future__ import annotations

import argparse
import copy
import shutil
import subprocess
import sys
from pathlib import Path

from attest.collect import collect_for_specs, utc_now_stamp
from attest.engine import (
    ENGINE_VERSION,
    ApprovalError,
    ObjectStore,
    TamperError,
    build_attestation,
    build_manifest,
    diff_attestations,
    ensure_valid,
    hash_obj,
    load_registry,
    read_json,
    replay,
    evaluate_specs,
    write_attestation,
    write_snapshot,
)

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"
SPEC_DIR = ROOT / "specs"
STATE = ROOT / "state" / "demo"

_failures: list[str] = []


def check(claim: str, ok: bool) -> None:
    marker = "OK " if ok else "FAIL"
    print(f"    [{marker}] {claim}")
    if not ok:
        _failures.append(claim)


def section(number: int, title: str) -> None:
    print(f"\n--- {number}. {title} " + "-" * max(0, 60 - len(title)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-clock", action="store_true",
                        help="stamp the snapshot with wall-clock time instead of the fixture time")
    args = parser.parse_args()

    demo_config = read_json(FIXTURES / "demo_config.json")
    frozen_at = None if args.live_clock else demo_config["frozen_collected_at"]

    if STATE.exists():
        shutil.rmtree(STATE)
    STATE.mkdir(parents=True)

    print("RIPTIDE ATTEST -- deterministic verification demo")
    print(f"engine {ENGINE_VERSION}, offline, zero model spend")

    # 1 ------------------------------------------------------------------
    section(1, "Triage: what is machine-attestable at all")
    plan = read_json(FIXTURES / "ria_remediation_plan.json")
    triage = read_json(FIXTURES / "triage_decisions.json")
    print(f"  input: RIA briefing {plan['briefing_document']} remediation plan, {len(plan['actions'])} actions")
    print("  (offline demo replays the recorded triage; the live verb is: python main.py triage)")
    for decision in triage["decisions"]:
        route = "ATTEST      " if decision["attestable"] else "HUMAN-TRACK "
        print(f"    [{route}] {decision['action_ref']}: {decision['action'][:58]}")
    attestable = [d for d in triage["decisions"] if d["attestable"]]
    check("uncertainty routes to humans, never to automation",
          all(d["confidence"] >= 0.7 for d in attestable))

    # 2 ------------------------------------------------------------------
    section(2, "The approval gate: approval is a hash pin")
    registry = load_registry(ROOT / "registry" / "approved.json")
    spec_paths = sorted(SPEC_DIR.glob("*.json"))
    specs = [ensure_valid(read_json(p)) for p in spec_paths]
    for spec, path in zip(specs, spec_paths):
        print(f"    approved: {spec['control_id']}  {hash_obj(spec)[:16]}  ({path.name})")
    tampered = copy.deepcopy(specs[0])
    tampered["checks"][0]["predicate"]["preds"][1]["value"] = 9999  # relax the control
    store_probe = ObjectStore(STATE)
    try:
        evaluate_specs([tampered], {"collected_at": "2026-07-17T00:00:00Z", "items": {}},
                       store_probe, registry)
        check("an edited spec is refused at the point of use", False)
    except ApprovalError as exc:
        print(f"    refused as designed: {str(exc)[:96]}...")
        check("an edited spec is refused at the point of use", True)

    # 3 ------------------------------------------------------------------
    section(3, "Snapshot: evidence frozen, content-addressed")
    store = ObjectStore(STATE)
    records, stamp = collect_for_specs(specs, FIXTURES / "target_system", frozen_at)
    manifest = build_manifest(records, stamp, store)
    snapshot_id = write_snapshot(STATE, manifest, store)
    print(f"    {snapshot_id}: {len(manifest['items'])} items at {stamp}")
    for selector, entry in sorted(manifest["items"].items()):
        print(f"      {selector}  {entry.get('sha256', 'ERROR')[:16]}")

    # 4 ------------------------------------------------------------------
    section(4, "Evaluate: verdicts with the failing predicate named")
    results = evaluate_specs(specs, manifest, store, registry)
    att_id, body = build_attestation(results, manifest, ENGINE_VERSION)
    att_path = write_attestation(STATE, att_id, body)
    for control in body["controls"]:
        print(f"    [{control['verdict'].upper():7}] {control['control_id']}  {control['title']}")
        if control["verdict"] != "pass":
            for c in control["checks"]:
                if c["verdict"] != "pass":
                    print(f"              {c['check_id']}: {c['detail']}")
    print(f"    attestation {att_id} (rollup: {body['rollup']['verdict']})")
    check("verdicts are 2 pass / 1 fail as the fixtures dictate",
          body["rollup"]["counts"] == {"pass": 2, "fail": 1, "unknown": 0})

    # 5 ------------------------------------------------------------------
    section(5, "Determinism: run it again, compare bytes")
    results2 = evaluate_specs(specs, manifest, store, registry)
    att_id2, body2 = build_attestation(results2, manifest, ENGINE_VERSION)
    same = hash_obj(body) == hash_obj(body2) and att_id == att_id2
    print(f"    first : {att_id}  sha256 {hash_obj(body)[:32]}")
    print(f"    second: {att_id2}  sha256 {hash_obj(body2)[:32]}")
    check("same snapshot + same specs -> identical attestation, byte for byte", same)
    reversed_results = evaluate_specs(list(reversed(specs)), manifest, store, registry)
    att_id3, _ = build_attestation(reversed_results, manifest, ENGINE_VERSION)
    check("spec order on the command line cannot change the attestation", att_id3 == att_id)

    # 6 ------------------------------------------------------------------
    section(6, "Tamper: modify stored evidence, watch it refuse")
    tamper_state = STATE.parent / "demo_tampered"
    if tamper_state.exists():
        shutil.rmtree(tamper_state)
    shutil.copytree(STATE, tamper_state)
    retention_selector = "fs://logging/retention.json"
    retention_sha = manifest["items"][retention_selector]["sha256"]
    target_object = tamper_state / "objects" / f"{retention_sha}.json"
    doctored = read_json(target_object)
    doctored["audit_log"]["retention_days"] = 400  # make the failing control 'pass'
    target_object.write_bytes((__import__("json").dumps(doctored)).encode("utf-8"))
    try:
        evaluate_specs(specs, manifest, ObjectStore(tamper_state), registry)
        check("tampered evidence is refused at the moment of use", False)
    except TamperError as exc:
        print(f"    refused as designed: {str(exc)[:96]}...")
        check("tampered evidence is refused at the moment of use", True)

    # 7 ------------------------------------------------------------------
    section(7, "Remediation drift: fix retention, re-attest, diff")
    records_after, stamp_after = collect_for_specs(
        specs, FIXTURES / "target_system_remediated",
        demo_config["remediated_collected_at"] if not args.live_clock else None)
    manifest_after = build_manifest(records_after, stamp_after, store)
    write_snapshot(STATE, manifest_after, store)
    results_after = evaluate_specs(specs, manifest_after, store, registry)
    att_id_after, body_after = build_attestation(results_after, manifest_after, ENGINE_VERSION)
    write_attestation(STATE, att_id_after, body_after)
    drift = diff_attestations(body, body_after)
    for t in drift["transitions"]:
        print(f"    {t['control_id']}: {t['from']} -> {t['to']} ({t['change']})")
    check("exactly one verdict transition: the remediated control, fail -> pass",
          drift["summary"]["verdicts_changed"] == 1
          and drift["transitions"][0]["from"] == "fail"
          and drift["transitions"][0]["to"] == "pass")
    check("rollup after remediation is pass", body_after["rollup"]["verdict"] == "pass")

    # 8 ------------------------------------------------------------------
    section(8, "Replay: re-derive attestation #1 from stored artifacts")
    replayed = replay(att_path, STATE, registry, ENGINE_VERSION)
    print(f"    {replayed['attestation_id']}: {replayed['reason']}")
    check("stored attestation re-derives byte-for-byte", replayed["ok"])

    # 9 ------------------------------------------------------------------
    section(9, "The publish gate: no human key, no external effect")
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "publish", str(att_path)],
        capture_output=True, text=True, cwd=ROOT,
        env={k: v for k, v in __import__("os").environ.items() if k != "ATTEST_PUBLISH_APPROVED"},
    )
    refused = result.returncode == 3 and "ATTEST_PUBLISH_APPROVED" in result.stderr
    print(f"    {result.stderr.strip()[:110]}")
    check("external publish is refused without ATTEST_PUBLISH_APPROVED", refused)

    # ---------------------------------------------------------------------
    print("\n" + "=" * 66)
    if _failures:
        print(f"DEMO FAILED: {len(_failures)} determinism assertion(s) did not hold:")
        for failure in _failures:
            print(f"  - {failure}")
        return 1
    print("ALL ASSERTIONS HELD.")
    print(f"  attestation (before remediation): {att_id}")
    print(f"  attestation (after remediation):  {att_id_after}")
    if not args.live_clock:
        print("  These ids are reproducible: compare them against docs/DETERMINISM.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
