"""ISSUE-043 grep guard: dead scripts are removed and repo hygiene holds.

The 2026-08-10 repo audit (findings 8 + 11) retired four dead scripts:
`ensure_permissions.py` and `ensure_gh.sh` (zero callers), `kit_root.sh`
(referenced only by its own test — wrappers inline their own root
resolution per ISSUE-023), and `lint_skill_cache_order.py` (wired to
neither CI nor any skill; deleted per the audit default rather than wired
into ci.yml). No active surface may reference them again.

Also guards the two hygiene invariants from the same audit: no
`__pycache__`/.pyc paths tracked by git, and `.claude/run/` telemetry
ignored so it never shows as untracked noise.

Historical records (docs/, issues.md, CHANGELOG.md) are exempt from the
reference scan, matching the ISSUE-027 guard convention. Note: bare
`kit_root`/`KIT_ROOT` identifiers (e.g. `find_kit_root` in
session_start.py) are live and unrelated — only the `kit_root.sh` script
name is banned.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REMOVED_FILES = (
    "scripts/ensure_permissions.py",
    "scripts/ensure_gh.sh",
    "scripts/kit_root.sh",
    "scripts/lint_skill_cache_order.py",
    "tests/test_kit_root.py",
    "tests/test_lint_skill_cache_order.py",
)

BANNED = ("ensure_permissions", "ensure_gh", "kit_root.sh", "lint_skill_cache_order")

ACTIVE_SURFACES = (
    "README.md",
    "CONTRIBUTING.md",
    ".github",
    "agents",
    "skills",
    "project",
    "hooks",
    "scripts",
    "templates",
    "user",
)

TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".tmpl", ".toml"}


def _iter_files():
    for surface in ACTIVE_SURFACES:
        path = ROOT / surface
        if path.is_file():
            yield path
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file() and f.suffix in TEXT_SUFFIXES and "__pycache__" not in f.parts:
                    yield f


def test_removed_dead_scripts_are_gone():
    """TC-043a: the four dead scripts and their orphaned tests do not exist."""
    for rel in REMOVED_FILES:
        assert not (ROOT / rel).exists(), f"{rel} was re-added (removed by ISSUE-043)"


def test_no_active_surface_references_removed_scripts():
    """TC-043b: no active surface references the removed script names."""
    offenders = []
    for f in _iter_files():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for token in BANNED:
            if token in text:
                offenders.append(f"{f.relative_to(ROOT)}: {token}")
    assert not offenders, (
        "Removed dead script referenced on active surfaces (ISSUE-043):\n"
        + "\n".join(offenders)
    )


def test_no_tracked_pycache_artifacts():
    """TC-043c: git tracks no __pycache__ directories or .pyc files."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    tracked = [
        line
        for line in result.stdout.splitlines()
        if "__pycache__" in line or line.endswith(".pyc")
    ]
    assert not tracked, "Tracked build artifacts found:\n" + "\n".join(tracked)


def test_claude_run_telemetry_is_gitignored():
    """TC-043d: .claude/run/ paths are ignored (no untracked telemetry noise)."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".claude/run/telemetry-probe.jsonl"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        ".claude/run/ is not gitignored — telemetry files would appear as "
        "untracked noise in git status (ISSUE-043)"
    )


def test_gitignore_scopes_claude_run_not_whole_claude_dir():
    """TC-043e: only .claude/run/ is ignored — .claude/ itself stays visible."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    lines = [ln.strip() for ln in gitignore]
    assert ".claude/run/" in lines, ".gitignore must list .claude/run/"
    for banned in (".claude", ".claude/", ".claude/*", ".claude/**"):
        assert banned not in lines, (
            f".gitignore must not blanket-ignore {banned!r} — only the run/ "
            "subpath (ISSUE-043 scope guard)"
        )
