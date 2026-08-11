#!/usr/bin/env python3
"""SessionStart hook — run session-level kit checks ONCE per session (ISSUE-032).

Replaces the per-skill preamble steps that every skill invocation used to
re-run: the kit update check and contributor-mode detection. Whatever this
prints lands in the session context exactly once; when there is nothing to
say (no update, contributor mode off) it prints nothing and costs nothing.

Must never fail or block session start: every path exits 0.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def find_kit_root() -> tuple[Path, bool] | None:
    """Kit root = the directory holding scripts/kit_update_check.py.

    Returns (root, from_plugin): from_plugin is True when the root came from
    CLAUDE_PLUGIN_ROOT — under plugin installs that is a version-pinned
    marketplace cache dir, so callers must not print it (ISSUE-037).
    """
    candidates = []
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidates.append((Path(plugin_root), True))
    hook_root = os.environ.get("HOOK_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if hook_root:
        candidates.append((Path(hook_root), False))
    # Standalone kit repo: this file lives at <kit>/project/.claude/hooks/
    candidates.append((Path(__file__).resolve().parents[3], False))
    for c, from_plugin in candidates:
        if (c / "scripts" / "kit_update_check.py").is_file():
            return c, from_plugin
    return None


def run_quiet(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return proc.returncode, proc.stdout.strip()
    except Exception:
        return 0, ""


def main() -> None:
    try:
        json.load(sys.stdin)  # payload unused; drain so the pipe closes cleanly
    except Exception:
        pass

    found = find_kit_root()
    if found is None:
        return
    kit, from_plugin = found

    # 1) Kit update check — exit 1 means "update available, show once".
    rc, out = run_quiet([sys.executable, str(kit / "scripts" / "kit_update_check.py")])
    if rc == 1 and out:
        print(out)

    # 2) Contributor mode — only inject the instructions when it is ON.
    _, mode = run_quiet([sys.executable, str(kit / "scripts" / "kit_config.py"),
                         "get", "contributor_mode"])
    if mode.lower() == "true":
        if from_plugin:
            # Plugin installs live in a version-pinned cache dir; a baked-in
            # absolute path dies on plugin update / cache GC (ISSUE-037).
            # Point at the Kit Script Root each skill preamble substitutes at
            # load time — it always names the currently installed version.
            report = "<kit-root>/scripts/contributor_report.py"
            resolve = (" (<kit-root> = the Kit Script Root absolute path shown "
                       "in the preamble of any active kit skill)")
        else:
            report = str(kit / "scripts" / "contributor_report.py")
            resolve = ""
        print(
            "KIT CONTRIBUTOR MODE: ON. At the end of each major kit-skill workflow "
            "step, self-rate the kit experience 0-10. If rating < 10 with an "
            "actionable improvement, file a field report inline (do not stop the "
            f"workflow): python3 {report} --skill <name> --step \"<step>\" "
            f"--rating <N> --notes \"<friction or suggestion>\"{resolve} — max 3 "
            "reports per session, one per step, kit/skill issues only (not "
            "user-app bugs or network errors)."
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
