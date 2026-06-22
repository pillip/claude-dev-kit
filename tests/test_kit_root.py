"""Tests for ISSUE-023: ${CLAUDE_PLUGIN_ROOT}-aware kit-root resolution."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT_ROOT_SH = ROOT / "scripts" / "kit_root.sh"
CHECKPOINT_SH = ROOT / "scripts" / "checkpoint.sh"


def _run(cmd, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_kit_root_prefers_plugin_root(tmp_path):
    # A fake plugin root containing scripts/ is honored over the real location.
    (tmp_path / "scripts").mkdir()
    out = _run(["bash", str(KIT_ROOT_SH)], {"CLAUDE_PLUGIN_ROOT": str(tmp_path)})
    assert out.returncode == 0
    assert out.stdout.strip() == str(tmp_path)


def test_kit_root_falls_back_to_script_parent_when_unset():
    out = _run(["bash", str(KIT_ROOT_SH)], {"CLAUDE_PLUGIN_ROOT": ""})
    assert out.returncode == 0
    # Falls back to the realpath parent of scripts/ — the kit root.
    assert out.stdout.strip() == str(ROOT.resolve())


def test_kit_root_ignores_plugin_root_without_scripts(tmp_path):
    # If CLAUDE_PLUGIN_ROOT has no scripts/ dir, fall back (defensive).
    out = _run(["bash", str(KIT_ROOT_SH)], {"CLAUDE_PLUGIN_ROOT": str(tmp_path)})
    assert out.returncode == 0
    assert out.stdout.strip() == str(ROOT.resolve())


def test_checkpoint_resolves_verify_under_plugin_root(tmp_path):
    # Point CLAUDE_PLUGIN_ROOT at a fake plugin whose verify_checkpoint.py just
    # prints a marker; checkpoint.sh must exec THAT one, proving plugin-root wins.
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "verify_checkpoint.py").write_text(
        "import sys\nprint('FAKE_PLUGIN_VERIFY', *sys.argv[1:])\n", encoding="utf-8"
    )
    out = _run(
        ["bash", str(CHECKPOINT_SH), "--skill", "implement", "--phase", "code", "--issue", "X"],
        {"CLAUDE_PLUGIN_ROOT": str(tmp_path)},
    )
    assert out.returncode == 0, out.stderr
    assert "FAKE_PLUGIN_VERIFY" in out.stdout
    assert "--phase code" in out.stdout


def test_checkpoint_falls_back_to_real_verify_when_unset():
    # With no plugin root, checkpoint.sh runs the real verify_checkpoint.py,
    # which errors on an unknown issue but proves it resolved + executed it.
    out = _run(
        ["bash", str(CHECKPOINT_SH), "--skill", "implement", "--phase", "code", "--issue", "ISSUE-999"],
        {"CLAUDE_PLUGIN_ROOT": ""},
    )
    # Real verifier ran (it prints a FAIL/diagnostic and exits non-zero) — not a
    # "file not found" from a broken path.
    assert "No module named" not in (out.stderr or "")
    assert "can't open file" not in (out.stderr or "")
