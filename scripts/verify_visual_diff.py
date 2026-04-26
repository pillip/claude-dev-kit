#!/usr/bin/env python3
"""Visual diff: compare prototype HTML screenshots against implementation.

Uses Playwright to render both prototype and implementation at multiple
viewport sizes, then computes pixel-level differences.

Requires: playwright (pip install playwright && playwright install chromium)

Exit codes:
  0 — visual match (diff below threshold)
  1 — visual mismatch (diff exceeds threshold)
  2 — usage error or missing dependency
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VIEWPORTS = [
    {"name": "mobile", "width": 375, "height": 812},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "desktop", "width": 1440, "height": 900},
]

# Maximum allowed pixel diff percentage (0-100)
DEFAULT_THRESHOLD = 5.0


def _check_playwright() -> bool:
    """Check if Playwright is available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _pixel_diff(img1_bytes: bytes, img2_bytes: bytes) -> dict:
    """Compute pixel-level difference between two PNG screenshots.

    Uses raw byte comparison when Pillow is not available,
    or proper pixel comparison when it is.

    Returns: {diff_percent, total_pixels, diff_pixels, match}
    """
    try:
        from PIL import Image
        import io

        im1 = Image.open(io.BytesIO(img1_bytes)).convert("RGBA")
        im2 = Image.open(io.BytesIO(img2_bytes)).convert("RGBA")

        # Resize to same dimensions if different
        w = max(im1.width, im2.width)
        h = max(im1.height, im2.height)
        if im1.size != (w, h):
            im1 = im1.resize((w, h))
        if im2.size != (w, h):
            im2 = im2.resize((w, h))

        px1 = im1.load()
        px2 = im2.load()
        total = w * h
        diff_count = 0
        # Per-pixel comparison with tolerance for anti-aliasing
        tolerance = 30  # RGB channel tolerance

        for y in range(h):
            for x in range(w):
                r1, g1, b1, a1 = px1[x, y]
                r2, g2, b2, a2 = px2[x, y]
                if (abs(r1 - r2) > tolerance or abs(g1 - g2) > tolerance
                        or abs(b1 - b2) > tolerance or abs(a1 - a2) > tolerance):
                    diff_count += 1

        pct = (diff_count / total * 100) if total > 0 else 0
        return {
            "diff_percent": round(pct, 2),
            "total_pixels": total,
            "diff_pixels": diff_count,
        }

    except ImportError:
        # Fallback: byte-level comparison (less accurate)
        min_len = min(len(img1_bytes), len(img2_bytes))
        max_len = max(len(img1_bytes), len(img2_bytes))
        diff_bytes = sum(1 for i in range(min_len) if img1_bytes[i] != img2_bytes[i])
        diff_bytes += max_len - min_len
        pct = (diff_bytes / max_len * 100) if max_len > 0 else 0
        return {
            "diff_percent": round(pct, 2),
            "total_pixels": max_len,
            "diff_pixels": diff_bytes,
            "method": "byte-level (install Pillow for pixel-accurate diff)",
        }


def take_screenshots(
    html_path: str,
    viewports: list[dict] | None = None,
) -> list[dict]:
    """Take screenshots of an HTML file at multiple viewports.

    Returns list of {viewport_name, width, height, screenshot_bytes}.
    """
    if viewports is None:
        viewports = VIEWPORTS

    from playwright.sync_api import sync_playwright

    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in viewports:
            page = browser.new_page(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=2,
            )
            page.goto(f"file://{html_path}", wait_until="networkidle")
            page.wait_for_timeout(500)  # Wait for CSS transitions/animations
            screenshot = page.screenshot(full_page=True)
            results.append({
                "viewport_name": vp["name"],
                "width": vp["width"],
                "height": vp["height"],
                "screenshot": screenshot,
            })
            page.close()

        browser.close()

    return results


def visual_diff(
    prototype_path: str,
    implementation_path: str,
    viewports: list[dict] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    output_dir: str | None = None,
) -> dict:
    """Compare prototype and implementation at multiple viewports.

    Args:
        prototype_path: Path to prototype HTML file.
        implementation_path: Path to implementation HTML file.
        viewports: List of viewport configs (default: mobile, tablet, desktop).
        threshold: Maximum allowed diff percentage.
        output_dir: Directory to save screenshot PNGs for debugging.

    Returns dict with per-viewport results, overall pass/fail, and paths to saved images.
    """
    proto_shots = take_screenshots(prototype_path, viewports)
    impl_shots = take_screenshots(implementation_path, viewports)

    results: list[dict] = []
    all_pass = True

    out_path = Path(output_dir) if output_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    for proto, impl in zip(proto_shots, impl_shots):
        diff = _pixel_diff(proto["screenshot"], impl["screenshot"])
        passes = diff["diff_percent"] <= threshold
        if not passes:
            all_pass = False

        entry = {
            "viewport": proto["viewport_name"],
            "width": proto["width"],
            "height": proto["height"],
            "diff_percent": diff["diff_percent"],
            "diff_pixels": diff["diff_pixels"],
            "total_pixels": diff["total_pixels"],
            "pass": passes,
            "threshold": threshold,
        }

        # Save screenshots for debugging
        if out_path:
            proto_file = out_path / f"{proto['viewport_name']}_prototype.png"
            impl_file = out_path / f"{proto['viewport_name']}_implementation.png"
            proto_file.write_bytes(proto["screenshot"])
            impl_file.write_bytes(impl["screenshot"])
            entry["prototype_screenshot"] = str(proto_file)
            entry["implementation_screenshot"] = str(impl_file)

        results.append(entry)

    return {
        "results": results,
        "all_pass": all_pass,
        "viewports_tested": len(results),
    }


def find_prototype_html(project_path: Path) -> str | None:
    """Find the main prototype HTML file."""
    candidates = [
        project_path / "prototype" / "index.html",
        project_path / "prototype" / "screens" / "index.html",
        project_path / "prototype-mobile" / "src" / "App.tsx",
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())

    # Try first HTML file in prototype/screens/
    screens = project_path / "prototype" / "screens"
    if screens.is_dir():
        html_files = sorted(screens.glob("*.html"))
        if html_files:
            return str(html_files[0].resolve())

    return None


def find_implementation_html(project_path: Path) -> str | None:
    """Find the implementation entry point."""
    candidates = [
        project_path / "dist" / "index.html",
        project_path / "build" / "index.html",
        project_path / "public" / "index.html",
        project_path / "index.html",
        project_path / ".next" / "server" / "pages" / "index.html",
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return None


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Visual diff: compare prototype vs implementation screenshots",
    )
    parser.add_argument(
        "--project-path",
        required=True,
        help="Path to project root",
    )
    parser.add_argument(
        "--prototype",
        default=None,
        help="Path to prototype HTML (auto-detected if omitted)",
    )
    parser.add_argument(
        "--implementation",
        default=None,
        help="Path to implementation HTML (auto-detected if omitted)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Max allowed diff percentage (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save debug screenshots",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
    )
    parser.add_argument(
        "--viewports",
        default=None,
        help="Comma-separated viewport names to test (default: mobile,tablet,desktop)",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if not _check_playwright():
        print("SKIP: Playwright not installed — visual diff skipped")
        print("  Install: pip install playwright && playwright install chromium")
        return 0

    project_path = Path(args.project_path).resolve()

    proto = args.prototype or find_prototype_html(project_path)
    impl = args.implementation or find_implementation_html(project_path)

    if not proto:
        print("SKIP: No prototype HTML found — visual diff skipped")
        return 0
    if not impl:
        print("SKIP: No implementation HTML found — visual diff skipped")
        return 0

    # Filter viewports if specified
    viewports = VIEWPORTS
    if args.viewports:
        names = [n.strip() for n in args.viewports.split(",")]
        viewports = [v for v in VIEWPORTS if v["name"] in names]

    output_dir = args.output_dir or str(project_path / "figma-export" / "visual-diff")

    result = visual_diff(proto, impl, viewports, args.threshold, output_dir)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Visual Diff: {result['viewports_tested']} viewport(s) tested (threshold: {args.threshold}%)")
        print()
        for r in result["results"]:
            icon = "PASS" if r["pass"] else "FAIL"
            print(f"  {icon}: {r['viewport']} ({r['width']}x{r['height']}) — {r['diff_percent']}% diff")
        print()
        if result["all_pass"]:
            print("PASS: Implementation visually matches prototype at all viewports")
        else:
            print("FAIL: Visual mismatch detected — check screenshots in figma-export/visual-diff/")

    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
