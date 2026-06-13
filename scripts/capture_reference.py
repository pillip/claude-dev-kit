#!/usr/bin/env python3
"""Capture a reference page URL to PNG for image-grounded /uiux input.

ISSUE-011: Phase 2 step 6.5 of the uiux skill no longer uses WebFetch to
"read" visual references — WebFetch returns parsed text, which means extracted
"hex colors" and "font pairings" were fabrications. References must arrive as
actual pixels.

Two paths:
- user-provided image URL / local path → /uiux Reads the image directly
- HTML page URL → this script captures it to PNG via headless browser

Uses the same backend probing logic as screenshot_pilot.py (Playwright → headless
Chrome/Chromium). Saves under docs/references/ by default.

Exit codes:
    0 = success, PNG written
    2 = bad input (URL missing, etc.)
    3 = no screenshot backend available

Usage:
    python3 scripts/capture_reference.py https://linear.app/
    python3 scripts/capture_reference.py https://linear.app/ --out docs/references/linear.png
    python3 scripts/capture_reference.py https://linear.app/ --slug linear-landing
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_DIR = Path("docs/references")
DEFAULT_VIEWPORT = (1440, 900)


def slug_from_url(url: str) -> str:
    """Derive a filesystem-safe slug from a URL."""
    parsed = urlparse(url)
    base = parsed.netloc.replace(".", "-") or "ref"
    path = re.sub(r"[^a-zA-Z0-9]+", "-", parsed.path).strip("-")
    if path:
        base = f"{base}-{path}"
    return base[:80].strip("-") or "ref"


def try_playwright(url: str, out: Path, viewport: tuple[int, int]) -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(
                viewport={"width": viewport[0], "height": viewport[1]}
            )
            page.goto(url, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(800)
            page.screenshot(path=str(out), full_page=False)
        finally:
            browser.close()
    return out.exists()


def try_chrome(url: str, out: Path, viewport: tuple[int, int]) -> bool:
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for binary in candidates:
        path = shutil.which(binary) or (binary if Path(binary).exists() else None)
        if not path:
            continue
        try:
            subprocess.run(
                [
                    path,
                    "--headless=new",
                    f"--screenshot={out}",
                    f"--window-size={viewport[0]},{viewport[1]}",
                    "--hide-scrollbars",
                    "--no-sandbox",
                    url,
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            if out.exists():
                return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Capture reference page to PNG")
    ap.add_argument("url", help="Page URL to capture")
    ap.add_argument(
        "--out",
        type=Path,
        help=f"Output PNG path (default: {DEFAULT_DIR}/<slug>.png)",
    )
    ap.add_argument(
        "--slug",
        help="Filename slug (default: derived from URL host+path)",
    )
    ap.add_argument(
        "--viewport",
        default=f"{DEFAULT_VIEWPORT[0]}x{DEFAULT_VIEWPORT[1]}",
        help=f"Viewport WxH (default: {DEFAULT_VIEWPORT[0]}x{DEFAULT_VIEWPORT[1]})",
    )
    args = ap.parse_args(argv)

    if not args.url.startswith(("http://", "https://")):
        print(
            f"error: URL must start with http:// or https://, got {args.url!r}",
            file=sys.stderr,
        )
        return 2

    if args.out:
        out = args.out
    else:
        slug = args.slug or slug_from_url(args.url)
        out = DEFAULT_DIR / f"{slug}.png"

    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        w, h = args.viewport.lower().split("x")
        viewport = (int(w), int(h))
    except ValueError:
        print(f"error: bad --viewport {args.viewport!r}", file=sys.stderr)
        return 2

    if try_playwright(args.url, out, viewport):
        print(f"reference: {out} (playwright)")
        return 0
    if try_chrome(args.url, out, viewport):
        print(f"reference: {out} (headless chrome)")
        return 0

    print(
        "no screenshot backend available — cannot capture a reference page.\n"
        "Either install one of:\n"
        "  - playwright:  uv add --dev playwright && uv run playwright install chromium\n"
        "  - Google Chrome (macOS/Linux/Windows)\n"
        "  - chromium-browser (Linux)\n"
        "\n"
        "Or pass image paths directly to /uiux (image URLs or local files) so it\n"
        "can Read them as pixels without a browser.",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
