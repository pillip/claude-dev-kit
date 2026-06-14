#!/usr/bin/env python3
"""Validate pack manifests under packs/<name>/manifest.yaml.

Schema (documented in packs/README.md):
    name: <pack-name>           # required, must match directory name
    description: <one line>     # required
    depends_on: [core, ...]     # required; must include "core"
    agents: [...]               # optional — *.md filenames under agents/
    skills: [...]               # optional — skill dir names under skills/
    templates: [...]            # optional — *.md filenames under templates/
    settings_snippet: file.json # optional — relative path

Validates:
- YAML is well-formed
- `name` matches directory name
- `description` is a non-empty string
- `depends_on` includes "core" (every pack at minimum)
- `depends_on` entries refer to existing packs OR the literal "core"
- Every listed agent/skill/template path exists at the expected location
- `settings_snippet` (if set) points to an existing file
- No entry duplicates across packs (same agent filename in two packs is rejected)

Exit code:
    0 = all manifests valid
    1 = one or more violations
    2 = bad input (target not found)

Usage:
    python3 scripts/validate_pack_manifest.py packs/sales/manifest.yaml
    python3 scripts/validate_pack_manifest.py packs/         # validate every pack
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover — only hit when PyYAML is absent
    yaml = None  # type: ignore[assignment]


def _require_yaml() -> None:
    """Fail loudly with an install hint at the point YAML parsing is actually needed.

    Importing this module must not trigger sys.exit — that breaks unrelated
    test collection on environments where PyYAML isn't installed yet.
    """
    if yaml is None:
        raise ImportError(
            "PyYAML is required for pack manifest parsing. "
            "Install with: uv add --dev pyyaml  OR  pip install pyyaml"
        )


REQUIRED_FIELDS = {"name", "description", "depends_on"}
OPTIONAL_LIST_FIELDS = {"agents", "skills", "templates"}


def _load_manifest(path: Path) -> dict[str, Any]:
    _require_yaml()
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: manifest must be a YAML mapping at top level")
    return data


def _validate_single(
    manifest_path: Path,
    known_packs: set[str],
    seen_entries: dict[str, dict[str, str]],
) -> list[str]:
    """Validate one manifest.

    seen_entries: shared dict tracking previously-seen entries across packs.
        Keyed by category ("agents"/"skills"/"templates"), value is
        {entry_name: owning_pack_name}. Used to detect duplicate entries.
    """
    errors: list[str] = []
    pack_dir = manifest_path.parent
    pack_dir_name = pack_dir.name

    try:
        manifest = _load_manifest(manifest_path)
    except ImportError as exc:
        # PyYAML is not installed — surface as a clean validation failure.
        return [f"{manifest_path}: {exc}"]
    except Exception as exc:
        # YAMLError, ValueError, and any other parser-level failure.
        return [f"{manifest_path}: failed to parse YAML — {exc}"]

    # Required fields
    missing = REQUIRED_FIELDS - manifest.keys()
    if missing:
        errors.append(
            f"{manifest_path}: missing required field(s): {sorted(missing)}"
        )

    # name must match directory
    name = manifest.get("name")
    if name and name != pack_dir_name:
        errors.append(
            f"{manifest_path}: name={name!r} does not match directory name "
            f"{pack_dir_name!r}"
        )

    # description must be a non-empty string
    desc = manifest.get("description")
    if desc is not None and (not isinstance(desc, str) or not desc.strip()):
        errors.append(f"{manifest_path}: description must be a non-empty string")

    # depends_on must include "core" and reference real packs
    deps = manifest.get("depends_on")
    if deps is not None:
        if not isinstance(deps, list):
            errors.append(f"{manifest_path}: depends_on must be a list")
        else:
            if "core" not in deps:
                errors.append(
                    f"{manifest_path}: depends_on must include 'core' "
                    "(every pack depends on the core layer)"
                )
            for dep in deps:
                if dep == "core":
                    continue
                if dep not in known_packs:
                    errors.append(
                        f"{manifest_path}: depends_on references unknown pack "
                        f"{dep!r} (known: {sorted(known_packs)})"
                    )

    # Optional list fields: each entry must exist + must not duplicate across packs
    for field in OPTIONAL_LIST_FIELDS:
        entries = manifest.get(field)
        if entries is None:
            continue
        if not isinstance(entries, list):
            errors.append(f"{manifest_path}: {field} must be a list")
            continue
        for entry in entries:
            if not isinstance(entry, str) or not entry.strip():
                errors.append(
                    f"{manifest_path}: {field} entry must be a non-empty string, "
                    f"got {entry!r}"
                )
                continue
            expected_path = pack_dir / field / entry
            if not expected_path.exists():
                errors.append(
                    f"{manifest_path}: {field} entry {entry!r} does not exist "
                    f"at {expected_path}"
                )
            # Duplicate detection across packs
            owners = seen_entries.setdefault(field, {})
            if entry in owners:
                errors.append(
                    f"{manifest_path}: {field} entry {entry!r} duplicates an "
                    f"entry in pack {owners[entry]!r}"
                )
            else:
                owners[entry] = name or pack_dir_name

    # settings_snippet (if present) must exist
    snippet = manifest.get("settings_snippet")
    if snippet:
        if not isinstance(snippet, str):
            errors.append(f"{manifest_path}: settings_snippet must be a string")
        else:
            snippet_path = pack_dir / snippet
            if not snippet_path.exists():
                errors.append(
                    f"{manifest_path}: settings_snippet {snippet!r} does not "
                    f"exist at {snippet_path}"
                )

    return errors


def _discover_packs(packs_root: Path) -> list[Path]:
    """Return manifest.yaml paths under packs_root."""
    return sorted(packs_root.glob("*/manifest.yaml"))


def validate_packs(target: Path) -> tuple[int, list[str]]:
    """Validate one manifest or all manifests under a packs directory.

    Returns (manifest_count, error_list).
    """
    if target.is_file():
        manifests = [target]
    elif target.is_dir():
        manifests = _discover_packs(target)
    else:
        return 0, [f"target not found: {target}"]

    # Pre-compute known pack names from filesystem so depends_on validation works.
    known_packs: set[str] = set()
    for m in manifests:
        known_packs.add(m.parent.name)

    all_errors: list[str] = []
    seen_entries: dict[str, dict[str, str]] = {}
    for m in manifests:
        all_errors.extend(_validate_single(m, known_packs, seen_entries))
    return len(manifests), all_errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate pack manifest(s)")
    ap.add_argument(
        "target",
        help="Path to a pack manifest.yaml OR the packs/ directory",
    )
    args = ap.parse_args(argv)

    target = Path(args.target)
    count, errors = validate_packs(target)

    if not count:
        print(errors[0] if errors else f"no manifests found at {target}", file=sys.stderr)
        return 2

    if errors:
        print(f"{len(errors)} violation(s) across {count} manifest(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"All {count} manifest(s) passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
