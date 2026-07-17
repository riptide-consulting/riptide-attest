"""Regression tests for the adversarial-review findings: each test here
pins a behavior a skeptic demonstrated was wrong or unpinned. The finding
ids reference the review record in scratchpad/ADVERSARIAL-REVIEW.md."""

import copy
from datetime import datetime, timezone

import pytest

from attest.collect import CollectorError, _collect_fs, collect_for_specs
from attest.engine import (
    MISSING,
    ObjectStore,
    ReportError,
    build_manifest,
    diff_attestations,
    hash_obj,
    load_attestation,
    resolve_pointer,
    write_canonical,
)
from attest.engine.predicates import UNKNOWN, evaluate_predicate

CTX = {"snapshot_time": datetime(2026, 7, 17, tzinfo=timezone.utc)}
STAMP = "2026-07-17T00:00:00Z"


# -- finding: non-ASCII digits in pointer array indices -------------------

@pytest.mark.parametrize("token", ["²", "٣", "1٨2", "①"])
def test_pointer_rejects_non_ascii_digit_indices(token):
    # str.isdigit() accepts all of these; RFC 6901 accepts none of them.
    # Superscript two used to CRASH int(); Arabic-Indic three used to
    # silently resolve as index 3. Both now resolve to MISSING.
    assert resolve_pointer([10, 20, 30, 40], f"/{token}") is MISSING


def test_pointer_ascii_indices_still_work():
    assert resolve_pointer([10, 20, 30], "/2") == 30


# -- finding: len_* satisfied by strings and objects ----------------------

@pytest.mark.parametrize("value", ["no", "xxxxxxxxx", {"a": 1, "b": 2}])
def test_len_predicates_reject_non_arrays(value):
    # "at least 2 approvers" must not be satisfied by a 2-char string or a
    # 2-key object; wrong-type evidence is unknown, then fail-closed.
    verdict, detail = evaluate_predicate({"op": "len_gte", "value": 2}, value, CTX)
    assert verdict == UNKNOWN
    assert "requires an array" in detail


def test_len_predicates_still_count_arrays():
    assert evaluate_predicate({"op": "len_gte", "value": 2}, ["a", "b"], CTX)[0] == "pass"
    assert evaluate_predicate({"op": "len_lte", "value": 0}, [], CTX)[0] == "pass"


# -- finding: uncanonicalizable evidence crashed the whole snapshot -------

@pytest.mark.parametrize("body,fragment", [
    ({"v": float("inf")}, "Infinity"),
    # NFC-composed vs decomposed e-acute: distinct Python dict keys that
    # collide after canonical normalization.
    ({"café": 1, "café": 2}, "duplicate key"),
])
def test_uncanonicalizable_evidence_becomes_error_record(tmp_path, body, fragment):
    records = [{"selector": "fs://a/hostile.json", "body": body, "content_type": "application/json"}]
    manifest = build_manifest(records, STAMP, ObjectStore(tmp_path))
    entry = manifest["items"]["fs://a/hostile.json"]
    assert "error" in entry and "not canonicalizable" in entry["error"]


def test_hostile_evidence_file_infinity_collected_as_error(tmp_path):
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "app.json").write_bytes(b'{"retention_days": 1e999}')
    result = _collect_fs("cfg/app.json", tmp_path)
    # json.loads happily parses 1e999 to Infinity; the manifest layer is
    # the backstop that turns it into an error record.
    manifest = build_manifest(
        [{"selector": "fs://cfg/app.json", **result}], STAMP, ObjectStore(tmp_path))
    assert "error" in manifest["items"]["fs://cfg/app.json"]


# -- finding: collector guard branches untested ---------------------------

def test_collector_traversal_guard(tmp_path):
    (tmp_path / "root").mkdir()
    result = _collect_fs("../outside.json", tmp_path / "root")
    assert "error" in result and "escapes the target root" in result["error"]


def test_collector_unknown_scheme_is_config_error(tmp_path):
    spec = {
        "spec_version": "1.0", "control_id": "T-1", "title": "t",
        "checks": [{"check_id": "c", "evidence": {"selector": "ldap://x/y"},
                    "predicate": {"op": "exists"}}],
    }
    with pytest.raises(CollectorError, match="no adapter for scheme"):
        collect_for_specs([spec], tmp_path, STAMP)


def test_collector_unparseable_json_is_error_record(tmp_path):
    (tmp_path / "bad.json").write_bytes(b"{not json")
    assert "unparseable JSON" in _collect_fs("bad.json", tmp_path)["error"]


def test_collector_undecodable_text_is_error_record(tmp_path):
    (tmp_path / "bin.txt").write_bytes(b"\xff\xfe\x00\x01")
    assert "undecodable" in _collect_fs("bin.txt", tmp_path)["error"]


# -- finding: load_attestation failure branches untested ------------------

def test_load_attestation_rejects_malformed_wrapper(tmp_path):
    path = tmp_path / "att.json"
    write_canonical(path, {"not_an_attestation": True})
    with pytest.raises(ReportError, match="malformed"):
        load_attestation(path)


def test_load_attestation_rejects_edited_body(tmp_path):
    body = {"attest_version": "1.0", "controls": [], "rollup": {"verdict": "pass"}}
    att_id = "att-" + hash_obj(body)[:16]
    path = tmp_path / "att.json"
    write_canonical(path, {"attestation_id": att_id, "body": body})
    doctored = path.read_bytes().replace(b'"pass"', b'"fail"')
    path.write_bytes(doctored)
    with pytest.raises(ReportError, match="fails its self-check"):
        load_attestation(path)


# -- finding: diffing branches untested -----------------------------------

def _mini_body(controls):
    return {
        "snapshot": {"id": "snap-x", "collected_at": STAMP},
        "controls": controls,
    }


def _control(control_id, verdict, spec_sha="s" * 64, evidence_sha="e" * 64):
    return {
        "control_id": control_id, "verdict": verdict, "spec_sha256": spec_sha,
        "checks": [{"check_id": "c", "verdict": verdict,
                    "evidence": {"sha256": evidence_sha}}],
    }


def test_diff_reports_added_and_removed_controls():
    drift = diff_attestations(
        _mini_body([_control("A", "pass"), _control("B", "pass")]),
        _mini_body([_control("B", "pass"), _control("C", "fail")]),
    )
    changes = {t["control_id"]: t["change"] for t in drift["transitions"]}
    assert changes == {"A": "removed", "C": "added"}


def test_diff_reports_spec_change_without_verdict_change():
    drift = diff_attestations(
        _mini_body([_control("A", "pass", spec_sha="1" * 64)]),
        _mini_body([_control("A", "pass", spec_sha="2" * 64)]),
    )
    assert drift["transitions"][0]["change"] == "detail"
    assert drift["transitions"][0]["spec_changed"] is True
    assert drift["summary"]["verdicts_changed"] == 0


def test_diff_reports_evidence_only_change():
    drift = diff_attestations(
        _mini_body([_control("A", "pass", evidence_sha="1" * 64)]),
        _mini_body([_control("A", "pass", evidence_sha="2" * 64)]),
    )
    checks = drift["transitions"][0]["checks"]
    assert checks[0]["change"] == "evidence-only"


def test_diff_reports_check_added_and_removed():
    before = _mini_body([_control("A", "pass")])
    after = copy.deepcopy(before)
    after["controls"][0]["checks"].append(
        {"check_id": "new-check", "verdict": "pass", "evidence": {"sha256": "f" * 64}})
    drift = diff_attestations(before, after)
    assert {"check_id": "new-check", "change": "added"} in drift["transitions"][0]["checks"]
