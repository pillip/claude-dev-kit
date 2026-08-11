"""Bash-level tests for scripts/gate_server.sh (ISSUE-044).

Uses file:// health URLs so no network or real server is needed:
curl -sf on an existing file succeeds, on a missing file fails.
"""

import os
import signal
import subprocess
import time
from pathlib import Path

GATE_SERVER = Path(__file__).resolve().parent.parent / "scripts" / "gate_server.sh"


def run_gate(*, start_cmd, health_url, test_cmd, timeout=None, cwd, extra_args=()):
    args = [
        "bash",
        str(GATE_SERVER),
        "--start-cmd", start_cmd,
        "--health-url", health_url,
        "--test-cmd", test_cmd,
    ]
    if timeout is not None:
        args += ["--timeout", str(timeout)]
    args += ["--cwd", str(cwd)]
    args += list(extra_args)
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def passing_health(tmp_path):
    path = tmp_path / "health.ok"
    path.write_text("ok\n")
    return f"file://{path}"


def failing_health(tmp_path):
    return f"file://{tmp_path}/no-such-file"


def pid_dead(pid):
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def wait_dead(pid, deadline=5.0):
    end = time.time() + deadline
    while time.time() < end:
        if pid_dead(pid):
            return True
        time.sleep(0.1)
    return pid_dead(pid)


def read_pid(path):
    end = time.time() + 5.0
    while time.time() < end:
        if path.exists() and path.read_text().strip():
            break
        time.sleep(0.1)
    return int(path.read_text().strip())


def best_effort_kill(path):
    try:
        os.kill(read_pid(path), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, FileNotFoundError, ValueError):
        pass


def test_happy_path_exit_code_passthrough_and_cleanup(tmp_path):
    """TC-044a: test-cmd exit code passes through and the server is cleaned up.

    Uses `exec bash -c` so the eval subshell is replaced in-place and the
    recorded $$ equals the PID gate_server.sh tracks (macOS ships bash 3.2,
    which has no BASHPID).
    """
    start = f"exec bash -c 'echo $$ > {tmp_path}/server.pid; exec sleep 30'"
    result = run_gate(
        start_cmd=start,
        health_url=passing_health(tmp_path),
        test_cmd="exit 0",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    pid = read_pid(tmp_path / "server.pid")
    assert wait_dead(pid), f"server pid {pid} still alive after gate exit"

    (tmp_path / "server.pid").unlink()
    result = run_gate(
        start_cmd=start,
        health_url=passing_health(tmp_path),
        test_cmd="exit 7",
        cwd=tmp_path,
    )
    assert result.returncode == 7, result.stderr
    pid = read_pid(tmp_path / "server.pid")
    assert wait_dead(pid), f"server pid {pid} still alive after gate exit"


def test_immediate_exit_returns_125(tmp_path):
    """TC-044b: a server that exits immediately yields 125 (documented contract).

    NOTE: FAILS against current gate_server.sh on this machine — the EXIT
    trap's failing `kill` under `set -e` overrides `exit 125` with 1
    (bash 3.2). The cleanup rewrite must make trap kills best-effort so the
    documented 125 is preserved.
    """
    result = run_gate(
        start_cmd="bash -c 'exit 1'",
        health_url=failing_health(tmp_path),
        test_cmd="exit 0",
        timeout=5,
        cwd=tmp_path,
    )
    assert result.returncode == 125, result.stderr
    assert "exited immediately" in result.stderr


def test_health_timeout_returns_124(tmp_path):
    """TC-044c: failing health endpoint yields 124 and cleanup still runs."""
    start = f"exec bash -c 'echo $$ > {tmp_path}/server.pid; exec sleep 30'"
    result = run_gate(
        start_cmd=start,
        health_url=failing_health(tmp_path),
        test_cmd="exit 0",
        timeout=2,
        cwd=tmp_path,
    )
    assert result.returncode == 124, result.stderr
    assert "Health check timed out" in result.stderr
    pid = read_pid(tmp_path / "server.pid")
    assert wait_dead(pid), f"server pid {pid} still alive after health timeout"


def test_usage_error_returns_2(tmp_path):
    """TC-044d: missing required arguments yields usage error 2."""
    result = subprocess.run(
        ["bash", str(GATE_SERVER), "--start-cmd", "sleep 5"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2, result.stderr


def test_forking_server_leaves_no_orphans(tmp_path):
    """TC-044e: cleanup must reap forked children, not just the leader PID."""
    start = (
        f"bash -c 'echo $$ > {tmp_path}/parent.pid; "
        f"sleep 60 & echo $! > {tmp_path}/child.pid; wait'"
    )
    try:
        result = run_gate(
            start_cmd=start,
            health_url=passing_health(tmp_path),
            test_cmd="exit 0",
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        parent_pid = read_pid(tmp_path / "parent.pid")
        child_pid = read_pid(tmp_path / "child.pid")
        assert wait_dead(parent_pid), f"parent {parent_pid} still alive"
        assert wait_dead(child_pid), f"orphaned child {child_pid} still alive"
    finally:
        best_effort_kill(tmp_path / "parent.pid")
        best_effort_kill(tmp_path / "child.pid")


def test_daemonizing_start_cmd_probes_group(tmp_path):
    """TC-044f: a daemonizing start cmd (leader exits after forking) must not
    be misclassified as 'exited immediately' (125), and the worker is reaped."""
    start = f"bash -c 'sleep 30 & echo $! > {tmp_path}/worker.pid'"
    try:
        result = run_gate(
            start_cmd=start,
            health_url=passing_health(tmp_path),
            test_cmd="exit 0",
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        worker_pid = read_pid(tmp_path / "worker.pid")
        assert wait_dead(worker_pid), f"worker {worker_pid} still alive"
    finally:
        best_effort_kill(tmp_path / "worker.pid")


def test_sigterm_immune_server_reaped_by_escalation(tmp_path):
    """TC-044g: a server that ignores SIGTERM is reaped via kill -9 escalation.

    Uses `exec bash -c` so the recorded $$ equals the tracked PID (bash 3.2
    has no BASHPID), and a short-sleep loop instead of `sleep 60` so no
    long-lived child can leak past teardown.
    """
    start = (
        f"exec bash -c 'echo $$ > {tmp_path}/server.pid; "
        f"trap \"\" TERM; while :; do sleep 1; done'"
    )
    try:
        result = run_gate(
            start_cmd=start,
            health_url=passing_health(tmp_path),
            test_cmd="exit 0",
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        pid = read_pid(tmp_path / "server.pid")
        assert wait_dead(pid), f"SIGTERM-immune server {pid} still alive"
    finally:
        best_effort_kill(tmp_path / "server.pid")
