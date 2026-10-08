#!/usr/bin/env python3
"""Deterministic hollow-test validator (SPEC-056 / ISSUE-056).

Promotes the testgen step-3d / test-generator predicate from skill prose to
a script with exit codes:

  Python  every `def test_*` function (module or class level, found via
          `ast`) must contain at least one assertion mechanism: an `assert`
          statement, a `raises(...)` usage (pytest.raises), a mock reference
          (any identifier containing "mock", or an attribute starting with
          "assert" such as `m.assert_called_once()` / `self.assertEqual`),
          or a `fail(...)` call. AST-based: the word "assert" inside a
          string literal never counts.
  JS/TS   every `it(` / `test(` block must contain `expect(` / `.toBe` /
          `.toEqual`. Blocks are delimited by consecutive it()/test() call
          sites (segment heuristic mirroring the prose predicate's grep
          semantics, not a full JS parser). JS comments (`//` line and
          `/* */` block) are blanked before matching, so a commented-out
          assertion can never vouch for a test (review hardening, PR #101);
          string-literal contexts are NOT parsed - still a heuristic.

A test file with ZERO test functions/blocks is itself hollow, and an empty
input set never passes (AC: no vacuous pass).

Exit codes (verify_* family convention):
  0 - every discovered test asserts
  1 - hollow test(s) found, unparseable test file, or no test files at all
  2 - usage error (nonexistent --tests-dir or file argument)

Usage:
    python3 scripts/verify_hollow_tests.py --tests-dir tests/
    python3 scripts/verify_hollow_tests.py path/to/test_x.py path/to/y.test.ts
    ... [--json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

PY_GLOBS = ("test_*.py", "*_test.py")
JS_GLOBS = tuple(
    f"*.{kind}.{ext}" for kind in ("test", "spec") for ext in ("js", "jsx", "ts", "tsx")
)
_SKIP_DIRS = {"__pycache__", "node_modules", ".git"}

JS_TEST_CALL = re.compile(r"""\b(?:it|test)\s*\(\s*(['"`])(.*?)\1""", re.S)
JS_ASSERT_HINT = re.compile(r"\bexpect\s*\(|\.toBe\b|\.toEqual\b")

_JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# `//` line comments; the (?<!:) lookbehind keeps URL schemes inside string
# literals (https://..., wss://...) from being treated as comment openers.
_JS_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")


def _blank(match: re.Match) -> str:
    """Replace a comment with spaces, preserving newlines and offsets."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_js_comments(text: str) -> str:
    """Blank /* */ and // comments so commented-out assertions never count.

    Gate-bypass class found in review of PR #101: `// expect(x).toBe(1)`
    satisfied JS_ASSERT_HINT on the raw source. Blanking preserves line
    structure and character offsets, so test-title extraction and segment
    boundaries are unaffected.
    """
    return _JS_LINE_COMMENT.sub(_blank, _JS_BLOCK_COMMENT.sub(_blank, text))


# ── Python analysis (AST) ───────────────────────────────────────────


def _py_function_asserts(fn: ast.AST) -> bool:
    """True if the function subtree carries an assertion mechanism."""
    for node in ast.walk(fn):
        if node is fn:
            continue  # never count the test's own name
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("assert") or attr in ("raises", "fail"):
                return True
            if "mock" in attr.lower():
                return True
        if isinstance(node, ast.Name):
            if node.id == "raises" or "mock" in node.id.lower():
                return True
    return False


def analyze_python(path: Path) -> tuple[int, list[dict]]:
    """Return (test_function_count, hollow_entries) for one Python file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return 0, [
            {"file": str(path), "test": None, "reason": f"unparseable: {exc.msg}"}
        ]

    counted = 0
    hollow: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            counted += 1
            if not _py_function_asserts(node):
                hollow.append(
                    {
                        "file": str(path),
                        "test": node.name,
                        "reason": "no assert/mock/raises",
                    }
                )
    if counted == 0 and not hollow:
        hollow.append(
            {"file": str(path), "test": None, "reason": "no test functions found"}
        )
    return counted, hollow


# ── JS/TS analysis (segment heuristic) ──────────────────────────────


def analyze_js(path: Path) -> tuple[int, list[dict]]:
    """Return (test_block_count, hollow_entries) for one JS/TS test file."""
    src = strip_js_comments(path.read_text(encoding="utf-8"))
    matches = list(JS_TEST_CALL.finditer(src))
    if not matches:
        return 0, [
            {"file": str(path), "test": None, "reason": "no it()/test() blocks found"}
        ]

    hollow: list[dict] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(src)
        segment = src[m.start() : end]
        if not JS_ASSERT_HINT.search(segment):
            hollow.append(
                {
                    "file": str(path),
                    "test": m.group(2),
                    "reason": "no expect/toBe/toEqual",
                }
            )
    return len(matches), hollow


# ── Discovery + CLI ─────────────────────────────────────────────────


def discover(tests_dir: Path) -> list[Path]:
    found: set[Path] = set()
    for pattern in PY_GLOBS + JS_GLOBS:
        for p in tests_dir.rglob(pattern):
            if not any(part in _SKIP_DIRS for part in p.parts):
                found.add(p)
    return sorted(found)


def _analyze(path: Path) -> tuple[int, list[dict]]:
    if path.suffix == ".py":
        return analyze_python(path)
    return analyze_js(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hollow-test validator (SPEC-056): every test must assert"
    )
    parser.add_argument("files", nargs="*", help="explicit test files to check")
    parser.add_argument("--tests-dir", default=None, help="directory to scan recursively")
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args(argv)

    if args.files:
        paths = [Path(f) for f in args.files]
        missing = [p for p in paths if not p.is_file()]
        if missing:
            print(f"ERROR: file(s) not found: {', '.join(map(str, missing))}")
            return 2
    else:
        tests_dir = Path(args.tests_dir or "tests")
        if not tests_dir.is_dir():
            print(f"ERROR: tests directory not found: {tests_dir}")
            return 2
        paths = discover(tests_dir)

    hollow: list[dict] = []
    counted = 0
    if not paths:
        hollow.append(
            {
                "file": str(args.tests_dir or "tests"),
                "test": None,
                "reason": "no test files found (empty input set never passes)",
            }
        )
    for path in paths:
        n, entries = _analyze(path)
        counted += n
        hollow.extend(entries)

    status = "fail" if hollow else "pass"
    if args.json_out:
        print(
            json.dumps(
                {"status": status, "counted": counted, "hollow": hollow}, indent=2
            )
        )
    else:
        for h in hollow:
            name = h["test"] if h["test"] is not None else "-"
            print(f"HOLLOW: {h['file']}::{name} ({h['reason']})")
        if not hollow:
            print(
                f"PASS: {counted} test function(s)/block(s) across "
                f"{len(paths)} file(s) all carry assertions"
            )
    return 1 if hollow else 0


if __name__ == "__main__":
    raise SystemExit(main())
