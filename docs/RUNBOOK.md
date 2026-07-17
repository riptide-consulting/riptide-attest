# Operator runbook

Procedures for running Riptide Attest day to day. Command shapes come
from `main.py`; flag defaults are `--state state/` and
`--registry registry/approved.json` on every verb, plus `--json` for
machine-readable stdout. Exit codes: `0` success, `2` rollup not pass
(a finding, not an error), `1` replay mismatch (the world or the inputs
changed), `3` refused (approval missing, spec invalid, or an integrity
self-check failed -- tampered evidence, snapshot, or attestation file).
Refusals are one-line `refused:` messages, never tracebacks; `1` and `3`
are distinct so alerting can tell drift from tampering
(`tests/unit/test_cli.py` pins the contract).

## Authoring a new control, end to end

The three authoring verbs call a model and need `ANTHROPIC_API_KEY` (see
`.env.example`). Nothing else in this runbook does.

**1. Triage** -- decide what is machine-attestable at all:

```
python main.py triage fixtures/ria_remediation_plan.json --json
```

One decision per remediation action: `attestable`, `confidence`,
`rationale`. The backstop is deterministic: confidence below 0.7 forces
`attestable=false` -- uncertainty routes to humans, never to automation.
Actions marked human-tracked stay in the tracker; do not compile them.

**2. Compile** -- one attestable action into a draft spec:

```
python main.py compile action-A6.json --out state/drafts/A6.json
```

The action file holds one remediation action object (the shape in
`fixtures/ria_remediation_plan.json`). The draft must already pass
`attest/engine/schema.py` validation (the compiler rejects rather than
repairs, and forces `on_unknown: "fail"`). A draft is inert: it is not
in the registry, so the engine refuses to evaluate it.

**3. Explain** -- the plain-language half of the review packet:

```
python main.py explain state/drafts/A6.json
```

The output is labeled advisory. It helps you read the spec; it carries
no authority and is never quoted into verdicts.

**4. Dry-run** -- execute the draft against real evidence in a scratch
state, using a scratch registry so the real one stays clean:

```
python main.py approve state/drafts/A6.json --by <your-name> --registry state/scratch/approved.json
python main.py snapshot --specs state/drafts/A6.json --target <target-root> --state state/scratch
python main.py evaluate --specs state/drafts/A6.json --snapshot <snap-id> --state state/scratch --registry state/scratch/approved.json
```

(`snapshot` prints the `snap-...` id to use.) Read the per-check
verdicts and details. The question to answer before approving: does
this spec fail when the control is actually unmet? If you only have
compliant evidence to test against, temporarily doctor a copy -- a spec
that cannot fail is not checking anything. This is the same grading rule
the eval suite applies to the compiler (`evaluations/`).

**5. Approve** -- the real pin, with the draft, the dry-run result, and
the explainer in hand:

```
python main.py approve state/drafts/A6.json --by <your-name>
```

This writes the spec's canonical SHA-256 into `registry/approved.json`
under your name and timestamp. Move the approved file into `specs/` and
commit both. Any subsequent edit to the spec voids the approval
(`attest/engine/registry.py`).

## Running attestations on a schedule

Each scheduled run is two verbs -- freeze, then verify:

```
python main.py snapshot --specs specs/*.json --target <target-root> --json
python main.py evaluate --specs specs/*.json --snapshot <snap-id> --json
```

(`--specs` takes explicit file paths; POSIX shells expand the glob, but
Windows PowerShell does not -- list the spec files there.)

Omit `--at` so the snapshot is stamped with the single sanctioned clock
read (`utc_now_stamp` in `attest/collect.py`). Parse `snapshot_id` from
the snapshot's JSON output and feed it to `evaluate`. Wire alerting to
the exit code: `2` means the rollup is fail or unknown and names the
failing predicate in the output; `3` means the run was refused (see
troubleshooting) and needs an operator, not a re-run. Every verb
appends one JSONL line to `logs/attest.log` (`attest/audit.py`), which
is the operational record of who ran what, when, on which hashes.

Snapshots taken at different instants are different snapshots by design
(`docs/DETERMINISM.md`); the schedule produces a series of attestations,
and `diff` turns any two into a drift report.

## Reading a drift report

```
python main.py diff state/attestations/att-A.json state/attestations/att-B.json
```

Shapes from `attest/engine/diffing.py`:

* `summary.stable: true` -- the attestations are equivalent; nothing
  changed that the controls can see.
* a transition with `change: "verdict"` -- a control's verdict moved
  (`from`/`to`); the `checks` array names which check moved and the
  evidence hashes on each side. Fail -> pass after a fix is the
  expected shape; pass -> fail is a regression to act on.
* `change: "detail"` -- the control's verdict held but something under
  it moved: a check's evidence hash changed with no verdict impact
  (`evidence-only`), or the spec hash changed (`spec_changed: true`,
  meaning a re-approved spec revision).
* `change: "added"` / `"removed"` -- the control set itself differs
  between the two attestations.

The report is canonical JSON: "what changed between Monday and Friday"
has exactly one answer.

## Replaying for an auditor

Hand over three things: the attestation file, the state directory
(`objects/` and `snapshots/`), and `registry/approved.json`. The auditor
runs:

```
python main.py replay state/attestations/att-ef4d859e0bd776f6.json
```

The chain of custody it walks (`attest/engine/replay.py`): the
attestation self-check (id == hash of body), the manifest fetched from
the object store by the hash the body cites, each spec fetched by the
hash each control cites, the approval check for each spec, then full
re-evaluation and byte comparison. Anything short of an exact hash
match is a failure with a named reason -- there is no "close enough,"
because the entire value of the artifact is that there is nothing to
argue about. The auditor needs no credentials, no network, and no trust
in your copy of the engine's output: the replay re-derives it.

## Rotating and revoking approvals

An approval is one entry in `registry/approved.json`, keyed by the
spec's canonical hash. To revoke: delete that hash's entry from the file
(it is canonical single-line JSON; edit with a JSON-aware tool and keep
the file valid). To rotate a control to a new spec version: approve the
new spec (a new hash entry), then delete the old hash.

What revocation does, immediately and retroactively:

* `evaluate` refuses the spec at the point of use with `ApprovalError`,
  exit 3 (`require_approved` in `attest/engine/registry.py`).
* **Replay of any past attestation citing that spec fails loudly** --
  the replay chain re-checks approval, so a verdict whose authority was
  withdrawn no longer re-verifies (`attest/engine/replay.py`, asserted
  by `test_replay_fails_when_approval_revoked` in
  `tests/unit/test_determinism.py`). This is by design: keep the old
  registry file (it is in version control) if you need to demonstrate
  what was approved at the time.
* Re-approving the identical bytes restores both, because the pin is
  content, not time.

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| `refused: spec ... is not in the approval registry` right after you edited a spec that ran yesterday | The approval is the hash of the content; your edit voided it. **This is the design working**, not a bug (invariant 2, `attest/engine/registry.py`). | Re-review the edited spec (dry-run + explain) and re-approve: `python main.py approve <spec> --by <name>`. |
| `TamperError: object store integrity failure: content at address ... hashes to ...` | A stored evidence object (or stored spec/manifest) was modified after collection. `ObjectStore.get()` re-hashes on every read (`attest/engine/snapshot.py`). | Treat as an incident: the store no longer proves what it stored. Restore `state/objects/` from backup or re-snapshot; attestations citing the doctored object cannot be re-derived from this store. |
| `TamperError: snapshot ...: manifest content does not hash to the snapshot id` | A snapshot file under `state/snapshots/` was edited or renamed (`load_snapshot` in `attest/engine/snapshot.py`). | Same as above: restore or re-snapshot. |
| `refused: attestation ... fails its self-check` (exit 3) | The attestation file was modified after it was written; the stored id no longer matches the body's hash (`load_attestation` in `attest/engine/report.py`). | Recover the original from backup, or re-evaluate the snapshot -- determinism means the regenerated file is byte-identical to what the original was. |
| `refused: ATTEST_PUBLISH_APPROVED is not set` (exit 3) on publish | The human key for the one external effect is checked inside the write, at the moment of the write (`attest/publish.py`). | If a human has decided to publish: set `ATTEST_PUBLISH_APPROVED=1` for that shell and re-run. Never persist it in a config file -- that is deliberate (`.env.example`). |
| publish returns `published: false ... no tracker credentials configured` | The key was set, but `NOTION_API_KEY` is not; nothing was sent (`attest/publish.py`). | Configure tracker credentials, or accept the local attestation file as the deliverable. |
| `evaluate` exits 2 | Not an error: the rollup is fail or unknown. The output names each failing check and its detail string. | Read the attestation; fix the control in the target system; re-snapshot and re-evaluate. |
| `SpecError` listing unknown keys or bad predicate params | The grammar rejects unknown keys everywhere -- a typo validation ignored would weaken a control forever (`attest/engine/schema.py`). | Fix every listed error (the exception carries all of them, not just the first) and re-validate. |
| `CollectorError: no adapter for scheme ...` | A spec cites a selector scheme no configured adapter serves (`attest/collect.py`). This is a config error, not evidence absence. | Add or configure the adapter; absence of evidence would have been recorded as an error entry and failed closed instead. |
| replay: `re-derived attestation ... differs from stored` | Inputs, engine version, or approvals changed since the original run (`attest/engine/replay.py`). | Compare `engine_version` in the attestation body against `ENGINE_VERSION`; check the registry for revocations; diff the re-derived attestation against the stored one to localize the change. |
