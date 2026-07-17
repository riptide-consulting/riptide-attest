"""RFC 6901 JSON Pointer resolution, implemented in ~40 lines rather than
imported, so the engine's dependency count for evidence addressing stays at
zero and the resolution behavior is testable line by line.

Resolution never raises on absent paths: it returns the MISSING sentinel,
and the predicate layer decides what MISSING means (exists -> fail,
comparisons -> unknown). Failing closed is a verdict-policy decision that
belongs in one place, not an exception-handling accident scattered here.
"""

from __future__ import annotations


class _Missing:
    """Sentinel for 'the pointer resolved to nothing'. Falsy, single instance."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # deterministic repr for detail strings
        return "<missing>"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


class PointerSyntaxError(ValueError):
    """Raised for malformed pointer syntax (a spec-validation error, caught
    at compile/approve time; never during evaluation of an approved spec)."""


def validate_pointer(pointer: str) -> None:
    if not isinstance(pointer, str):
        raise PointerSyntaxError("pointer must be a string")
    if pointer == "":
        return
    if not pointer.startswith("/"):
        raise PointerSyntaxError(f"pointer must be empty or start with '/': {pointer!r}")
    for token in pointer.split("/")[1:]:
        i = 0
        while i < len(token):
            if token[i] == "~":
                if i + 1 >= len(token) or token[i + 1] not in ("0", "1"):
                    raise PointerSyntaxError(f"bad escape in pointer token: {token!r}")
                i += 2
            else:
                i += 1


def resolve_pointer(doc: object, pointer: str) -> object:
    """Resolve a validated RFC 6901 pointer against a JSON value.
    Returns MISSING when any step of the path is absent."""
    if pointer == "":
        return doc
    current = doc
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return MISSING
            current = current[token]
        elif isinstance(current, list):
            # RFC 6901 array indices are ASCII digits only. str.isdigit()
            # is wider than that (it accepts superscripts, which then crash
            # int(), and non-ASCII decimal digits, which int() silently
            # converts); both violate the RFC and determinism, so the check
            # is explicit.
            if not token or any(c not in "0123456789" for c in token):
                return MISSING
            if len(token) > 1 and token.startswith("0"):
                return MISSING
            index = int(token)
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            return MISSING
    return current
