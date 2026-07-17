# Recordings: compile once, grade forever

One JSON file per eval case, named `<case_id>.json`:

```json
{
  "case": "mfa-required",
  "spec": { "spec_version": "1.0", "...": "..." },
  "model": "claude-opus-4-8",
  "recorded_at": "2026-07-17T00:00:00Z"
}
```

`spec` is the compiler's draft exactly as `attest.compiler.compile_control`
returned it. When the compiler refused to produce a spec (its
reject-don't-repair backstop raised `SpecError`), `spec` is `null` and a
`refusal` field carries the reason -- the refusal is a graded outcome for
injection cases, so it is recorded like any other.

The harness (`evaluations/harness.py`) writes a recording after every live
compilation and prefers an existing recording over the API on every run, so
each control text costs one compilation ever. Grading a recording is
offline, free, and byte-stable: the grader is the deterministic engine
(`attest/engine/`), and same spec + same fixtures means same verdicts.

Recordings are committed once they exist. None ship with the repo yet: the
first `--live` run (an operator decision -- it spends API dollars against
the operator's key) produces them, and until then `--offline` reports every
case SKIPPED with pass rate n/a. A skipped suite is reported as ungraded,
never as passing: the injection results only count as safety evidence after
a live run has been recorded and committed. To record, or to re-record a
case (new compiler model, changed control text -- delete its file first):

    .venv/Scripts/python evaluations/harness.py --live

A recording holds model output that has never crossed human approval. It is
input to the grading sandbox only; nothing here is executable in production
and nothing here is ever written to registry/approved.json.
