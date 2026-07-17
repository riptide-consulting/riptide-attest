"""PreToolUse tripwire for the engine purity contract.

Blocks an Edit/Write whose target is inside attest/engine/ and whose new
content matches a forbidden import or attribute pattern. The lists below
mirror FORBIDDEN_MODULES / FORBIDDEN_ATTRIBUTES in
tests/unit/test_purity.py; if the two ever drift, the test is
authoritative -- it parses the real syntax tree of the shipped code on
every push, while this hook only greps a proposed fragment before it
lands.

FAIL OPEN on any internal error: log the exception to
logs/hook_audit.jsonl and exit 0. The wall is the AST test plus CI; this
hook is only the tripwire. A guard that crashes on odd input teaches
operators to disable guards, and a disabled guard is worse than no guard
(RIA's argument -- keep this comment so nobody "hardens" the except
clause into a block).

Protocol: Claude Code hook JSON on stdin. Exit 0 allows the tool call;
exit 2 blocks it and feeds stderr back to the agent.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT / "logs" / "hook_audit.jsonl"

# Mirror of tests/unit/test_purity.py. The test is authoritative.
FORBIDDEN_MODULES = {
    "time", "random", "uuid", "secrets", "socket", "ssl", "select", "asyncio",
    "http", "urllib", "urllib3", "requests", "httpx", "subprocess", "multiprocessing",
    "threading", "anthropic", "claude_agent_sdk", "mcp", "notion_client", "googleapiclient",
    "importlib", "ctypes", "signal", "platform", "getpass", "tempfile", "webbrowser",
}
FORBIDDEN_ATTRIBUTES = [
    ("datetime", "now"), ("datetime", "today"), ("datetime", "utcnow"),
    ("date", "today"), ("dt", "now"), ("dt", "today"), ("dt", "utcnow"),
    ("os", "environ"), ("os", "urandom"), ("os", "getenv"), ("os", "system"),
]
# Dangerous names pulled out of otherwise-allowed modules, and dynamic
# import machinery -- forbidden outright; the engine has no use for them.
FORBIDDEN_FRAGMENTS = [
    ("from os import", re.compile(r"^\s*from\s+os\s+import\b", re.MULTILINE)),
    ("__import__", re.compile(r"\b__import__\s*\(")),
    ("exec(", re.compile(r"\bexec\s*\(")),
    ("eval(", re.compile(r"\beval\s*\(")),
    ("compile(", re.compile(r"\bcompile\s*\(")),
    ("getattr on a guarded attribute",
     re.compile(r"getattr\s*\([^)]*['\"](?:environ|getenv|urandom|now|today|utcnow|system)['\"]")),
    ("aliased clock import",
     re.compile(r"^\s*from\s+datetime\s+import\s+[^\n#]*\bas\b", re.MULTILINE)),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(record: dict) -> None:
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # the log is best-effort; a guard must never crash over it


def _patterns() -> list[tuple[str, re.Pattern]]:
    pats: list[tuple[str, re.Pattern]] = []
    for mod in sorted(FORBIDDEN_MODULES):
        pats.append((f"import {mod}",
                     re.compile(rf"^\s*import\s+[^\n#]*\b{mod}\b", re.MULTILINE)))
        pats.append((f"from {mod} import",
                     re.compile(rf"^\s*from\s+{mod}\b", re.MULTILINE)))
    for obj, attr in FORBIDDEN_ATTRIBUTES:
        pats.append((f"{obj}.{attr}", re.compile(rf"\b{obj}\s*\.\s*{attr}\b")))
    pats.extend(FORBIDDEN_FRAGMENTS)
    return pats


def main() -> int:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")

    # Normalize separators so absolute Windows paths, relative paths, and
    # forward-slash paths all resolve to the same question.
    norm = "/" + file_path.replace("\\", "/").lstrip("/")
    if "/attest/engine/" not in norm:
        return 0

    # Write carries full content; Edit carries the replacement fragment.
    content = "\n".join(
        str(tool_input.get(key) or "") for key in ("content", "new_string")
    )
    for label, pattern in _patterns():
        if pattern.search(content):
            print(
                f"purity guard: '{label}' is forbidden inside attest/engine/ "
                "(contract: tests/unit/test_purity.py; rationale: attest/engine/__init__.py)",
                file=sys.stderr,
            )
            _log({"ts": _now(), "hook": "purity_guard", "decision": "block",
                  "file_path": file_path, "matched": label})
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # FAIL OPEN -- see module docstring
        _log({"ts": _now(), "hook": "purity_guard", "decision": "fail_open",
              "error": repr(exc)})
        sys.exit(0)
