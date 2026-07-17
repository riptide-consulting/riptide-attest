"""Spec grammar validation: the border checkpoint for compiler output."""

import copy

import pytest

from attest.engine import SpecError, ensure_valid, spec_selectors, validate_spec

VALID = {
    "spec_version": "1.0",
    "control_id": "RIA-2026-14012-A2",
    "title": "Session timeout enforced",
    "on_unknown": "fail",
    "combine": {"op": "all"},
    "checks": [
        {
            "check_id": "timeout",
            "evidence": {"selector": "fs://portal/security.json", "path": "/session/timeout_minutes"},
            "predicate": {"op": "lte", "value": 15},
        }
    ],
}


def broken(mutate):
    spec = copy.deepcopy(VALID)
    mutate(spec)
    return spec


def test_valid_spec_passes():
    assert validate_spec(VALID) == []
    assert ensure_valid(VALID) is VALID


def test_defaults_are_optional():
    spec = copy.deepcopy(VALID)
    del spec["on_unknown"], spec["combine"]
    assert validate_spec(spec) == []


@pytest.mark.parametrize("mutate,fragment", [
    (lambda s: s.update(spec_version="2.0"), "spec_version"),
    (lambda s: s.update(control_id="../etc/passwd"), "control_id"),
    (lambda s: s.update(title="  "), "title"),
    (lambda s: s.update(checks=[]), "non-empty"),
    (lambda s: s.update(extra_key=1), "unknown top-level"),
    (lambda s: s.update(on_unknown="ignore"), "on_unknown"),
    (lambda s: s.update(combine={"op": "none"}), "combine"),
    (lambda s: s["checks"][0].update(check_id="Bad_ID"), "check_id"),
    (lambda s: s["checks"][0].pop("predicate"), "predicate"),
    (lambda s: s["checks"][0].update(surprise=1), "unknown keys"),
    (lambda s: s["checks"][0]["evidence"].update(selector="fs://../../secrets"), "segments"),
    (lambda s: s["checks"][0]["evidence"].update(selector="no-scheme-path"), "selector"),
    (lambda s: s["checks"][0]["evidence"].update(path="no-slash"), "path"),
    (lambda s: s["checks"][0].update(predicate={"op": "sounds_plausible"}), "unknown predicate op"),
    (lambda s: s["checks"][0].update(predicate={"op": "lte"}), "requires"),
    (lambda s: s["checks"][0].update(predicate={"op": "lte", "value": "15"}), "numeric"),
    (lambda s: s["checks"][0].update(predicate={"op": "lte", "value": 15, "vaule": 1}), "unknown keys"),
    (lambda s: s["checks"][0].update(predicate={"op": "in", "values": []}), "non-empty"),
    (lambda s: s["checks"][0].update(predicate={"op": "regex_fullmatch", "pattern": "("}), "compile"),
    (lambda s: s["checks"][0].update(predicate={"op": "max_age_days", "value": -1}), ">= 0"),
    (lambda s: s["checks"][0].update(predicate={"op": "len_lte", "value": True}), "integer"),
    (lambda s: s["checks"][0].update(predicate={"op": "all", "preds": []}), "non-empty"),
    (lambda s: s["checks"][0].update(predicate={"op": "not"}), "requires"),
])
def test_invalid_specs_are_named_precisely(mutate, fragment):
    errors = validate_spec(broken(mutate))
    assert errors, "expected validation errors"
    assert any(fragment in e for e in errors), f"no error mentions {fragment!r}: {errors}"


def test_duplicate_check_ids_rejected():
    spec = copy.deepcopy(VALID)
    spec["checks"].append(copy.deepcopy(spec["checks"][0]))
    assert any("duplicate check_id" in e for e in validate_spec(spec))


def test_deep_nesting_bounded():
    pred = {"op": "exists"}
    for _ in range(10):
        pred = {"op": "not", "pred": pred}
    spec = broken(lambda s: s["checks"][0].update(predicate=pred))
    assert any("nesting" in e for e in validate_spec(spec))


def test_ensure_valid_raises_with_every_error():
    spec = broken(lambda s: (s.update(spec_version="2.0"), s.update(checks=[])))
    with pytest.raises(SpecError) as excinfo:
        ensure_valid(spec)
    assert len(excinfo.value.errors) >= 2


def test_spec_selectors_sorted_deduplicated():
    spec = copy.deepcopy(VALID)
    spec["checks"].append({
        "check_id": "second",
        "evidence": {"selector": "fs://a/first.json"},
        "predicate": {"op": "exists"},
    })
    spec["checks"].append({
        "check_id": "third",
        "evidence": {"selector": "fs://portal/security.json", "path": "/mfa"},
        "predicate": {"op": "exists"},
    })
    assert spec_selectors(spec) == ["fs://a/first.json", "fs://portal/security.json"]
