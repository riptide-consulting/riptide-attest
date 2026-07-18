# FACTS: every number the deck asserts, and where it comes from

Each claim in Riptide-Attest-Master-Deck.pptx maps to a source file in this
repository. Checked against the `presentation` branch on 18 July 2026; the
drift rule is the same as RIA's: if a number moves in code, this file and
the deck builder move with it, and the check below is how you notice.

## Verification and determinism

| Claim (slide) | Value | Source | Verified |
|---|---|---|---|
| Offline tests (4, 24, 32) | 234 passed, under 2 s | `tests/unit/`, live pytest run | yes |
| Demo assertions (4, 32) | 9, exit code is the verdict | `run_demo.py` | yes |
| Attestation before remediation (4, 8, 28) | `att-ef4d859e0bd776f6`, rollup fail | `tests/golden/meta.json` | yes |
| Attestation after remediation (8, 28) | `att-3e9b22a10ea2e55f`, rollup pass | `tests/golden/meta.json` | yes |
| Frozen snapshot (28) | `snap-180fbe2ab1b28ee2` at 2026-07-17T00:00:00Z | `tests/golden/meta.json`, `fixtures/demo_config.json` | yes |
| Failing check detail (8) | retention 90 >= 180 is false | `fixtures/target_system/logging/retention.json`, spec A3 | yes |
| Engine dependencies (24) | 0 beyond the standard library | `tests/unit/test_purity.py` (AST wall) | yes |
| Invariants (21) | 9, each enforced and tested | `docs/PLAN.md`, mapping in `docs/`, `tests/unit/` | yes |
| Cross-platform CI (24, 30, 32) | Linux re-derives Windows-frozen goldens | `.github/workflows/ci.yml` | yes |

## The grammar and the gates

| Claim (slide) | Value | Source | Verified |
|---|---|---|---|
| Predicate vocabulary (26) | 16 leaf predicates, 4 combinators | `attest/engine/schema.py` `_LEAF_OPS` | yes |
| A3 spec hash (26) | `8ba036b71470c022...` | `registry/approved.json` | yes |
| Compiler cannot emit fail-open (26, 29) | `on_unknown` forced to `fail` | `attest/compiler.py` backstop, `docs/PLAN.md` | yes |
| Triage confidence floor (29) | below 0.7 routes to humans | `attest/triage.py` backstop | yes |
| Publish gate variable (31) | `ATTEST_PUBLISH_APPROVED`, checked inside the write | `attest/publish.py` | yes |
| Adversarial review (30, 32) | 59 agents, 18 raw findings, 11 confirmed, 11 fixed | `scratchpad/ADVERSARIAL-REVIEW.md` | yes |

## Models and economics

| Claim (slide) | Value | Source | Verified |
|---|---|---|---|
| Triage / Explainer model (29) | claude-haiku-4-5-20251001 | `.env.example` | yes |
| Compiler model (29) | claude-opus-4-8 | `.env.example` | yes |
| Runtime model spend (4, 11, 12) | $0.00, structurally (no SDK in runtime verbs) | `tests/unit/test_purity.py`, lazy imports in `main.py` | yes |
| Compile cost (12) | ~$0.15-0.40 per control, one-time | estimate from Opus list pricing; a live `--live` eval run will replace it with a measured figure | estimate, labeled |
| RIA contrast figures (9, 12) | $0.59/document recurring, five stages | RIA `docs/COST-BREAKDOWN.md` (companion repo) | yes, against RIA main |

## Drift summary

No drift found. One figure is an estimate and labeled as such in this file:
the per-control compile cost, which becomes a measured number after the
first `evaluations/harness.py --live` run is recorded.
