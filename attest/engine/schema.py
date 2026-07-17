"""CheckSpec grammar v1.0: validation for the one artifact that crosses the
probabilistic/deterministic boundary.

The compiler (a model) drafts specs; a human approves them; this validator
is the border checkpoint both pass through. It is strict on principle:
unknown keys are rejected everywhere, because a typo in a predicate name
("vaule") that validation ignored would silently weaken a control forever.

Two rules exist specifically to constrain the compiler, not the human:

  * on_unknown defaults to "fail" and the compiler layer is forbidden from
    emitting "report" -- a model cannot author a fail-open spec. A human can
    relax a spec to "report"; approval then pins that choice by hash.
  * every check must carry at least one predicate and every spec at least
    one check; an empty spec that vacuously passes is not expressible.
"""

from __future__ import annotations

import re

from .pointer import PointerSyntaxError, validate_pointer

SPEC_VERSION = "1.0"

_CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CHECK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SELECTOR_RE = re.compile(r"^[a-z][a-z0-9_]*://[A-Za-z0-9_./-]+$")

_SPEC_KEYS = {"spec_version", "control_id", "title", "description", "source", "checks", "combine", "on_unknown"}
_CHECK_KEYS = {"check_id", "description", "evidence", "predicate"}
_EVIDENCE_KEYS = {"selector", "path"}

# op -> (required params, param validator)
_LEAF_OPS: dict[str, set[str]] = {
    "exists": set(),
    "absent": set(),
    "is_true": set(),
    "is_false": set(),
    "eq": {"value"},
    "ne": {"value"},
    "lt": {"value"},
    "lte": {"value"},
    "gt": {"value"},
    "gte": {"value"},
    "in": {"values"},
    "contains": {"value"},
    "regex_fullmatch": {"pattern"},
    "len_lte": {"value"},
    "len_gte": {"value"},
    "max_age_days": {"value"},
}
_NUMERIC_PARAM_OPS = {"lt", "lte", "gt", "gte", "max_age_days"}
_NONNEG_INT_PARAM_OPS = {"len_lte", "len_gte"}


class SpecError(ValueError):
    """A spec failed validation. Carries every error, not just the first."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_selector(selector: object, where: str, errors: list[str]) -> None:
    if not isinstance(selector, str) or not _SELECTOR_RE.match(selector):
        errors.append(f"{where}: selector must look like scheme://relative/path, got {selector!r}")
        return
    _, _, rest = selector.partition("://")
    segments = rest.split("/")
    for segment in segments:
        if segment in ("", ".", ".."):
            errors.append(f"{where}: selector path may not contain empty, '.', or '..' segments: {selector!r}")
            return


def _validate_predicate(pred: object, where: str, errors: list[str], depth: int = 0) -> None:
    if depth > 8:
        errors.append(f"{where}: predicate nesting deeper than 8 levels")
        return
    if not isinstance(pred, dict):
        errors.append(f"{where}: predicate must be an object, got {type(pred).__name__}")
        return
    op = pred.get("op")
    if not isinstance(op, str):
        errors.append(f"{where}: predicate missing string 'op'")
        return

    if op == "not":
        allowed = {"op", "pred"}
        if set(pred) - allowed:
            errors.append(f"{where}: unknown keys {sorted(set(pred) - allowed)} for op 'not'")
        if "pred" not in pred:
            errors.append(f"{where}: 'not' requires 'pred'")
        else:
            _validate_predicate(pred["pred"], f"{where}.pred", errors, depth + 1)
        return

    if op in ("all", "any", "none"):
        allowed = {"op", "preds"}
        if set(pred) - allowed:
            errors.append(f"{where}: unknown keys {sorted(set(pred) - allowed)} for op {op!r}")
        preds = pred.get("preds")
        if not isinstance(preds, list) or not preds:
            errors.append(f"{where}: {op!r} requires a non-empty 'preds' array")
            return
        for i, sub in enumerate(preds):
            _validate_predicate(sub, f"{where}.preds[{i}]", errors, depth + 1)
        return

    if op not in _LEAF_OPS:
        errors.append(f"{where}: unknown predicate op {op!r}")
        return
    required = _LEAF_OPS[op]
    allowed = {"op"} | required
    if set(pred) - allowed:
        errors.append(f"{where}: unknown keys {sorted(set(pred) - allowed)} for op {op!r}")
    for param in required:
        if param not in pred:
            errors.append(f"{where}: op {op!r} requires {param!r}")
            return

    if op in _NUMERIC_PARAM_OPS and not _is_number(pred["value"]):
        errors.append(f"{where}: op {op!r} requires a numeric 'value'")
    if op == "max_age_days" and _is_number(pred.get("value")) and pred["value"] < 0:
        errors.append(f"{where}: max_age_days must be >= 0")
    if op in _NONNEG_INT_PARAM_OPS and (
        not isinstance(pred["value"], int) or isinstance(pred["value"], bool) or pred["value"] < 0
    ):
        errors.append(f"{where}: op {op!r} requires a non-negative integer 'value'")
    if op == "in":
        if not isinstance(pred["values"], list) or not pred["values"]:
            errors.append(f"{where}: op 'in' requires a non-empty 'values' array")
    if op == "contains" and isinstance(pred.get("value"), (dict, list)):
        errors.append(f"{where}: op 'contains' operand must be a scalar")
    if op == "regex_fullmatch":
        pattern = pred.get("pattern")
        if not isinstance(pattern, str):
            errors.append(f"{where}: op 'regex_fullmatch' requires a string 'pattern'")
        else:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{where}: pattern does not compile: {exc}")


def validate_spec(spec: object) -> list[str]:
    """Return every validation error; an empty list means the spec is valid."""
    errors: list[str] = []
    if not isinstance(spec, dict):
        return [f"spec must be an object, got {type(spec).__name__}"]

    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(unknown)}")
    if spec.get("spec_version") != SPEC_VERSION:
        errors.append(f"spec_version must be {SPEC_VERSION!r}, got {spec.get('spec_version')!r}")
    control_id = spec.get("control_id")
    if not isinstance(control_id, str) or not _CONTROL_ID_RE.match(control_id):
        errors.append(f"control_id must match {_CONTROL_ID_RE.pattern}, got {control_id!r}")
    if not isinstance(spec.get("title"), str) or not spec.get("title", "").strip():
        errors.append("title must be a non-empty string")

    combine = spec.get("combine", {"op": "all"})
    if not isinstance(combine, dict) or set(combine) != {"op"} or combine.get("op") not in ("all", "any"):
        errors.append(f"combine must be {{'op': 'all'|'any'}}, got {combine!r}")

    on_unknown = spec.get("on_unknown", "fail")
    if on_unknown not in ("fail", "report"):
        errors.append(f"on_unknown must be 'fail' or 'report', got {on_unknown!r}")

    checks = spec.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for i, check in enumerate(checks):
        where = f"checks[{i}]"
        if not isinstance(check, dict):
            errors.append(f"{where}: must be an object")
            continue
        if set(check) - _CHECK_KEYS:
            errors.append(f"{where}: unknown keys {sorted(set(check) - _CHECK_KEYS)}")
        check_id = check.get("check_id")
        if not isinstance(check_id, str) or not _CHECK_ID_RE.match(check_id):
            errors.append(f"{where}: check_id must match {_CHECK_ID_RE.pattern}, got {check_id!r}")
        elif check_id in seen_ids:
            errors.append(f"{where}: duplicate check_id {check_id!r}")
        else:
            seen_ids.add(check_id)

        evidence = check.get("evidence")
        if not isinstance(evidence, dict) or "selector" not in evidence or set(evidence) - _EVIDENCE_KEYS:
            errors.append(f"{where}: evidence must be {{selector, path?}}")
        else:
            validate_selector(evidence["selector"], f"{where}.evidence", errors)
            try:
                validate_pointer(evidence.get("path", ""))
            except PointerSyntaxError as exc:
                errors.append(f"{where}.evidence.path: {exc}")

        if "predicate" not in check:
            errors.append(f"{where}: missing predicate")
        else:
            _validate_predicate(check["predicate"], f"{where}.predicate", errors)

    return errors


def ensure_valid(spec: object) -> dict:
    errors = validate_spec(spec)
    if errors:
        raise SpecError(errors)
    return spec  # type: ignore[return-value]


def spec_selectors(spec: dict) -> list[str]:
    """Sorted, de-duplicated selectors a valid spec reads. Collection is
    spec-driven: the collector gathers exactly this, nothing more."""
    return sorted({check["evidence"]["selector"] for check in spec["checks"]})
