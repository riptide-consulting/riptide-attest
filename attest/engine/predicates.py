"""The predicate library: pure functions from (predicate, value, context) to
a verdict. This is the entire vocabulary a compiled spec can use; anything
the grammar cannot express, the engine cannot check, and that boundary is a
feature -- an approved spec's behavior is exhaustively enumerable from this
file.

Verdict algebra, stated once:

    fail dominates unknown dominates pass

  * all:  any fail -> fail; else any unknown -> unknown; else pass
  * any:  any pass -> pass; else any unknown -> unknown; else fail
  * none: any pass -> fail; else any unknown -> unknown; else pass
  * not:  swaps pass/fail; unknown stays unknown (ignorance does not invert)

MISSING evidence: `exists` fails, `absent` passes; every other predicate
returns unknown, and unknown becomes fail at the spec rollup unless the spec
explicitly opts into reporting it (schema.py forces the compiler's default
to fail-closed).

Time: the only clock this module ever sees is the snapshot's collected_at,
passed in as context. `max_age_days` measures evidence timestamps against
that frozen instant, so re-evaluating an old snapshot years later yields the
same verdict it yielded on day one. A future-dated timestamp fails rather
than passing: a clock that disagrees with the snapshot is itself a finding.
"""

from __future__ import annotations

from datetime import datetime

from .canonical import CanonicalizationError, canonical_dumps
from .pointer import MISSING

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"

_DETAIL_LIMIT = 120


def _fmt(value: object) -> str:
    """Deterministic rendering of a value for detail strings."""
    if value is MISSING:
        return "<missing>"
    try:
        text = canonical_dumps(value)
    except CanonicalizationError:
        text = repr(value)
    if len(text) > _DETAIL_LIMIT:
        text = text[: _DETAIL_LIMIT - 3] + "..."
    return text


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_utc_timestamp(value: object):
    """Parse an ISO-8601 timestamp with explicit offset ('Z' accepted).
    Returns None for anything else -- naive timestamps are rejected because
    'local time' is nondeterministic across machines."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def combine_verdicts(op: str, verdicts: list[str]) -> str:
    if op == "all":
        if FAIL in verdicts:
            return FAIL
        if UNKNOWN in verdicts:
            return UNKNOWN
        return PASS
    if op == "any":
        if PASS in verdicts:
            return PASS
        if UNKNOWN in verdicts:
            return UNKNOWN
        return FAIL
    if op == "none":
        if PASS in verdicts:
            return FAIL
        if UNKNOWN in verdicts:
            return UNKNOWN
        return PASS
    raise ValueError(f"unknown combinator {op!r}")


def evaluate_predicate(pred: dict, value: object, ctx: dict) -> tuple[str, str]:
    """Evaluate one predicate against one evidence value.
    Returns (verdict, detail). Pure: output depends only on arguments.
    Specs reaching this function have already passed schema validation, so
    structural errors here indicate an engine bug, not bad input."""
    op = pred["op"]

    # -- combinators -------------------------------------------------------
    if op in ("all", "any", "none"):
        results = [evaluate_predicate(p, value, ctx) for p in pred["preds"]]
        verdict = combine_verdicts(op, [v for v, _ in results])
        parts = "; ".join(f"[{v}] {d}" for v, d in results)
        return verdict, f"{op}({parts})"
    if op == "not":
        inner_verdict, inner_detail = evaluate_predicate(pred["pred"], value, ctx)
        if inner_verdict == PASS:
            return FAIL, f"not({inner_detail})"
        if inner_verdict == FAIL:
            return PASS, f"not({inner_detail})"
        return UNKNOWN, f"not({inner_detail})"

    # -- existence: the only ops with an opinion about MISSING -------------
    if op == "exists":
        if value is MISSING:
            return FAIL, "expected a value, found none"
        return PASS, f"value present: {_fmt(value)}"
    if op == "absent":
        if value is MISSING:
            return PASS, "no value present, as required"
        return FAIL, f"expected no value, found {_fmt(value)}"

    if value is MISSING:
        return UNKNOWN, f"cannot apply {op}: evidence value missing"

    # -- leaves ------------------------------------------------------------
    if op in ("eq", "ne"):
        expected = pred["value"]
        if isinstance(expected, bool) != isinstance(value, bool):
            equal = False  # True == 1 in Python; not in an attestation
        else:
            equal = value == expected
        if op == "eq":
            return (PASS if equal else FAIL), f"{_fmt(value)} {'==' if equal else '!='} {_fmt(expected)}"
        return (FAIL if equal else PASS), f"{_fmt(value)} {'==' if equal else '!='} {_fmt(expected)}"

    if op in ("lt", "lte", "gt", "gte"):
        if not _is_number(value):
            return UNKNOWN, f"{op} requires a number, got {_fmt(value)}"
        bound = pred["value"]
        outcome = {
            "lt": value < bound,
            "lte": value <= bound,
            "gt": value > bound,
            "gte": value >= bound,
        }[op]
        symbol = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}[op]
        return (PASS if outcome else FAIL), f"{_fmt(value)} {symbol} {_fmt(bound)} is {str(outcome).lower()}"

    if op == "in":
        allowed = pred["values"]
        hit = any(
            (isinstance(v, bool) == isinstance(value, bool)) and v == value for v in allowed
        )
        return (PASS if hit else FAIL), f"{_fmt(value)} {'in' if hit else 'not in'} {_fmt(allowed)}"

    if op == "contains":
        needle = pred["value"]
        if isinstance(value, str):
            if not isinstance(needle, str):
                return UNKNOWN, "contains on a string requires a string operand"
            hit = needle in value
        elif isinstance(value, list):
            hit = any(
                (isinstance(v, bool) == isinstance(needle, bool)) and v == needle for v in value
            )
        else:
            return UNKNOWN, f"contains requires a string or array, got {_fmt(value)}"
        return (PASS if hit else FAIL), f"{_fmt(needle)} {'found in' if hit else 'not found in'} {_fmt(value)}"

    if op == "regex_fullmatch":
        if not isinstance(value, str):
            return UNKNOWN, f"regex_fullmatch requires a string, got {_fmt(value)}"
        import re  # stdlib re is deterministic for a given pattern and input

        hit = re.fullmatch(pred["pattern"], value) is not None
        return (PASS if hit else FAIL), f"{_fmt(value)} {'matches' if hit else 'does not match'} /{pred['pattern']}/"

    if op in ("len_lte", "len_gte"):
        # Arrays only. A length predicate expresses "how many members", and
        # accepting strings or objects here would let a scalar of the wrong
        # JSON type masquerade as a member count ({"approvers": "no"} has
        # len 2) -- an undeserved pass from malformed or hostile evidence.
        if not isinstance(value, list):
            return UNKNOWN, f"{op} requires an array, got {_fmt(value)}"
        length = len(value)
        bound = pred["value"]
        outcome = length <= bound if op == "len_lte" else length >= bound
        symbol = "<=" if op == "len_lte" else ">="
        return (PASS if outcome else FAIL), f"len {length} {symbol} {bound} is {str(outcome).lower()}"

    if op in ("is_true", "is_false"):
        expected = op == "is_true"
        if not isinstance(value, bool):
            return FAIL, f"expected the boolean {str(expected).lower()}, got {_fmt(value)}"
        outcome = value is expected
        return (PASS if outcome else FAIL), f"value is {_fmt(value)}, expected {str(expected).lower()}"

    if op == "max_age_days":
        timestamp = parse_utc_timestamp(value)
        if timestamp is None:
            return UNKNOWN, f"max_age_days requires an ISO-8601 timestamp with offset, got {_fmt(value)}"
        snapshot_time = ctx["snapshot_time"]
        age_days = (snapshot_time - timestamp).total_seconds() / 86400.0
        if age_days < 0:
            return FAIL, f"timestamp {_fmt(value)} is later than the snapshot itself"
        outcome = age_days <= pred["value"]
        return (
            (PASS if outcome else FAIL),
            f"age {age_days:.2f} days vs limit {_fmt(pred['value'])} at snapshot time",
        )

    raise ValueError(f"unknown predicate op {op!r}")  # unreachable for validated specs
