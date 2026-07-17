"""Riptide Attest CLI.

Verbs follow the control lifecycle, which is a state machine, not a
pipeline (the deliberate structural divergence from RIA's composable stage
flags -- documented in docs/DESIGN-DECISIONS.md):

  authoring (model, costs API dollars, runs once per control):
    triage     classify remediation actions: machine-attestable or human-tracked
    compile    control text -> draft CheckSpec (never executable as-is)
    explain    approved spec -> plain-language summary for the review packet

  authority (human):
    approve    pin a spec's hash into the approval registry

  runtime (pure code, zero model spend, runs forever):
    snapshot   freeze evidence for the approved spec set
    evaluate   approved specs x snapshot -> attestation
    replay     re-derive a stored attestation, assert byte equality
    diff       two attestations -> deterministic drift report
    publish    send an attestation to the tracker (human-keyed)

All verbs support --json: results as JSON on stdout, diagnostics on stderr,
for pipes and CI (RIA's -p convention).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from attest.audit import audit
from attest.engine import (
    ENGINE_VERSION,
    ObjectStore,
    ReportError,
    SnapshotError,
    SpecError,
    TamperError,
    approve_spec,
    build_attestation,
    build_manifest,
    diff_attestations,
    ensure_valid,
    hash_obj,
    load_attestation,
    load_registry,
    load_snapshot,
    read_json,
    replay,
    save_registry,
    evaluate_specs,
    write_attestation,
    write_snapshot,
)

DEFAULT_STATE = Path("state")
DEFAULT_REGISTRY = Path("registry") / "approved.json"


def _emit(args: argparse.Namespace, payload: dict, human: str) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(human)


def _load_specs(paths: list[str]) -> list[dict]:
    return [ensure_valid(read_json(Path(p))) for p in paths]


def cmd_approve(args: argparse.Namespace) -> int:
    spec = ensure_valid(read_json(Path(args.spec)))
    registry = load_registry(args.registry)
    from attest.collect import utc_now_stamp

    approved_at = args.at or utc_now_stamp()
    registry, digest = approve_spec(registry, spec, args.by, approved_at)
    save_registry(args.registry, registry)
    audit("approve", spec_sha256=digest, control_id=spec["control_id"], approved_by=args.by)
    _emit(args, {"approved": digest, "control_id": spec["control_id"]},
          f"approved {spec['control_id']} as {digest[:16]} (by {args.by}). Any edit voids this approval.")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    from attest.collect import collect_for_specs

    specs = _load_specs(args.specs)
    records, stamp = collect_for_specs(specs, Path(args.target), args.at)
    store = ObjectStore(args.state)
    manifest = build_manifest(records, stamp, store)
    snapshot_id = write_snapshot(args.state, manifest, store)
    audit("snapshot", snapshot_id=snapshot_id, items=len(manifest["items"]), collected_at=stamp)
    _emit(args, {"snapshot_id": snapshot_id, "manifest_sha256": hash_obj(manifest), "items": len(manifest["items"])},
          f"snapshot {snapshot_id}: {len(manifest['items'])} evidence items frozen at {stamp}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    specs = _load_specs(args.specs)
    registry = load_registry(args.registry)
    store = ObjectStore(args.state)
    manifest = load_snapshot(args.state, args.snapshot)
    results = evaluate_specs(specs, manifest, store, registry)
    attestation_id, body = build_attestation(results, manifest, ENGINE_VERSION)
    path = write_attestation(args.state, attestation_id, body)
    audit("evaluate", attestation_id=attestation_id, snapshot_id=args.snapshot,
          rollup=body["rollup"]["verdict"], specs=[r["spec_sha256"] for r in results])
    lines = [f"attestation {attestation_id} -> {path}"]
    for control in body["controls"]:
        lines.append(f"  [{control['verdict'].upper():7}] {control['control_id']}  {control['title']}")
        if control["verdict"] != "pass":
            for check in control["checks"]:
                if check["verdict"] != "pass":
                    lines.append(f"            {check['check_id']}: {check['detail']}")
    lines.append(f"  rollup: {body['rollup']['verdict']} ({body['rollup']['counts']})")
    payload = {
        "attestation_id": attestation_id,
        "path": str(path),
        "rollup": body["rollup"],
        "controls": [{"control_id": c["control_id"], "verdict": c["verdict"]} for c in body["controls"]],
    }
    _emit(args, payload, "\n".join(lines))
    return 0 if body["rollup"]["verdict"] == "pass" else 2


def cmd_replay(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    result = replay(Path(args.attestation), args.state, registry, ENGINE_VERSION)
    audit("replay", **result)
    _emit(args, result, f"replay {result['attestation_id']}: {'OK' if result['ok'] else 'FAILED'} -- {result['reason']}")
    return 0 if result["ok"] else 1


def cmd_diff(args: argparse.Namespace) -> int:
    _, body_a = load_attestation(Path(args.attestation_a))
    _, body_b = load_attestation(Path(args.attestation_b))
    drift = diff_attestations(body_a, body_b)
    audit("diff", from_snapshot=drift["from"]["snapshot_id"], to_snapshot=drift["to"]["snapshot_id"],
          verdicts_changed=drift["summary"]["verdicts_changed"])
    if args.json:
        print(json.dumps(drift, ensure_ascii=False))
    else:
        if drift["summary"]["stable"]:
            print("no drift: attestations are equivalent")
        for t in drift["transitions"]:
            print(f"  {t['control_id']}: {t['from']} -> {t['to']} ({t['change']})")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from attest.publish import publish_attestation

    result = publish_attestation(Path(args.attestation))
    _emit(args, result, f"publish: {result['reason'] if not result['published'] else result}")
    return 0


def _model_cmd(module: str, func: str):
    """Authoring verbs import the model layer lazily: the runtime verbs
    above must work on a machine with no anthropic SDK installed."""

    def runner(args: argparse.Namespace) -> int:
        import importlib

        mod = importlib.import_module(module)
        return getattr(mod, func)(args)

    return runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="attest", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--state", default=str(DEFAULT_STATE), help="state directory (default: state/)")
        p.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="approval registry path")
        p.add_argument("--json", action="store_true", help="machine-readable stdout, diagnostics on stderr")

    p = sub.add_parser("approve", help="pin a spec's hash into the approval registry")
    p.add_argument("spec")
    p.add_argument("--by", required=True, help="name of the approving human")
    p.add_argument("--at", help="ISO-8601 UTC timestamp (default: now)")
    common(p)
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("snapshot", help="freeze evidence for a spec set")
    p.add_argument("--specs", nargs="+", required=True)
    p.add_argument("--target", required=True, help="target system root (fs adapter)")
    p.add_argument("--at", help="frozen collected_at for reproducible runs (default: now)")
    common(p)
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("evaluate", help="approved specs x snapshot -> attestation")
    p.add_argument("--specs", nargs="+", required=True)
    p.add_argument("--snapshot", required=True)
    common(p)
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("replay", help="re-derive a stored attestation, assert byte equality")
    p.add_argument("attestation")
    common(p)
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("diff", help="two attestations -> drift report")
    p.add_argument("attestation_a")
    p.add_argument("attestation_b")
    common(p)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("publish", help="send an attestation to the tracker (human-keyed)")
    p.add_argument("attestation")
    common(p)
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("triage", help="classify remediation actions (model, authoring time)")
    p.add_argument("plan", help="RIA remediation plan JSON")
    common(p)
    p.set_defaults(func=_model_cmd("attest.triage", "cli"))

    p = sub.add_parser("compile", help="control text -> draft CheckSpec (model, authoring time)")
    p.add_argument("action", help="path to a JSON file holding one remediation action")
    p.add_argument("--out", required=True, help="where to write the draft spec")
    common(p)
    p.set_defaults(func=_model_cmd("attest.compiler", "cli"))

    p = sub.add_parser("explain", help="spec -> plain-language summary (model, authoring time)")
    p.add_argument("spec")
    common(p)
    p.set_defaults(func=_model_cmd("attest.explainer", "cli"))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (PermissionError, SpecError, TamperError, ReportError, SnapshotError) as exc:
        # Exit 3 is the refusal code, and it covers every integrity path:
        # PermissionError (both gates: spec approval and the publish key),
        # SpecError (invalid spec), TamperError (modified evidence or
        # manifest), ReportError (a doctored attestation file), and
        # SnapshotError (missing or malformed snapshot). A refusal is a
        # named one-line message, never a traceback, and never shares an
        # exit code with a legitimate replay mismatch (exit 1).
        print(f"refused: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
