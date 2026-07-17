"""Read-only MCP server for the fs evidence port.

Exposes attest/collect.py's fs adapter (_collect_fs -- imported, not
duplicated) over MCP, so evidence collection can run against a machine the
collector cannot reach directly. Two tools, both read-only:

    list_selectors(target_root)      -> every fs:// selector under the root
    collect(target_root, selectors)  -> evidence records, the same shape
                                        attest/collect.py freezes into a
                                        snapshot manifest

The security property this server is built around: it holds NO WRITE
TOOLS. A compromised or confused caller can enumerate and read the files
under a root it names, and change nothing. Path escapes are refused inside
_collect_fs (a selector resolving outside the root comes back as an error
record), and error records become unknown verdicts downstream, which fail
closed (attest/engine/evaluator.py).

The mcp package is imported lazily inside build_server(), so importing
this module needs nothing beyond the standard library plus the attest
package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# When an MCP client launches this file as a script, sys.path[0] is this
# directory, not the repository root; make the attest package importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from attest.collect import _collect_fs  # noqa: E402  the one fs adapter; never duplicate it
from attest.engine.schema import validate_selector  # noqa: E402


def list_selectors(target_root: str) -> list[str]:
    """Every valid fs:// selector currently readable under target_root,
    sorted. A file whose relative path does not fit the selector grammar
    in attest/engine/schema.py is omitted rather than misquoted; a root
    that is not a directory yields an empty list."""
    root = Path(target_root)
    if not root.is_dir():
        return []
    selectors: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        candidate = "fs://" + path.relative_to(root).as_posix()
        errors: list[str] = []
        validate_selector(candidate, "list_selectors", errors)
        if not errors:
            selectors.append(candidate)
    return sorted(selectors)


def collect(target_root: str, selectors: list[str]) -> list[dict]:
    """One evidence record per requested selector, sorted and
    de-duplicated -- the record shape attest/collect.py's
    collect_for_specs produces. A selector this adapter cannot serve
    (foreign scheme, escape attempt, missing file) is an error record,
    not an exception: absence is data, and downstream evaluation fails
    closed on it (attest/engine/evaluator.py)."""
    root = Path(target_root)
    records: list[dict] = []
    for selector in sorted(set(selectors)):
        scheme, _, rest = selector.partition("://")
        if scheme != "fs":
            records.append({"selector": selector,
                            "error": f"this adapter serves only fs://, got scheme {scheme!r}"})
            continue
        records.append({"selector": selector, **_collect_fs(rest, root)})
    return records


def build_server():
    """Construct the FastMCP server, registering exactly the two read
    tools above -- the registration list IS the write-tool audit. Lazy
    import: py_compile and unit tests need no mcp package."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "the mcp package is required to serve (pip install mcp==1.28.1); "
            "list_selectors/collect remain importable and testable without it"
        ) from exc
    server = FastMCP("attest-evidence-fs")
    server.tool()(list_selectors)
    server.tool()(collect)
    return server


def main() -> int:
    build_server().run()  # stdio transport
    return 0


if __name__ == "__main__":
    sys.exit(main())
