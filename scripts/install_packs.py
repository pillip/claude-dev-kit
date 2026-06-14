#!/usr/bin/env python3
"""Install core + optional packs into a project's .claude/ directory.

Replaces the directory-symlink pattern (`.claude/agents` → kit) with per-entry
symlinks so core + selected packs can coexist in the same `.claude/agents`
and `.claude/skills` directories.

Selection model:
- (no flag)         → core only
- --pack=core       → core only (explicit)
- --pack=sales      → core + sales (sales depends on core)
- --pack=<name>     → core + named pack
- --pack=all        → core + every pack declared under packs/
- Multiple --pack flags allowed; deduplicated; selecting any non-core pack
  always implies core.

Exit codes:
  0 = installation succeeded
  1 = validation or installation failure (depends_on unsatisfied, entry
      collision, unknown pack, missing manifest, etc.)
  2 = bad input (kit root missing required dirs)

Usage:
    python3 install_packs.py <kit_root> <proj_root>
    python3 install_packs.py <kit_root> <proj_root> --pack=sales
    python3 install_packs.py <kit_root> <proj_root> --pack=sales --pack=other
    python3 install_packs.py <kit_root> <proj_root> --pack=all

Side outputs:
- Writes the list of settings_snippet paths (one per line) to stdout
  AFTER installation completes. The shell wrapper captures this and
  feeds it to merge_settings.py in order (core's snippet first, then
  pack snippets in alphabetical pack-name order).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# Import the validator so the schema lives in exactly one place.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_pack_manifest import _load_manifest  # noqa: E402


CORE_TOKEN = "core"


def discover_packs(kit_root: Path) -> dict[str, Path]:
    """Return {pack_name: manifest_path} for every pack in kit_root/packs/."""
    packs: dict[str, Path] = {}
    packs_dir = kit_root / "packs"
    if packs_dir.is_dir():
        for manifest in sorted(packs_dir.glob("*/manifest.yaml")):
            packs[manifest.parent.name] = manifest
    return packs


def resolve_pack_selection(
    requested: list[str], available_packs: dict[str, Path]
) -> list[str]:
    """Resolve --pack arg list into an ordered set of pack names to install.

    Output is always ['core'] + sorted([selected non-core packs]).
    Raises ValueError on unknown pack names.
    """
    # Deduplicate
    requested_set = set(requested)
    if "all" in requested_set:
        requested_set.discard("all")
        requested_set.update(available_packs.keys())

    if not requested_set:
        requested_set = {CORE_TOKEN}

    # Validate names
    unknown = requested_set - {CORE_TOKEN} - set(available_packs.keys())
    if unknown:
        available_list = sorted([CORE_TOKEN, "all", *available_packs.keys()])
        raise ValueError(
            f"unknown pack name(s): {sorted(unknown)}; "
            f"available: {available_list}"
        )

    # Core is always first; non-core packs in alphabetical order for
    # deterministic settings-merge order.
    non_core = sorted(requested_set - {CORE_TOKEN})
    return [CORE_TOKEN] + non_core


def _verify_depends_on(pack_name: str, manifest: dict, selected: set[str]) -> None:
    """Raise ValueError if the manifest's depends_on isn't satisfied."""
    deps = manifest.get("depends_on") or []
    for dep in deps:
        if dep == CORE_TOKEN:
            continue
        if dep not in selected:
            raise ValueError(
                f"pack {pack_name!r} declares depends_on: {dep!r} "
                "but that pack is not in the install set"
            )


def _emit_migration_note(claude_dir: Path) -> bool:
    """If .claude/agents or .claude/skills is a legacy directory symlink, warn.

    Returns True if a note was printed (informational only — no failure).
    """
    legacy = False
    for d in ("agents", "skills"):
        path = claude_dir / d
        if path.is_symlink() and path.resolve().is_dir() and path.resolve().name in {"agents", "skills"}:
            target = path.readlink() if hasattr(path, "readlink") else os.readlink(path)
            if str(target).startswith(".."):
                # heuristic: directory symlink pointing into the kit
                print(
                    f"  migration note: {path} was a legacy directory symlink "
                    "from a pre-pack install. Replacing with per-entry symlinks.",
                    file=sys.stderr,
                )
                legacy = True
    return legacy


def _prepare_dirs(claude_dir: Path) -> None:
    """Clean .claude/agents and .claude/skills to a fresh empty directory."""
    for d in ("agents", "skills"):
        target = claude_dir / d
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)


def _symlink_entry(src: Path, dst: Path) -> None:
    """Create a symlink dst → src, raising on collision."""
    if dst.exists() or dst.is_symlink():
        raise ValueError(
            f"entry collision: {dst.name} already exists at {dst}; "
            "two packs cannot contribute the same entry"
        )
    dst.symlink_to(src)


def install_core(kit_root: Path, claude_dir: Path) -> None:
    """Symlink every top-level agents/*.md and skills/*/ into .claude/."""
    agents_src = kit_root / "agents"
    skills_src = kit_root / "skills"
    if not agents_src.is_dir() or not skills_src.is_dir():
        raise ValueError(
            f"kit root {kit_root} is missing agents/ or skills/ directories"
        )
    for src in sorted(agents_src.glob("*.md")):
        _symlink_entry(src, claude_dir / "agents" / src.name)
    for src in sorted(p for p in skills_src.iterdir() if p.is_dir()):
        _symlink_entry(src, claude_dir / "skills" / src.name)


def install_pack(
    kit_root: Path,
    claude_dir: Path,
    pack_name: str,
    manifest: dict,
) -> Path | None:
    """Symlink every entry in the manifest into .claude/.

    Returns the absolute settings_snippet path if the manifest declares one,
    else None.
    """
    pack_root = kit_root / "packs" / pack_name
    for agent in manifest.get("agents") or []:
        src = pack_root / "agents" / agent
        _symlink_entry(src, claude_dir / "agents" / agent)
    for skill in manifest.get("skills") or []:
        src = pack_root / "skills" / skill
        _symlink_entry(src, claude_dir / "skills" / skill)
    snippet_name = manifest.get("settings_snippet")
    if snippet_name:
        return pack_root / snippet_name
    return None


def run_install(
    kit_root: Path,
    proj_root: Path,
    selection: list[str],
) -> list[Path]:
    """Perform the installation. Returns the ordered list of settings snippets
    to merge AFTER core's snippet (which is handled by the shell wrapper).
    """
    claude_dir = proj_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    _emit_migration_note(claude_dir)
    _prepare_dirs(claude_dir)

    # Always install core
    install_core(kit_root, claude_dir)

    pack_snippets: list[Path] = []
    selected_set = set(selection)
    for pack_name in selection:
        if pack_name == CORE_TOKEN:
            continue
        manifest_path = kit_root / "packs" / pack_name / "manifest.yaml"
        if not manifest_path.is_file():
            raise ValueError(f"missing manifest: {manifest_path}")
        manifest = _load_manifest(manifest_path)
        _verify_depends_on(pack_name, manifest, selected_set)
        snippet = install_pack(kit_root, claude_dir, pack_name, manifest)
        if snippet:
            pack_snippets.append(snippet)

    return pack_snippets


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install core + optional packs")
    ap.add_argument("kit_root", help="Path to kit source root")
    ap.add_argument("proj_root", help="Path to target project root")
    ap.add_argument(
        "--pack",
        action="append",
        default=[],
        help="Pack to install (default: core). Use --pack=all for every pack.",
    )
    args = ap.parse_args(argv)

    kit_root = Path(args.kit_root).resolve()
    proj_root = Path(args.proj_root).resolve()

    if not kit_root.is_dir():
        print(f"error: kit_root {kit_root} not found", file=sys.stderr)
        return 2
    if not proj_root.is_dir():
        print(f"error: proj_root {proj_root} not found", file=sys.stderr)
        return 2

    available_packs = discover_packs(kit_root)

    try:
        selection = resolve_pack_selection(args.pack, available_packs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        pack_snippets = run_install(kit_root, proj_root, selection)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Stdout: pack snippet paths (one per line) for the shell wrapper.
    for snippet in pack_snippets:
        print(snippet)

    print(f"installed packs: {','.join(selection)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
