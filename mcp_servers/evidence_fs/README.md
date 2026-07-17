# evidence_fs -- the fs evidence adapter, served over MCP

A read-only MCP server exposing the same fs adapter the collector calls
directly (`_collect_fs` in `attest/collect.py` -- imported, not
duplicated). It exists so evidence collection can run on a machine other
than the one holding the target system: the collector talks to the port,
the port talks to the files.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `list_selectors` | `target_root` | every valid `fs://` selector currently readable under the root, sorted |
| `collect` | `target_root`, `selectors` | one record per selector: `{selector, body, content_type}` on success, `{selector, error}` otherwise |

## The read-only contract

`build_server()` in `server.py` registers exactly two tools and both only
read -- there is no write, delete, or execute tool to misuse. A
compromised or confused caller can enumerate and read files under a root
it names, and change nothing. A selector that resolves outside the target
root is refused inside `_collect_fs` and comes back as an error record;
error records flow downstream as `unknown` verdicts, which fail closed
(`attest/engine/evaluator.py`).

## Running it

    # from the repository root
    .venv/Scripts/python mcp_servers/evidence_fs/server.py

The server speaks MCP over stdio. Register it with an MCP client as:

    {
      "mcpServers": {
        "attest-evidence-fs": {
          "command": "<repo>/.venv/Scripts/python",
          "args": ["<repo>/mcp_servers/evidence_fs/server.py"]
        }
      }
    }

Serving requires `mcp==1.28.1` (pinned in `requirements.txt`). The tool
functions themselves import without it -- the lazy import lives in
`build_server()` -- so py_compile and the unit-test surface carry no MCP
dependency.
