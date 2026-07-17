"""The CLI's documented contract, pinned: exit codes, refusal messages,
--json payload shapes. RUNBOOK tells operators to wire alerting to these
codes; from now on a change to them is a failing test, not a silent doc
drift.

Exit codes: 0 success (evaluate: rollup pass; replay: byte-match),
2 evaluate completed with a non-pass rollup, 1 replay mismatch,
3 refused (approval, spec validation, tamper, integrity, publish key).
"""

import shutil
import sys
from pathlib import Path

import pytest

import main as cli
from attest.engine import read_json

ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN = ROOT / "tests" / "golden"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """A working directory holding a copy of the golden state, an approved
    registry, and the repo specs -- the CLI exercised as an operator would."""
    monkeypatch.chdir(tmp_path)  # audit log writes land here, not in the repo
    state = tmp_path / "state"
    shutil.copytree(GOLDEN / "state", state)
    meta = read_json(GOLDEN / "meta.json")
    return {
        "state": str(state),
        "registry": str(ROOT / "registry" / "approved.json"),
        "specs": [str(p) for p in sorted((ROOT / "specs").glob("*.json"))],
        "meta": meta,
        "att_path": str(state / "attestations" / f"{meta['attestation_id']}.json"),
    }


def run(argv):
    return cli.main(argv)


def test_evaluate_nonpass_rollup_exits_2(env, capsys):
    code = run(["evaluate", "--specs", *env["specs"], "--snapshot", env["meta"]["snapshot_id"],
                "--state", env["state"], "--registry", env["registry"]])
    out = capsys.readouterr().out
    assert code == 2
    assert "[FAIL" in out
    # The failing check and its detail are named in the output (RUNBOOK's claim).
    assert "retention-at-least-180" in out
    assert "90 >= 180 is false" in out


def test_evaluate_json_payload_shape(env, capsys):
    import json

    code = run(["evaluate", "--specs", *env["specs"], "--snapshot", env["meta"]["snapshot_id"],
                "--state", env["state"], "--registry", env["registry"], "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["attestation_id"] == env["meta"]["attestation_id"]
    assert payload["rollup"]["verdict"] == "fail"
    assert {c["control_id"]: c["verdict"] for c in payload["controls"]} == {
        "RIA-2026-14012-A2": "pass", "RIA-2026-14012-A3": "fail", "RIA-2026-14012-A4": "pass"}


def test_evaluate_unknown_snapshot_refused_exit_3(env, capsys):
    code = run(["evaluate", "--specs", *env["specs"], "--snapshot", "snap-bogus0bogus0bo",
                "--state", env["state"], "--registry", env["registry"]])
    err = capsys.readouterr().err
    assert code == 3
    assert err.startswith("refused:")
    assert "not found" in err


def test_evaluate_unapproved_spec_refused_exit_3(env, tmp_path, capsys):
    import copy

    from attest.engine import write_canonical

    spec = copy.deepcopy(read_json(Path(env["specs"][0])))
    spec["checks"][0]["predicate"]["preds"][1]["value"] = 9999
    edited = tmp_path / "edited-spec.json"
    write_canonical(edited, spec)
    code = run(["evaluate", "--specs", str(edited), "--snapshot", env["meta"]["snapshot_id"],
                "--state", env["state"], "--registry", env["registry"]])
    err = capsys.readouterr().err
    assert code == 3
    assert "not in the approval registry" in err


def test_replay_ok_exit_0(env, capsys):
    code = run(["replay", env["att_path"], "--state", env["state"], "--registry", env["registry"]])
    assert code == 0
    assert "re-derived byte-for-byte" in capsys.readouterr().out


def test_replay_tampered_attestation_refused_exit_3_no_traceback(env, capsys):
    # A doctored attestation file must be a clean refusal (exit 3), never a
    # traceback, and never exit 1 -- alerting distinguishes "the report was
    # edited" from "the world drifted".
    path = Path(env["att_path"])
    path.write_bytes(path.read_bytes().replace(b'"fail"', b'"pass"', 1))
    code = run(["replay", env["att_path"], "--state", env["state"], "--registry", env["registry"]])
    err = capsys.readouterr().err
    assert code == 3
    assert err.startswith("refused:")
    assert "self-check" in err


def test_replay_tampered_evidence_reports_mismatch_exit_1(env, capsys):
    victim = None
    for obj in (Path(env["state"]) / "objects").glob("*.json"):
        if b'"retention_days":90' in obj.read_bytes():
            victim = obj
            break
    assert victim is not None
    victim.write_bytes(victim.read_bytes().replace(b'"retention_days":90', b'"retention_days":180'))
    code = run(["replay", env["att_path"], "--state", env["state"], "--registry", env["registry"]])
    out = capsys.readouterr().out
    assert code == 1
    assert "integrity" in out


def test_diff_exit_0(env, capsys):
    remediated = env["meta"]["remediated_attestation_id"]
    code = run(["diff", env["att_path"],
                str(Path(env["state"]) / "attestations" / f"{remediated}.json"),
                "--state", env["state"], "--registry", env["registry"]])
    out = capsys.readouterr().out
    assert code == 0
    assert "RIA-2026-14012-A3: fail -> pass" in out


def test_publish_without_key_refused_exit_3(env, monkeypatch, capsys):
    monkeypatch.delenv("ATTEST_PUBLISH_APPROVED", raising=False)
    code = run(["publish", env["att_path"], "--state", env["state"], "--registry", env["registry"]])
    err = capsys.readouterr().err
    assert code == 3
    assert "ATTEST_PUBLISH_APPROVED" in err


def test_approve_writes_registry(env, tmp_path, capsys):
    from attest.engine import load_registry

    registry_path = tmp_path / "registry.json"
    code = run(["approve", env["specs"][0], "--by", "test.human",
                "--at", "2026-07-17T00:00:00Z", "--registry", str(registry_path),
                "--state", env["state"]])
    assert code == 0
    registry = load_registry(registry_path)
    assert len(registry["approved"]) == 1
    entry = next(iter(registry["approved"].values()))
    assert entry["approved_by"] == "test.human"
