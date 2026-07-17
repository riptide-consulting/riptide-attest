"""The headline claims, asserted: byte-stability, order-independence,
replay, golden files, and the drift report. These tests run the real
pipeline over the committed fixtures -- if any of them breaks, the product
claim on the README's first screen is false."""

import shutil
from pathlib import Path

import pytest

from attest.collect import collect_for_specs
from attest.engine import (
    ENGINE_VERSION,
    ObjectStore,
    build_attestation,
    build_manifest,
    canonical_bytes,
    diff_attestations,
    ensure_valid,
    evaluate_specs,
    hash_obj,
    load_attestation,
    load_registry,
    read_json,
    replay,
    write_attestation,
    write_snapshot,
)

ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN = ROOT / "tests" / "golden"


@pytest.fixture(scope="module")
def specs():
    return [ensure_valid(read_json(p)) for p in sorted((ROOT / "specs").glob("*.json"))]


@pytest.fixture(scope="module")
def registry():
    return load_registry(ROOT / "registry" / "approved.json")


@pytest.fixture()
def frozen_at():
    return read_json(ROOT / "fixtures" / "demo_config.json")["frozen_collected_at"]


def run_pipeline(state_root, specs, registry, frozen_at, target="target_system"):
    store = ObjectStore(state_root)
    records, stamp = collect_for_specs(specs, ROOT / "fixtures" / target, frozen_at)
    manifest = build_manifest(records, stamp, store)
    write_snapshot(state_root, manifest, store)
    results = evaluate_specs(specs, manifest, store, registry)
    att_id, body = build_attestation(results, manifest, ENGINE_VERSION)
    path = write_attestation(state_root, att_id, body)
    return att_id, body, path, manifest


def test_two_runs_identical_bytes(tmp_path, specs, registry, frozen_at):
    id1, body1, path1, _ = run_pipeline(tmp_path / "run1", specs, registry, frozen_at)
    id2, body2, path2, _ = run_pipeline(tmp_path / "run2", specs, registry, frozen_at)
    assert id1 == id2
    assert path1.read_bytes() == path2.read_bytes()


def test_spec_order_is_irrelevant(tmp_path, specs, registry, frozen_at):
    id1, _, _, _ = run_pipeline(tmp_path / "fwd", specs, registry, frozen_at)
    id2, _, _, _ = run_pipeline(tmp_path / "rev", list(reversed(specs)), registry, frozen_at)
    assert id1 == id2


def test_attestation_id_is_body_hash(tmp_path, specs, registry, frozen_at):
    att_id, body, path, _ = run_pipeline(tmp_path, specs, registry, frozen_at)
    assert att_id == "att-" + hash_obj(body)[:16]
    loaded_id, loaded_body = load_attestation(path)
    assert (loaded_id, loaded_body) == (att_id, body)


def test_attestation_carries_no_wall_clock(tmp_path, specs, registry, frozen_at):
    _, body, _, _ = run_pipeline(tmp_path, specs, registry, frozen_at)
    text = canonical_bytes(body).decode("utf-8")
    # The only timestamps in the body are the snapshot's collected_at and
    # timestamps that are themselves evidence; nothing from this machine's clock.
    assert body["snapshot"]["collected_at"] == frozen_at
    assert "2026-07-17T00:00:00Z" in text


def test_matches_committed_golden(tmp_path, specs, registry, frozen_at):
    meta = read_json(GOLDEN / "meta.json")
    att_id, _, path, manifest = run_pipeline(tmp_path, specs, registry, frozen_at)
    assert att_id == meta["attestation_id"]
    assert hash_obj(manifest) == meta["manifest_sha256"]
    golden_bytes = (GOLDEN / "state" / "attestations" / f"{att_id}.json").read_bytes()
    assert path.read_bytes() == golden_bytes


def test_replay_golden_state(tmp_path, registry):
    meta = read_json(GOLDEN / "meta.json")
    state = tmp_path / "state"
    shutil.copytree(GOLDEN / "state", state)
    result = replay(state / "attestations" / f"{meta['attestation_id']}.json",
                    state, registry, ENGINE_VERSION)
    assert result["ok"], result["reason"]


def test_replay_detects_evidence_tamper(tmp_path, registry):
    meta = read_json(GOLDEN / "meta.json")
    state = tmp_path / "state"
    shutil.copytree(GOLDEN / "state", state)
    # Doctor the retention evidence object in place (not the spec object,
    # which also mentions retention_days), keeping its now-wrong address.
    victim = None
    for obj in (state / "objects").glob("*.json"):
        if b'"retention_days":90' in obj.read_bytes():
            victim = obj
            break
    assert victim is not None
    victim.write_bytes(victim.read_bytes().replace(b'"retention_days":90', b'"retention_days":180'))
    result = replay(state / "attestations" / f"{meta['attestation_id']}.json",
                    state, registry, ENGINE_VERSION)
    assert not result["ok"]
    assert "integrity" in result["reason"]


def test_replay_fails_when_approval_revoked(tmp_path, specs, registry, frozen_at):
    from attest.engine import empty_registry

    _, _, path, _ = run_pipeline(tmp_path, specs, registry, frozen_at)
    with pytest.raises(Exception):  # ApprovalError surfaces from the gate
        replay(path, tmp_path, empty_registry(), ENGINE_VERSION)


def test_drift_report_matches_golden(tmp_path, specs, registry, frozen_at):
    remediated_at = read_json(ROOT / "fixtures" / "demo_config.json")["remediated_collected_at"]
    _, body_before, _, _ = run_pipeline(tmp_path / "before", specs, registry, frozen_at)
    _, body_after, _, _ = run_pipeline(tmp_path / "after", specs, registry, remediated_at,
                                       target="target_system_remediated")
    drift = diff_attestations(body_before, body_after)
    assert drift == read_json(GOLDEN / "drift_report.json")
    assert drift["summary"]["verdicts_changed"] == 1
    assert drift["transitions"][0]["control_id"] == "RIA-2026-14012-A3"
    assert (drift["transitions"][0]["from"], drift["transitions"][0]["to"]) == ("fail", "pass")


def test_self_diff_is_stable(tmp_path, specs, registry, frozen_at):
    _, body, _, _ = run_pipeline(tmp_path, specs, registry, frozen_at)
    drift = diff_attestations(body, body)
    assert drift["summary"]["stable"] is True
    assert drift["transitions"] == []
