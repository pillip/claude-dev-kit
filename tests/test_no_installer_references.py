"""ISSUE-027 grep guard: the bespoke installer is retired.

`install_project.sh`, `install_packs.py`, and `merge_settings.py` were removed
once the plugin path reached parity. No active surface (code, skills,
templates, README/CONTRIBUTING) may reference them again — the plugin is the
only install path. Historical records (docs/specs/, issues.md) are exempt.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED = ("install_project.sh", "install_packs", "merge_settings")

ACTIVE_SURFACES = (
    "README.md",
    "CONTRIBUTING.md",
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


def test_removed_installer_scripts_are_gone():
    for name in ("install_project.sh", "install_packs.py", "merge_settings.py"):
        assert not (ROOT / "scripts" / name).exists(), f"scripts/{name} was re-added"


def test_no_active_surface_references_removed_installer():
    offenders = []
    for f in _iter_files():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for token in BANNED:
            if token in text:
                offenders.append(f"{f.relative_to(ROOT)}: {token}")
    assert not offenders, (
        "Retired installer referenced on active surfaces (plugin is the only "
        "install path — ISSUE-027):\n" + "\n".join(offenders)
    )
