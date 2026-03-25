#!/usr/bin/env python3
"""Check for claude-dev-kit updates.

Compares local VERSION with the remote repository's VERSION.
Caches the result for 24h to avoid repeated network calls.
Supports snooze to suppress update notifications.

Usage:
    python3 scripts/kit_update_check.py              # check and print status
    python3 scripts/kit_update_check.py --snooze 7d  # snooze for 7 days
    python3 scripts/kit_update_check.py --reset       # reset snooze

Exit codes:
    0 = up to date or snoozed
    1 = update available
    2 = error (network, parse, etc.)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = KIT_ROOT / "VERSION"
STATE_DIR = Path.home() / ".claude-kit"
CACHE_FILE = STATE_DIR / "update-cache.json"
SNOOZE_FILE = STATE_DIR / "update-snooze.json"

CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds

SNOOZE_DURATIONS = {
    "24h": 24 * 60 * 60,
    "48h": 48 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}


def _local_version() -> str:
    """Read the local VERSION file."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def _remote_version() -> str | None:
    """Fetch the remote VERSION by checking the git remote."""
    try:
        # Get the remote URL of the kit repo
        remote = subprocess.run(
            ["git", "-C", str(KIT_ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if remote.returncode != 0:
            return None

        # Fetch the VERSION file content from remote main branch
        result = subprocess.run(
            ["git", "-C", str(KIT_ROOT), "ls-remote", "origin", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None

        remote_sha = result.stdout.strip().split()[0] if result.stdout.strip() else None
        if not remote_sha:
            return None

        # Try to get the VERSION file from the remote
        result = subprocess.run(
            ["git", "-C", str(KIT_ROOT), "fetch", "origin", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )

        result = subprocess.run(
            ["git", "-C", str(KIT_ROOT), "show", "origin/main:VERSION"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()

        # Fallback: try origin/master
        result = subprocess.run(
            ["git", "-C", str(KIT_ROOT), "show", "origin/master:VERSION"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()

        return None
    except Exception:
        return None


def _read_cache() -> dict | None:
    """Read the update cache."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if time.time() - data.get("timestamp", 0) > CACHE_TTL:
            return None  # expired
        return data
    except Exception:
        return None


def _write_cache(local: str, remote: str | None) -> None:
    """Write the update cache."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({
            "timestamp": time.time(),
            "local_version": local,
            "remote_version": remote,
        }, indent=2) + "\n",
        encoding="utf-8",
    )


def _is_snoozed() -> bool:
    """Check if update notifications are snoozed.

    Even during snooze, refreshes the cache if expired so we can detect
    new versions. If a newer version than the snoozed one appears, the
    snooze is automatically reset.
    """
    if not SNOOZE_FILE.exists():
        return False
    try:
        data = json.loads(SNOOZE_FILE.read_text(encoding="utf-8"))
        until = data.get("until", 0)
        snoozed_version = data.get("version", "")
        if time.time() >= until:
            return False  # expired

        # Refresh cache if expired, even during snooze
        cache = _read_cache()
        if cache is None:
            remote = _remote_version()
            local = _local_version()
            _write_cache(local, remote)
            if remote and remote != snoozed_version:
                return False  # new version found, reset snooze
        elif cache.get("remote_version") and cache["remote_version"] != snoozed_version:
            return False  # cached version differs, reset snooze

        return True
    except Exception:
        return False


def _set_snooze(duration_key: str, version: str) -> None:
    """Set snooze for the given duration."""
    seconds = SNOOZE_DURATIONS.get(duration_key)
    if not seconds:
        print(f"Invalid snooze duration: {duration_key}. Use: {', '.join(SNOOZE_DURATIONS)}", file=sys.stderr)
        sys.exit(2)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SNOOZE_FILE.write_text(
        json.dumps({
            "until": time.time() + seconds,
            "version": version,
            "duration": duration_key,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Update notifications snoozed for {duration_key}.")


def _reset_snooze() -> None:
    """Reset snooze."""
    if SNOOZE_FILE.exists():
        SNOOZE_FILE.unlink()
    print("Snooze reset.")


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string into a tuple for comparison."""
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


def check_update() -> tuple[bool, str, str | None]:
    """Check for updates. Returns (update_available, local_ver, remote_ver)."""
    local = _local_version()

    # Try cache first
    cache = _read_cache()
    if cache:
        remote = cache.get("remote_version")
    else:
        remote = _remote_version()
        _write_cache(local, remote)

    if remote is None:
        return False, local, None

    update_available = _parse_version(remote) > _parse_version(local)
    return update_available, local, remote


def main() -> None:
    args = sys.argv[1:]

    if "--reset" in args:
        _reset_snooze()
        return

    if "--snooze" in args:
        idx = args.index("--snooze")
        if idx + 1 >= len(args):
            print("Usage: --snooze <24h|48h|7d>", file=sys.stderr)
            sys.exit(2)
        _, local, remote = check_update()
        _set_snooze(args[idx + 1], remote or local)
        return

    # Check for updates
    if _is_snoozed():
        sys.exit(0)

    update_available, local, remote = check_update()

    if remote is None:
        # Could not reach remote, silently pass
        sys.exit(0)

    if update_available:
        print(f"claude-dev-kit update available: {local} → {remote}")
        print(f"  Update:  cd .claude-kit && git pull")
        print(f"  Snooze:  python3 scripts/kit_update_check.py --snooze 7d")
        sys.exit(1)
    else:
        # Up to date, print nothing
        sys.exit(0)


if __name__ == "__main__":
    main()
