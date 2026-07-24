#!/usr/bin/env python3
"""Capture a source URL to a verifiable text snapshot for /brainstorm and /bizanalysis.

ISSUE-018 / SPEC-018: the kit's degraded research path requires every claim
to carry a verbatim quote that can be grep-validated against an on-disk
source. This script is the text-domain analogue of `capture_reference.py`
(ISSUE-011, image-domain): it fetches a URL to a stable HTML snapshot plus
a sidecar JSON metadata file, so a later validator can confirm the quote
actually appears in the page.

Outputs under `docs/references/research/<slug>.{html,meta.json}` by default:
- <slug>.html              — the captured HTML body
- <slug>.meta.json         — {source_url, accessed_at, published_at?, slug,
                              backend, byte_count}

Backends tried in order:
- Playwright (Chromium headless) — handles JS-rendered pages
- headless Chrome / Chromium binary — same as capture_reference.py
- urllib (no JS) — text-only fallback; flagged in metadata

Exit codes:
    0 = success, snapshot + metadata written
    2 = bad input (URL missing, malformed args)
    3 = no fetch backend available

Usage:
    python3 scripts/capture_source.py https://example.com/report
    python3 scripts/capture_source.py https://example.com/report --slug acme-2025
    python3 scripts/capture_source.py https://example.com/report --published 2025-03-01
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

DEFAULT_DIR = Path("docs/references/research")

META_TAG_PATTERNS = [
    # OpenGraph / Schema.org — order matters: most authoritative first
    r'<meta\s+property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+property=["\']og:published_time["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+name=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+name=["\']pubdate["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+name=["\']publish-date["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+name=["\']publication_date["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+itemprop=["\']datePublished["\']\s+content=["\']([^"\']+)["\']',
    r'<time[^>]+itemprop=["\']datePublished["\'][^>]+datetime=["\']([^"\']+)["\']',
    r'<time[^>]+datetime=["\']([^"\']+)["\']',
]


def slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    base = parsed.netloc.replace(".", "-") or "src"
    path = re.sub(r"[^a-zA-Z0-9]+", "-", parsed.path).strip("-")
    if path:
        base = f"{base}-{path}"
    return base[:80].strip("-") or "src"


def extract_published_at(html: str) -> Optional[str]:
    """Heuristically extract a published-at timestamp from HTML meta tags.

    Returns ISO-8601-ish string as it appears in the page (no normalization);
    callers compare against an accessed_at timestamp using string-prefix or
    parsed datetime as they see fit. Returns None if no candidate is found.
    """
    for pattern in META_TAG_PATTERNS:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def try_playwright(url: str) -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            content = page.content()
        finally:
            browser.close()
    return content


def try_chrome(url: str) -> Optional[str]:
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
            result = subprocess.run(
                [
                    path,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def try_urllib(url: str) -> Optional[str]:
    """Plain-HTTP fallback. No JS execution. Marked in metadata as 'urllib'."""
    try:
        from urllib.request import Request, urlopen

        req = Request(url, headers={"User-Agent": "Mozilla/5.0 claude-kit-capture"})
        with urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception:
        return None


def capture(url: str) -> tuple[Optional[str], str]:
    """Return (html, backend_name). html=None if all backends failed."""
    html = try_playwright(url)
    if html is not None:
        return html, "playwright"
    html = try_chrome(url)
    if html is not None:
        return html, "chrome"
    html = try_urllib(url)
    if html is not None:
        return html, "urllib"
    return None, "none"


def write_outputs(
    html: str,
    backend: str,
    url: str,
    slug: str,
    out_dir: Path,
    published_override: Optional[str] = None,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{slug}.html"
    meta_path = out_dir / f"{slug}.meta.json"
    html_path.write_text(html, encoding="utf-8")
    meta = {
        "source_url": url,
        "slug": slug,
        "accessed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "published_at": published_override or extract_published_at(html),
        "backend": backend,
        "byte_count": len(html.encode("utf-8")),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return html_path, meta_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a URL to a text snapshot for verifiable research grounding."
    )
    parser.add_argument("url", help="URL to capture")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_DIR),
        help=f"Output directory (default: {DEFAULT_DIR})",
    )
    parser.add_argument("--slug", default=None, help="Override slug derivation")
    parser.add_argument(
        "--published",
        default=None,
        help="Override published_at (ISO-8601). Use when page lacks meta tags.",
    )
    args = parser.parse_args()

    if not args.url or not args.url.startswith(("http://", "https://")):
        print("Error: a valid http(s) URL is required.", file=sys.stderr)
        return 2

    slug = args.slug or slug_from_url(args.url)
    html, backend = capture(args.url)
    if html is None:
        print(
            "Error: no fetch backend available. Install Playwright or Chromium, "
            "or pass image/HTML directly per docs/references/research/.gitkeep.",
            file=sys.stderr,
        )
        return 3

    html_path, meta_path = write_outputs(
        html, backend, args.url, slug, Path(args.out_dir), args.published
    )
    print(f"snapshot: {html_path}")
    print(f"metadata: {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
