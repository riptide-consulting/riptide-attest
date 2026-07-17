# CLAUDE.md -- Riptide Attest, spec for agentic development

This file governs any agent working in this repository. The binding design
brief is docs/PLAN.md; where this file, the brief, and the code disagree,
the code is authoritative.

## What this project is

Riptide Attest is the deterministic sibling of Riptide RIA. RIA is a
governed probabilistic pipeline: models write opinions every run, code
applies the rules, a human holds the key. Attest inverts the split: the
model compiles intent once, at authoring time; a deterministic engine
verifies forever; same evidence, same verdict, byte for byte. Attest
consumes RIA's remediation plan and proves whether the work is done, and
stays done. RIA writes the opinion; Attest carries the proof.

## The purity contract for attest/engine/

attest/engine/ is the pure core. It is done and reviewed. Do not add
modules, imports, or "small helpers" to it.

Inside the engine there is no clock, no randomness, no network, no
environment, no process spawning, and no model SDK. The authoritative
forbidden lists are `FORBIDDEN_MODULES` and `FORBIDDEN_ATTRIBUTES` in
tests/unit/test_purity.py: no importing time, random, uuid, secrets,
socket, ssl, select, asyncio, http, urllib, urllib3, requests, httpx,
subprocess, multiprocessing, threading, anthropic, claude_agent_sdk, mcp,
notion_client, or googleapiclient; no calling datetime.now/today/utcnow or
date.today; no touching os.environ, os.getenv, or os.urandom. The engine
may parse timestamps; it may never ask what time it is. It may read files;
it may never read the environment.

Enforcement is three layers deep, and the layers are not interchangeable:

1. tests/unit/test_purity.py -- the wall. AST scan of every engine module
   on every push. Cannot be fooled by formatting.
2. .claude/hooks/purity_guard.py -- the tripwire. Blocks an Edit/Write
   into attest/engine/ that matches a forbidden pattern, before it lands.
   It fails open by design; do not "harden" it into a wall.
3. CI (.github/workflows/ci.yml) -- runs the wall on Linux, as its own
   named step.

The one sanctioned clock read in the whole codebase is
`utc_now_stamp()` in attest/collect.py. Wall-clock timestamps are also
allowed in attest/audit.py (the operational log) and in the .claude hooks
-- none of which are engine code.

## Model routing policy

Model spend exists only at authoring time (the triage, compile, and
explain verbs). Runtime verbs -- snapshot, evaluate, replay, diff, publish
-- import no model SDK: main.py dispatches the authoring verbs through
lazy imports, and the purity test makes an engine-level `import anthropic`
a test failure.

Model ids are pinned snapshots, declared once, in .env.example
(MODEL_TRIAGE, MODEL_COMPILER, MODEL_EXPLAINER). Opus sits at the compile
step because compilation is the trust boundary: a wrong spec produces
wrong attestations forever. Changing any model id is an operator decision,
made by a human editing their .env deliberately -- never something an
agent does as a side effect of another task, and never a hardcoded
fallback in code.

## Human-authority artifacts -- agents never modify these

- registry/approved.json -- the approval registry. An approval is a hash
  pin placed by a named human (`python main.py approve --by <name>`). An
  agent writing this file is forging an approval; require_approved() in
  attest/engine/registry.py is the invariant it would be forging past.
- tests/golden/** -- frozen artifacts. Regenerated only by a human running
  scripts/freeze_goldens.py after reviewing why the bytes changed.
- specs/*.json -- approved CheckSpecs. Editing one voids its approval
  (the registry pins the canonical SHA-256; the engine refuses an edited
  spec at the point of use -- run_demo.py section 2 demonstrates this).

If you believe one of these artifacts is wrong, say so and stop. Do not
fix it. The same restraint applies to attest/engine/ itself and to
fixtures/: they are the ground the tests stand on.

## Running things

    .venv/Scripts/python -m pytest tests/ -q          # full offline suite, <1s
    .venv/Scripts/python -m pytest tests/unit/test_purity.py -q   # the purity wall alone
    .venv/Scripts/python run_demo.py                  # self-verifying demo; exit code is the proof
    run_demo.bat                                      # the double-click form of the same

Both must be green before any commit. The suite and the demo run offline
with zero model spend; needing a network or an API key to pass a test is
itself a bug.

## Commit conventions

- Subject: imperative, <= 72 characters, prefixed with the area touched:
  `engine:`, `model:`, `cli:`, `collect:`, `tests:`, `docs:`, `demo:`,
  `hooks:`, `ci:`, `evals:`, `mcp:`.
- Body: name the invariant the change touches (docs/PLAN.md numbers them)
  and the test that proves it still holds.
- One concern per commit. Never mix a human-authority artifact change
  (which only a human makes) into a code commit.
- No commit with a red test suite or a red demo; no `--no-verify`.
