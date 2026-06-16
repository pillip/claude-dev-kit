#!/usr/bin/env python3
"""PostToolUse hook: auto-run related tests after Write/Edit on source files."""

import json
import os
import shutil
import subprocess
import sys

SKIP_EXTS = {".json", ".md", ".toml", ".yaml", ".yml", ".css", ".html", ".txt", ".cfg", ".ini", ".lock"}
PYTHON_EXTS = {".py"}
JS_EXTS = {".js", ".ts", ".jsx", ".tsx"}
E2E_EXTS = {".spec.ts", ".spec.js", ".cy.ts", ".cy.js"}
TIMEOUT = 30
E2E_TIMEOUT = 60


def find_python_test(filepath: str) -> str | None:
    """Find the corresponding test file for a Python source file."""
    basename = os.path.basename(filepath)
    dirpath = os.path.dirname(filepath)

    # If it's already a test file, run it directly
    if basename.startswith("test_"):
        return filepath

    # Search for test_<module>.py in tests/ directories
    module_name = basename.replace(".py", "")
    test_name = f"test_{module_name}.py"

    # Walk up to find a tests/ directory
    search_dir = dirpath
    while search_dir:
        tests_dir = os.path.join(search_dir, "tests")
        candidate = os.path.join(tests_dir, test_name)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent

    return None


def find_js_test(filepath: str) -> str | None:
    """Find the corresponding test file for a JS/TS source file."""
    basename = os.path.basename(filepath)
    dirpath = os.path.dirname(filepath)

    # If it's already a test/spec file, run it directly
    if ".test." in basename or ".spec." in basename:
        return filepath

    # Search for <name>.test.<ext> or <name>.spec.<ext>
    name, ext = os.path.splitext(basename)
    for suffix in [".test", ".spec"]:
        for search_ext in [ext, ".ts", ".js", ".tsx", ".jsx"]:
            candidate = os.path.join(dirpath, f"{name}{suffix}{search_ext}")
            if os.path.isfile(candidate):
                return candidate
            # Also check __tests__ directory
            tests_candidate = os.path.join(dirpath, "__tests__", f"{name}{suffix}{search_ext}")
            if os.path.isfile(tests_candidate):
                return tests_candidate

    return None


def _find_up(start_dir: str, *relpaths: str) -> str | None:
    """Walk up from start_dir, returning the first existing relpath match."""
    d = os.path.abspath(start_dir)
    while True:
        for rel in relpaths:
            cand = os.path.join(d, rel)
            if os.path.exists(cand):
                return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _pkg_has_dep(start_dir: str, dep: str) -> bool:
    """True if the nearest package.json declares `dep` in (dev)dependencies."""
    pkg = _find_up(start_dir, "package.json")
    if not pkg:
        return False
    try:
        with open(pkg, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return False
    return any(
        dep in (data.get(key) or {})
        for key in ("dependencies", "devDependencies")
    )


def find_js_runner(test_file: str) -> list[str] | None:
    """Detect the JS test runner, preferring locally-installed binaries.

    `shutil.which` only sees the global PATH, but vitest/jest are almost always
    installed locally under `node_modules/.bin`. Missing the local binary used
    to fall back to `npx jest`, which can't run TS/ESM test files and produced
    a false "Test failed" on every edit even when vitest was green. So:
      1. Prefer a local `node_modules/.bin/{vitest,jest}` near the test file.
      2. If the project declares vitest but has no local binary yet, use
         `npx vitest` — never fall back to jest for a vitest project.
      3. Only then consider a global vitest/jest, and `npx jest` last.
    """
    start = os.path.dirname(os.path.abspath(test_file))
    has_vitest = _pkg_has_dep(start, "vitest")

    local_vitest = _find_up(start, os.path.join("node_modules", ".bin", "vitest"))
    if local_vitest:
        return [local_vitest, "run"]
    local_jest = _find_up(start, os.path.join("node_modules", ".bin", "jest"))
    if local_jest:
        return [local_jest, "--no-coverage"]

    npx = shutil.which("npx")
    if has_vitest and npx:
        return [npx, "vitest", "run"]
    if shutil.which("vitest"):
        return ["vitest", "run"]
    if shutil.which("jest"):
        return ["jest", "--no-coverage"]
    # Don't run jest against a vitest project's TS/ESM tests — guaranteed false
    # failure. Only use the npx jest fallback when vitest isn't in play.
    if npx and not has_vitest:
        return [npx, "jest", "--no-coverage"]
    return None


def run_python_test(test_file: str) -> dict | None:
    pytest_cmd = shutil.which("pytest")
    if not pytest_cmd:
        return None

    try:
        result = subprocess.run(
            [pytest_cmd, test_file, "-x", "-q", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "decision": "block",
            "reason": f"Test timed out after {TIMEOUT}s: {test_file}",
        }

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-1000:]
        return {
            "decision": "block",
            "reason": f"Test failed: {test_file}\n{output}",
        }

    return None


def run_js_test(test_file: str) -> dict | None:
    runner = find_js_runner(test_file)
    if not runner:
        return None

    try:
        result = subprocess.run(
            [*runner, test_file],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "decision": "block",
            "reason": f"Test timed out after {TIMEOUT}s: {test_file}",
        }

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-1000:]
        return {
            "decision": "block",
            "reason": f"Test failed: {test_file}\n{output}",
        }

    return None


MAX_RELATED_TESTS = 5


def find_related_python_tests(filepath: str) -> list[str]:
    """Find all test files that import or reference the edited module."""
    basename = os.path.basename(filepath)
    module_name = basename.replace(".py", "")
    results = []

    # Walk up to find project root (directory containing tests/ or pyproject.toml)
    search_dir = os.path.dirname(filepath)
    project_root = None
    d = search_dir
    while d:
        if os.path.isdir(os.path.join(d, "tests")) or os.path.isfile(os.path.join(d, "pyproject.toml")):
            project_root = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    if not project_root:
        return results

    tests_dir = os.path.join(project_root, "tests")
    if not os.path.isdir(tests_dir):
        return results

    for root, _dirs, files in os.walk(tests_dir):
        for f in files:
            if not f.endswith(".py") or not (f.startswith("test_") or f.endswith("_test.py")):
                continue
            test_path = os.path.join(root, f)
            try:
                content = open(test_path, encoding="utf-8", errors="replace").read()
                if module_name in content:
                    results.append(test_path)
            except OSError:
                continue

    return results


def find_related_js_tests(filepath: str) -> list[str]:
    """Find all test files that import or reference the edited JS/TS module."""
    basename = os.path.basename(filepath)
    name, _ = os.path.splitext(basename)
    results = []

    search_dir = os.path.dirname(filepath)
    project_root = None
    d = search_dir
    while d:
        if os.path.isfile(os.path.join(d, "package.json")):
            project_root = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    if not project_root:
        return results

    for root, _dirs, files in os.walk(project_root):
        if "node_modules" in root.split(os.sep):
            continue
        for f in files:
            if not (".test." in f or ".spec." in f):
                continue
            test_path = os.path.join(root, f)
            try:
                content = open(test_path, encoding="utf-8", errors="replace").read()
                if name in content:
                    results.append(test_path)
            except OSError:
                continue

    return results


def detect_e2e_framework(filepath: str) -> str | None:
    """Detect E2E framework from file path patterns."""
    if filepath.endswith((".spec.ts", ".spec.js")):
        # Check if it's in a Playwright or Cypress directory
        if "cypress" in filepath.lower() or filepath.endswith(".cy.ts") or filepath.endswith(".cy.js"):
            return "cypress"
        if os.path.sep + "e2e" + os.sep in filepath or filepath.startswith("tests/e2e/"):
            return "playwright"
        return "playwright"  # default for .spec files
    if filepath.endswith((".cy.ts", ".cy.js")):
        return "cypress"
    if filepath.endswith(".yaml") and ("e2e" in filepath or "maestro" in filepath.lower()):
        return "maestro"
    if filepath.endswith((".test.ts", ".test.js")) and "e2e" in filepath:
        return "detox"
    return None


def find_e2e_tests(filepath: str) -> list[tuple[str, str]]:
    """Find E2E test files related to the changed source file.

    Returns list of (test_file_path, framework) tuples.
    """
    results: list[tuple[str, str]] = []
    dirpath = os.path.dirname(filepath)

    # Walk up to find project root
    project_root = None
    d = dirpath
    while d:
        if os.path.isfile(os.path.join(d, "package.json")) or os.path.isfile(os.path.join(d, "pyproject.toml")):
            project_root = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    if not project_root:
        return results

    # Check for Playwright tests
    playwright_dir = os.path.join(project_root, "tests", "e2e")
    if os.path.isdir(playwright_dir):
        for f in os.listdir(playwright_dir):
            if f.endswith((".spec.ts", ".spec.js")):
                results.append((os.path.join(playwright_dir, f), "playwright"))

    # Check for Cypress tests
    cypress_dir = os.path.join(project_root, "cypress", "e2e")
    if os.path.isdir(cypress_dir):
        for f in os.listdir(cypress_dir):
            if f.endswith((".cy.ts", ".cy.js")):
                results.append((os.path.join(cypress_dir, f), "cypress"))

    # Check for Maestro tests
    maestro_dir = os.path.join(project_root, "e2e")
    if os.path.isdir(maestro_dir):
        for f in os.listdir(maestro_dir):
            if f.endswith(".yaml"):
                results.append((os.path.join(maestro_dir, f), "maestro"))

    # Check for Detox tests
    detox_dir = os.path.join(project_root, "e2e")
    if os.path.isdir(detox_dir):
        for f in os.listdir(detox_dir):
            if f.endswith((".test.ts", ".test.js")):
                results.append((os.path.join(detox_dir, f), "detox"))

    return results


def run_e2e_test(test_file: str, framework: str) -> dict | None:
    """Run a single E2E test file with the appropriate framework."""
    cmd: list[str] = []

    if framework == "playwright":
        npx = shutil.which("npx")
        if not npx:
            return None
        cmd = [npx, "playwright", "test", test_file]
    elif framework == "cypress":
        npx = shutil.which("npx")
        if not npx:
            return None
        cmd = [npx, "cypress", "run", "--spec", test_file]
    elif framework == "maestro":
        maestro = shutil.which("maestro")
        if not maestro:
            return None
        cmd = [maestro, "test", test_file]
    elif framework == "detox":
        npx = shutil.which("npx")
        if not npx:
            return None
        cmd = [npx, "detox", "test", "--file", test_file]
    else:
        return None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=E2E_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "decision": "block",
            "reason": f"E2E test timed out after {E2E_TIMEOUT}s: {test_file} ({framework})",
        }

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-1000:]
        return {
            "decision": "block",
            "reason": f"E2E test failed ({framework}): {test_file}\n{output}",
        }

    return None


def main():
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")

    if tool_name not in ("Write", "Edit"):
        return

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")
    if not filepath:
        return

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext in SKIP_EXTS:
        return

    # Check if the file itself is an E2E test
    e2e_fw = detect_e2e_framework(filepath)
    if e2e_fw:
        result = run_e2e_test(filepath, e2e_fw)
        if result:
            print(json.dumps(result))
        return

    if ext in PYTHON_EXTS:
        # Primary: direct corresponding test
        test_files = []
        primary = find_python_test(filepath)
        if primary and os.path.isfile(primary):
            test_files.append(primary)

        # Secondary: all test files that reference this module
        for rf in find_related_python_tests(filepath):
            if rf not in test_files:
                test_files.append(rf)

        # Run all (capped to avoid slow runs)
        for tf in test_files[:MAX_RELATED_TESTS]:
            result = run_python_test(tf)
            if result:
                print(json.dumps(result))
                return

    elif ext in JS_EXTS:
        test_files = []
        primary = find_js_test(filepath)
        if primary and os.path.isfile(primary):
            test_files.append(primary)

        for rf in find_related_js_tests(filepath):
            if rf not in test_files:
                test_files.append(rf)

        for tf in test_files[:MAX_RELATED_TESTS]:
            result = run_js_test(tf)
            if result:
                print(json.dumps(result))
                return

    # Also check for related E2E tests when editing source files
    e2e_tests = find_e2e_tests(filepath)
    for e2e_file, framework in e2e_tests[:2]:  # Cap at 2 E2E tests
        result = run_e2e_test(e2e_file, framework)
        if result:
            print(json.dumps(result))
            return


if __name__ == "__main__":
    main()
