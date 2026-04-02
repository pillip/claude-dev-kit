#!/usr/bin/env python3
"""Verify Gates — run applicable test gates for a project.

Detects project platforms and runs the appropriate test gates (unit, integration,
e2e-web, e2e-mobile, api, load). Each gate reports pass/fail/skip/warn status.

Exit codes:
  0 — all blocking gates passed (or skipped)
  1 — at least one blocking gate failed
  2 — usage error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


# ── data types ───────────────────────────────────────────────────────


@dataclass
class GateResult:
    """Result of a single gate execution."""

    gate: str  # "unit" | "integration" | "e2e-web" | "e2e-mobile" | "api" | "load"
    status: str  # "pass" | "fail" | "skip" | "warn"
    blocking: bool  # True → failure = overall failure
    output: str  # last 2000 chars of test output
    duration_s: float  # execution time in seconds


# ── subprocess helpers (same pattern as verify_checkpoint.py) ────────


def _run(cmd: list[str], timeout: int = 120, **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result (no exception on failure)."""
    try:
        t = timeout if timeout > 0 else None
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t, **kwargs)
    except subprocess.TimeoutExpired:
        prog = cmd[0] if cmd else "<unknown>"
        mock = subprocess.CompletedProcess(cmd, 124)
        mock.stdout = ""
        mock.stderr = f"{prog}: timed out after {timeout}s"
        return mock
    except FileNotFoundError:
        prog = cmd[0] if cmd else "<unknown>"
        mock = subprocess.CompletedProcess(cmd, 127)
        mock.stdout = ""
        mock.stderr = f"{prog}: command not found"
        return mock


def _tail(text: str, max_chars: int = 2000) -> str:
    """Return the last max_chars characters of text."""
    return text[-max_chars:] if len(text) > max_chars else text


# ── platform detection ───────────────────────────────────────────────


def _read_file_safe(path: Path) -> str:
    """Read file contents or return empty string."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""


def detect_platforms(project_path: Path) -> set[str]:
    """Detect which platforms a project targets.

    Returns a set of platform strings: "unit", "web", "mobile", "api".
    "unit" is always included if any test files exist.
    """
    platforms: set[str] = set()
    pp = project_path

    # 1. Check docs/test_plan.md for explicit declaration
    test_plan = pp / "docs" / "test_plan.md"
    if test_plan.exists():
        content = _read_file_safe(test_plan)
        match = re.search(r"Detected platform:\s*(.+)", content)
        if match:
            declared = match.group(1).strip().lower()
            for token in re.split(r"[,\s|+]+", declared):
                token = token.strip()
                if token in ("web", "mobile", "api", "api-only"):
                    platforms.add("api" if token == "api-only" else token)

    # 2. File-pattern heuristics (supplement, don't replace explicit)
    pkg_json = pp / "package.json"
    pkg_content = _read_file_safe(pkg_json) if pkg_json.exists() else ""

    # Web detection
    web_frameworks = ["react", "vue", "svelte", "next", "angular", "nuxt"]
    if any(f'"{fw}"' in pkg_content for fw in web_frameworks):
        platforms.add("web")
    if list(pp.glob("playwright.config.*")):
        platforms.add("web")

    # Mobile detection
    if (pp / "app.json").exists():
        platforms.add("mobile")
    if "react-native" in pkg_content:
        platforms.add("mobile")
    if (pp / "android").is_dir() or (pp / "ios").is_dir():
        platforms.add("mobile")

    # API detection
    if (pp / "openapi.yaml").exists() or (pp / "openapi.json").exists():
        platforms.add("api")
    pyproject = pp / "pyproject.toml"
    pyproject_content = _read_file_safe(pyproject) if pyproject.exists() else ""
    api_frameworks_py = ["fastapi", "flask", "django"]
    if any(fw in pyproject_content.lower() for fw in api_frameworks_py):
        platforms.add("api")
    api_frameworks_js = ["express", "fastify", "koa", "hapi"]
    if any(f'"{fw}"' in pkg_content for fw in api_frameworks_js):
        platforms.add("api")

    # Unit: always included if test files exist
    has_tests_dir = (pp / "tests").is_dir()
    has_test_files = bool(list(pp.glob("test_*.py")) or list(pp.glob("**/test_*.py")))
    has_js_tests = bool(
        list(pp.glob("**/*.test.ts"))
        or list(pp.glob("**/*.test.js"))
        or list(pp.glob("**/*.spec.ts"))
        or list(pp.glob("**/*.spec.js"))
    )
    if has_tests_dir or has_test_files or has_js_tests:
        platforms.add("unit")

    return platforms


# ── gate config reading ──────────────────────────────────────────────


DEFAULT_GATE_CONFIG = {
    "server_start_cmd": "",
    "server_health_url": "",
    "server_timeout": 30,
    "gate_overrides": {},
    "mobile_test_framework": "",
    "mobile_build_cmd": "",
    "mobile_detox_config": "ios.sim.debug",
}

DEFAULT_BLOCKING = {
    "unit": True,
    "integration": True,
    "e2e-web": True,
    "e2e-mobile": True,
    "api": True,
    "load": False,
}


def read_gate_config(project_path: Path) -> dict:
    """Read gate configuration from docs/test_plan.md.

    Looks for a '## Verify Gates Configuration' section and parses:
    - Server start command
    - Server health URL
    - Server startup timeout
    - Gate Overrides table
    """
    test_plan = project_path / "docs" / "test_plan.md"
    if not test_plan.exists():
        return dict(DEFAULT_GATE_CONFIG)

    content = _read_file_safe(test_plan)
    if "## Verify Gates Configuration" not in content:
        return dict(DEFAULT_GATE_CONFIG)

    # Extract section
    section_match = re.search(
        r"## Verify Gates Configuration\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if not section_match:
        return dict(DEFAULT_GATE_CONFIG)
    section = section_match.group(1)

    config = dict(DEFAULT_GATE_CONFIG)

    # Parse fields
    cmd_match = re.search(r"Server start command:\s*(?:`([^`]+)`|(\S.+))", section)
    if cmd_match:
        config["server_start_cmd"] = (cmd_match.group(1) or cmd_match.group(2) or "").strip()

    url_match = re.search(r"Server health URL:\s*(?:`([^`]+)`|(\S.+))", section)
    if url_match:
        config["server_health_url"] = (url_match.group(1) or url_match.group(2) or "").strip()

    timeout_match = re.search(r"Server startup timeout:\s*(\d+)", section)
    if timeout_match:
        config["server_timeout"] = int(timeout_match.group(1))

    # Parse mobile fields
    mobile_fw_match = re.search(r"Mobile test framework:\s*(?:`([^`]+)`|(\S+))", section)
    if mobile_fw_match:
        config["mobile_test_framework"] = (
            mobile_fw_match.group(1) or mobile_fw_match.group(2) or ""
        ).strip().lower()

    mobile_build_match = re.search(r"Mobile build command:\s*(?:`([^`]+)`|(\S.+))", section)
    if mobile_build_match:
        config["mobile_build_cmd"] = (
            mobile_build_match.group(1) or mobile_build_match.group(2) or ""
        ).strip()

    detox_cfg_match = re.search(r"Mobile Detox config:\s*(?:`([^`]+)`|(\S+))", section)
    if detox_cfg_match:
        config["mobile_detox_config"] = (
            detox_cfg_match.group(1) or detox_cfg_match.group(2) or ""
        ).strip()

    # Parse Gate Overrides table
    overrides: dict[str, dict] = {}
    table_lines = re.findall(r"^\|(.+)\|$", section, re.MULTILINE)
    for line in table_lines:
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 3 and cols[0].lower() not in ("gate", "---", "----", ""):
            # Skip separator rows
            if cols[0].startswith("-"):
                continue
            gate_name = cols[0].lower().strip()
            enabled_raw = cols[1].lower().strip() if len(cols) > 1 else "yes"
            blocking_raw = cols[2].lower().strip() if len(cols) > 2 else "yes"
            overrides[gate_name] = {
                "enabled": enabled_raw in ("yes", "true", "1"),
                "blocking": blocking_raw in ("yes", "true", "1"),
            }
    config["gate_overrides"] = overrides

    return config


# ── gate server helper ───────────────────────────────────────────────


def _gate_server_path() -> Path:
    """Path to gate_server.sh."""
    return Path(__file__).resolve().parent / "gate_server.sh"


def _run_with_server(
    project_path: Path,
    config: dict,
    test_cmd: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run a test command with server lifecycle managed by gate_server.sh."""
    server_sh = _gate_server_path()
    if not server_sh.exists():
        mock = subprocess.CompletedProcess([], 127)
        mock.stdout = ""
        mock.stderr = "gate_server.sh not found"
        return mock

    cmd = [
        "bash",
        str(server_sh),
        "--start-cmd",
        config.get("server_start_cmd", ""),
        "--health-url",
        config.get("server_health_url", ""),
        "--test-cmd",
        test_cmd,
        "--timeout",
        str(config.get("server_timeout", 30)),
        "--cwd",
        str(project_path),
    ]
    return _run(cmd, timeout=timeout)


# ── individual gate runners ──────────────────────────────────────────


def run_gate_unit(project_path: Path, **_kwargs) -> GateResult:
    """Run unit tests (pytest or npm test)."""
    start = time.monotonic()
    pp = project_path

    # Decide: pytest or npm test
    pkg_json = pp / "package.json"
    if (pp / "pyproject.toml").exists() or (pp / "tests").is_dir() or list(pp.glob("test_*.py")):
        result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], timeout=120, cwd=str(pp))
    elif pkg_json.exists():
        result = _run(["npm", "test"], timeout=120, cwd=str(pp))
    else:
        return GateResult(
            gate="unit",
            status="skip",
            blocking=True,
            output="No test framework detected",
            duration_s=time.monotonic() - start,
        )

    output = _tail(result.stdout + "\n" + result.stderr)
    status = "pass" if result.returncode == 0 else "fail"
    return GateResult(
        gate="unit",
        status=status,
        blocking=True,
        output=output,
        duration_s=time.monotonic() - start,
    )


def run_gate_integration(project_path: Path, **_kwargs) -> GateResult:
    """Run integration tests (pytest -m integration, optionally with docker-compose)."""
    start = time.monotonic()
    pp = project_path

    # Check if there are integration-marked tests
    collect = _run(
        ["python3", "-m", "pytest", "--collect-only", "-q", "-m", "integration"],
        timeout=30,
        cwd=str(pp),
    )
    if collect.returncode != 0 and "no tests ran" in (collect.stdout + collect.stderr).lower():
        return GateResult(
            gate="integration",
            status="skip",
            blocking=True,
            output="No integration tests found",
            duration_s=time.monotonic() - start,
        )

    has_compose = (pp / "docker-compose.yml").exists() or (pp / "docker-compose.yaml").exists()

    if has_compose:
        # Start services
        _run(["docker", "compose", "up", "-d"], timeout=60, cwd=str(pp))
        result = _run(
            ["python3", "-m", "pytest", "-q", "--tb=short", "-m", "integration"],
            timeout=120,
            cwd=str(pp),
        )
        _run(["docker", "compose", "down"], timeout=30, cwd=str(pp))
    else:
        result = _run(
            ["python3", "-m", "pytest", "-q", "--tb=short", "-m", "integration"],
            timeout=120,
            cwd=str(pp),
        )

    output = _tail(result.stdout + "\n" + result.stderr)
    status = "pass" if result.returncode == 0 else "fail"
    return GateResult(
        gate="integration",
        status=status,
        blocking=True,
        output=output,
        duration_s=time.monotonic() - start,
    )


def run_gate_e2e_web(project_path: Path, config: dict | None = None, **_kwargs) -> GateResult:
    """Run web E2E tests via Playwright."""
    start = time.monotonic()
    pp = project_path
    config = config or {}

    # Check for e2e directory
    e2e_dir = pp / "tests" / "e2e"
    if not e2e_dir.is_dir():
        return GateResult(
            gate="e2e-web",
            status="skip",
            blocking=True,
            output="No tests/e2e/ directory found",
            duration_s=time.monotonic() - start,
        )

    # Check Playwright is installed
    pw_check = _run(["npx", "playwright", "--version"], timeout=15, cwd=str(pp))
    if pw_check.returncode != 0:
        return GateResult(
            gate="e2e-web",
            status="skip",
            blocking=True,
            output="Playwright not installed. Run: npx playwright install",
            duration_s=time.monotonic() - start,
        )

    # Run with server if config provides start cmd
    if config.get("server_start_cmd") and config.get("server_health_url"):
        result = _run_with_server(pp, config, "npx playwright test", timeout=180)
    else:
        result = _run(["npx", "playwright", "test"], timeout=180, cwd=str(pp))

    output = _tail(result.stdout + "\n" + result.stderr)
    status = "pass" if result.returncode == 0 else "fail"
    return GateResult(
        gate="e2e-web",
        status=status,
        blocking=True,
        output=output,
        duration_s=time.monotonic() - start,
    )


def _check_mobile_device() -> tuple[str, str]:
    """Check for running simulator/emulator.

    Returns (platform, device_info) or ("", "") if none found.
    platform: "ios" | "android" | ""
    """
    # Check iOS simulator (macOS only)
    if sys.platform == "darwin":
        result = _run(["xcrun", "simctl", "list", "devices", "booted"], timeout=10)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and "Booted" in line:
                    return ("ios", line)

    # Check Android emulator
    result = _run(["adb", "devices"], timeout=10)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("List") and "device" in line:
                return ("android", line)

    return ("", "")


def _find_available_ios_simulator() -> str:
    """Find an available (Shutdown) iOS simulator UDID.

    Prefers iPhone simulators with the highest runtime version.
    Returns UDID string or "" if none found.
    """
    if sys.platform != "darwin":
        return ""
    result = _run(["xcrun", "simctl", "list", "devices", "available", "-j"], timeout=10)
    if result.returncode != 0:
        return ""
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return ""

    # Collect all available, shutdown devices — prefer iPhones
    candidates: list[tuple[str, str, str]] = []  # (runtime, name, udid)
    for runtime, devices in data.get("devices", {}).items():
        for dev in devices:
            if dev.get("isAvailable") and dev.get("state") == "Shutdown":
                candidates.append((runtime, dev.get("name", ""), dev.get("udid", "")))

    if not candidates:
        return ""

    # Sort: prefer iPhone, then highest runtime (lexicographic works for version strings)
    iphones = [c for c in candidates if "iPhone" in c[1]]
    pool = iphones if iphones else candidates
    pool.sort(key=lambda c: c[0], reverse=True)
    return pool[0][2]


def _find_available_android_avd() -> str:
    """Find an available Android AVD name.

    Returns AVD name or "" if none found.
    """
    if not shutil.which("emulator"):
        return ""
    result = _run(["emulator", "-list-avds"], timeout=10)
    if result.returncode != 0:
        return ""
    avds = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return avds[0] if avds else ""


def _boot_mobile_device() -> tuple[str, str]:
    """Attempt to boot a simulator/emulator automatically.

    Tries iOS first (macOS), then Android.
    Returns (platform, device_info) or ("", "") if boot failed.
    """
    # Try iOS simulator
    udid = _find_available_ios_simulator()
    if udid:
        boot = _run(["xcrun", "simctl", "boot", udid], timeout=30)
        if boot.returncode == 0:
            # Wait briefly for simulator to become ready
            time.sleep(3)
            return ("ios", f"Auto-booted simulator {udid}")

    # Try Android emulator
    avd = _find_available_android_avd()
    if avd:
        # Launch emulator in background (-no-window for CI, -no-audio to avoid issues)
        try:
            subprocess.Popen(
                ["emulator", "-avd", avd, "-no-audio", "-no-window"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return ("", "")
        # Wait for device to come online
        wait = _run(["adb", "wait-for-device"], timeout=60)
        if wait.returncode == 0:
            # Extra wait for boot animation to finish
            _run(
                ["adb", "shell", "getprop", "sys.boot_completed"],
                timeout=60,
            )
            time.sleep(5)
            return ("android", f"Auto-booted AVD {avd}")

    return ("", "")


def _detect_mobile_framework(
    project_path: Path, config: dict | None = None
) -> str:
    """Detect mobile test framework: 'maestro', 'detox', or ''.

    Priority:
    1. Explicit config from test_plan.md (mobile_test_framework)
    2. e2e/*.yaml or e2e/*.yml → maestro
    3. e2e/*.test.ts or e2e/*.test.js → detox
    4. '' if nothing found
    """
    config = config or {}
    explicit = config.get("mobile_test_framework", "")
    if explicit in ("maestro", "detox"):
        return explicit

    e2e_dir = project_path / "e2e"
    if not e2e_dir.is_dir():
        return ""

    has_yaml = bool(list(e2e_dir.glob("*.yaml")) + list(e2e_dir.glob("*.yml")))
    if has_yaml:
        return "maestro"

    has_test_ts = bool(list(e2e_dir.glob("*.test.ts")) + list(e2e_dir.glob("*.test.js")))
    if has_test_ts:
        return "detox"

    return ""


def run_gate_e2e_mobile(
    project_path: Path, config: dict | None = None, **_kwargs
) -> GateResult:
    """Run mobile E2E tests via Maestro or Detox."""
    start = time.monotonic()
    pp = project_path
    config = config or {}

    # 1. Detect framework
    framework = _detect_mobile_framework(pp, config)
    if not framework:
        return GateResult(
            gate="e2e-mobile",
            status="skip",
            blocking=True,
            output="No mobile test files found (e2e/*.yaml for Maestro or e2e/*.test.ts for Detox)",
            duration_s=time.monotonic() - start,
        )

    # 2. Check CLI availability
    if framework == "maestro":
        if not shutil.which("maestro"):
            return GateResult(
                gate="e2e-mobile",
                status="skip",
                blocking=True,
                output="Maestro CLI not installed. Install: https://maestro.mobile.dev",
                duration_s=time.monotonic() - start,
            )
    elif framework == "detox":
        detox_check = _run(["npx", "detox", "--version"], timeout=15, cwd=str(pp))
        if detox_check.returncode != 0:
            return GateResult(
                gate="e2e-mobile",
                status="skip",
                blocking=True,
                output="Detox not installed. Run: npm install detox --save-dev",
                duration_s=time.monotonic() - start,
            )

    # 3. Check for running simulator/emulator — auto-boot if none found
    platform, device_info = _check_mobile_device()
    if not platform:
        platform, device_info = _boot_mobile_device()
        if not platform:
            return GateResult(
                gate="e2e-mobile",
                status="skip",
                blocking=True,
                output="No booted simulator/emulator found and auto-boot failed. "
                "Install a simulator (Xcode) or emulator (Android SDK) first.",
                duration_s=time.monotonic() - start,
            )

    # 4. Run build command if configured
    build_cmd = config.get("mobile_build_cmd", "")
    if build_cmd:
        build_result = _run(build_cmd.split(), timeout=300, cwd=str(pp))
        if build_result.returncode != 0:
            output = _tail(build_result.stdout + "\n" + build_result.stderr)
            return GateResult(
                gate="e2e-mobile",
                status="fail",
                blocking=True,
                output=f"Build failed: {output}",
                duration_s=time.monotonic() - start,
            )

    # 5. Run tests
    if framework == "maestro":
        result = _run(["maestro", "test", "e2e/"], timeout=300, cwd=str(pp))
    else:
        detox_config = config.get("mobile_detox_config", "ios.sim.debug")
        result = _run(
            ["npx", "detox", "test", "-c", detox_config, "--cleanup"],
            timeout=300,
            cwd=str(pp),
        )

    output = _tail(result.stdout + "\n" + result.stderr)
    status = "pass" if result.returncode == 0 else "fail"
    return GateResult(
        gate="e2e-mobile",
        status=status,
        blocking=True,
        output=output,
        duration_s=time.monotonic() - start,
    )


def run_gate_api(project_path: Path, config: dict | None = None, **_kwargs) -> GateResult:
    """Run API contract tests (schemathesis or pytest -m api)."""
    start = time.monotonic()
    pp = project_path
    config = config or {}

    has_openapi = (pp / "openapi.yaml").exists() or (pp / "openapi.json").exists()

    # Check for pytest -m api tests
    collect = _run(
        ["python3", "-m", "pytest", "--collect-only", "-q", "-m", "api"],
        timeout=30,
        cwd=str(pp),
    )
    has_api_tests = collect.returncode == 0 and "no tests" not in collect.stdout.lower()

    if not has_openapi and not has_api_tests:
        return GateResult(
            gate="api",
            status="skip",
            blocking=True,
            output="No OpenAPI spec and no pytest -m api tests found",
            duration_s=time.monotonic() - start,
        )

    # Prefer schemathesis if openapi spec exists and tool is available
    if has_openapi and shutil.which("schemathesis"):
        spec_file = "openapi.yaml" if (pp / "openapi.yaml").exists() else "openapi.json"
        if config.get("server_start_cmd") and config.get("server_health_url"):
            test_cmd = f"schemathesis run {spec_file} --base-url {config['server_health_url']}"
            result = _run_with_server(pp, config, test_cmd, timeout=180)
        else:
            result = _run(
                ["schemathesis", "run", str(pp / spec_file)],
                timeout=120,
                cwd=str(pp),
            )
    else:
        # Fall back to pytest -m api
        if config.get("server_start_cmd") and config.get("server_health_url"):
            result = _run_with_server(
                pp, config, "python3 -m pytest -q --tb=short -m api", timeout=120
            )
        else:
            result = _run(
                ["python3", "-m", "pytest", "-q", "--tb=short", "-m", "api"],
                timeout=120,
                cwd=str(pp),
            )

    output = _tail(result.stdout + "\n" + result.stderr)
    status = "pass" if result.returncode == 0 else "fail"
    return GateResult(
        gate="api",
        status=status,
        blocking=True,
        output=output,
        duration_s=time.monotonic() - start,
    )


def run_gate_load(project_path: Path, config: dict | None = None, **_kwargs) -> GateResult:
    """Run load/performance smoke test (always non-blocking)."""
    start = time.monotonic()
    pp = project_path
    config = config or {}

    has_k6 = shutil.which("k6")
    has_locust = shutil.which("locust")

    if not has_k6 and not has_locust:
        return GateResult(
            gate="load",
            status="skip",
            blocking=False,
            output="Neither k6 nor locust installed",
            duration_s=time.monotonic() - start,
        )

    if has_k6 and list(pp.glob("**/*.k6.js")):
        k6_script = list(pp.glob("**/*.k6.js"))[0]
        result = _run(
            ["k6", "run", "--duration", "10s", "--vus", "5", str(k6_script)],
            timeout=30,
            cwd=str(pp),
        )
    elif has_locust and (pp / "locustfile.py").exists():
        result = _run(
            ["locust", "--headless", "-u", "5", "-r", "5", "-t", "10s", "-f", "locustfile.py"],
            timeout=30,
            cwd=str(pp),
        )
    else:
        return GateResult(
            gate="load",
            status="skip",
            blocking=False,
            output="No load test scripts found (*.k6.js or locustfile.py)",
            duration_s=time.monotonic() - start,
        )

    output = _tail(result.stdout + "\n" + result.stderr)
    status = "pass" if result.returncode == 0 else "warn"
    return GateResult(
        gate="load",
        status=status,
        blocking=False,
        output=output,
        duration_s=time.monotonic() - start,
    )


# ── gate registry ────────────────────────────────────────────────────


GATE_REGISTRY: dict[str, str] = {
    "unit": "run_gate_unit",
    "integration": "run_gate_integration",
    "e2e-web": "run_gate_e2e_web",
    "e2e-mobile": "run_gate_e2e_mobile",
    "api": "run_gate_api",
    "load": "run_gate_load",
}


def _get_gate_runner(gate_name: str):
    """Look up gate runner function by name (allows mocking)."""
    import verify_gates as _self
    return getattr(_self, GATE_REGISTRY[gate_name])

# Maps platforms to their applicable gates
PLATFORM_GATES: dict[str, list[str]] = {
    "unit": ["unit"],
    "web": ["e2e-web"],
    "mobile": ["e2e-mobile"],
    "api": ["integration", "api"],
}


# ── orchestrator ─────────────────────────────────────────────────────


def run_applicable_gates(
    project_path: Path, gates_override: list[str] | None = None
) -> list[GateResult]:
    """Run all applicable gates for a project.

    1. Detect platforms to determine which gates apply
    2. Read gate config for overrides
    3. Run each gate sequentially
    4. Return list of GateResults
    """
    pp = Path(project_path)
    config = read_gate_config(pp)
    overrides = config.get("gate_overrides", {})

    if gates_override is not None:
        # Explicit gate list from CLI
        gate_names = [g.strip() for g in gates_override if g.strip() in GATE_REGISTRY]
    else:
        # Auto-detect
        platforms = detect_platforms(pp)
        gate_names_set: set[str] = set()
        for platform in platforms:
            for gate in PLATFORM_GATES.get(platform, []):
                gate_names_set.add(gate)
        # Always try load gate
        gate_names_set.add("load")
        # Deterministic order
        gate_order = ["unit", "integration", "e2e-web", "e2e-mobile", "api", "load"]
        gate_names = [g for g in gate_order if g in gate_names_set]

    results: list[GateResult] = []
    for gate_name in gate_names:
        # Check override: skip if explicitly disabled
        override = overrides.get(gate_name, {})
        if override.get("enabled") is False:
            results.append(
                GateResult(
                    gate=gate_name,
                    status="skip",
                    blocking=DEFAULT_BLOCKING.get(gate_name, True),
                    output="Disabled by gate_overrides in test_plan.md",
                    duration_s=0.0,
                )
            )
            continue

        runner = _get_gate_runner(gate_name)
        result = runner(project_path=pp, config=config)

        # Apply blocking override if specified
        if "blocking" in override:
            result = GateResult(
                gate=result.gate,
                status=result.status,
                blocking=override["blocking"],
                output=result.output,
                duration_s=result.duration_s,
            )

        results.append(result)

    return results


# ── CLI ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run verify gates for a project",
        prog="verify_gates",
    )
    parser.add_argument(
        "--project-path",
        required=True,
        help="Path to project root (worktree or repo)",
    )
    parser.add_argument(
        "--gates",
        default=None,
        help="Comma-separated list of specific gates to run (e.g. unit,e2e-web)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )

    args = parser.parse_args(argv)
    project_path = Path(args.project_path).resolve()

    if not project_path.is_dir():
        print(f"Error: {project_path} is not a directory", file=sys.stderr)
        return 2

    gates_override = None
    if args.gates:
        gates_override = [g.strip() for g in args.gates.split(",")]

    results = run_applicable_gates(project_path, gates_override=gates_override)

    if args.json_output:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            icon = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "warn": "WARN"}[r.status]
            blocking_tag = " [blocking]" if r.blocking else ""
            print(f"  {icon}: {r.gate}{blocking_tag} ({r.duration_s:.1f}s)")
            if r.status == "fail":
                # Show last few lines of output for failures
                lines = r.output.strip().splitlines()
                for line in lines[-5:]:
                    print(f"        {line}")

    # Exit code: 1 if any blocking gate failed
    has_blocking_failure = any(r.status == "fail" and r.blocking for r in results)
    return 1 if has_blocking_failure else 0


if __name__ == "__main__":
    sys.exit(main())
