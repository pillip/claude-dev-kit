#!/usr/bin/env python3
"""Validate a research claim against the captured source snapshot.

ISSUE-018 / SPEC-018 degraded path: every quantitative or factual claim in
brainstorm/bizanalysis output must carry a verbatim quote from a captured
source. This validator grep-checks the quote string against the snapshot
written by `capture_source.py` and flags the claim as `stale` when the
source's published_at is older than the freshness window.

Claim record schema (JSON):
    {
      "quote":        "...verbatim text from the source...",
      "source_url":   "https://example.com/page",
      "accessed_at":  "2026-06-18T12:00:00+00:00",     // ISO-8601
      "published_at": "2025-01-01",                     // optional; reuses snapshot meta if omitted
      "slug":         "example-com-page"                // optional; derived from URL if omitted
    }

Verdicts:
    ok              — quote found in snapshot AND not stale
    quote_missing   — quote substring not present in snapshot HTML
    stale           — quote present BUT source older than freshness window
    snapshot_absent — no snapshot file exists at the expected path

Exit codes:
    0 = verdict == ok
    1 = verdict is a failure (quote_missing | stale | snapshot_absent)
    2 = bad input (malformed JSON, missing required field)

Usage:
    python3 scripts/validate_research_claim.py < claim.json
    python3 scripts/validate_research_claim.py --claim-file claim.json
    python3 scripts/validate_research_claim.py --claim-file claim.json --max-age-days 180
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Reuse slug derivation to keep snapshot paths consistent.
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from capture_source import DEFAULT_DIR, slug_from_url  # noqa: E402

DEFAULT_MAX_AGE_DAYS = 365  # 12 months — matches SPEC-018


@dataclass
class Verdict:
    ok: bool
    code: str  # ok | quote_missing | stale | snapshot_absent
    reason: str


def _resolve_slug(claim: dict) -> str:
    slug = claim.get("slug")
    if slug:
        return slug
    return slug_from_url(claim["source_url"])


def _parse_iso(value: str) -> Optional[datetime]:
    """Best-effort ISO-8601 parser. Accepts 'YYYY-MM-DD' or full ISO timestamps."""
    if not value:
        return None
    # Python 3.11+ fromisoformat handles offsets; for older Z-suffixed inputs
    # we normalize manually.
    s = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Try date-only fallback
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def validate_claim(
    claim: dict,
    references_dir: Path,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Verdict:
    """Validate a single claim record. Pure function — no side effects."""
    required = {"quote", "source_url", "accessed_at"}
    missing = required - set(claim)
    if missing:
        return Verdict(False, "bad_input", f"missing required field(s): {sorted(missing)}")

    slug = _resolve_slug(claim)
    html_path = references_dir / f"{slug}.html"
    meta_path = references_dir / f"{slug}.meta.json"

    if not html_path.is_file():
        return Verdict(
            False,
            "snapshot_absent",
            f"snapshot HTML not found at {html_path} — re-run capture_source.py",
        )

    html = html_path.read_text(encoding="utf-8", errors="replace")
    quote = claim["quote"]
    if quote not in html:
        return Verdict(
            False,
            "quote_missing",
            f"quote not found verbatim in {html_path} (length {len(quote)})",
        )

    accessed = _parse_iso(claim["accessed_at"])
    if accessed is None:
        return Verdict(
            False, "bad_input", f"accessed_at not parseable as ISO-8601: {claim['accessed_at']!r}"
        )

    # Freshness: use claim's published_at, otherwise consult sidecar meta.
    published_value = claim.get("published_at")
    if not published_value and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            published_value = meta.get("published_at")
        except (OSError, json.JSONDecodeError):
            published_value = None

    if published_value:
        published = _parse_iso(published_value)
        if published is not None:
            age_days = (accessed - published).days
            if age_days > max_age_days:
                return Verdict(
                    False,
                    "stale",
                    (
                        f"source published_at {published_value} is {age_days} days "
                        f"before accessed_at (max {max_age_days})"
                    ),
                )

    return Verdict(True, "ok", "quote present, source within freshness window")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a research claim.")
    parser.add_argument(
        "--claim-file",
        type=Path,
        help="Path to a JSON file containing the claim record. "
        "If omitted, the script reads JSON from stdin.",
    )
    parser.add_argument(
        "--references-dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Directory containing snapshot files (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Freshness threshold in days (default: {DEFAULT_MAX_AGE_DAYS})",
    )
    args = parser.parse_args()

    try:
        if args.claim_file:
            raw = args.claim_file.read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        claim = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading claim: {exc}", file=sys.stderr)
        return 2

    verdict = validate_claim(claim, args.references_dir, args.max_age_days)
    print(json.dumps({"verdict": verdict.code, "ok": verdict.ok, "reason": verdict.reason}))
    if verdict.code == "bad_input":
        return 2
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
