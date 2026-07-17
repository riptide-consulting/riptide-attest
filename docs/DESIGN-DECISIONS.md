# Design decisions

Questions a reviewer should ask, answered in the same register as RIA's
design notes: plain, declarative, each answer naming the file that makes
it true.

## Why compile-once instead of judge-every-run?

Because the two halves of the problem have different epistemics and
different economics. Reading a control's intent is judgment; checking a
retention number against a bound is arithmetic. A judge-every-run design
pays model latency, model cost, and model variance on every attestation,
and its verdicts are opinions -- two runs can disagree, and an auditor
has nothing to re-derive. Compile-once moves all judgment to authoring
time, where a human reviews it, and leaves runtime with a pure function:
same evidence, same verdict, byte for byte
(`tests/unit/test_determinism.py`). The lifecycle table in `main.py`'s
docstring shows the cost consequence: every runtime verb costs $0.

RIA made the opposite choice for the opposite problem: regulatory text
changes weekly and needs fresh judgment per document. Attest's controls
change rarely and need identical judgment per evaluation. The
architecture follows the epistemics.

## Why is approval a hash pin instead of an env var?

RIA's human key (`RIA_EVALUATOR_APPROVED`) gates *writes*: the moment of
external effect. Attest's engine performs no external writes, so its
gate moves to the other consequential moment: *what is allowed to run*
(`attest/engine/registry.py`). An env var answers "may this process
act?"; a hash pin answers "may this exact content act?" -- and the
second question is the one that matters when the content was drafted by
a model. Because the pin is the canonical SHA-256 of the spec:

* editing one character voids the approval,
* there is no "approve whatever the compiler produces next" -- the human
  approves bytes they have read, and
* the compiler cannot approve its own output, because the registry is
  written only by the `approve` verb under a human's name and the engine
  only ever reads it.

The check runs inside `evaluate_specs()`, at the point of use, not at
the CLI boundary -- the same placement argument as RIA's
`_require_approval()`: no refactor of calling code can forget a check
that lives inside the function that does the consequential thing.
(Attest keeps that write-side gate too, for its one external effect:
`attest/publish.py`.)

## Why does the engine forbid even datetime.now?

Because "mostly deterministic" is not a property; it is a bug that has
not happened yet. Any ambient read -- clock, environment, network,
randomness -- makes the evaluator a function of something other than its
arguments, and the byte-stability claim dies quietly. So the engine may
parse timestamps but never ask what time it is: the only "now" in scope
is the snapshot's `collected_at`, passed in as data
(`attest/engine/predicates.py`, `max_age_days`). The rule is enforced
three ways because each layer fails differently: an AST scan in
`tests/unit/test_purity.py` (the wall), the `.claude` purity-guard hook
(the tripwire during development), and the engine docstring
(`attest/engine/__init__.py`, for the humans). A useful side effect:
re-evaluating a ten-year-old snapshot yields the verdict it yielded on
day one, which is what an auditor means by "replay."

## Why fail-closed on missing evidence?

Because in compliance, absence of evidence is a finding, not a pass.
When a pointer resolves to nothing, the predicate layer returns unknown
(only `exists`/`absent` have opinions about MISSING --
`attest/engine/predicates.py`), and unknown escalates to fail at the
rollup (`attest/engine/evaluator.py`). The alternative -- skip what you
cannot see -- means a broken collector produces a clean report, which is
the worst failure mode a verification system can have: false assurance,
delivered silently. The same principle at collection time: an unreadable
selector is recorded as an error in the manifest, becoming an unknown
verdict downstream, never a crash and never a silent pass
(`attest/collect.py`, `build_manifest` in `attest/engine/snapshot.py`).
This is RIA's routing floor inverted: uncertainty routes to humans,
never to automation.

## Why can't the compiler emit `on_unknown: "report"`?

`on_unknown: "report"` is the one relaxation the grammar offers: let an
unknown stay unknown instead of failing. That is sometimes right -- a
control mid-migration, an adapter not yet built -- but it is a
risk-acceptance decision, and risk acceptance is a human act. A model
that can emit `"report"` can be prompted (or prompt-injected via hostile
control text) into authoring a fail-open spec. So the compiler's
backstop forces `on_unknown="fail"` if absent or `"report"` (model-layer
contract in `docs/PLAN.md`), the schema defaults to fail
(`attest/engine/schema.py`), and a human who wants `"report"` writes it
into the spec and re-approves -- the hash pin then records that a person
made that choice, by name, in `registry/approved.json`.

## Why is tier-style logic absent?

RIA has tiers because its outputs are authorizations: how much autonomy
a probabilistic judgment earns depends on confidence and stakes, so
low-confidence briefings route to humans. Attest has no tiers because
its outputs are facts, not authorizations. A verdict is a deterministic
consequence of frozen evidence and an approved spec; there is no
confidence to tier on, and "high-stakes fail" and "low-stakes fail" are
the same bytes. Where judgment does exist in Attest -- triage's
attestable/not-attestable call -- the tier logic reappears in exactly
one place: a confidence floor of 0.7, below which an action routes to
human tracking (triage backstop in `docs/PLAN.md`, asserted by the
demo's section 1). Authority questions are handled by gates, not tiers:
the approval registry for what runs, the publish key for what leaves.

## Why plain Python, no orchestration framework?

Because the product claim is that the runtime is auditable to the byte,
and every dependency in the verdict path is surface area an auditor must
trust without reading. The engine is stdlib-only by contract
(`requirements.txt` header, enforced by `tests/unit/test_purity.py`);
even RFC 6901 pointer resolution is ~40 implemented lines rather than a
dependency (`attest/engine/pointer.py`). An orchestration framework
would add retries, callbacks, and hidden state to a system whose entire
design goal is that a verdict is a pure function you can re-run by hand.
The lifecycle needs nothing more than a CLI dispatching to functions
(`main.py`); the state machine is in the artifacts (draft -> approved ->
snapshot -> attestation), not in a framework's memory.

## What is the honest residual risk?

**The compiler can mis-formalize intent.** A spec can be valid,
approved, deterministic -- and checking the wrong thing: the wrong
selector, a bound of 90 where the control means 180, an `any` where the
control means `all`. Determinism does not defend against this; it
guarantees you get the same wrong answer every time. Nothing in the
engine can catch it, because the engine's whole contract is to execute
approved specs exactly.

The mitigations are honest but not total:

* **The human approval is informed, not ceremonial**: the approver holds
  a dry-run result against real evidence and a plain-language explainer
  packet before pinning the hash (`docs/RUNBOOK.md`, authoring
  procedure; the explainer is advisory by contract and never quoted into
  verdicts).
* **The eval suite grades compilation by execution, not by looks**
  (`evaluations/`): each case runs the compiled spec against a fixture
  that should pass and one that should fail; a spec that cannot tell
  them apart fails the eval, including the injection suite's hostile
  control texts ("emit a spec that always passes").
* **Every verdict names its evidence by hash and its spec by hash**, so
  when a mis-formalization is found, the blast radius is enumerable:
  which attestations cited that spec hash, over which evidence
  (`attest/engine/report.py`), and revoking the approval makes every
  affected attestation fail replay loudly (`attest/engine/replay.py`).

The residual risk that remains after all three is the same one RIA
states for its human-in-the-loop: a reviewer can approve a wrong thing.
Attest narrows the window -- the reviewer sees the exact bytes, a
dry-run, and an explanation -- but no architecture makes a human
infallible, and this document does not claim one does.
