import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks" / "autotest.py"


def run_hook(payload: dict) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    if stdout:
        return json.loads(stdout)
    return None


class TestPythonTestDiscovery:
    def test_runs_test_file_directly(self):
        """When editing a test file itself, it should run that file."""
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(test_file)},
            }
            out = run_hook(payload)
            # Test should pass, so no block
            assert out is None

    def test_finds_corresponding_test(self):
        """When editing src/module.py, should find tests/test_module.py."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src_dir = td / "src"
            src_dir.mkdir()
            tests_dir = td / "tests"
            tests_dir.mkdir()

            src_file = src_dir / "calculator.py"
            src_file.write_text("def add(a, b): return a + b\n")

            test_file = tests_dir / "test_calculator.py"
            test_file.write_text("def test_add(): assert 1 + 1 == 2\n")

            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(src_file)},
            }
            out = run_hook(payload)
            assert out is None

    def test_blocks_on_failing_test(self):
        """When the corresponding test fails, should block."""
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test_broken.py"
            test_file.write_text("def test_fail(): assert False\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(test_file)},
            }
            out = run_hook(payload)
            assert out is not None
            assert out["decision"] == "block"
            assert "Test failed" in out["reason"]

    def test_skips_when_no_test_found(self):
        """When no corresponding test exists, should not block."""
        with tempfile.TemporaryDirectory() as td:
            src_file = Path(td) / "orphan_module.py"
            src_file.write_text("x = 1\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(src_file)},
            }
            out = run_hook(payload)
            assert out is None


class TestSkipFiles:
    def test_skips_json(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/config.json"},
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_markdown(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/README.md"},
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_toml(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/pyproject.toml"},
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_css(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/styles.css"},
        }
        out = run_hook(payload)
        assert out is None


class TestJSTestDiscovery:
    def test_runs_test_file_directly(self):
        """When editing a .test.ts file, it should try to run it (skip if no runner)."""
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "app.test.js"
            test_file.write_text("test('pass', () => expect(true).toBe(true));\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(test_file)},
            }
            # Without jest/vitest installed, should skip gracefully
            out = run_hook(payload)
            # Either None (no runner) or a result - should not crash
            assert out is None or "decision" in out

    def test_finds_test_file_for_source(self):
        """When editing app.ts, should look for app.test.ts."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "app.ts"
            src.write_text("export const x = 1;\n")
            test = td / "app.test.ts"
            test.write_text("test('x', () => {});\n")

            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(src)},
            }
            # Without jest/vitest installed, should skip gracefully
            out = run_hook(payload)
            assert out is None or "decision" in out


class TestRelatedPythonTestDiscovery:
    """Tests for find_related_python_tests() — multi-file test discovery."""

    def test_finds_test_that_imports_module(self):
        """Should find test files that reference the edited module."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src_dir = td / "src"
            src_dir.mkdir()
            tests_dir = td / "tests"
            tests_dir.mkdir()
            (td / "pyproject.toml").write_text("[tool.pytest]\n")

            # Source file
            src_file = src_dir / "user.py"
            src_file.write_text("class User: pass\n")

            # Test that references 'user'
            (tests_dir / "test_user_service.py").write_text(
                "from src.user import User\ndef test_user(): assert True\n"
            )
            # Unrelated test
            (tests_dir / "test_other.py").write_text(
                "def test_other(): assert True\n"
            )

            # Import the module to test
            sys.path.insert(0, str(SCRIPT.parent))
            import importlib
            import autotest
            importlib.reload(autotest)

            results = autotest.find_related_python_tests(str(src_file))
            assert len(results) == 1
            assert "test_user_service.py" in results[0]

    def test_returns_empty_when_no_tests_dir(self):
        """Should return empty list when no tests/ directory exists."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src_file = td / "standalone.py"
            src_file.write_text("x = 1\n")

            sys.path.insert(0, str(SCRIPT.parent))
            import importlib
            import autotest
            importlib.reload(autotest)

            results = autotest.find_related_python_tests(str(src_file))
            assert results == []


class TestRelatedJSTestDiscovery:
    """Tests for find_related_js_tests() — multi-file JS test discovery."""

    def test_finds_test_that_references_module(self):
        """Should find .test.ts files that reference the edited module name."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "package.json").write_text('{"name": "test"}\n')

            src_file = td / "utils.ts"
            src_file.write_text("export const helper = () => {};\n")

            test_file = td / "utils.test.ts"
            test_file.write_text(
                "import { helper } from './utils';\n"
                "test('helper', () => expect(helper()).toBe(undefined));\n"
            )

            sys.path.insert(0, str(SCRIPT.parent))
            import importlib
            import autotest
            importlib.reload(autotest)

            results = autotest.find_related_js_tests(str(src_file))
            assert len(results) == 1
            assert "utils.test.ts" in results[0]


class TestMultiFileTestExecution:
    """Tests for the enhanced main() that runs multiple related tests."""

    def test_runs_multiple_related_tests(self):
        """When editing a source file with multiple related tests, all should run."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            tests_dir = td / "tests"
            tests_dir.mkdir()
            (td / "pyproject.toml").write_text("[tool.pytest]\n")

            # Source module
            src_file = td / "calculator.py"
            src_file.write_text("def add(a, b): return a + b\n")

            # Direct corresponding test (no imports, standalone)
            (tests_dir / "test_calculator.py").write_text(
                "def test_add(): assert 1 + 1 == 2\n"
            )
            # Another test that references 'calculator' in its content
            (tests_dir / "test_math_utils.py").write_text(
                "# tests calculator module\n"
                "def test_calculator_add_via_utils(): assert 2 + 3 == 5\n"
            )

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(src_file)},
            }
            out = run_hook(payload)
            # Both tests should pass, so no block
            assert out is None

    def test_blocks_if_any_related_test_fails(self):
        """If any related test fails, should block."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            tests_dir = td / "tests"
            tests_dir.mkdir()
            (td / "pyproject.toml").write_text("[tool.pytest]\n")

            src_file = td / "calculator.py"
            src_file.write_text("def add(a, b): return a + b\n")

            # Passing direct test
            (tests_dir / "test_calculator.py").write_text(
                "def test_add(): assert 1 + 1 == 2\n"
            )
            # Failing related test (references 'calculator' in content)
            (tests_dir / "test_calculator_edge.py").write_text(
                "# tests calculator edge cases\n"
                "def test_calculator_fail(): assert False\n"
            )

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(src_file)},
            }
            out = run_hook(payload)
            assert out is not None
            assert out["decision"] == "block"


class TestE2EFrameworkDetection:
    """Tests for detect_e2e_framework() — E2E framework detection."""

    def test_detects_playwright_spec(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)

        assert autotest.detect_e2e_framework("tests/e2e/login.spec.ts") == "playwright"

    def test_detects_cypress(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)

        assert autotest.detect_e2e_framework("cypress/e2e/login.cy.ts") == "cypress"

    def test_detects_maestro_yaml(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)

        assert autotest.detect_e2e_framework("e2e/login-flow.yaml") == "maestro"

    def test_detects_detox(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)

        assert autotest.detect_e2e_framework("e2e/login.test.ts") == "detox"

    def test_returns_none_for_regular_file(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)

        assert autotest.detect_e2e_framework("src/utils.py") is None


class TestE2ETestDiscovery:
    """Tests for find_e2e_tests() — E2E test file discovery."""

    def test_finds_playwright_tests(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "package.json").write_text('{"name": "test"}\n')
            e2e_dir = td / "tests" / "e2e"
            e2e_dir.mkdir(parents=True)
            (e2e_dir / "login.spec.ts").write_text("test('login', () => {});\n")

            src_file = td / "src" / "auth.ts"
            src_file.parent.mkdir()
            src_file.write_text("export const login = () => {};\n")

            sys.path.insert(0, str(SCRIPT.parent))
            import importlib
            import autotest
            importlib.reload(autotest)

            results = autotest.find_e2e_tests(str(src_file))
            assert len(results) >= 1
            assert any("login.spec.ts" in r[0] for r in results)
            assert any(r[1] == "playwright" for r in results)

    def test_returns_empty_when_no_e2e_dir(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "package.json").write_text('{"name": "test"}\n')
            src_file = td / "src" / "utils.ts"
            src_file.parent.mkdir()
            src_file.write_text("export const x = 1;\n")

            sys.path.insert(0, str(SCRIPT.parent))
            import importlib
            import autotest
            importlib.reload(autotest)

            results = autotest.find_e2e_tests(str(src_file))
            assert results == []


class TestNonTargetTools:
    def test_ignores_bash(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        }
        out = run_hook(payload)
        assert out is None


class TestFindJsRunner:
    def _load(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)
        return autotest

    def test_prefers_local_vitest_bin(self):
        autotest = self._load()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bin_dir = root / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "vitest").write_text("#!/bin/sh\n")
            (root / "package.json").write_text('{"devDependencies": {"vitest": "^1"}}')
            test_file = root / "src" / "a.test.ts"
            test_file.parent.mkdir()
            test_file.write_text("test('x', () => {})\n")

            runner = autotest.find_js_runner(str(test_file))
            assert runner is not None
            assert runner[0].endswith(os.path.join("node_modules", ".bin", "vitest"))
            assert runner[1] == "run"

    def test_no_jest_fallback_for_vitest_project(self):
        # vitest declared but no local bin and no global vitest/jest:
        # must NOT fall back to `npx jest` (would mis-run TS/ESM tests).
        autotest = self._load()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "package.json").write_text('{"devDependencies": {"vitest": "^1"}}')
            test_file = root / "a.test.ts"
            test_file.write_text("test('x', () => {})\n")

            import shutil as _sh
            from unittest.mock import patch

            def fake_which(name):
                return "/usr/bin/npx" if name == "npx" else None

            with patch.object(_sh, "which", side_effect=fake_which):
                runner = autotest.find_js_runner(str(test_file))
            # Should choose npx vitest, never npx jest.
            assert runner == ["/usr/bin/npx", "vitest", "run"]


class TestIndexCache:
    """Tests for the disk-persisted module->test-files index (ISSUE-038)."""

    def _load(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)
        return autotest

    def _make_python_project(self, root: Path) -> Path:
        """Create pyproject.toml, src/user.py, tests/test_user_service.py."""
        (root / "pyproject.toml").write_text("[tool.pytest]\n")
        src_dir = root / "src"
        src_dir.mkdir()
        tests_dir = root / "tests"
        tests_dir.mkdir()
        src_file = src_dir / "user.py"
        src_file.write_text("class User: pass\n")
        (tests_dir / "test_user_service.py").write_text(
            "from src.user import User\ndef test_user(): assert True\n"
        )
        return src_file

    def _count_walks(self, autotest, monkeypatch):
        """Wrap the real os.walk with a counter; return the mutable counter."""
        real_walk = autotest.os.walk
        calls = {"n": 0}

        def counting_walk(*args, **kwargs):
            calls["n"] += 1
            return real_walk(*args, **kwargs)

        monkeypatch.setattr(autotest.os, "walk", counting_walk)
        return calls

    def test_warm_index_avoids_tests_tree_walk(self, tmp_path, monkeypatch):
        """TC-038a: warm index hit returns cached tests with zero os.walk calls."""
        src_file = self._make_python_project(tmp_path)
        autotest = self._load()
        calls = self._count_walks(autotest, monkeypatch)

        first = autotest.find_related_python_tests(str(src_file))
        assert len(first) == 1
        assert "test_user_service.py" in first[0]
        assert calls["n"] >= 1  # cold miss must scan the tests tree

        cold_walks = calls["n"]
        second = autotest.find_related_python_tests(str(src_file))
        assert second == first
        assert calls["n"] == cold_walks  # warm hit: no new os.walk calls

    def test_js_warm_index_avoids_walk(self, tmp_path, monkeypatch):
        """TC-038a (JS path): warm js_index hit adds zero os.walk calls."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        src_file = tmp_path / "utils.ts"
        src_file.write_text("export const helper = () => {};\n")
        (tmp_path / "utils.test.ts").write_text(
            "import { helper } from './utils';\n"
            "test('helper', () => expect(helper()).toBe(undefined));\n"
        )
        autotest = self._load()
        calls = self._count_walks(autotest, monkeypatch)

        first = autotest.find_related_js_tests(str(src_file))
        assert len(first) == 1
        assert "utils.test.ts" in first[0]
        assert calls["n"] >= 1

        cold_walks = calls["n"]
        second = autotest.find_related_js_tests(str(src_file))
        assert second == first
        assert calls["n"] == cold_walks  # warm hit: no new os.walk calls

    def test_new_test_file_invalidates_index(self, tmp_path):
        """TC-038b: adding a test file changes the fingerprint and refreshes the on-disk index."""
        src_file = self._make_python_project(tmp_path)
        autotest = self._load()

        first = autotest.find_related_python_tests(str(src_file))
        assert len(first) == 1
        assert "test_user_service.py" in first[0]

        extra_test = tmp_path / "tests" / "test_user_extra.py"
        extra_test.write_text(
            "from src.user import User\ndef test_user_extra(): assert True\n"
        )

        second = autotest.find_related_python_tests(str(src_file))
        assert len(second) == 2
        names = {os.path.basename(p) for p in second}
        assert names == {"test_user_service.py", "test_user_extra.py"}

        cache_file = tmp_path / ".claude" / "run" / "autotest_cache.json"
        assert cache_file.is_file()
        data = json.loads(cache_file.read_text())
        module_entries = data["python_index"]["modules"]["user"]
        assert any(os.path.basename(p) == "test_user_extra.py" for p in module_entries)

    def test_corrupt_cache_rebuilds_and_exits_clean(self, tmp_path):
        """TC-038e: garbage cache file never crashes the hook and gets rebuilt as valid JSON."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        src_file = src_dir / "user.py"
        src_file.write_text("class User: pass\n")
        (tests_dir / "test_user.py").write_text(
            "# exercises the user module\ndef test_ok(): assert True\n"
        )

        cache_file = tmp_path / ".claude" / "run" / "autotest_cache.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("{{{ not json")

        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(src_file)},
        }
        out = run_hook(payload)
        assert out is None  # passing test, no block, no crash

        data = json.loads(cache_file.read_text())  # rebuilt as valid JSON
        assert "version" in data


class TestDebounce:
    """Tests for the debounce that skips identical passing re-runs (ISSUE-038)."""

    def _load(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        import autotest
        importlib.reload(autotest)
        return autotest

    def _make_python_project(self, root: Path) -> Path:
        (root / "pyproject.toml").write_text("[tool.pytest]\n")
        src_dir = root / "src"
        src_dir.mkdir()
        tests_dir = root / "tests"
        tests_dir.mkdir()
        src_file = src_dir / "user.py"
        src_file.write_text("class User: pass\n")
        (tests_dir / "test_user.py").write_text(
            "# exercises the user module\ndef test_ok(): assert True\n"
        )
        return src_file

    def test_duplicate_edit_within_window_skips_rerun(self, tmp_path, monkeypatch):
        """TC-038c: an identical edit within the debounce window skips the re-run."""
        src_file = self._make_python_project(tmp_path)
        autotest = self._load()

        calls = {"n": 0}

        def fake_run_python_test(test_file):
            calls["n"] += 1
            return None  # pass

        monkeypatch.setattr(autotest, "run_python_test", fake_run_python_test)

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(src_file)},
        }
        first = autotest.handle_event(payload)
        assert first is None
        assert calls["n"] >= 1  # tests actually ran the first time

        runs_after_first = calls["n"]
        second = autotest.handle_event(payload)
        assert second is None
        assert calls["n"] == runs_after_first  # debounced: no re-run

    def test_failure_is_never_debounced(self, tmp_path, monkeypatch):
        """TC-038d: a failing result is re-run on the next identical edit, never debounced."""
        src_file = self._make_python_project(tmp_path)
        autotest = self._load()

        calls = {"n": 0}
        block = {"decision": "block", "reason": "boom"}

        def fake_run_python_test(test_file):
            calls["n"] += 1
            return dict(block)

        monkeypatch.setattr(autotest, "run_python_test", fake_run_python_test)

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(src_file)},
        }
        first = autotest.handle_event(payload)
        assert first is not None
        assert first["decision"] == "block"
        runs_after_first = calls["n"]
        assert runs_after_first >= 1

        second = autotest.handle_event(payload)
        assert second is not None
        assert second["decision"] == "block"
        assert calls["n"] > runs_after_first  # failure must be re-run, not debounced
