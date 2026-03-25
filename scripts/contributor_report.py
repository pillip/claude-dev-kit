#!/usr/bin/env python3
"""Write a contributor field report for kit self-improvement.

Reports are stored at ~/.claude-kit/contributor-logs/{skill}-{slug}.md.
Enforces: max 3 reports per session, skip duplicates, contributor_mode check.

Usage:
    python3 scripts/contributor_report.py --skill <name> --step "<step>" --rating <0-10> --notes "<text>"
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from kit_config import get as config_get  # noqa: E402

LOGS_DIR = Path.home() / ".claude-kit" / "contributor-logs"
SESSION_ID = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{os.getppid()}"


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in slug)
    slug = slug.replace(" ", "-").replace("_", "-")
    # Collapse multiple hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60]


def _log_path(skill: str, step: str) -> Path:
    slug = _slugify(step)
    return LOGS_DIR / f"{skill}-{slug}.md"


def _count_session_reports() -> int:
    """Count reports written in the current session."""
    if not LOGS_DIR.exists():
        return 0
    count = 0
    for f in LOGS_DIR.iterdir():
        if f.suffix == ".md":
            content = f.read_text(encoding="utf-8")
            if f"Session: {SESSION_ID}" in content:
                count += 1
    return count


def _has_duplicate(path: Path, step: str, rating: int) -> bool:
    """Check if a report with the same step+rating already exists."""
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    marker = f"Step: {step} | Rating: {rating}"
    return marker in content


def write_report(
    skill: str, step: str, rating: int, notes: str
) -> tuple[bool, str]:
    """Write a field report. Returns (success, message)."""
    # Check contributor mode
    if not config_get("contributor_mode"):
        return False, "Contributor mode is off. Skipping."

    # Validate rating
    if not 0 <= rating <= 10:
        return False, f"Rating must be 0-10, got {rating}."

    # Check session limit
    if _count_session_reports() >= 3:
        return False, "Session limit (3 reports) reached. Skipping."

    path = _log_path(skill, step)

    # Check duplicates
    if _has_duplicate(path, step, rating):
        return False, f"Duplicate report for step '{step}' with rating {rating}. Skipping."

    # Write report
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = (
        f"\n## {step}\n"
        f"- Step: {step} | Rating: {rating}\n"
        f"- Notes: {notes}\n"
        f"- Skill: /{skill}\n"
        f"- Date: {now}\n"
        f"- Session: {SESSION_ID}\n"
    )

    if path.exists():
        content = path.read_text(encoding="utf-8")
        path.write_text(content + entry, encoding="utf-8")
    else:
        header = f"# Contributor Report: /{skill}\n"
        path.write_text(header + entry, encoding="utf-8")

    return True, f"Report written to {path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a contributor field report.")
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument("--step", required=True, help="Workflow step name")
    parser.add_argument("--rating", required=True, type=int, help="Rating 0-10")
    parser.add_argument("--notes", required=True, help="Friction or suggestion notes")
    args = parser.parse_args()

    success, message = write_report(args.skill, args.step, args.rating, args.notes)
    print(message)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
