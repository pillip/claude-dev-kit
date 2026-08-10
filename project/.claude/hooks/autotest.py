#!/usr/bin/env python3
"""PostToolUse hook: auto-run related tests after Write/Edit on source files."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

SKIP_EXTS = {".json", ".md", ".toml", ".yaml", ".yml", ".css", ".html", ".txt", ".cfg", ".ini", ".lock"}
PYTHON_EXTS = {".py"}
JS_EXTS = {".js", ".ts", ".jsx", ".tsx"}
E2E_EXTS = {".spec.ts", ".spec.js", ".cy.ts", ".cy.js"}
TIMEOUT = 30
E2E_TIMEOUT = 60
CACHE_VERSION = 1
CACHE_RELPATH = os.path.join(".claude", "run", "autotest_cache.json")
DEBOUNCE_SECONDS = 30.0


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


def _find_python_root(filepath: str) -> str | None:
    """Find the project root: nearest ancestor with a tests/ dir or pyproject.toml."""
    d = os.path.dirname(filepath)
    while d:
        if os.path.isdir(os.path.join(d, "tests")) or os.path.isfile(os.path.join(d, "pyproject.toml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _find_js_root(filepath: str) -> str | None:
    """Find the project root: nearest ancestor containing package.json."""
    d = os.path.dirname(filepath)
    while d:
        if os.path.isfile(os.path.join(d, "package.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _is_python_test_file(name: str) -> bool:
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _is_js_test_file(name: str) -> bool:
    return ".test." in name or ".spec." in name


def _skip_js_scan_dir(name: str) -> bool:
    # Skip node_modules and ALL hidden dirs: the cache itself lives under
    # .claude/run/, so scanning hidden dirs would self-invalidate the
    # fingerprint on every save.
    return name == "node_modules" or name.startswith(".")


def _empty_cache() -> dict:
    return {
        "version": CACHE_VERSION,
        "python_index": {"fingerprint": "", "modules": {}},
        "js_index": {"fingerprint": "", "modules": {}},
        "debounce": {},
    }


def _load_cache(project_root: str) -> dict:
    """Load the on-disk cache; any problem yields a fresh empty cache (fail-soft)."""
    path = os.path.join(project_root, CACHE_RELPATH)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return _empty_cache()
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return _empty_cache()
    for key in ("python_index", "js_index"):
        index = data.get(key)
        if (
            not isinstance(index, dict)
            or not isinstance(index.get("fingerprint"), str)
            or not isinstance(index.get("modules"), dict)
        ):
            return _empty_cache()
    if not isinstance(data.get("debounce"), dict):
        return _empty_cache()
    return data


def _save_cache(project_root: str, cache: dict) -> None:
    """Best-effort write of the cache file; never raises."""
    path = os.path.join(project_root, CACHE_RELPATH)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except OSError:
        pass


def _stat_fingerprint(scan_root: str, match, skip_dir=None) -> str:
    """Hash of sorted (relpath, mtime_ns, size) for matching files under scan_root.

    Uses recursive os.scandir — stat-only, no os.walk and no file reads — so
    warm cache hits never touch the tests tree beyond cheap stats.
    """
    entries: list[tuple[str, int, int]] = []

    def scan(d: str) -> None:
        try:
            with os.scandir(d) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if skip_dir and skip_dir(entry.name):
                                continue
                            scan(entry.path)
                        elif entry.is_file(follow_symlinks=False) and match(entry.name):
                            st = entry.stat(follow_symlinks=False)
                            entries.append(
                                (os.path.relpath(entry.path, scan_root), st.st_mtime_ns, st.st_size)
                            )
                    except OSError:
                        continue
        except OSError:
            pass

    scan(scan_root)
    entries.sort()
    return hashlib.sha1(repr(entries).encode("utf-8")).hexdigest()


def _test_set_hash(paths: list[str]) -> str:
    """Hash identifying the exact set + content-state of the selected test files."""
    entries: list[tuple[str, int, int]] = []
    for p in sorted(paths):
        try:
            st = os.stat(p)
            entries.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            entries.append((p, -1, -1))
    return hashlib.sha1(repr(entries).encode("utf-8")).hexdigest()


def find_related_python_tests(filepath: str) -> list[str]:
    """Find all test files that import or reference the edited module."""
    basename = os.path.basename(filepath)
    module_name = basename.replace(".py", "")

    project_root = _find_python_root(filepath)
    if not project_root:
        return []

    tests_dir = os.path.join(project_root, "tests")
    if not os.path.isdir(tests_dir):
        return []

    cache = _load_cache(project_root)
    fingerprint = _stat_fingerprint(tests_dir, _is_python_test_file)
    index = cache["python_index"]
    if index["fingerprint"] != fingerprint:
        index = {"fingerprint": fingerprint, "modules": {}}
        cache["python_index"] = index
    cached = index["modules"].get(module_name)
    if isinstance(cached, list):
        return list(cached)

    results = []
    for root, _dirs, files in os.walk(tests_dir):
        for f in files:
            if not _is_python_test_file(f):
                continue
            test_path = os.path.join(root, f)
            try:
                content = open(test_path, encoding="utf-8", errors="replace").read()
                if module_name in content:
                    results.append(test_path)
            except OSError:
                continue

    index["modules"][module_name] = results
    _save_cache(project_root, cache)
    return results


def find_related_js_tests(filepath: str) -> list[str]:
    """Find all test files that import or reference the edited JS/TS module."""
    basename = os.path.basename(filepath)
    name, _ = os.path.splitext(basename)

    project_root = _find_js_root(filepath)
    if not project_root:
        return []

    cache = _load_cache(project_root)
    fingerprint = _stat_fingerprint(project_root, _is_js_test_file, _skip_js_scan_dir)
    index = cache["js_index"]
    if index["fingerprint"] != fingerprint:
        index = {"fingerprint": fingerprint, "modules": {}}
        cache["js_index"] = index
    cached = index["modules"].get(name)
    if isinstance(cached, list):
        return list(cached)

    results = []
    for root, _dirs, files in os.walk(project_root):
        # Unlike the fingerprint scan, this walk skips only node_modules —
        # test files are not expected in hidden dirs.
        if "node_modules" in root.split(os.sep):
            continue
        for f in files:
            if not _is_js_test_file(f):
                continue
            test_path = os.path.join(root, f)
            try:
                content = open(test_path, encoding="utf-8", errors="replace").read()
                if name in content:
                    results.append(test_path)
            except OSError:
                continue

    index["modules"][name] = results
    _save_cache(project_root, cache)
    return results


def detect_e2e_framework(filepath: str) -> str | None:
    """Detect E2E framework from file path patterns."""
    if filepath.endswith((".spec.ts", ".spec.js")):
        # Check if it's in a Playwright or Cypress directory
        if "cypress" in filepath.lower() or filepath.endswith(".cy.ts") or filepath.endswith(".cy.js"):
            return "cypress"
        if os.path.sep + "e2e" + os.path.sep in filepath or filepath.startswith("tests/e2e/"):
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


def _run_source_branch(filepath: str, lang: str) -> dict | None:
    """Run unit + related E2E tests for a Python ("py") or JS ("js") source file.

    Identical passing runs within DEBOUNCE_SECONDS are skipped; failures are
    never debounced — a "fail" entry always re-runs on the next edit.
    """
    if lang == "py":
        primary = find_python_test(filepath)
        related = find_related_python_tests(filepath)
        project_root = _find_python_root(filepath)
    else:
        primary = find_js_test(filepath)
        related = find_related_js_tests(filepath)
        project_root = _find_js_root(filepath)

    test_files = []
    if primary and os.path.isfile(primary):
        test_files.append(primary)
    for rf in related:
        if rf not in test_files:
            test_files.append(rf)

    # Cap unit and E2E selection BEFORE running anything (debounce covers both)
    selected = test_files[:MAX_RELATED_TESTS]
    e2e_selected = find_e2e_tests(filepath)[:2]  # Cap at 2 E2E tests

    cache = key = test_set = None
    if project_root and (selected or e2e_selected):
        cache = _load_cache(project_root)
        key = lang + ":" + os.path.abspath(filepath)
        test_set = _test_set_hash(selected + [t for t, _ in e2e_selected])
        entry = cache["debounce"].get(key)
        if (
            isinstance(entry, dict)
            and entry.get("test_set") == test_set
            and entry.get("result") == "pass"
            and isinstance(entry.get("last_run"), (int, float))
            and time.time() - entry["last_run"] < DEBOUNCE_SECONDS
        ):
            return None

    # Runners looked up via module globals so tests can monkeypatch them
    blocked = None
    for tf in selected:
        blocked = run_python_test(tf) if lang == "py" else run_js_test(tf)
        if blocked:
            break
    if blocked is None:
        for e2e_file, framework in e2e_selected:
            blocked = run_e2e_test(e2e_file, framework)
            if blocked:
                break

    # Record the outcome BEFORE returning any block dict
    if cache is not None:
        cache["debounce"][key] = {
            "test_set": test_set,
            "last_run": time.time(),
            "result": "fail" if blocked else "pass",
        }
        _save_cache(project_root, cache)

    return blocked


def handle_event(hook_input: dict) -> dict | None:
    """Process one PostToolUse event; return a block dict or None."""
    tool_name = hook_input.get("tool_name", "")

    if tool_name not in ("Write", "Edit"):
        return None

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")
    if not filepath:
        return None

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext in SKIP_EXTS:
        return None

    # Check if the file itself is an E2E test (direct E2E runs are never debounced)
    e2e_fw = detect_e2e_framework(filepath)
    if e2e_fw:
        return run_e2e_test(filepath, e2e_fw)

    if ext in PYTHON_EXTS:
        return _run_source_branch(filepath, "py")

    if ext in JS_EXTS:
        return _run_source_branch(filepath, "js")

    # Also check for related E2E tests when editing other source files
    for e2e_file, framework in find_e2e_tests(filepath)[:2]:  # Cap at 2 E2E tests
        result = run_e2e_test(e2e_file, framework)
        if result:
            return result
    return None


def main():
    hook_input = json.loads(sys.stdin.read())
    result = handle_event(hook_input)
    if result:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
