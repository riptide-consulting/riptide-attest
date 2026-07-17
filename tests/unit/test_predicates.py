"""The predicate library: table-driven over every op, plus the verdict
algebra and the MISSING/unknown contract."""

from datetime import datetime, timezone

import pytest

from attest.engine import FAIL, MISSING, PASS, UNKNOWN
from attest.engine.predicates import combine_verdicts, evaluate_predicate

CTX = {"snapshot_time": datetime(2026, 7, 17, tzinfo=timezone.utc)}


def verdict(pred, value):
    return evaluate_predicate(pred, value, CTX)[0]


# -- leaves ---------------------------------------------------------------

@pytest.mark.parametrize("pred,value,expected", [
    ({"op": "exists"}, 5, PASS),
    ({"op": "exists"}, None, PASS),          # null is a value; MISSING is not
    ({"op": "exists"}, MISSING, FAIL),
    ({"op": "absent"}, MISSING, PASS),
    ({"op": "absent"}, 0, FAIL),

    ({"op": "eq", "value": 15}, 15, PASS),
    ({"op": "eq", "value": 15}, 16, FAIL),
    ({"op": "eq", "value": "siem"}, "siem", PASS),
    ({"op": "eq", "value": True}, True, PASS),
    ({"op": "eq", "value": True}, 1, FAIL),   # bool/int never conflate
    ({"op": "eq", "value": 1}, True, FAIL),
    ({"op": "ne", "value": 90}, 180, PASS),
    ({"op": "ne", "value": 90}, 90, FAIL),

    ({"op": "lte", "value": 15}, 15, PASS),
    ({"op": "lte", "value": 15}, 16, FAIL),
    ({"op": "lt", "value": 15}, 14, PASS),
    ({"op": "lt", "value": 15}, 15, FAIL),
    ({"op": "gte", "value": 180}, 180, PASS),
    ({"op": "gte", "value": 180}, 90, FAIL),
    ({"op": "gt", "value": 0}, 1, PASS),
    ({"op": "gte", "value": 1}, "1", UNKNOWN),   # strings never compare as numbers
    ({"op": "gte", "value": 1}, True, UNKNOWN),  # bools are not numbers here

    ({"op": "in", "values": ["AES-256-GCM", "AES-256-CBC"]}, "AES-256-GCM", PASS),
    ({"op": "in", "values": ["AES-256-GCM"]}, "DES", FAIL),
    ({"op": "in", "values": [1, 2]}, True, FAIL),  # bool/int distinction holds inside 'in'

    ({"op": "contains", "value": "siem"}, "splunk-siem-prod", PASS),
    ({"op": "contains", "value": "totp"}, ["totp", "webauthn"], PASS),
    ({"op": "contains", "value": "sms"}, ["totp", "webauthn"], FAIL),
    ({"op": "contains", "value": "x"}, 42, UNKNOWN),

    ({"op": "regex_fullmatch", "pattern": r"AES-256-(GCM|CBC)"}, "AES-256-GCM", PASS),
    ({"op": "regex_fullmatch", "pattern": r"AES.*"}, "3DES", FAIL),
    ({"op": "regex_fullmatch", "pattern": r"a+"}, 5, UNKNOWN),

    ({"op": "len_lte", "value": 0}, [], PASS),
    ({"op": "len_lte", "value": 0}, ["public-ep"], FAIL),
    ({"op": "len_gte", "value": 2}, ["totp", "webauthn"], PASS),
    ({"op": "len_gte", "value": 2}, 42, UNKNOWN),

    ({"op": "is_true"}, True, PASS),
    ({"op": "is_true"}, False, FAIL),
    ({"op": "is_true"}, 1, FAIL),             # truthiness is not truth
    ({"op": "is_true"}, "true", FAIL),
    ({"op": "is_false"}, False, PASS),
    ({"op": "is_false"}, 0, FAIL),
])
def test_leaf_predicates(pred, value, expected):
    assert verdict(pred, value) == expected


@pytest.mark.parametrize("pred", [
    {"op": "eq", "value": 1}, {"op": "lte", "value": 5}, {"op": "in", "values": [1]},
    {"op": "contains", "value": "x"}, {"op": "regex_fullmatch", "pattern": "x"},
    {"op": "len_lte", "value": 1}, {"op": "is_true"}, {"op": "max_age_days", "value": 30},
])
def test_missing_is_unknown_for_every_non_existence_op(pred):
    assert verdict(pred, MISSING) == UNKNOWN


# -- time: only the snapshot clock ----------------------------------------

@pytest.mark.parametrize("timestamp,limit,expected", [
    ("2026-07-01T00:00:00Z", 92, PASS),       # 16 days old at snapshot
    ("2026-01-01T00:00:00Z", 92, FAIL),       # 197 days old
    ("2026-07-17T00:00:00Z", 0, PASS),        # exactly at snapshot
    ("2026-08-01T00:00:00Z", 92, FAIL),       # future vs snapshot: fail-closed
    ("2026-07-01T00:00:00+00:00", 92, PASS),  # explicit offset accepted
    ("2026-07-01", 92, UNKNOWN),              # date without time/offset: rejected
    ("2026-07-01T00:00:00", 92, UNKNOWN),     # naive timestamp: rejected
    ("not-a-date", 92, UNKNOWN),
    (1719792000, 92, UNKNOWN),                # epoch numbers are not timestamps
])
def test_max_age_days_measures_against_snapshot_time_only(timestamp, limit, expected):
    assert verdict({"op": "max_age_days", "value": limit}, timestamp) == expected


# -- combinators and the verdict algebra ----------------------------------

def test_all_fail_dominates_unknown():
    pred = {"op": "all", "preds": [{"op": "is_true"}, {"op": "gte", "value": 1}]}
    # value False: is_true fails, gte is unknown (bool not number) -> fail wins
    assert verdict(pred, False) == FAIL


def test_any_pass_dominates_unknown():
    pred = {"op": "any", "preds": [{"op": "gte", "value": 1}, {"op": "eq", "value": "x"}]}
    assert verdict(pred, "x") == PASS


def test_not_inverts_pass_fail_but_preserves_unknown():
    assert verdict({"op": "not", "pred": {"op": "is_true"}}, False) == PASS
    assert verdict({"op": "not", "pred": {"op": "is_true"}}, True) == FAIL
    assert verdict({"op": "not", "pred": {"op": "gte", "value": 1}}, "s") == UNKNOWN


def test_none_combinator():
    pred = {"op": "none", "preds": [{"op": "eq", "value": "http"}, {"op": "eq", "value": "ftp"}]}
    assert verdict(pred, "https") == PASS
    assert verdict(pred, "ftp") == FAIL


@pytest.mark.parametrize("op,verdicts,expected", [
    ("all", [PASS, PASS], PASS),
    ("all", [PASS, UNKNOWN], UNKNOWN),
    ("all", [UNKNOWN, FAIL], FAIL),
    ("all", [], PASS),
    ("any", [FAIL, PASS], PASS),
    ("any", [FAIL, UNKNOWN], UNKNOWN),
    ("any", [FAIL, FAIL], FAIL),
    ("none", [FAIL, FAIL], PASS),
    ("none", [UNKNOWN, FAIL], UNKNOWN),
    ("none", [PASS, FAIL], FAIL),
])
def test_verdict_algebra(op, verdicts, expected):
    assert combine_verdicts(op, verdicts) == expected


def test_details_are_deterministic():
    pred = {"op": "eq", "value": {"b": 1, "a": 2}}
    _, d1 = evaluate_predicate(pred, {"a": 2, "b": 1}, CTX)
    _, d2 = evaluate_predicate(pred, {"b": 1, "a": 2}, CTX)
    assert d1 == d2  # canonical rendering inside detail strings
