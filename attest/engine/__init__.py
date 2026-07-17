"""attest.engine: the deterministic core.

Purity contract for every module in this package, enforced three ways
(tests/unit/test_purity.py AST scan on every push; the .claude purity-guard
hook during development; this docstring for the humans):

  FORBIDDEN  imports: time, random, uuid, secrets, socket, ssl, http,
             urllib, subprocess, requests, httpx, anthropic, or any other
             network or model SDK.
  FORBIDDEN  calls: datetime.now / today / utcnow, os.environ, os.urandom.
             The engine may parse timestamps; it may never ask what time it
             is. It may read files; it may never read the environment.

  ALLOWED    hashlib, json, math, re, unicodedata, pathlib, and
             datetime.fromisoformat -- pure functions over their inputs.

Consequence: everything importable from this package is a deterministic
function of its arguments and the bytes in the state directory. The model
layer (attest/compiler.py and friends) sits outside this package and cannot
be imported from inside it.
"""

from .canonical import (
    CanonicalizationError,
    canonical_bytes,
    canonical_dumps,
    hash_obj,
    read_json,
    sha256_hex,
    write_canonical,
)
from .diffing import diff_attestations
from .evaluator import FAIL, PASS, UNKNOWN, evaluate_spec, evaluate_specs
from .pointer import MISSING, resolve_pointer, validate_pointer
from .registry import ApprovalError, approve_spec, empty_registry, load_registry, require_approved, save_registry
from .replay import replay
from .report import ReportError, build_attestation, load_attestation, write_attestation
from .schema import SpecError, ensure_valid, spec_selectors, validate_spec
from .snapshot import (
    ObjectStore,
    SnapshotError,
    TamperError,
    build_manifest,
    load_snapshot,
    snapshot_id_for,
    write_snapshot,
)

ENGINE_VERSION = "1.0.0"

__all__ = [
    "ENGINE_VERSION",
    "ApprovalError", "CanonicalizationError", "ReportError", "SnapshotError", "SpecError", "TamperError",
    "FAIL", "MISSING", "PASS", "UNKNOWN",
    "ObjectStore",
    "approve_spec", "build_attestation", "build_manifest",
    "canonical_bytes", "canonical_dumps",
    "diff_attestations", "empty_registry", "ensure_valid",
    "evaluate_spec", "evaluate_specs",
    "hash_obj", "load_attestation", "load_registry", "load_snapshot",
    "read_json", "replay", "require_approved", "resolve_pointer",
    "save_registry", "sha256_hex", "snapshot_id_for", "spec_selectors",
    "validate_pointer", "validate_spec", "write_attestation", "write_canonical", "write_snapshot",
]
