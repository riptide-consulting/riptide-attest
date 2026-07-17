# Logical architecture

This document names no vendor, no product, and no model, by construction:
if any name here would change when a supplier changes, the architecture
was never separable from the supplier. Capabilities are named for what
they do; concrete adapters are cited by file path, because a file path is
a proof, not an endorsement. (The sibling advisory system's architecture
document holds itself to the same rule; this one inherits it.)

## The premise

An upstream advisory system produces remediation plans: statements of
what should be done. This system answers the follow-up question -- is it
done, and does it stay done -- in a form that two parties who distrust
each other's memories can both re-derive.

The design splits the work by epistemic kind. Judgment (reading a
control's intent, formalizing it) is probabilistic and runs once, at
authoring time, under human review. Verification (checking evidence
against the formalized control) is deterministic and runs forever, at
zero marginal reasoning cost. The boundary between the two is a single
artifact -- the check specification -- and a single act -- a human
pinning that artifact's content hash into an approval registry.

## Capabilities

Named for what they do, not for what performs them.

| Capability | Nature | Description |
|---|---|---|
| Classify | judgment, authoring | Sort remediation actions into machine-attestable vs human-tracked. Uncertainty routes to humans, never to automation. |
| Formalize | judgment, authoring | Translate one action's intent into a draft check specification in a closed grammar. A draft is inert: nothing executes it. |
| Explain | advisory, authoring | Render a specification in plain language for the human review packet. No authority; never quoted into verdicts. |
| Authorize | human authority | Pin a specification's canonical content hash into the approval registry. Editing one character voids the authorization. |
| Freeze | mechanical | Collect exactly the evidence the approved specifications cite, stamp the collection once, store every item by content hash. |
| Verify | mechanical | Evaluate approved specifications against a frozen snapshot. A pure function of its arguments. |
| Reproduce | mechanical | Re-derive any past verdict from stored artifacts and assert byte equality. |
| Compare | mechanical | Diff two verdicts into a deterministic drift report. |
| Disclose | mechanical + human authority | The one external effect: send a verdict outward, gated by a human-held key at the moment of the write. |

## Contracts: the entities that cross boundaries

| Entity | Crosses from -> to | Proof of shape |
|---|---|---|
| Remediation action | advisory system -> Classify/Formalize | `fixtures/ria_remediation_plan.json` (verbatim upstream shape) |
| Check specification | Formalize -> human review -> Authorize | grammar in `attest/engine/schema.py`; reference in `docs/SPEC-GRAMMAR.md` |
| Approval record | Authorize -> Verify | `registry/approved.json`; consumed by `attest/engine/registry.py` |
| Evidence record | target systems -> Freeze | collector contract in `attest/collect.py` |
| Snapshot manifest | Freeze -> Verify/Reproduce | `attest/engine/snapshot.py` |
| Attestation | Verify -> Compare/Reproduce/Disclose | `attest/engine/report.py` |
| Drift report | Compare -> operators | `attest/engine/diffing.py` |
| Audit record | every capability -> audit sink | `attest/audit.py` |

Every entity that the verification core must later re-derive from --
specifications, manifests, evidence bodies -- lives in one
content-addressed store (`attest/engine/snapshot.py`), so each is
addressable by its hash and any modification changes an address a
verifier will check.

## Invariants as acceptance criteria

The system is correct when all nine hold; each is testable and each names
its enforcement.

1. Formalized output cannot execute without authorization
   (`require_approved()` in `attest/engine/registry.py`, called inside
   the evaluation path).
2. Authorization is a content hash; any edit voids it
   (`attest/engine/registry.py`).
3. Verification is pure: no clock, no randomness, no network, no
   environment, no reasoning component in the core
   (`tests/unit/test_purity.py`, an AST scan of every core module).
4. Same snapshot + same specifications -> byte-identical attestation
   (`tests/unit/test_determinism.py`, `tests/golden/`).
5. Every verdict reproduces from stored artifacts
   (`attest/engine/replay.py`).
6. Evidence is content-addressed; tampering surfaces at the moment of
   use, not at audit time (`ObjectStore.get()` in
   `attest/engine/snapshot.py`).
7. External effects require a human-held key at the point of the write
   (`attest/publish.py`).
8. Reasoning cost exists only at authoring time (lazy imports in
   `main.py`; invariant 3 for the core).
9. Missing evidence fails closed; only a human can relax a
   specification to report-instead-of-fail (`attest/engine/schema.py`,
   `attest/engine/evaluator.py`).

## Ports and adapters

| Port | Direction | Contract | Adapters |
|---|---|---|---|
| Evidence Port | in | selector scheme -> evidence record or recorded error; collection is specification-driven and need-to-know | `fs` adapter in `attest/collect.py`; protocol-served adapters under `mcp_servers/` |
| Control Source Port | in | remediation plan document, consumed verbatim | `fixtures/ria_remediation_plan.json` (recorded); live plans from the advisory system |
| Approval Port | in (human) | named approver + specification content hash -> registry entry | the `approve` verb in `main.py` writing `registry/approved.json` |
| Attestation Sink | out | canonical attestation file; onward disclosure gated by a human key | `state/attestations/` via `attest/engine/report.py`; gated writer in `attest/publish.py` |
| Audit Sink | out | one structured line per operator action, wall-clock stamped | JSONL log via `attest/audit.py` |
| Reasoning Port | in (authoring only) | forced structured output against the specification grammar, with deterministic backstops | the authoring modules under `attest/`; loaded lazily by `main.py` |

The Reasoning Port attaches only to the authoring capabilities
(Classify, Formalize, Explain). It is structurally absent from the
verification core: the core's package cannot import a reasoning SDK, and
`tests/unit/test_purity.py` fails the build if one appears. This is the
load-bearing asymmetry of the whole design -- the advisory sibling
consults its reasoning port on every run; this system consults it only
when a human is present to review what came back.
