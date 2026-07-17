"""The evaluator: verdicts, fail-closed policy, and the gate at point of use."""

import copy

import pytest

from attest.engine import (
    ApprovalError,
    ObjectStore,
    approve_spec,
    build_manifest,
    empty_registry,
    evaluate_spec,
    evaluate_specs,
)

STAMP = "2026-07-17T00:00:00Z"


def make_spec(**overrides):
    spec = {
        "spec_version": "1.0",
        "control_id": "T-1",
        "title": "retention control",
        "on_unknown": "fail",
        "combine": {"op": "all"},
        "checks": [
            {
                "check_id": "retention",
                "evidence": {"selector": "fs://logging/retention.json", "path": "/retention_days"},
                "predicate": {"op": "gte", "value": 180},
            }
        ],
    }
    spec.update(overrides)
    return spec


def make_env(tmp_path, body):
    store = ObjectStore(tmp_path)
    records = [{"selector": "fs://logging/retention.json", "body": body, "content_type": "application/json"}]
    manifest = build_manifest(records, STAMP, store)
    return store, manifest


def test_pass_and_fail_verdicts(tmp_path):
    store, manifest = make_env(tmp_path, {"retention_days": 180})
    assert evaluate_spec(make_spec(), manifest, store)["verdict"] == "pass"

    store2, manifest2 = make_env(tmp_path, {"retention_days": 90})
    result = evaluate_spec(make_spec(), manifest2, store2)
    assert result["verdict"] == "fail"
    assert result["checks"][0]["detail"] == "90 >= 180 is false"


def test_missing_evidence_fails_closed(tmp_path):
    store = ObjectStore(tmp_path)
    manifest = build_manifest([], STAMP, store)  # snapshot holds nothing
    result = evaluate_spec(make_spec(), manifest, store)
    assert result["raw_verdict"] == "unknown"
    assert result["verdict"] == "fail"          # on_unknown: fail


def test_collection_error_fails_closed(tmp_path):
    store = ObjectStore(tmp_path)
    manifest = build_manifest(
        [{"selector": "fs://logging/retention.json", "error": "permission denied"}], STAMP, store)
    result = evaluate_spec(make_spec(), manifest, store)
    assert result["verdict"] == "fail"
    assert "collection failed" in result["checks"][0]["detail"]


def test_report_mode_surfaces_unknown_without_failing(tmp_path):
    store = ObjectStore(tmp_path)
    manifest = build_manifest([], STAMP, store)
    result = evaluate_spec(make_spec(on_unknown="report"), manifest, store)
    assert result["raw_verdict"] == "unknown"
    assert result["verdict"] == "unknown"


def test_missing_pointer_target_fails_closed(tmp_path):
    store, manifest = make_env(tmp_path, {"unrelated": True})
    result = evaluate_spec(make_spec(), manifest, store)
    assert result["verdict"] == "fail"  # gte on MISSING -> unknown -> fail


def test_evidence_hashes_are_cited(tmp_path):
    store, manifest = make_env(tmp_path, {"retention_days": 180})
    result = evaluate_spec(make_spec(), manifest, store)
    cited = result["checks"][0]["evidence"]["sha256"]
    assert cited == manifest["items"]["fs://logging/retention.json"]["sha256"]
    assert result["checks"][0]["evidence"]["value"] == 180


def test_evaluate_specs_enforces_approval(tmp_path):
    store, manifest = make_env(tmp_path, {"retention_days": 180})
    spec = make_spec()
    with pytest.raises(ApprovalError):
        evaluate_specs([spec], manifest, store, empty_registry())

    registry, _ = approve_spec(empty_registry(), spec, "drew.poole", STAMP)
    results = evaluate_specs([spec], manifest, store, registry)
    assert results[0]["verdict"] == "pass"


def test_evaluate_specs_rejects_duplicate_controls(tmp_path):
    store, manifest = make_env(tmp_path, {"retention_days": 180})
    spec = make_spec()
    registry, _ = approve_spec(empty_registry(), spec, "drew.poole", STAMP)
    with pytest.raises(ValueError, match="duplicate control_id"):
        evaluate_specs([spec, copy.deepcopy(spec)], manifest, store, registry)


def test_evaluate_specs_stores_spec_for_replay(tmp_path):
    store, manifest = make_env(tmp_path, {"retention_days": 180})
    spec = make_spec()
    registry, digest = approve_spec(empty_registry(), spec, "drew.poole", STAMP)
    evaluate_specs([spec], manifest, store, registry)
    assert store.get(digest) == spec
