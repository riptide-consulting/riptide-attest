"""Canonicalization: the layer every hash in the system rests on."""

import unicodedata

import pytest

from attest.engine import CanonicalizationError, canonical_dumps, hash_obj
from attest.engine.canonical import canonical_bytes


def test_key_order_is_irrelevant():
    assert canonical_dumps({"b": 1, "a": 2}) == canonical_dumps({"a": 2, "b": 1})


def test_minimal_separators_no_whitespace():
    assert canonical_dumps({"a": [1, 2], "b": True}) == '{"a":[1,2],"b":true}'


def test_nested_ordering():
    left = {"outer": {"z": 1, "a": {"y": 2, "b": 3}}}
    right = {"outer": {"a": {"b": 3, "y": 2}, "z": 1}}
    assert hash_obj(left) == hash_obj(right)


def test_nfc_normalization_unifies_visually_identical_strings():
    composed = "café"            # e-acute, single code point
    decomposed = "café"         # e + combining acute
    assert composed != decomposed     # different code points...
    assert hash_obj({"k": composed}) == hash_obj({"k": decomposed})  # ...same canonical hash


def test_nfc_duplicate_keys_rejected():
    with pytest.raises(CanonicalizationError, match="duplicate key"):
        canonical_dumps({"café": 1, "café": 2})


def test_non_string_keys_rejected():
    with pytest.raises(CanonicalizationError, match="non-string key"):
        canonical_dumps({1: "a"})


def test_nan_and_infinity_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalizationError):
            canonical_dumps({"v": bad})


def test_non_json_types_rejected():
    with pytest.raises(CanonicalizationError, match="non-JSON type"):
        canonical_dumps({"v": {1, 2}})
    with pytest.raises(CanonicalizationError, match="non-JSON type"):
        canonical_dumps(object())


def test_tuples_canonicalize_as_arrays():
    assert canonical_dumps((1, 2)) == canonical_dumps([1, 2])


def test_bool_and_int_serialize_distinctly():
    assert canonical_dumps(True) == "true"
    assert canonical_dumps(1) == "1"
    assert hash_obj({"v": True}) != hash_obj({"v": 1})


def test_utf8_bytes_not_ascii_escapes():
    assert canonical_bytes("café") == b'"caf\xc3\xa9"'


def test_known_hash_vector():
    # A pinned vector: if this ever changes, every hash in every stored
    # attestation changes, which is a breaking engine version bump.
    assert hash_obj({"a": 1}) == "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"


def test_unicode_in_hash_stable():
    assert hash_obj({"note": "rétention ≥ 180"}) == hash_obj({"note": "rétention ≥ 180"})


def test_string_values_nfc_normalized():
    assert canonical_dumps(unicodedata.normalize("NFD", "café")) == canonical_dumps("café")
