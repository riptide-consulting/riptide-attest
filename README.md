# Riptide Attest

Deterministic compliance verification. **The model compiles once; the
engine verifies forever.** A model translates a control's intent into a
formal CheckSpec at authoring time, a human approves that spec by hash,
and from then on a pure, deterministic engine evaluates it: same evidence,
same verdict, byte for byte, with zero model spend at runtime.

Attest is the deterministic sibling of Riptide RIA. RIA is a governed
probabilistic pipeline -- models write opinions every run, code applies
the rules, a human holds the key. Attest inverts the split. RIA's
briefing ends in a remediation plan; Attest consumes that plan and proves
whether each action is done, and stays done.

**RIA writes the opinion; Attest carries the proof.**

## The one-command demo

```
python run_demo.py
```

Offline, zero API spend, no dependencies beyond a Python 3.11+
interpreter (the engine is stdlib-only by contract -- `requirements.txt`
says so and `tests/unit/test_purity.py` enforces it). The demo is
self-verifying: every claim below is asserted with an exit code, not
narrated. It walks the full arc -- triage, the approval gate refusing an
edited spec, snapshot, evaluation, byte-identical re-evaluation, tamper
detection, remediation drift, replay, and the publish gate refusing an
external write without the human key.

Your run ends with these exact ids, because attestation ids are content
hashes and the demo freezes the snapshot timestamp to the fixture time:

```
ALL ASSERTIONS HELD.
  attestation (before remediation): att-ef4d859e0bd776f6
  attestation (after remediation):  att-3e9b22a10ea2e55f
```

If your bytes differ, something real is broken -- the demo exits nonzero
and names the assertion that failed. `docs/DETERMINISM.md` states the
claim precisely, including what is deliberately not claimed.

## The nine invariants

Each invariant names the file that enforces it. This table mirrors RIA's
invariants section; the enforcement moves because the architecture moves.

| # | Invariant | Enforcement |
|---|---|---|
| 1 | The compiler (a model) cannot execute. No code path runs model output without registry approval. | `require_approved()` in `attest/engine/registry.py`, called inside `evaluate_specs()` in `attest/engine/evaluator.py` |
| 2 | Only hash-approved specs run; editing a spec voids its approval. | The approval pin is the canonical SHA-256 of the spec content (`attest/engine/registry.py`) |
| 3 | Evaluation is pure: no clock, no randomness, no network, no environment, no model SDK inside the engine. | `tests/unit/test_purity.py` (AST scan of every engine module), the `.claude` purity-guard hook, CI |
| 4 | Same snapshot + same specs -> same attestation, byte for byte. | `tests/unit/test_determinism.py`, `tests/golden/`, `run_demo.py`'s own assertions |
| 5 | Every verdict replays. | `attest/engine/replay.py`; specs and manifests live in the same content-addressed store as evidence (`attest/engine/snapshot.py`) |
| 6 | Evidence is content-addressed; tampering is visible at the moment of use. | `ObjectStore.get()` re-hashes on every read (`attest/engine/snapshot.py`) |
| 7 | External effects require a human key at the point of the write. | `_require_approval()` inside `attest/publish.py` |
| 8 | Model spend exists only at authoring time. | Lazy imports in `main.py`; the purity test for the engine |
| 9 | Missing evidence fails closed. | MISSING -> unknown (`attest/engine/predicates.py`) -> fail at rollup (`attest/engine/evaluator.py`) unless a human approved `on_unknown: "report"`; the compiler is forbidden from emitting `"report"` (`attest/engine/schema.py`) |

## Install

```
python -m venv .venv
.venv\Scripts\activate          # Windows; on POSIX: source .venv/bin/activate
pip install -r requirements.txt
```

The engine itself needs nothing: `attest/engine/` is stdlib-only by
contract, so the demo and the runtime verbs (snapshot, evaluate, replay,
diff) run on a bare interpreter. `requirements.txt` serves the
authoring-time model layer (`anthropic`), integrations, and dev tooling
(`pytest`, `ruff`). No configuration is required for the runtime verbs
or the demo: `ANTHROPIC_API_KEY` serves only the three authoring verbs,
and tracker credentials serve only `publish` -- see `.env.example`.

Run the test suite (offline, under a second):

```
python -m pytest tests/ -q
```

175 tests pass. `tests/golden/` holds the frozen artifacts the
determinism tests compare bytes against.

## CLI verbs

`python main.py <verb>`. The verbs are a state machine, not a pipeline
(`main.py`'s docstring; the reasoning is in `docs/DESIGN-DECISIONS.md`).

| Verb | Actor | What it does |
|---|---|---|
| `triage <plan>` | model (authoring) | Classify remediation actions: machine-attestable or human-tracked |
| `compile <action> --out <path>` | model (authoring) | Control text -> draft CheckSpec; a draft is never executable as-is |
| `explain <spec>` | model (authoring) | Approved spec -> plain-language summary for the review packet |
| `approve <spec> --by <name>` | human | Pin the spec's canonical hash into `registry/approved.json` |
| `snapshot --specs ... --target <root>` | code | Freeze exactly the evidence the specs cite, content-addressed |
| `evaluate --specs ... --snapshot <id>` | code | Approved specs x snapshot -> attestation |
| `replay <attestation>` | code | Re-derive a stored attestation from stored artifacts, assert byte equality |
| `diff <att_a> <att_b>` | code | Two attestations -> deterministic drift report |
| `publish <attestation>` | code + human key | The one external effect, gated by `ATTEST_PUBLISH_APPROVED` at the point of the write |

All verbs take `--state` (default `state/`), `--registry` (default
`registry/approved.json`), and `--json` for machine-readable stdout.

Exit codes: `0` success (for `evaluate`, rollup pass); `2` rollup is not
pass (a finding, not an error); `1` replay mismatch -- the inputs or the
world changed since the original run; `3` refused -- an unapproved or
invalid spec, tampered evidence, a doctored snapshot or attestation file,
or the publish gate (`main.py` maps `PermissionError`/`SpecError`/
`TamperError`/`ReportError`/`SnapshotError` to 3). Refusals are one-line
`refused:` messages, never tracebacks; `tests/unit/test_cli.py` pins the
whole contract.

## Repository map

```
attest/engine/          the pure deterministic core (no clock, no network, no model SDK)
attest/collect.py       the one sanctioned clock read; fs evidence adapter
attest/audit.py         operational JSONL log (wall clock allowed here)
attest/publish.py       the gated external write
attest/{triage,compiler,explainer,model_client}.py   model layer (authoring time only)
agents/*/CLAUDE.md      per-agent scoped specs
main.py                 CLI; runtime verbs never import the model layer
run_demo.py             self-verifying offline demo (exit code = proof)
specs/                  compiled CheckSpecs (committed for the offline demo)
registry/approved.json  the approval registry (hash pins)
fixtures/               simulated target system + RIA plan + recorded triage
tests/unit/             175 offline tests; tests/golden/ frozen artifacts
evaluations/            compiler evals: deterministic verdict-based grading
mcp_servers/            evidence adapter + tracker writer behind ports
scripts/freeze_goldens.py   regenerates goldens when specs/fixtures/engine change
.claude/                root CLAUDE.md, purity-guard + audit hooks
docs/                   this documentation set
```

## Suggested reading order for a technical reviewer

1. `python run_demo.py` -- watch the nine sections assert themselves.
2. `attest/engine/canonical.py` -- the serialization rules every hash
   rests on.
3. `attest/engine/schema.py` and `docs/SPEC-GRAMMAR.md` -- the grammar
   that bounds what a compiled spec can ever do.
4. `attest/engine/predicates.py` -- the entire verdict vocabulary and the
   verdict algebra, in one file.
5. `attest/engine/evaluator.py` and `attest/engine/registry.py` -- the
   approval gate at the point of use.
6. `attest/engine/snapshot.py` and `attest/engine/replay.py` -- content
   addressing and the chain of custody a replay walks.
7. `tests/unit/test_determinism.py` and `tests/unit/test_purity.py` --
   the headline claims as executable assertions.
8. `docs/DESIGN-DECISIONS.md` -- why it is built this way, including the
   honest residual risk.
