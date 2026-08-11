"""Static checks on .github/workflows/ci.yml and pyproject.toml (ISSUE-044).

Reads ci.yml as plain text (no yaml import — the uv venv has no pyyaml) and
pyproject.toml via stdlib tomllib.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
PYPROJECT = REPO / "pyproject.toml"


def test_ci_install_does_not_swallow_failures():
    """TC-044h: ci.yml must not mask install failures with || true or 2>/dev/null."""
    text = CI_YML.read_text()
    assert "|| true" not in text, "ci.yml swallows failures with '|| true'"
    assert "2>/dev/null" not in text, "ci.yml hides errors with '2>/dev/null'"


def test_ci_installs_via_uv():
    """TC-044i: ci.yml must install via uv (setup-uv + uv sync --locked), not pip."""
    text = CI_YML.read_text()
    assert "astral-sh/setup-uv" in text, "ci.yml missing astral-sh/setup-uv"
    assert "uv sync --locked" in text, "ci.yml missing 'uv sync --locked'"
    assert "pip install" not in text, "ci.yml still uses 'pip install'"


def test_ci_interpreter_invocations_consistent():
    """TC-044j: every python/python3 invocation in ci.yml must go through uv run."""
    text = CI_YML.read_text()
    violations = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if re.search(r"\bpython3?\b", line) and "python-version" not in line:
            if "uv run" not in line:
                violations.append(f"line {lineno}: {line.strip()}")
    assert not violations, (
        "ci.yml lines invoke python outside 'uv run' (interpreter/env mismatch):\n"
        + "\n".join(violations)
    )
    assert "uv run pytest" in text, "ci.yml must run tests via 'uv run pytest'"


def test_pyproject_asyncio_config_removed():
    """TC-044k: asyncio_mode and pytest-asyncio must be gone from pyproject.toml."""
    with PYPROJECT.open("rb") as f:
        cfg = tomllib.load(f)
    ini = cfg["tool"]["pytest"]["ini_options"]
    assert "asyncio_mode" not in ini, "pyproject still sets asyncio_mode"
    dev = cfg["project"]["optional-dependencies"]["dev"]
    offenders = [d for d in dev if "pytest-asyncio" in d]
    assert not offenders, f"pyproject dev deps still include {offenders}"


def test_pytest_run_has_no_config_warning():
    """TC-044l: pytest must start without PytestConfigWarning about asyncio_mode.

    Bounded: --collect-only of a single test file with -p no:cacheprovider
    (~1s). This is NOT the recursive full-suite pytest anti-pattern (see
    docs/test_plan.md TC-047g).
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "--collect-only", "-q",
            "-p", "no:cacheprovider", "tests/test_ci_workflow.py",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = result.stdout + result.stderr
    assert "PytestConfigWarning" not in combined, combined
    assert "Unknown config option: asyncio_mode" not in combined, combined
    assert result.returncode == 0, combined
