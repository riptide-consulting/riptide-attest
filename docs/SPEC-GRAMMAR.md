# CheckSpec grammar v1.0

The CheckSpec is the one artifact that crosses the
probabilistic/deterministic boundary: a model drafts it, a human approves
it, the engine executes it forever. This document is the complete
reference for what a spec can say. The validator is
`attest/engine/schema.py`; the predicate semantics are
`attest/engine/predicates.py`; evidence addressing is
`attest/engine/pointer.py`. Where this document and those files disagree,
the code is authoritative.

The grammar is deliberately closed: anything it cannot express, the
engine cannot check, and an approved spec's entire possible behavior is
enumerable from `attest/engine/predicates.py`. That boundary is a
feature.

## Strictness

Unknown keys are rejected everywhere -- at the top level, in checks, in
evidence blocks, in every predicate. The reason is stated in
`attest/engine/schema.py`'s docstring: a typo in a predicate parameter
("vaule") that validation ignored would silently weaken a control
forever. A spec is approved by content hash, so a defect that survives
validation survives approval, and every attestation thereafter inherits
it. Validation is the border checkpoint; it is strict on principle, and
it reports every error, not just the first (`SpecError.errors`).

Two rules exist specifically to constrain the compiler, not the human:

* `on_unknown` defaults to `"fail"`, and the compiler layer is forbidden
  from emitting `"report"` -- a model cannot author a fail-open spec. A
  human can relax a spec to `"report"`; approval then pins that choice
  by hash.
* Every check carries at least one predicate and every spec at least one
  check; an empty spec that vacuously passes is not expressible.

## Top-level fields

| Field | Required | Constraint |
|---|---|---|
| `spec_version` | yes | exactly `"1.0"` |
| `control_id` | yes | matches `^[A-Za-z0-9][A-Za-z0-9._-]*$` |
| `title` | yes | non-empty string |
| `description` | no | free text for humans |
| `source` | no | provenance object (briefing ref, action ref, compiled_by/at); recorded, not validated in shape, never evaluated |
| `checks` | yes | non-empty array of checks; duplicate `check_id`s rejected |
| `combine` | no | exactly `{"op": "all"}` or `{"op": "any"}`; default `all` |
| `on_unknown` | no | `"fail"` or `"report"`; default `"fail"` |

## Checks

```json
{
  "check_id": "retention-at-least-180",
  "description": "Audit log retention period is 180 days or more",
  "evidence": {"selector": "fs://logging/retention.json", "path": "/audit_log/retention_days"},
  "predicate": {"op": "gte", "value": 180}
}
```

| Field | Required | Constraint |
|---|---|---|
| `check_id` | yes | matches `^[a-z0-9][a-z0-9-]*$`, unique within the spec |
| `description` | no | free text |
| `evidence` | yes | `{selector, path?}`; no other keys |
| `predicate` | yes | one predicate tree (below) |

**Selectors** name what to collect: `scheme://relative/path`, matching
`^[a-z][a-z0-9_]*://[A-Za-z0-9_./-]+$`, with empty, `.`, and `..` path
segments rejected (`validate_selector` in `attest/engine/schema.py`).
The collector reads exactly the selectors the approved specs cite and
nothing else (`spec_selectors` in `attest/engine/schema.py`,
`collect_for_specs` in `attest/collect.py`). The only adapter in this
build is `fs`.

**Paths** address a value inside the collected evidence body: an
RFC 6901 JSON Pointer, validated at spec-validation time
(`attest/engine/pointer.py`). The empty string addresses the whole
document. Resolution never raises on absent paths -- it returns the
MISSING sentinel, and the predicate layer decides what MISSING means.

## Predicates

A predicate is a tree of combinators over leaves. Nesting deeper than 8
levels is rejected.

### Combinators

| Op | Shape | Semantics |
|---|---|---|
| `all` | `{"op": "all", "preds": [...]}` | any fail -> fail; else any unknown -> unknown; else pass |
| `any` | `{"op": "any", "preds": [...]}` | any pass -> pass; else any unknown -> unknown; else fail |
| `none` | `{"op": "none", "preds": [...]}` | any pass -> fail; else any unknown -> unknown; else pass |
| `not` | `{"op": "not", "pred": {...}}` | swaps pass/fail; unknown stays unknown |

`preds` must be non-empty.

### Leaves

The MISSING column is the behavior when the evidence path resolved to
nothing; the wrong-type column is the behavior when a value is present
but not of the kind the predicate compares. From
`attest/engine/predicates.py`.

| Op | Params | On MISSING | On wrong type | Semantics |
|---|---|---|---|---|
| `exists` | -- | **fail** | -- | a value is present |
| `absent` | -- | **pass** | -- | no value is present |
| `is_true` | -- | unknown | **fail** | value is exactly the boolean `true` |
| `is_false` | -- | unknown | **fail** | value is exactly the boolean `false` |
| `eq` | `value` | unknown | -- | equality; booleans never equal numbers (`True == 1` in Python; not in an attestation) |
| `ne` | `value` | unknown | -- | negation of `eq` |
| `lt` `lte` `gt` `gte` | `value` (number) | unknown | unknown | numeric comparison |
| `in` | `values` (non-empty array) | unknown | -- | membership, boolean-strict like `eq` |
| `contains` | `value` (scalar) | unknown | unknown | substring of a string, or boolean-strict membership in an array |
| `regex_fullmatch` | `pattern` (compilable) | unknown | unknown | full match of a string value |
| `len_lte` `len_gte` | `value` (non-negative int) | unknown | unknown | member-count bound on an array; any other type (including strings and objects) is unknown, so wrong-type evidence cannot masquerade as a member count |
| `max_age_days` | `value` (number >= 0) | unknown | unknown (unparseable timestamp) | evidence timestamp is no older than N days, measured against the snapshot's `collected_at` |

Notes, each anchored in `attest/engine/predicates.py`:

* **Existence checks are the only predicates with an opinion about
  MISSING.** Every other predicate returns unknown for missing evidence:
  you cannot compare what you did not see.
* `is_true`/`is_false` fail (not unknown) on a present non-boolean: the
  assertion is "the value is this boolean," and a present value that is
  not is a decided failure, not ignorance. The number `1` is not `true`.
* `max_age_days` accepts only ISO-8601 timestamps with an explicit
  offset (`Z` accepted); naive timestamps yield unknown, because "local
  time" is nondeterministic across machines (`parse_utc_timestamp`). A
  timestamp later than the snapshot itself **fails**: a clock that
  disagrees with the snapshot is itself a finding. The only "now" this
  predicate ever sees is the snapshot's `collected_at`, so re-evaluating
  an old snapshot years later yields the same verdict it yielded on day
  one.
* Values quoted inside detail strings are rendered deterministically
  (canonical JSON) and truncated at 120 characters (`_fmt`).

## Verdict algebra

Stated once in `attest/engine/predicates.py`, restated here:

```
fail dominates unknown dominates pass
```

`not` swaps pass and fail and preserves unknown -- ignorance does not
invert.

At the spec level (`attest/engine/evaluator.py`): each check produces a
verdict; the spec's `combine` op (`all` or `any`) folds them into a raw
verdict; then, if the raw verdict is unknown and `on_unknown` is
`"fail"`, the effective verdict is fail. The attestation records both
(`raw_verdict` and `verdict`), so a fail-closed unknown is
distinguishable from a genuine fail.

A check is also unknown -- before any predicate runs -- when the snapshot
holds no evidence for its selector or the collector recorded an error for
it (`attest/engine/evaluator.py`). Fail-closed is the default state of
the world, not a configuration achievement.

## Worked examples (from `specs/`, executed by the demo)

**Bound plus enforcement flag**
(`specs/RIA-2026-14012-A2-session-timeout.json`): the timeout check
composes `exists` with `lte` so that a missing value fails via `exists`
rather than going unknown via `lte` alone -- the compiler chose to make
absence a decided failure:

```json
"predicate": {"op": "all", "preds": [{"op": "exists"}, {"op": "lte", "value": 15}]}
```

**Numeric bound, enum, boolean**
(`specs/RIA-2026-14012-A3-log-retention.json`): three independent
checks -- `gte 180` on retention days, `eq "siem"` on the destination,
`is_true` on immutable storage -- combined with `all`. In the demo's
before-remediation snapshot, retention is 90, so `retention-at-least-180`
fails and the control fails; the other two checks still report their own
verdicts.

**Freshness measured at snapshot time**
(`specs/RIA-2026-14012-A4-encryption-at-rest.json`): `max_age_days 92`
on the last key rotation proves the rotation actually happened within a
quarter of the snapshot instant -- a cadence policy nobody executes does
not satisfy the control -- and `len_lte 0` on the public-endpoints array
expresses "there are none."

## What approval means for the grammar

A spec is approved as bytes: the registry pins the canonical SHA-256 of
its content (`attest/engine/registry.py`, hashing rules in
`attest/engine/canonical.py`). Defaults are applied at evaluation time,
not written back, so adding an explicit `"on_unknown": "fail"` to a spec
that previously omitted it changes the hash and voids the approval --
the human re-approves what they can read, byte for byte.
