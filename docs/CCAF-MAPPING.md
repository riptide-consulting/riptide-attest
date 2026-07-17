# CCAF domain mapping

How this build maps to the five CCAF domains. Attest and RIA are a
deliberate pair: each domain is demonstrated twice, once in a governed
probabilistic architecture (RIA) and once in a compile-once deterministic
one (Attest). The contrast is the point -- the same discipline, applied
to opposite epistemics.

## Agentic Architecture & Orchestration (27%)

**Attest artifacts.** The lifecycle as a state machine with three actor
classes -- model (authoring), human (authority), pure code (runtime) --
in `main.py`'s docstring and dispatch. The trust boundary as a package
boundary: `attest/engine/` cannot import the model layer, the collector,
or the publisher, and the dependency arrow is tested
(`test_engine_never_imports_the_outer_package` in
`tests/unit/test_purity.py`). Ports and adapters with the Reasoning Port
structurally absent from the runtime (`docs/ARCHITECTURE.md`). The
approval registry as the compile/execute gate
(`attest/engine/registry.py`).

**Contrast with RIA.** RIA demonstrates orchestration as a governed
pipeline: models write opinions every run, staged, gated, and routed by
confidence tiers. Attest demonstrates the other fundamental shape:
move all model judgment to authoring time, make runtime a pure function,
and replace runtime governance with content-hash approval. Knowing when
each shape applies is the architecture skill; `docs/DESIGN-DECISIONS.md`
("Why compile-once") argues the choice explicitly.

## Tool Design & MCP (18%)

**Attest artifacts.** Evidence adapters behind a selector-scheme port,
spec-driven and need-to-know: the collector reads exactly what approved
specs cite, nothing more (`attest/collect.py`, `spec_selectors` in
`attest/engine/schema.py`). The MCP-served forms -- evidence adapter and
tracker writer -- under `mcp_servers/`, sitting behind the same ports as
the in-process `fs` adapter, so transport is swappable without touching
the engine. The one external writer is gated inside the write
(`attest/publish.py`).

**Contrast with RIA.** RIA's tool surface acts on every run under
per-write gates. Attest's tool surface is read-mostly by design: one
writer exists, it is the only external effect in the system, and its
gate is the human key at the point of the write. Minimizing the acting
surface is itself a tool-design decision.

## Claude Code Config & Workflows (20%)

**Attest artifacts.** The root `CLAUDE.md` and per-agent scoped specs in
`agents/*/CLAUDE.md`, scoped by trust boundary rather than convenience.
The `.claude` purity-guard hook -- a development-time tripwire in front
of the AST-scan wall (`tests/unit/test_purity.py`) -- and audit hooks.
The golden-freeze workflow: `scripts/freeze_goldens.py` is the one
sanctioned way reproducible constants change, so a drive-by edit to
`tests/golden/` is a red flag by convention.

**Contrast with RIA.** RIA scopes its agent instructions by pipeline
stage (what each stage may read and write). Attest scopes by purity
contract: the engine's rules ("no clock, no network, no model SDK") are
stated in `attest/engine/__init__.py`, guarded by hook, and enforced by
test -- three layers because hooks can be disabled and greps can be
fooled, but the AST scan parses the shipped code.

## Prompt Engineering & Structured Output (20%)

**Attest artifacts.** The CheckSpec grammar as a closed structured-output
contract: forced tool use with a strict schema, validated by
`attest/engine/schema.py` with unknown keys rejected everywhere
(`docs/SPEC-GRAMMAR.md`). Deterministic backstops that do not trust the
model to follow instructions: reject-don't-repair on invalid drafts,
`on_unknown="fail"` forced regardless of what the model emitted, the
triage confidence floor of 0.7 (model-layer contracts in
`docs/PLAN.md`). Untrusted-content framing around control text, which
can be hostile, and an injection eval suite that grades the compiled
spec by execution -- a hostile prompt succeeds only if the spec stops
failing the negative fixture (`evaluations/`).

**Contrast with RIA.** RIA's structured output feeds human readers: the
schema disciplines briefings a person will judge. Attest's structured
output feeds an executor: the schema disciplines an artifact that will
run unattended forever, so the grammar is smaller, the validation is
stricter, and the failure mode being designed against is not "confusing
prose" but "a fail-open control."

## Context Management & Reliability (15%)

**Attest artifacts.** Reliability as reproducibility: canonical
serialization (`attest/engine/canonical.py`), content addressing with
tamper detection at point of use (`attest/engine/snapshot.py`), replay
(`attest/engine/replay.py`), golden files (`tests/golden/`), and 175
offline tests that run in under a second. The demo as a self-verifying
artifact -- every documentation claim asserted with an exit code
(`run_demo.py`). Record/replay for the model layer: recorded triage in
`fixtures/triage_decisions.json`; the eval harness re-grades offline from
recordings under `evaluations/recordings/` once a live `--live` run has
produced them (none ship in the repo -- `--offline` before that first run
reports every case SKIPPED, and says so rather than passing vacuously).

**Contrast with RIA.** RIA manages context per run -- what each model
call may see, at what stage, from what source. Attest's runtime
eliminates the problem class: the engine's entire context is its
arguments and the bytes in the state directory
(`attest/engine/__init__.py`), so there is no context to manage, only
inputs to hash. Where context management genuinely exists in Attest --
the authoring calls -- it uses RIA's techniques: scoped inputs,
untrusted-content framing, and recordings for repeatability.
