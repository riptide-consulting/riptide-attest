"""Content-addressed evidence storage.

Layout under a state root:

    objects/<sha256>.json      one canonical JSON body per hash (evidence
                               bodies, approved specs, manifests -- one store
                               for everything the engine must re-derive from)
    snapshots/<snapshot_id>.json   {"snapshot_id": ..., "manifest": {...}}

A snapshot manifest names every evidence item by selector and content hash,
plus the single frozen collected_at for the whole collection pass. The
manifest's own canonical hash is the snapshot's identity, so two collections
that saw identical evidence at the same instant produce the identical
snapshot, and any modification to any byte of any item changes an identity
somewhere a verifier will look.

Tamper policy: ObjectStore.get() re-hashes what it reads and refuses to
return content whose hash does not match its address. Tampering with stored
evidence is therefore visible at the moment of use, not survivable until an
audit. This is the property that lets an attestation cite evidence by hash
and mean it.

The engine never looks at a clock: collected_at arrives from the collector
(outside this package), is validated here for form, and is thereafter the
only notion of 'now' the evaluator has.
"""

from __future__ import annotations

from pathlib import Path

from .canonical import CanonicalizationError, hash_obj, read_json, write_canonical
from .predicates import parse_utc_timestamp

SNAPSHOT_VERSION = "1.0"
_ID_PREFIX_LEN = 16


class TamperError(RuntimeError):
    """Stored content does not match its content address."""


class SnapshotError(ValueError):
    """A snapshot or manifest is structurally invalid."""


class ObjectStore:
    def __init__(self, root: Path | str):
        self.root = Path(root) / "objects"

    def put(self, obj: object) -> str:
        """Store a JSON value by canonical hash. Idempotent: storing the
        same value twice writes once and returns the same address."""
        digest = hash_obj(obj)
        path = self.root / f"{digest}.json"
        if not path.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            write_canonical(path, obj)
        return digest

    def get(self, digest: str) -> object:
        """Load a JSON value by address, verifying content against address."""
        path = self.root / f"{digest}.json"
        if not path.exists():
            raise SnapshotError(f"object {digest[:_ID_PREFIX_LEN]} is not in the store")
        obj = read_json(path)
        actual = hash_obj(obj)
        if actual != digest:
            raise TamperError(
                f"object store integrity failure: content at address {digest[:_ID_PREFIX_LEN]} "
                f"hashes to {actual[:_ID_PREFIX_LEN]} -- evidence has been modified after collection"
            )
        return obj


def build_manifest(records: list[dict], collected_at: str, store: ObjectStore) -> dict:
    """Turn collected evidence records into a manifest, storing bodies.

    Each record: {"selector": str, "content_type": str, "body": <json>} or
    {"selector": str, "error": str} for evidence that could not be read.
    Errors are recorded, not raised: absent evidence is a verdict (unknown,
    then fail-closed), not a crash.
    """
    if parse_utc_timestamp(collected_at) is None:
        raise SnapshotError(f"collected_at must be an ISO-8601 UTC timestamp, got {collected_at!r}")
    items: dict[str, dict] = {}
    for record in records:
        selector = record["selector"]
        if selector in items:
            raise SnapshotError(f"duplicate selector in collection: {selector!r}")
        if "error" in record:
            items[selector] = {"error": str(record["error"])}
        else:
            try:
                items[selector] = {
                    "sha256": store.put(record["body"]),
                    "content_type": record.get("content_type", "application/json"),
                }
            except CanonicalizationError as exc:
                # A body that parses but cannot be canonicalized (Infinity
                # from 1e999, duplicate keys after NFC, ...) is bad evidence,
                # not a reason to lose the whole snapshot: it becomes an
                # error record, then an unknown verdict, then fail-closed.
                items[selector] = {"error": f"evidence not canonicalizable: {exc}"}
    return {"snapshot_version": SNAPSHOT_VERSION, "collected_at": collected_at, "items": items}


def snapshot_id_for(manifest: dict) -> str:
    return "snap-" + hash_obj(manifest)[:_ID_PREFIX_LEN]


def write_snapshot(state_root: Path | str, manifest: dict, store: ObjectStore) -> str:
    """Persist a manifest: into the object store (so replay can fetch it by
    hash) and as a named snapshot file (operator convenience). Returns id."""
    store.put(manifest)
    snapshot_id = snapshot_id_for(manifest)
    directory = Path(state_root) / "snapshots"
    directory.mkdir(parents=True, exist_ok=True)
    write_canonical(directory / f"{snapshot_id}.json", {"snapshot_id": snapshot_id, "manifest": manifest})
    return snapshot_id


def load_snapshot(state_root: Path | str, snapshot_id: str) -> dict:
    """Load a manifest by snapshot id, verifying the id is the manifest's
    canonical hash. A renamed or edited snapshot file fails here."""
    path = Path(state_root) / "snapshots" / f"{snapshot_id}.json"
    if not path.exists():
        raise SnapshotError(f"snapshot {snapshot_id} not found under {state_root}")
    wrapper = read_json(path)
    if not isinstance(wrapper, dict) or "manifest" not in wrapper:
        raise SnapshotError(f"snapshot file for {snapshot_id} is malformed")
    manifest = wrapper["manifest"]
    if snapshot_id_for(manifest) != snapshot_id:
        raise TamperError(
            f"snapshot {snapshot_id}: manifest content does not hash to the snapshot id -- "
            "the manifest has been modified after it was written"
        )
    return manifest
