# attest_tracker -- the tracker port's Notion instantiation

`writer.py` exposes one function, `publish_record(attestation_id, body)`.
It creates one page in a Notion database: the page title is the
attestation id; the page body carries the rollup verdict, the
pass/fail/unknown counts, the snapshot id and its collected_at, and the
engine version. Nothing else leaves the machine -- per-check evidence
values stay in the local attestation JSON.

## The two gates in front of it

`publish_record` checks its own configuration and nothing else; it does
not need to, because both gates sit upstream in `attest/publish.py`,
inside `publish_attestation()`:

1. **Attestation self-check before any external reach.**
   `load_attestation()` (`attest/engine/report.py`) re-hashes the body
   and refuses if the hash does not match the stored id: a report
   modified after it was written cannot be published.
2. **The human key at the point of the write.** `_require_approval()`
   refuses unless `ATTEST_PUBLISH_APPROVED` is set in the environment at
   the moment of the call. The check lives inside the publishing
   function, so no refactor of calling code can route around it.

## Configuration

Read from the environment at the point of use, never from a file:

| Variable | Meaning |
|---|---|
| `NOTION_API_KEY` | integration token |
| `NOTION_DATABASE_ID` | database that receives one page per published attestation |

A missing variable raises a `RuntimeError` naming it. Separately,
`attest/publish.py` treats an absent `NOTION_API_KEY` as "approved but
unconfigured": it reports what it would have written and never imports
this module.

Swapping this tracker for ServiceNow or Jira replaces the body of
`publish_record` and nothing else -- the ports argument is made in
`mcp_servers/README.md`.
