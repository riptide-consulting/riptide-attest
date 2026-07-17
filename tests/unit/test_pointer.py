"""RFC 6901 pointer resolution, including the MISSING contract."""

import pytest

from attest.engine import MISSING, resolve_pointer, validate_pointer
from attest.engine.pointer import PointerSyntaxError

DOC = {
    "a": {"b": [10, 20, {"c": "found"}]},
    "": "empty-key",
    "k/l": "slash",
    "m~n": "tilde",
    "0": "zero-key",
}


@pytest.mark.parametrize("pointer,expected", [
    ("", DOC),
    ("/a", DOC["a"]),
    ("/a/b/0", 10),
    ("/a/b/2/c", "found"),
    ("/", "empty-key"),
    ("/k~1l", "slash"),
    ("/m~0n", "tilde"),
    ("/0", "zero-key"),
])
def test_resolution(pointer, expected):
    assert resolve_pointer(DOC, pointer) == expected


@pytest.mark.parametrize("pointer", [
    "/missing", "/a/missing", "/a/b/9", "/a/b/-", "/a/b/01", "/a/b/0/deeper", "/a/b/x",
])
def test_absent_paths_return_missing(pointer):
    assert resolve_pointer(DOC, pointer) is MISSING


def test_missing_is_falsy_singleton():
    assert not MISSING
    assert repr(MISSING) == "<missing>"


@pytest.mark.parametrize("bad", ["a/b", "a", "/~2", "/~"])
def test_syntax_errors(bad):
    with pytest.raises(PointerSyntaxError):
        validate_pointer(bad)


def test_valid_syntax_accepted():
    for good in ("", "/", "/a/b/0", "/~0/~1"):
        validate_pointer(good)
