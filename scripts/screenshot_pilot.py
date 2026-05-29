#!/usr/bin/env python3
"""Screenshot a local HTML file for /uiux pilot review.

Used by Phase 5A of the /uiux skill to render pilot screens so the agent
can self-critique the visual output before presenting to the user.

Tries Playwright (Chromium) first — most reliable cross-platform.
Falls back to headless Google Chrome / Chromium binaries if present.
Exits non-zero with install instructions if no backend is available;
the calling skill is expected to handle this gracefully and proceed
without the self-critique step.

Usage:
    python3 scripts/screenshot_pilot.py <html_path>
    python3 scripts/screenshot_pilot.py <html_path> --out <png_path>
    python3 scripts/screenshot_pilot.py <html_path> --viewport 375x812
    python3 scripts/screenshot_pilot.py <html_path> --full-page
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_viewport(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


def try_playwright(html: Path, out: Path, viewport: tuple[int, int], full_page: bool) -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return False
    url = html.absolute().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(500)
            page.screenshot(path=str(out), full_page=full_page)
        finally:
            browser.close()
    return out.exists()


def try_chrome(html: Path, out: Path, viewport: tuple[int, int]) -> bool:
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    url = html.absolute().as_uri()
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html", type=Path, help="Path to local HTML file")
    ap.add_argument("--out", type=Path, help="Output PNG path (default: <html>.png)")
    ap.add_argument("--viewport", default="1280x800", help="Viewport WxH (default: 1280x800)")
    ap.add_argument("--full-page", action="store_true", help="Capture full scrollable page")
    args = ap.parse_args()

    if not args.html.exists():
        print(f"error: {args.html} not found", file=sys.stderr)
        return 2

    out = args.out or args.html.with_suffix(".png")
    viewport = parse_viewport(args.viewport)

    if try_playwright(args.html, out, viewport, args.full_page):
        print(f"screenshot: {out} (playwright)")
        return 0
    if try_chrome(args.html, out, viewport):
        print(f"screenshot: {out} (headless chrome)")
        return 0

    print(
        "no screenshot backend available. install one of:\n"
        "  - playwright:  uv add --dev playwright && uv run playwright install chromium\n"
        "  - Google Chrome (macOS/Linux/Windows)\n"
        "  - chromium-browser (Linux)",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
