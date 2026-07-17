# The determinism claim

This document states exactly what Riptide Attest claims about
reproducibility, what enforces each part of the claim, and what is
deliberately not claimed. Every statement names the file that proves it;
the fastest way to check the whole document is `python run_demo.py`.

## What is claimed

**Given a snapshot (a manifest plus its content-addressed evidence
objects) and a set of approved specs, the attestation is bit-for-bit
reproducible: same bytes, same hash, same id, on any machine, at any
later date.**

Consequences of the claim, each asserted by a test:

* Two evaluations of the same snapshot produce byte-identical
  attestation files (`test_two_runs_identical_bytes` in
  `tests/unit/test_determinism.py`).
* The order specs are listed on the command line cannot change the
  attestation (`test_spec_order_is_irrelevant`; controls are sorted by
  `control_id` in `attest/engine/report.py`).
* The attestation id is the canonical hash of the body, so the id is a
  claim anyone can check by rehashing
  (`test_attestation_id_is_body_hash`; `attest/engine/report.py`).
* A stored attestation re-derives from stored artifacts alone --
  manifest, specs, and evidence fetched from the object store by the
  hashes the attestation cites (`attest/engine/replay.py`,
  `test_replay_golden_state`).
* Today's build reproduces the committed golden artifacts byte for byte
  (`test_matches_committed_golden` against `tests/golden/`).

## What enforces it

**Canonical serialization** (`attest/engine/canonical.py`). Every
artifact the engine emits passes through `canonical_bytes()` before it is
hashed or written. The rules: UTF-8, NFC-normalized strings; object keys
sorted by code point, string keys only; minimal separators, no
whitespace; NaN and Infinity rejected; duplicate keys after NFC
normalization rejected; non-JSON types rejected, nothing coerced --
coercion is a hiding place for nondeterminism.

**Content addressing** (`attest/engine/snapshot.py`). Evidence bodies,
specs, and manifests share one object store addressed by canonical hash.
`ObjectStore.get()` re-hashes on every read and raises `TamperError` on
mismatch, so the artifacts a replay depends on cannot drift silently.

**Purity of the evaluator** (`tests/unit/test_purity.py`). An AST scan
of every module in `attest/engine/` forbids importing any clock,
randomness, network, process, or model-SDK module, and forbids
`datetime.now`/`today`/`utcnow`, `os.environ`, `os.getenv`, and
`os.urandom`. The engine may parse timestamps; it may never ask what
time it is. The attestation body carries no wall-clock timestamp of its
own -- its notion of time is the snapshot's `collected_at`
(`attest/engine/report.py`, `test_attestation_carries_no_wall_clock`).

**Binary-mode writes** (`write_canonical` and `read_json` in
`attest/engine/canonical.py`). Files are written and read in binary
mode, because Windows text-mode newline translation (CRLF) would
silently break byte-stability. File bytes are the canonical content plus
one trailing LF; hashes are always computed on the content alone.

## What is not claimed

* **Snapshots taken at different instants differ, by design.** The
  manifest embeds its single `collected_at`, so a live collection today
  and one tomorrow are different snapshots with different ids even over
  identical evidence. The claim is "same snapshot -> same bytes," not
  "the world stopped changing." `run_demo.py --live-clock` demonstrates
  the distinction: ids differ from this document, within-run determinism
  assertions still hold.
* **DOCX renderings are a convenience, not the artifact.** Only the
  canonical JSON attestation carries the claim; `python-docx` appears in
  `requirements.txt` for optional rendering and nothing verifies
  renderings byte-for-byte.
* **Float stability is inherited, not invented.** Python serializes
  floats via the shortest round-trip repr, documented deterministic for
  IEEE 754 doubles across CPython >= 3.1 on all supported platforms
  (float note in `attest/engine/canonical.py`). The spec grammar itself
  prefers integers; evidence may carry floats and they canonicalize
  stably.

## The reproducible constants

The demo freezes the snapshot timestamp to the fixture time
(`fixtures/demo_config.json`), so these identifiers are reproducible on
your machine, byte for byte. They are frozen in `tests/golden/meta.json`
and regenerated only by `scripts/freeze_goldens.py` when specs,
fixtures, or the engine change.

| Constant | Value |
|---|---|
| Engine version | `1.0.0` (`attest/engine/__init__.py`) |
| Frozen snapshot | `snap-180fbe2ab1b28ee2` at `2026-07-17T00:00:00Z` |
| Manifest sha256 | `180fbe2ab1b28ee22d6a24735df5ac4a8c1075e5a5aa2011ff5e5dc2f547373e` (the snapshot id is its first 16 hex digits) |
| Attestation, before remediation | `att-ef4d859e0bd776f6` -- rollup **fail**: `RIA-2026-14012-A3` retention is 90 days against a 180-day bound |
| Attestation, after remediation | `att-3e9b22a10ea2e55f` -- rollup **pass** |
| Drift between them | exactly one verdict transition: `RIA-2026-14012-A3` fail -> pass (`tests/golden/drift_report.json`) |

To verify:

```
python run_demo.py
```

The demo's final lines print both attestation ids; compare them against
the table above. If any determinism assertion fails, the demo exits
nonzero and names it. The same constants are asserted offline by
`tests/unit/test_determinism.py` (175 tests total in `tests/`, no
network, under a second).
