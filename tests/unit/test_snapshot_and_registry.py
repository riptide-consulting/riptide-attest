"""The content-addressed store, tamper detection, and the approval gate."""

import copy

import pytest

from attest.engine import (
    ApprovalError,
    ObjectStore,
    SnapshotError,
    TamperError,
    approve_spec,
    build_manifest,
    empty_registry,
    hash_obj,
    load_registry,
    load_snapshot,
    require_approved,
    save_registry,
    snapshot_id_for,
    write_snapshot,
)

RECORDS = [
    {"selector": "fs://a/config.json", "body": {"retention_days": 90}, "content_type": "application/json"},
    {"selector": "fs://b/missing.json", "error": "no such file under target root: b/missing.json"},
]
STAMP = "2026-07-17T00:00:00Z"

SPEC = {
    "spec_version": "1.0",
    "control_id": "T-1",
    "title": "test control",
    "checks": [{"check_id": "c", "evidence": {"selector": "fs://a/config.json"}, "predicate": {"op": "exists"}}],
}


def test_put_is_idempotent_and_content_addressed(tmp_path):
    store = ObjectStore(tmp_path)
    d1 = store.put({"a": 1})
    d2 = store.put({"a": 1})
    assert d1 == d2 == hash_obj({"a": 1})
    assert store.get(d1) == {"a": 1}


def test_get_refuses_tampered_content(tmp_path):
    store = ObjectStore(tmp_path)
    digest = store.put({"retention_days": 90})
    path = tmp_path / "objects" / f"{digest}.json"
    path.write_bytes(b'{"retention_days":400}')
    with pytest.raises(TamperError, match="modified after collection"):
        store.get(digest)


def test_get_unknown_object_is_a_named_error(tmp_path):
    with pytest.raises(SnapshotError, match="not in the store"):
        ObjectStore(tmp_path).get("0" * 64)


def test_manifest_records_errors_as_data(tmp_path):
    store = ObjectStore(tmp_path)
    manifest = build_manifest(copy.deepcopy(RECORDS), STAMP, store)
    assert "sha256" in manifest["items"]["fs://a/config.json"]
    assert "error" in manifest["items"]["fs://b/missing.json"]


def test_manifest_rejects_bad_timestamp(tmp_path):
    with pytest.raises(SnapshotError, match="collected_at"):
        build_manifest([], "yesterday-ish", ObjectStore(tmp_path))


def test_manifest_rejects_duplicate_selectors(tmp_path):
    records = [RECORDS[0], copy.deepcopy(RECORDS[0])]
    with pytest.raises(SnapshotError, match="duplicate selector"):
        build_manifest(records, STAMP, ObjectStore(tmp_path))


def test_snapshot_roundtrip_and_id_binding(tmp_path):
    store = ObjectStore(tmp_path)
    manifest = build_manifest(copy.deepcopy(RECORDS), STAMP, store)
    snapshot_id = write_snapshot(tmp_path, manifest, store)
    assert snapshot_id == snapshot_id_for(manifest)
    assert load_snapshot(tmp_path, snapshot_id) == manifest


def test_edited_snapshot_file_is_refused(tmp_path):
    store = ObjectStore(tmp_path)
    manifest = build_manifest(copy.deepcopy(RECORDS), STAMP, store)
    snapshot_id = write_snapshot(tmp_path, manifest, store)
    path = tmp_path / "snapshots" / f"{snapshot_id}.json"
    original = path.read_bytes()
    doctored = original.replace(b'"collected_at":"2026-07-17T00:00:00Z"',
                                b'"collected_at":"2026-07-18T00:00:00Z"')
    assert doctored != original  # the edit must actually land
    path.write_bytes(doctored)
    with pytest.raises(TamperError, match="modified after it was written"):
        load_snapshot(tmp_path, snapshot_id)


# -- the approval gate ----------------------------------------------------

def test_unapproved_spec_is_refused():
    with pytest.raises(ApprovalError, match="not in the approval registry"):
        require_approved(SPEC, empty_registry())


def test_approval_pins_the_exact_content():
    registry, digest = approve_spec(empty_registry(), SPEC, "drew.poole", STAMP)
    assert require_approved(SPEC, registry) == digest

    edited = copy.deepcopy(SPEC)
    edited["checks"][0]["predicate"] = {"op": "absent"}  # one predicate flipped
    with pytest.raises(ApprovalError):
        require_approved(edited, registry)


def test_approval_requires_a_named_human():
    with pytest.raises(ApprovalError, match="named approver"):
        approve_spec(empty_registry(), SPEC, "   ", STAMP)


def test_registry_roundtrip(tmp_path):
    registry, _ = approve_spec(empty_registry(), SPEC, "drew.poole", STAMP)
    path = tmp_path / "approved.json"
    save_registry(path, registry)
    assert load_registry(path) == registry


def test_missing_registry_loads_empty(tmp_path):
    assert load_registry(tmp_path / "nope.json") == empty_registry()


def test_malformed_registry_is_refused(tmp_path):
    path = tmp_path / "approved.json"
    path.write_bytes(b'{"whatever": true}')
    with pytest.raises(ApprovalError, match="malformed"):
        load_registry(path)
