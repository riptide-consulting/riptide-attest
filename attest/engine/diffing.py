"""Attestation diffing: drift as a deterministic artifact.

Two attestations of the same control set, taken at different times, differ
only where the world differed. The drift report names each transition --
verdict changes, evidence content changes (by hash, so a change with no
verdict impact is still visible), controls added or removed -- and is itself
canonical JSON, so 'what changed between Monday and Friday' has exactly one
answer.
"""

from __future__ import annotations

DRIFT_VERSION = "1.0"


def diff_attestations(body_a: dict, body_b: dict) -> dict:
    controls_a = {c["control_id"]: c for c in body_a["controls"]}
    controls_b = {c["control_id"]: c for c in body_b["controls"]}

    transitions = []
    for control_id in sorted(set(controls_a) | set(controls_b)):
        in_a, in_b = control_id in controls_a, control_id in controls_b
        if not in_b:
            transitions.append({"control_id": control_id, "change": "removed",
                                "from": controls_a[control_id]["verdict"], "to": None})
            continue
        if not in_a:
            transitions.append({"control_id": control_id, "change": "added",
                                "from": None, "to": controls_b[control_id]["verdict"]})
            continue

        a, b = controls_a[control_id], controls_b[control_id]
        check_changes = []
        checks_a = {c["check_id"]: c for c in a["checks"]}
        checks_b = {c["check_id"]: c for c in b["checks"]}
        for check_id in sorted(set(checks_a) | set(checks_b)):
            ca, cb = checks_a.get(check_id), checks_b.get(check_id)
            if ca is None or cb is None:
                check_changes.append({"check_id": check_id,
                                      "change": "added" if ca is None else "removed"})
                continue
            verdict_changed = ca["verdict"] != cb["verdict"]
            evidence_changed = ca["evidence"].get("sha256") != cb["evidence"].get("sha256")
            if verdict_changed or evidence_changed:
                check_changes.append({
                    "check_id": check_id,
                    "change": "verdict" if verdict_changed else "evidence-only",
                    "from": {"verdict": ca["verdict"], "evidence_sha256": ca["evidence"].get("sha256")},
                    "to": {"verdict": cb["verdict"], "evidence_sha256": cb["evidence"].get("sha256")},
                })

        if a["verdict"] != b["verdict"] or a["spec_sha256"] != b["spec_sha256"] or check_changes:
            transitions.append({
                "control_id": control_id,
                "change": "verdict" if a["verdict"] != b["verdict"] else "detail",
                "from": a["verdict"],
                "to": b["verdict"],
                "spec_changed": a["spec_sha256"] != b["spec_sha256"],
                "checks": check_changes,
            })

    return {
        "drift_version": DRIFT_VERSION,
        "from": {"snapshot_id": body_a["snapshot"]["id"], "collected_at": body_a["snapshot"]["collected_at"]},
        "to": {"snapshot_id": body_b["snapshot"]["id"], "collected_at": body_b["snapshot"]["collected_at"]},
        "transitions": transitions,
        "summary": {
            "controls_compared": len(set(controls_a) | set(controls_b)),
            "verdicts_changed": sum(1 for t in transitions if t["change"] == "verdict"),
            "stable": not transitions,
        },
    }
