# mcp_servers/ -- integration adapters behind ports

The engine does not integrate with anything. `attest/engine/` imports no
network library, no vendor SDK, and nothing from this directory --
`tests/unit/test_purity.py` scans for exactly that. Integrations live out
here, each one a thin adapter behind a fixed contract (a port). The engine
sees only the contract's data shapes: selector strings in a manifest, a
dict returned from a publish call. It never learns which vendor answered.

## The two ports

| Port | Contract | This instantiation | Illustrative enterprise instantiation |
|---|---|---|---|
| evidence source | `list_selectors(target_root)`, `collect(target_root, selectors)` -> evidence records `{selector, body / error}` -- the record shape `attest/collect.py` freezes into a snapshot | `evidence_fs/server.py`: read-only MCP server over the `fs://` scheme, resolving paths under a target root (the demo's `fixtures/target_system/`) | a cloud-config API export, an IAM policy dump, a SIEM query -- any system that can answer "give me the bytes behind these selectors" |
| attestation tracker | `publish_record(attestation_id, body) -> dict`, called only from the gated path in `attest/publish.py` | `attest_tracker/writer.py`: one Notion page per published attestation | a ServiceNow change record, a Jira ticket, a GRC platform entry |

## Why a swap is an adapter change, not a redesign

Selectors are opaque `scheme://relative/path` strings (grammar in
`attest/engine/schema.py`). The scheme names the port; the engine treats
the whole selector as a dictionary key in the manifest and hashes whatever
bytes came back. Swapping the fs adapter for a cloud-config API means
registering a new scheme in `attest/collect.py` with the same record
contract. Nothing in `attest/engine/`, no approved spec, and no stored
attestation changes shape.

The same holds on the write side. `attest/publish.py` owns both gates (the
attestation self-check via `load_attestation`, the human key in
`_require_approval()`) and only then calls `publish_record`. Swapping
Notion for ServiceNow replaces the body of one function; the gates, the
audit trail (`attest/audit.py`), and the CLI verb (`python main.py
publish`) do not move.

Adapters hold no authority: the evidence server registers no write tools
(`evidence_fs/README.md`), and the tracker writer runs only after a
human-key check it does not itself perform (`attest_tracker/README.md`).
