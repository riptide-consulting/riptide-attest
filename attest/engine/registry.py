"""The approval registry: the deterministic mirror of RIA's human key.

RIA gates *writes*: an external side effect requires RIA_EVALUATOR_APPROVED
at the moment of the write. Attest's engine performs no external writes, so
its gate moves to the other consequential moment: *what is allowed to run*.
A spec executes only if its canonical hash appears in the registry a human
wrote. Because the pin is the hash of the content:

  * editing one character of an approved spec voids its approval,
  * approval cannot be granted to a spec the human has not seen in final
    form -- there is no "approve whatever the compiler produces next",
  * and the compiler (a model) cannot approve its own output, because the
    registry is written by the `approve` CLI verb under a human's name and
    the engine only ever reads it.

require_approved() is called inside the evaluation path, at the point of
use, not at the CLI boundary -- the same placement argument as RIA's
_require_approval(): no refactor of the calling code can forget a check
that lives inside the function that does the consequential thing.
"""

from __future__ import annotations

from pathlib import Path

from .canonical import hash_obj, read_json, write_canonical

REGISTRY_VERSION = "1.0"
_ID_PREFIX_LEN = 16


class ApprovalError(PermissionError):
    """A spec is not approved for execution."""


def empty_registry() -> dict:
    return {"registry_version": REGISTRY_VERSION, "approved": {}}


def load_registry(path: Path | str) -> dict:
    path = Path(path)
    if not path.exists():
        return empty_registry()
    registry = read_json(path)
    if not isinstance(registry, dict) or "approved" not in registry:
        raise ApprovalError(f"registry at {path} is malformed; refusing to treat it as approvals")
    return registry


def approve_spec(registry: dict, spec: dict, approved_by: str, approved_at: str) -> tuple[dict, str]:
    """Pure approval: returns (updated registry, spec hash). IO stays with
    the caller so this is trivially testable and auditable."""
    if not approved_by.strip():
        raise ApprovalError("approval requires a named approver")
    digest = hash_obj(spec)
    updated = {
        "registry_version": registry.get("registry_version", REGISTRY_VERSION),
        "approved": dict(registry.get("approved", {})),
    }
    updated["approved"][digest] = {
        "control_id": spec.get("control_id"),
        "title": spec.get("title"),
        "approved_by": approved_by,
        "approved_at": approved_at,
    }
    return updated, digest


def save_registry(path: Path | str, registry: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_canonical(path, registry)


def require_approved(spec: dict, registry: dict) -> str:
    """The gate. Returns the spec hash or raises. Called at point of use."""
    digest = hash_obj(spec)
    if digest not in registry.get("approved", {}):
        raise ApprovalError(
            f"spec {digest[:_ID_PREFIX_LEN]} ({spec.get('control_id', '?')}) is not in the approval "
            "registry -- refusing to evaluate. Any edit to a spec voids its approval; a human must "
            "re-approve with: python main.py approve <spec-file> --by <name>"
        )
    return digest
