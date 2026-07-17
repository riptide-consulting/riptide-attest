"""Canonical serialization and hashing. Deterministic by construction.

Every artifact the engine emits -- manifests, specs, attestations, drift
reports -- passes through canonical_bytes() before it is hashed or written.
The rules, stated once and enforced here:

  * UTF-8 encoding, NFC-normalized strings (keys and values).
  * Object keys sorted by Unicode code point; keys must be strings.
  * Minimal separators, no whitespace, no trailing newline in hashed content.
  * NaN and Infinity rejected outright (allow_nan=False would raise later;
    we reject earlier with a clearer error).
  * Duplicate keys after NFC normalization rejected: two visually identical
    keys with different code-point sequences would otherwise silently drop
    data depending on dict construction order.
  * Non-JSON types rejected; nothing is coerced. Coercion is a hiding place
    for nondeterminism.

Float note: Python serializes floats via the shortest round-trip repr, which
is deterministic for IEEE 754 doubles across CPython >= 3.1 on all supported
platforms. The spec grammar itself prefers integers; evidence may carry
floats and they canonicalize stably.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized deterministically."""


def _normalize(obj: object, path: str = "$") -> object:
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise CanonicalizationError(f"{path}: NaN/Infinity cannot be canonicalized")
        return obj
    if isinstance(obj, dict):
        out: dict[str, object] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"{path}: non-string key {key!r}")
            nkey = unicodedata.normalize("NFC", key)
            if nkey in out:
                raise CanonicalizationError(f"{path}: duplicate key after NFC normalization: {nkey!r}")
            out[nkey] = _normalize(value, f"{path}.{nkey}")
        return out
    if isinstance(obj, (list, tuple)):
        return [_normalize(item, f"{path}[{i}]") for i, item in enumerate(obj)]
    raise CanonicalizationError(f"{path}: non-JSON type {type(obj).__name__}")


def canonical_dumps(obj: object) -> str:
    """Serialize to the one canonical JSON text for this value."""
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(obj: object) -> bytes:
    return canonical_dumps(obj).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj: object) -> str:
    """The canonical hash of a JSON value: sha256 of its canonical bytes."""
    return sha256_hex(canonical_bytes(obj))


def write_canonical(path, obj: object) -> str:
    """Write a canonical JSON file (binary mode: no platform newline
    translation -- CRLF would silently break byte-stability on Windows).
    File bytes are canonical content plus one trailing LF for POSIX
    friendliness; hashes are always computed on the content alone.
    Returns the content hash."""
    data = canonical_bytes(obj)
    with open(path, "wb") as fh:
        fh.write(data)
        fh.write(b"\n")
    return sha256_hex(data)


def read_json(path) -> object:
    """Read JSON in binary mode; canonical files round-trip exactly."""
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))
