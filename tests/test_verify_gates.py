"""Unit tests for scripts/verify_gates.py."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sys

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_gates as vg


# ── helpers ───────────────────────────────────────────────────────────


def _mock_run(returncode=0, stdout="", stderr=""):
    """Create a mock CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _write_package_json(project: Path, deps: dict | None = None):
    """Write a package.json with optional dependencies."""
    deps = deps or {}
    content = json.dumps({"dependencies": deps})
    project.joinpath("package.json").write_text(content)


def _write_test_plan(project: Path, content: str):
    """Write docs/test_plan.md."""
    docs = project / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "test_plan.md").write_text(content)


# ── TestDetectPlatforms ──────────────────────────────────────────────


class TestDetectPlatforms:
    def test_empty_project_returns_unit_only(self, tmp_path):
        # No files at all → no platforms (not even unit without test files)
        result = vg.detect_platforms(tmp_path)
        assert result == set()

    def test_empty_project_with_tests_dir_returns_unit(self, tmp_path):
        (tmp_path / "tests").mkdir()
        result = vg.detect_platforms(tmp_path)
        assert result == {"unit"}

    def test_react_project_detected_as_web(self, tmp_path):
        _write_package_json(tmp_path, {"react": "^18.0.0"})
        result = vg.detect_platforms(tmp_path)
        assert "web" in result

    def test_react_native_detected_as_mobile(self, tmp_path):
        _write_package_json(tmp_path, {"react-native": "^0.72.0"})
        result = vg.detect_platforms(tmp_path)
        assert "mobile" in result

    def test_openapi_detected_as_api(self, tmp_path):
        (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0")
        result = vg.detect_platforms(tmp_path)
        assert "api" in result

    def test_explicit_declaration_overrides_heuristic(self, tmp_path):
        _write_test_plan(tmp_path, "- Detected platform: mobile\n")
        result = vg.detect_platforms(tmp_path)
        assert "mobile" in result

    def test_multi_platform_detection(self, tmp_path):
        _write_package_json(tmp_path, {"react": "^18.0.0", "express": "^4.0.0"})
        (tmp_path / "tests").mkdir()
        result = vg.detect_platforms(tmp_path)
        assert "web" in result
        assert "api" in result
        assert "unit" in result

    def test_no_package_json_falls_back_to_file_patterns(self, tmp_path):
        (tmp_path / "playwright.config.ts").write_text("")
        result = vg.detect_platforms(tmp_path)
        assert "web" in result

    def test_fastapi_in_pyproject_detected_as_api(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi"]\n')
        result = vg.detect_platforms(tmp_path)
        assert "api" in result

    def test_android_dir_detected_as_mobile(self, tmp_path):
        (tmp_path / "android").mkdir()
        result = vg.detect_platforms(tmp_path)
        assert "mobile" in result

    def test_vue_project_detected_as_web(self, tmp_path):
        _write_package_json(tmp_path, {"vue": "^3.0.0"})
        result = vg.detect_platforms(tmp_path)
        assert "web" in result


# ── TestReadGateConfig ───────────────────────────────────────────────


class TestReadGateConfig:
    def test_reads_config_from_test_plan(self, tmp_path):
        _write_test_plan(
            tmp_path,
            """\
## Verify Gates Configuration
- Server start command: `npm run dev`
- Server health URL: `http://localhost:3000/health`
- Server startup timeout: 45s

### Gate Overrides
| Gate | Enabled | Blocking | Notes |
|------|---------|----------|-------|
| unit | yes | yes | Always enabled |
| e2e-web | no | yes | Not ready yet |
| load | yes | no | Non-blocking |

## Release Checklist (Smoke)
""",
        )
        config = vg.read_gate_config(tmp_path)
        assert config["server_start_cmd"] == "npm run dev"
        assert config["server_health_url"] == "http://localhost:3000/health"
        assert config["server_timeout"] == 45
        assert config["gate_overrides"]["unit"]["enabled"] is True
        assert config["gate_overrides"]["e2e-web"]["enabled"] is False
        assert config["gate_overrides"]["load"]["blocking"] is False

    def test_defaults_when_no_test_plan(self, tmp_path):
        config = vg.read_gate_config(tmp_path)
        assert config["server_start_cmd"] == ""
        assert config["server_health_url"] == ""
        assert config["server_timeout"] == 30
        assert config["gate_overrides"] == {}

    def test_defaults_when_no_gates_section(self, tmp_path):
        _write_test_plan(tmp_path, "## Strategy\nSome content\n")
        config = vg.read_gate_config(tmp_path)
        assert config["server_start_cmd"] == ""
        assert config["gate_overrides"] == {}

    def test_parses_gate_overrides_table(self, tmp_path):
        _write_test_plan(
            tmp_path,
            """\
## Verify Gates Configuration
- Server start command: `uvicorn main:app`
- Server health URL: `http://localhost:8000/health`
- Server startup timeout: 30s

### Gate Overrides
| Gate | Enabled | Blocking |
|------|---------|----------|
| unit | yes | yes |
| integration | yes | no |
| api | no | yes |
""",
        )
        config = vg.read_gate_config(tmp_path)
        overrides = config["gate_overrides"]
        assert overrides["unit"] == {"enabled": True, "blocking": True}
        assert overrides["integration"] == {"enabled": True, "blocking": False}
        assert overrides["api"] == {"enabled": False, "blocking": True}


# ── TestGateResult ───────────────────────────────────────────────────


class TestGateResult:
    def test_dataclass_fields(self):
        r = vg.GateResult(
            gate="unit",
            status="pass",
            blocking=True,
            output="ok",
            duration_s=1.5,
        )
        assert r.gate == "unit"
        assert r.status == "pass"
        assert r.blocking is True
        assert r.output == "ok"
        assert r.duration_s == 1.5

    def test_json_serialization(self):
        r = vg.GateResult(
            gate="e2e-web",
            status="fail",
            blocking=True,
            output="error",
            duration_s=2.0,
        )
        d = asdict(r)
        s = json.dumps(d)
        parsed = json.loads(s)
        assert parsed["gate"] == "e2e-web"
        assert parsed["status"] == "fail"
        assert parsed["blocking"] is True


# ── TestRunGateUnit ──────────────────────────────────────────────────


class TestRunGateUnit:
    @patch.object(vg, "_run")
    def test_passes_when_pytest_succeeds(self, mock_run, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        mock_run.return_value = _mock_run(0, "3 passed\n", "")
        result = vg.run_gate_unit(tmp_path)
        assert result.status == "pass"
        assert result.gate == "unit"
        assert result.blocking is True

    @patch.object(vg, "_run")
    def test_fails_when_pytest_fails(self, mock_run, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        mock_run.return_value = _mock_run(1, "1 failed\n", "ERRORS")
        result = vg.run_gate_unit(tmp_path)
        assert result.status == "fail"
        assert result.blocking is True

    @patch.object(vg, "_run")
    def test_falls_back_to_npm_test(self, mock_run, tmp_path):
        _write_package_json(tmp_path, {"jest": "^29.0.0"})
        mock_run.return_value = _mock_run(0, "Tests: 5 passed\n", "")
        result = vg.run_gate_unit(tmp_path)
        assert result.status == "pass"
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["npm", "test"]

    def test_skips_when_no_framework(self, tmp_path):
        result = vg.run_gate_unit(tmp_path)
        assert result.status == "skip"


# ── TestRunGateIntegration ───────────────────────────────────────────


class TestRunGateIntegration:
    @patch.object(vg, "_run")
    def test_skips_when_no_integration_markers(self, mock_run, tmp_path):
        mock_run.return_value = _mock_run(1, "", "no tests ran")
        result = vg.run_gate_integration(tmp_path)
        assert result.status == "skip"

    @patch.object(vg, "_run")
    def test_runs_docker_compose_when_available(self, mock_run, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("")
        # First call: collect → found tests; second: docker up; third: pytest; fourth: docker down
        mock_run.side_effect = [
            _mock_run(0, "2 items\n", ""),  # collect
            _mock_run(0, "", ""),  # docker compose up
            _mock_run(0, "2 passed\n", ""),  # pytest
            _mock_run(0, "", ""),  # docker compose down
        ]
        result = vg.run_gate_integration(tmp_path)
        assert result.status == "pass"
        assert mock_run.call_count == 4

    @patch.object(vg, "_run")
    def test_runs_without_docker(self, mock_run, tmp_path):
        mock_run.side_effect = [
            _mock_run(0, "2 items\n", ""),  # collect
            _mock_run(0, "2 passed\n", ""),  # pytest
        ]
        result = vg.run_gate_integration(tmp_path)
        assert result.status == "pass"


# ── TestRunGateE2EWeb ────────────────────────────────────────────────


class TestRunGateE2EWeb:
    def test_skips_when_no_e2e_directory(self, tmp_path):
        result = vg.run_gate_e2e_web(tmp_path)
        assert result.status == "skip"

    @patch.object(vg, "_run")
    def test_skips_when_playwright_not_installed(self, mock_run, tmp_path):
        (tmp_path / "tests" / "e2e").mkdir(parents=True)
        mock_run.return_value = _mock_run(127, "", "npx: command not found")
        result = vg.run_gate_e2e_web(tmp_path)
        assert result.status == "skip"
        assert "Playwright not installed" in result.output

    @patch.object(vg, "_run")
    def test_runs_via_gate_server(self, mock_run, tmp_path):
        (tmp_path / "tests" / "e2e").mkdir(parents=True)
        mock_run.side_effect = [
            _mock_run(0, "Version 1.40\n", ""),  # playwright --version
            _mock_run(0, "5 passed\n", ""),  # playwright test (direct, no server)
        ]
        result = vg.run_gate_e2e_web(tmp_path, config={})
        assert result.status == "pass"

    @patch.object(vg, "_run_with_server")
    @patch.object(vg, "_run")
    def test_uses_server_when_config_provided(self, mock_run, mock_server, tmp_path):
        (tmp_path / "tests" / "e2e").mkdir(parents=True)
        mock_run.return_value = _mock_run(0, "Version 1.40\n", "")  # playwright check
        mock_server.return_value = _mock_run(0, "5 passed\n", "")
        config = {
            "server_start_cmd": "npm run dev",
            "server_health_url": "http://localhost:3000",
        }
        result = vg.run_gate_e2e_web(tmp_path, config=config)
        assert result.status == "pass"
        mock_server.assert_called_once()


# ── TestRunGateE2EMobile ─────────────────────────────────────────────


class TestCheckMobileDevice:
    @patch.object(vg, "_run")
    def test_returns_ios_when_simulator_booted(self, mock_run, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "darwin")
        mock_run.return_value = _mock_run(
            0, "-- iOS 17.0 --\n    iPhone 15 (XXXX) (Booted)\n", ""
        )
        platform, info = vg._check_mobile_device()
        assert platform == "ios"
        assert "Booted" in info

    @patch.object(vg, "_run")
    def test_returns_android_when_emulator_connected(self, mock_run, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "linux")
        mock_run.return_value = _mock_run(
            0, "List of devices attached\nemulator-5554\tdevice\n", ""
        )
        platform, info = vg._check_mobile_device()
        assert platform == "android"
        assert "emulator" in info

    @patch.object(vg, "_run")
    def test_returns_empty_when_no_device(self, mock_run, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "linux")
        mock_run.return_value = _mock_run(0, "List of devices attached\n\n", "")
        platform, info = vg._check_mobile_device()
        assert platform == ""
        assert info == ""


class TestBootMobileDevice:
    @patch("time.sleep")
    @patch.object(vg, "_run")
    def test_boots_ios_simulator(self, mock_run, mock_sleep, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "darwin")
        simctl_json = json.dumps(
            {
                "devices": {
                    "com.apple.CoreSimulator.SimRuntime.iOS-17-0": [
                        {
                            "name": "iPhone 15",
                            "udid": "AAAA-BBBB",
                            "isAvailable": True,
                            "state": "Shutdown",
                        }
                    ]
                }
            }
        )
        mock_run.side_effect = [
            _mock_run(0, simctl_json, ""),  # simctl list -j
            _mock_run(0, "", ""),  # simctl boot
        ]
        platform, info = vg._boot_mobile_device()
        assert platform == "ios"
        assert "AAAA-BBBB" in info

    @patch.object(vg, "_find_available_ios_simulator", return_value="")
    @patch("time.sleep")
    @patch.object(vg, "_run")
    @patch("shutil.which", return_value="/usr/local/bin/emulator")
    def test_boots_android_emulator(self, mock_which, mock_run, mock_sleep, mock_ios, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "linux")
        mock_run.side_effect = [
            _mock_run(0, "Pixel_6_API_33\n", ""),  # emulator -list-avds
        ]
        with patch("subprocess.Popen"):
            mock_run.side_effect = [
                _mock_run(0, "Pixel_6_API_33\n", ""),  # emulator -list-avds (via _find)
                _mock_run(0, "", ""),  # adb wait-for-device
                _mock_run(0, "1", ""),  # getprop sys.boot_completed
            ]
            platform, info = vg._boot_mobile_device()
        assert platform == "android"
        assert "Pixel_6_API_33" in info

    @patch.object(vg, "_find_available_android_avd", return_value="")
    @patch.object(vg, "_find_available_ios_simulator", return_value="")
    def test_returns_empty_when_nothing_available(self, mock_ios, mock_android, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "linux")
        platform, info = vg._boot_mobile_device()
        assert platform == ""
        assert info == ""

    @patch.object(vg, "_run")
    def test_find_ios_prefers_iphone(self, mock_run, monkeypatch):
        monkeypatch.setattr(vg.sys, "platform", "darwin")
        simctl_json = json.dumps(
            {
                "devices": {
                    "com.apple.CoreSimulator.SimRuntime.iOS-17-0": [
                        {
                            "name": "iPad Air",
                            "udid": "IPAD-1",
                            "isAvailable": True,
                            "state": "Shutdown",
                        },
                        {
                            "name": "iPhone 15 Pro",
                            "udid": "IPHONE-1",
                            "isAvailable": True,
                            "state": "Shutdown",
                        },
                    ]
                }
            }
        )
        mock_run.return_value = _mock_run(0, simctl_json, "")
        udid = vg._find_available_ios_simulator()
        assert udid == "IPHONE-1"

    @patch.object(vg, "_run")
    def test_find_android_avd(self, mock_run):
        mock_run.return_value = _mock_run(0, "Pixel_6_API_33\nPixel_4\n", "")
        with patch("shutil.which", return_value="/usr/local/bin/emulator"):
            avd = vg._find_available_android_avd()
        assert avd == "Pixel_6_API_33"


class TestRunGateE2EMobile:
    def test_skips_when_no_test_files(self, tmp_path):
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "skip"
        assert "No mobile test files found" in result.output

    @patch("shutil.which", return_value=None)
    def test_skips_when_maestro_not_installed(self, mock_which, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "skip"
        assert "Maestro CLI not installed" in result.output

    def test_detects_maestro_by_yaml_files(self, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        framework = vg._detect_mobile_framework(tmp_path)
        assert framework == "maestro"

    def test_detects_detox_by_test_ts_files(self, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.test.ts").write_text("describe('Login', () => {})")
        framework = vg._detect_mobile_framework(tmp_path)
        assert framework == "detox"

    def test_explicit_framework_from_config(self, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        # Even though yaml exists (would be maestro), explicit config wins
        framework = vg._detect_mobile_framework(
            tmp_path, config={"mobile_test_framework": "detox"}
        )
        assert framework == "detox"

    @patch.object(vg, "_boot_mobile_device", return_value=("", ""))
    @patch.object(vg, "_check_mobile_device", return_value=("", ""))
    @patch("shutil.which", return_value="/usr/local/bin/maestro")
    def test_skips_when_no_simulator_and_autoboot_fails(
        self, mock_which, mock_device, mock_boot, tmp_path
    ):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "skip"
        assert "auto-boot failed" in result.output
        mock_boot.assert_called_once()

    @patch.object(vg, "_run")
    @patch.object(vg, "_boot_mobile_device", return_value=("ios", "Auto-booted simulator ABC"))
    @patch.object(vg, "_check_mobile_device", return_value=("", ""))
    @patch("shutil.which", return_value="/usr/local/bin/maestro")
    def test_autoboots_simulator_and_runs(
        self, mock_which, mock_device, mock_boot, mock_run, tmp_path
    ):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        mock_run.return_value = _mock_run(0, "Tests passed\n", "")
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "pass"
        mock_boot.assert_called_once()

    @patch.object(vg, "_run")
    @patch.object(vg, "_check_mobile_device", return_value=("ios", "iPhone 15 (Booted)"))
    @patch("shutil.which", return_value="/usr/local/bin/maestro")
    def test_runs_build_cmd_when_configured(self, mock_which, mock_device, mock_run, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        config = {"mobile_build_cmd": "xcodebuild -workspace App.xcworkspace"}
        # build succeeds, then maestro test succeeds
        mock_run.side_effect = [
            _mock_run(0, "Build succeeded\n", ""),  # build
            _mock_run(0, "Tests passed\n", ""),  # maestro test
        ]
        result = vg.run_gate_e2e_mobile(tmp_path, config=config)
        assert result.status == "pass"
        assert mock_run.call_count == 2

    @patch.object(vg, "_run")
    @patch.object(vg, "_check_mobile_device", return_value=("ios", "iPhone 15 (Booted)"))
    @patch("shutil.which", return_value="/usr/local/bin/maestro")
    def test_maestro_passes(self, mock_which, mock_device, mock_run, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.yaml").write_text("- tapOn: 'Login'")
        mock_run.return_value = _mock_run(0, "Tests passed\n", "")
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "pass"
        assert result.gate == "e2e-mobile"

    @patch.object(vg, "_run")
    @patch.object(vg, "_check_mobile_device", return_value=("ios", "iPhone 15 (Booted)"))
    def test_detox_passes(self, mock_device, mock_run, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.test.ts").write_text("describe('Login', () => {})")
        mock_run.side_effect = [
            _mock_run(0, "0.73.0\n", ""),  # npx detox --version
            _mock_run(0, "Tests passed\n", ""),  # npx detox test
        ]
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "pass"

    @patch.object(vg, "_run")
    @patch.object(vg, "_check_mobile_device", return_value=("ios", "iPhone 15 (Booted)"))
    def test_detox_uses_config_name(self, mock_device, mock_run, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.test.ts").write_text("describe('Login', () => {})")
        mock_run.side_effect = [
            _mock_run(0, "0.73.0\n", ""),  # npx detox --version
            _mock_run(0, "Tests passed\n", ""),  # npx detox test
        ]
        config = {"mobile_detox_config": "android.emu.release"}
        result = vg.run_gate_e2e_mobile(tmp_path, config=config)
        assert result.status == "pass"
        # Verify the config name was passed to detox
        detox_call = mock_run.call_args_list[1]
        assert "android.emu.release" in detox_call[0][0]

    @patch.object(vg, "_run")
    def test_skips_when_detox_not_installed(self, mock_run, tmp_path):
        e2e = tmp_path / "e2e"
        e2e.mkdir()
        (e2e / "login.test.ts").write_text("describe('Login', () => {})")
        mock_run.return_value = _mock_run(127, "", "npx: command not found")
        result = vg.run_gate_e2e_mobile(tmp_path)
        assert result.status == "skip"
        assert "Detox not installed" in result.output


# ── TestRunGateAPI ───────────────────────────────────────────────────


class TestRunGateAPI:
    @patch.object(vg, "_run")
    def test_skips_when_no_openapi_spec(self, mock_run, tmp_path):
        mock_run.return_value = _mock_run(0, "no tests collected\n", "")
        # Simulate no tests output
        mock_run.return_value.stdout = "no tests collected"
        result = vg.run_gate_api(tmp_path)
        assert result.status == "skip"

    @patch("shutil.which", return_value="/usr/local/bin/schemathesis")
    @patch.object(vg, "_run")
    def test_runs_schemathesis(self, mock_run, mock_which, tmp_path):
        (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0")
        mock_run.side_effect = [
            _mock_run(0, "no tests", ""),  # pytest collect (has "no tests")
            _mock_run(0, "All checks passed\n", ""),  # schemathesis
        ]
        result = vg.run_gate_api(tmp_path)
        assert result.status == "pass"

    @patch("shutil.which", return_value=None)
    @patch.object(vg, "_run")
    def test_falls_back_to_pytest_m_api(self, mock_run, mock_which, tmp_path):
        # No openapi, but pytest -m api finds tests
        mock_run.side_effect = [
            _mock_run(0, "2 items\n", ""),  # collect → has tests
            _mock_run(0, "2 passed\n", ""),  # pytest -m api
        ]
        result = vg.run_gate_api(tmp_path)
        assert result.status == "pass"


# ── TestRunGateLoad ──────────────────────────────────────────────────


class TestRunGateLoad:
    @patch("shutil.which", return_value=None)
    def test_always_non_blocking(self, mock_which, tmp_path):
        result = vg.run_gate_load(tmp_path)
        assert result.blocking is False

    @patch("shutil.which", return_value=None)
    def test_skips_when_no_tool_installed(self, mock_which, tmp_path):
        result = vg.run_gate_load(tmp_path)
        assert result.status == "skip"
        assert result.blocking is False


# ── TestRunApplicableGates ───────────────────────────────────────────


class TestRunApplicableGates:
    @patch.object(vg, "read_gate_config")
    @patch.object(vg, "detect_platforms")
    @patch.object(vg, "run_gate_unit")
    @patch.object(vg, "run_gate_load")
    def test_returns_all_results(
        self, mock_load, mock_unit, mock_detect, mock_config, tmp_path
    ):
        mock_detect.return_value = {"unit"}
        mock_config.return_value = {"gate_overrides": {}}
        mock_unit.return_value = vg.GateResult("unit", "pass", True, "ok", 1.0)
        mock_load.return_value = vg.GateResult("load", "skip", False, "no tool", 0.0)
        results = vg.run_applicable_gates(tmp_path)
        assert len(results) == 2
        assert results[0].gate == "unit"
        assert results[1].gate == "load"

    @patch.object(vg, "read_gate_config")
    @patch.object(vg, "detect_platforms")
    def test_skips_disabled_gates(self, mock_detect, mock_config, tmp_path):
        mock_detect.return_value = {"unit"}
        mock_config.return_value = {
            "gate_overrides": {"unit": {"enabled": False, "blocking": True}}
        }
        results = vg.run_applicable_gates(tmp_path)
        unit_result = [r for r in results if r.gate == "unit"][0]
        assert unit_result.status == "skip"
        assert "Disabled" in unit_result.output

    @patch.object(vg, "read_gate_config")
    @patch.object(vg, "run_gate_unit")
    @patch.object(vg, "run_gate_load")
    def test_blocking_failure_sets_exit_1(self, mock_load, mock_unit, mock_config, tmp_path):
        mock_config.return_value = {"gate_overrides": {}}
        mock_unit.return_value = vg.GateResult("unit", "fail", True, "error", 1.0)
        mock_load.return_value = vg.GateResult("load", "skip", False, "", 0.0)
        results = vg.run_applicable_gates(tmp_path, gates_override=["unit", "load"])
        has_blocking_fail = any(r.status == "fail" and r.blocking for r in results)
        assert has_blocking_fail is True

    @patch.object(vg, "read_gate_config")
    @patch.object(vg, "run_gate_load")
    def test_non_blocking_failure_still_exit_0(self, mock_load, mock_config, tmp_path):
        mock_config.return_value = {"gate_overrides": {}}
        mock_load.return_value = vg.GateResult("load", "warn", False, "slow", 10.0)
        results = vg.run_applicable_gates(tmp_path, gates_override=["load"])
        has_blocking_fail = any(r.status == "fail" and r.blocking for r in results)
        assert has_blocking_fail is False


# ── TestMain ─────────────────────────────────────────────────────────


class TestMain:
    @patch.object(vg, "run_applicable_gates")
    def test_json_output_flag(self, mock_gates, tmp_path):
        mock_gates.return_value = [
            vg.GateResult("unit", "pass", True, "ok", 1.0),
        ]
        result = vg.main(["--project-path", str(tmp_path), "--json"])
        assert result == 0

    @patch.object(vg, "run_applicable_gates")
    def test_gates_override_flag(self, mock_gates, tmp_path):
        mock_gates.return_value = [
            vg.GateResult("unit", "pass", True, "ok", 1.0),
        ]
        vg.main(["--project-path", str(tmp_path), "--gates", "unit,e2e-web"])
        call_kwargs = mock_gates.call_args[1]
        assert call_kwargs["gates_override"] == ["unit", "e2e-web"]

    @patch.object(vg, "run_applicable_gates")
    def test_exit_code_0_on_pass(self, mock_gates, tmp_path):
        mock_gates.return_value = [
            vg.GateResult("unit", "pass", True, "ok", 1.0),
        ]
        assert vg.main(["--project-path", str(tmp_path)]) == 0

    @patch.object(vg, "run_applicable_gates")
    def test_exit_code_1_on_blocking_failure(self, mock_gates, tmp_path):
        mock_gates.return_value = [
            vg.GateResult("unit", "fail", True, "error", 1.0),
        ]
        assert vg.main(["--project-path", str(tmp_path)]) == 1

    def test_exit_code_2_on_bad_path(self):
        assert vg.main(["--project-path", "/nonexistent/path/xyz"]) == 2
