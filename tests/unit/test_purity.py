"""The purity contract, enforced by AST inspection of every module in
attest/engine/. This is the wall behind the development-time hook: a hook
can be disabled, a CI grep can be fooled by formatting, but this test parses
the actual syntax tree of the shipped code on every push.

Forbidden for the engine:
  - importing any clock, randomness, network, process, or model-SDK module,
    under any alias
  - from-importing the dangerous names out of allowed modules
    (from os import environ / getenv / urandom ...)
  - calling datetime.now/today/utcnow through ANY alias the module's own
    imports establish (import datetime as dt; from datetime import datetime
    as DT -- both tracked)
  - dynamic import machinery outright: importlib, __import__, exec, eval,
    and getattr with a string-literal attribute on the watchlist. The
    engine has no legitimate use for any of them, so the rule is total.

The scanner itself is tested against the bypass shapes an adversarial
review demonstrated against the previous version (aliased imports,
from-imports, dynamic imports) -- the wall is only a wall if someone has
tried to walk through it.
"""

import ast
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent.parent / "attest" / "engine"

FORBIDDEN_MODULES = {
    "time", "random", "uuid", "secrets", "socket", "ssl", "select", "asyncio",
    "http", "urllib", "urllib3", "requests", "httpx", "subprocess", "multiprocessing",
    "threading", "anthropic", "claude_agent_sdk", "mcp", "notion_client", "googleapiclient",
    "importlib", "ctypes", "signal", "platform", "getpass", "tempfile", "webbrowser",
}
# Names that may not be pulled OUT of otherwise-allowed modules.
FORBIDDEN_FROM_IMPORTS = {
    "os": {"environ", "getenv", "putenv", "urandom", "system", "popen", "spawnl", "spawnv"},
    "builtins": {"exec", "eval", "__import__", "compile"},
}
# (canonical origin, attribute) pairs that may not be called or read.
# Origins are resolved through the module's own import aliases.
FORBIDDEN_ATTRIBUTES = {
    ("datetime", "now"), ("datetime", "today"), ("datetime", "utcnow"),
    ("datetime.datetime", "now"), ("datetime.datetime", "today"), ("datetime.datetime", "utcnow"),
    ("datetime.date", "today"),
    ("os", "environ"), ("os", "getenv"), ("os", "putenv"), ("os", "urandom"), ("os", "system"),
}
FORBIDDEN_CALL_NAMES = {"exec", "eval", "__import__", "compile"}
GETATTR_WATCHLIST = {"environ", "getenv", "urandom", "now", "today", "utcnow", "system"}


def scan_source(source: str, filename: str = "<engine>") -> list[str]:
    """Return every purity offense in a piece of engine source."""
    offenses: list[str] = []
    tree = ast.parse(source, filename=filename)

    # Pass 1: imports -- collect alias -> canonical origin, flag forbidden.
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    offenses.append(f"{filename}:{node.lineno} imports {alias.name}")
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in FORBIDDEN_MODULES:
                offenses.append(f"{filename}:{node.lineno} imports from {module}")
            for alias in node.names:
                if alias.name in FORBIDDEN_FROM_IMPORTS.get(root, set()):
                    offenses.append(
                        f"{filename}:{node.lineno} from {module} import {alias.name}")
                # Track what the bound name actually refers to.
                aliases[alias.asname or alias.name] = f"{module}.{alias.name}" if module else alias.name

    def dotted_parts(node):
        """Resolve an attribute chain to its full dotted path, or None."""
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            parts.reverse()
            return parts
        return None

    # Pass 2: attribute access and calls, resolved through the alias map.
    # Full chains are checked (datetime.datetime.now is three parts), so
    # nesting does not hide a forbidden attribute.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = dotted_parts(node)
            if parts and len(parts) >= 2:
                resolved = [aliases.get(parts[0], parts[0])] + parts[1:]
                origin, attr = ".".join(resolved[:-1]), resolved[-1]
                if (origin, attr) in FORBIDDEN_ATTRIBUTES:
                    offenses.append(f"{filename}:{node.lineno} uses {origin}.{attr}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                target = aliases.get(node.func.id, node.func.id)
                if node.func.id in FORBIDDEN_CALL_NAMES or target.split(".")[-1] in FORBIDDEN_CALL_NAMES:
                    offenses.append(f"{filename}:{node.lineno} calls {node.func.id}()")
                if node.func.id == "getattr" and len(node.args) >= 2:
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant) and arg.value in GETATTR_WATCHLIST:
                        offenses.append(
                            f"{filename}:{node.lineno} getattr(..., {arg.value!r})")
    return offenses


def engine_modules():
    files = sorted(ENGINE_DIR.glob("*.py"))
    assert files, f"engine package not found at {ENGINE_DIR}"
    return files


def test_engine_package_exists_and_is_nonempty():
    assert len(engine_modules()) >= 10


def test_engine_is_pure():
    offenses = []
    for path in engine_modules():
        offenses.extend(scan_source(path.read_text(encoding="utf-8"), path.name))
    assert not offenses, "engine purity violated:\n" + "\n".join(offenses)


def test_engine_never_imports_the_outer_package():
    """The dependency arrow points one way: attest/ may import the engine;
    the engine may not import attest/'s collectors, publishers, or model
    layer. (Relative imports inside the engine package are level-1;
    a level-2 'from .. import' would reach outside.)"""
    offenses = []
    for path in engine_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level >= 2 or (node.module or "").startswith("attest."):
                    offenses.append(f"{path.name}:{node.lineno}")
    assert not offenses, "engine imports the outer package:\n" + "\n".join(offenses)


# -- the wall, tested against the shapes that got past its predecessor ----

@pytest.mark.parametrize("snippet", [
    "import time",
    "import time as t",
    "from time import monotonic",
    "import random",
    "from os import getenv\nx = getenv('SECRET')",
    "from os import environ",
    "from os import urandom as entropy",
    "import datetime\ndatetime.datetime.now()",
    "from datetime import datetime\nx = datetime.now()",
    "from datetime import datetime as dt\nx = dt.now()",
    "from datetime import date as d\nx = d.today()",
    "import importlib",
    "from importlib import import_module",
    "x = __import__('time').time()",
    "exec('import socket')",
    "eval('__import__(\"random\").random()')",
    "import os\nx = getattr(os, 'environ')",
    "import os\nx = os.environ['HOME']",
    "import os\nx = os.getenv('HOME')",
    "import subprocess",
    "import anthropic",
])
def test_scanner_catches_bypass_shapes(snippet):
    assert scan_source(snippet), f"scanner missed: {snippet!r}"


@pytest.mark.parametrize("snippet", [
    "import hashlib",
    "import json",
    "from pathlib import Path",
    "from datetime import datetime\nx = datetime.fromisoformat('2026-01-01T00:00:00+00:00')",
    "import os\nx = os.path.join('a', 'b')",
    "import unicodedata\nunicodedata.normalize('NFC', 'x')",
    "import re\nre.fullmatch('a', 'a')",
])
def test_scanner_permits_pure_stdlib(snippet):
    assert scan_source(snippet) == [], f"false positive on: {snippet!r}"
