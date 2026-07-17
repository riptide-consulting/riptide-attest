"""The evaluator: a pure function from (approved spec, manifest, store) to
per-check results and a spec verdict. This is the module the determinism
claim rests on, so its discipline is explicit:

  * inputs are the arguments, the whole of them, and nothing else;
  * the only timestamp in scope is the manifest's collected_at;
  * check results appear in spec order (the spec is content-addressed, so
    its order is fixed by its hash);
  * unknown escalates to fail at the rollup unless the spec's human-pinned
    on_unknown says 'report' -- fail-closed is the default state of the
    world, not a configuration achievement.

The approval gate is invoked here, inside evaluation, at the point of use.
evaluate_specs() is the one path to a verdict, and it will not produce one
for a spec no human approved.
"""

from __future__ import annotations

from .canonical import hash_obj
from .pointer import MISSING, resolve_pointer
from .predicates import FAIL, PASS, UNKNOWN, combine_verdicts, evaluate_predicate, parse_utc_timestamp
from .registry import require_approved
from .schema import ensure_valid
from .snapshot import ObjectStore, SnapshotError


def evaluate_spec(spec: dict, manifest: dict, store: ObjectStore) -> dict:
    """Evaluate one validated, approved spec against one snapshot manifest.
    Approval is checked by evaluate_specs(); this function assumes a spec
    already past the gate (unit tests exercise it directly on fixtures)."""
    snapshot_time = parse_utc_timestamp(manifest["collected_at"])
    if snapshot_time is None:
        raise SnapshotError(f"manifest carries an invalid collected_at: {manifest.get('collected_at')!r}")
    ctx = {"snapshot_time": snapshot_time}

    results = []
    for check in spec["checks"]:
        selector = check["evidence"]["selector"]
        pointer = check["evidence"].get("path", "")
        entry = manifest["items"].get(selector)

        evidence_ref: dict[str, object] = {"selector": selector, "path": pointer}
        if entry is None:
            verdict, detail = UNKNOWN, f"snapshot holds no evidence for {selector}"
            evidence_ref["sha256"] = None
        elif "error" in entry:
            verdict, detail = UNKNOWN, f"evidence collection failed: {entry['error']}"
            evidence_ref["sha256"] = None
        else:
            body = store.get(entry["sha256"])  # raises TamperError on modified evidence
            value = resolve_pointer(body, pointer)
            verdict, detail = evaluate_predicate(check["predicate"], value, ctx)
            evidence_ref["sha256"] = entry["sha256"]
            evidence_ref["value"] = None if value is MISSING else value

        results.append(
            {"check_id": check["check_id"], "verdict": verdict, "detail": detail, "evidence": evidence_ref}
        )

    combine_op = spec.get("combine", {"op": "all"})["op"]
    raw_verdict = combine_verdicts(combine_op, [r["verdict"] for r in results])
    on_unknown = spec.get("on_unknown", "fail")
    effective = FAIL if (raw_verdict == UNKNOWN and on_unknown == "fail") else raw_verdict

    return {
        "control_id": spec["control_id"],
        "title": spec["title"],
        "spec_sha256": hash_obj(spec),
        "verdict": effective,
        "raw_verdict": raw_verdict,
        "on_unknown": on_unknown,
        "checks": results,
    }


def evaluate_specs(specs: list[dict], manifest: dict, store: ObjectStore, registry: dict) -> list[dict]:
    """The gated entry point: validate, require approval, store the spec
    (so replay can re-fetch it by hash), then evaluate. Duplicate control
    ids are rejected -- one attestation line per control, no ambiguity."""
    seen: set[str] = set()
    evaluated = []
    for spec in specs:
        ensure_valid(spec)
        require_approved(spec, registry)  # the gate, at the point of use
        if spec["control_id"] in seen:
            raise ValueError(f"duplicate control_id in evaluation set: {spec['control_id']!r}")
        seen.add(spec["control_id"])
        store.put(spec)
        evaluated.append(evaluate_spec(spec, manifest, store))
    return evaluated


__all__ = ["evaluate_spec", "evaluate_specs", "PASS", "FAIL", "UNKNOWN"]
