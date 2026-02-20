"""Tests for scripts/flock_edit.sh — file-lock wrapper."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "flock_edit.sh")


def _run(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", SCRIPT, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class TestBasic:
    def test_runs_command_under_lock(self, tmp_path):
        target = str(tmp_path / "data.txt")
        # Create target file
        with open(target, "w") as f:
            f.write("")

        result = _run([target, "--", "bash", "-c", f'echo hello >> "{target}"'])
        assert result.returncode == 0

        with open(target) as f:
            assert "hello" in f.read()

    def test_passes_exit_code(self, tmp_path):
        target = str(tmp_path / "data.txt")
        with open(target, "w") as f:
            f.write("")

        result = _run([target, "--", "bash", "-c", "exit 42"])
        assert result.returncode == 42

    def test_missing_separator(self, tmp_path):
        target = str(tmp_path / "data.txt")
        result = _run([target, "echo", "hi"])
        assert result.returncode == 1
        assert "error" in result.stderr.lower()

    def test_too_few_args(self):
        result = _run(["onlyone"])
        assert result.returncode == 1


class TestConcurrency:
    def test_serializes_concurrent_writes(self, tmp_path):
        """Two writers appending to the same file should not interleave."""
        target = str(tmp_path / "shared.txt")
        with open(target, "w") as f:
            f.write("")

        def writer(label: str):
            # Each writer appends 5 lines
            cmd = f'for i in 1 2 3 4 5; do echo "{label}-$i" >> "{target}"; done'
            return _run([target, "--", "bash", "-c", cmd])

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(writer, "A")
            fb = pool.submit(writer, "B")
            ra = fa.result()
            rb = fb.result()

        assert ra.returncode == 0
        assert rb.returncode == 0

        with open(target) as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        # All 10 lines should be present
        assert len(lines) == 10

        # Lines from each writer should appear in order (not interleaved within a group)
        a_lines = [l for l in lines if l.startswith("A-")]
        b_lines = [l for l in lines if l.startswith("B-")]
        assert a_lines == ["A-1", "A-2", "A-3", "A-4", "A-5"]
        assert b_lines == ["B-1", "B-2", "B-3", "B-4", "B-5"]
