# Adversarial review record — 2026-07-17

Five skeptic lenses (platform determinism, fail-open hunt, gate bypass,
model layer, coverage/docs) attacked the build; every finding was judged by
three independent refuters and survived only with >= 2 of 3 votes. 18 raw
findings, 11 confirmed, 7 refuted. Skeptics were permitted to run code;
every confirmed finding below was demonstrated, not argued. All 11 are
fixed; the regression tests live in `tests/unit/test_hardening.py` and
`tests/unit/test_cli.py`.

## Confirmed and fixed

1. **[major] main.py exit-code contract violation.** `ReportError` /
   `SnapshotError` escaped as tracebacks with exit 1 — colliding with the
   documented replay-mismatch code, so alerting could not tell a doctored
   attestation from genuine drift. Fixed: both map to a one-line `refused:`
   and exit 3; pinned by `test_cli.py`. README/RUNBOOK wording aligned.
2. **[major] Eval recordings claimed committed but absent.** The offline
   eval suite graded nothing while three documents implied the injection
   results existed. Fixed: docs now state recordings exist only after an
   operator `--live` run, and that SKIPPED is never counted as passed.
   (Generating recordings spends API dollars — an operator decision, not
   one this build makes unilaterally.)
3. **[major] The purity wall was bypassable.** `from os import getenv`,
   `from datetime import datetime as dt; dt.now()`, `importlib`,
   `__import__`, `exec`, and literal `getattr` all passed the AST test and
   the hook. Fixed: alias-aware scanner resolving full dotted chains;
   dynamic import machinery forbidden outright; the scanner is now itself
   tested against all six bypass shapes (plus false-positive guards); the
   hook mirrors the new lists.
4. **[major] `len_gte`/`len_lte` fail-open on wrong-type evidence.**
   "At least 2 approvers" was satisfied by the string "no" (len 2) or a
   2-key object. Fixed: length predicates are array-only; anything else is
   unknown → fail-closed. Grammar doc updated.
5. **[major] Non-ASCII digits in JSON Pointer indices.** '²' passed
   validation then crashed `int()` during evaluation of an approved spec;
   '٣' silently resolved as index 3 contrary to RFC 6901. Fixed: indices
   are explicit ASCII digits; anything else resolves MISSING.
6. **[major] Hostile-but-parseable evidence crashed the whole snapshot.**
   `1e999` (JSON parses to Infinity) or NFC-colliding keys raised
   `CanonicalizationError` out of `build_manifest`, losing the entire
   collection pass. Fixed: uncanonicalizable bodies become error records →
   unknown → fail-closed, and the run continues.
7. **[minor] RUNBOOK overclaimed `evaluate` output detail.** The CLI named
   only failing controls. Fixed the code up to the doc: failing checks and
   their detail strings now print, and `--json` carries per-control
   verdicts.
8. **[minor] `load_attestation` failure branches untested.** Now pinned:
   malformed wrapper and edited-body self-check both raise `ReportError`.
9. **[minor] Collector guard branches untested.** Now pinned: traversal
   escape, unknown scheme (`CollectorError`), unparseable JSON,
   undecodable text.
10. **[minor] `diff_attestations` branches untested.** Now pinned: added,
    removed, spec-changed-without-verdict-change, evidence-only, and
    check added/removed.
11. **[minor] main.py had zero tests.** Now `tests/unit/test_cli.py` pins
    every documented exit code, the refusal messages, and the `--json`
    payload shapes, in-process.

## Refuted (kept for the record)

Windows filename case-insensitivity through the fs adapter (fixture-only
demo surface; enterprise adapters own their semantics); `exists` passing on
explicit JSON `null` (intended: null is a value, MISSING is not — pinned by
test); untrusted-framing gaps for plan metadata fields (framing covers the
free-text fields; metadata is operator-shaped); token accounting on the
no-tool-call path; replay reason-string test granularity; harness grading
equality nuance.
