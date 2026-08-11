#!/usr/bin/env python3
"""Visual diff: compare prototype HTML screenshots against implementation.

Uses Playwright to render both prototype and implementation at multiple
viewport sizes, then computes pixel-level differences with anti-aliasing
awareness for sub-1% precision.

Requires: playwright (pip install playwright && playwright install chromium)
Optional: Pillow (pip install Pillow) for pixel-accurate diff + diff images

Exit codes:
  0 — visual match (diff below threshold)
  1 — visual mismatch (diff exceeds threshold)
  2 — usage error or missing dependency
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


VIEWPORTS = [
    {"name": "mobile", "width": 375, "height": 812},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "desktop", "width": 1440, "height": 900},
]

DEFAULT_THRESHOLD = 1.0  # 1% — sub-1% precision target

# CSS injected into every page to stabilize rendering for comparison
_STABILIZE_CSS = """
*, *::before, *::after {
  animation-duration: 0s !important;
  animation-delay: 0s !important;
  transition-duration: 0s !important;
  transition-delay: 0s !important;
  caret-color: transparent !important;
}
/* Hide scrollbars (differ across OS/themes) */
::-webkit-scrollbar { display: none !important; }
* { scrollbar-width: none !important; }
"""


def _playwright_importable() -> bool:
    """True iff `playwright.sync_api` imports (lazy — never at module load)."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _check_playwright() -> bool:
    """Report whether Playwright is available; auto-install only on opt-in.

    A review/CI gate must never mutate its environment or reach the network as a
    silent side effect (ISSUE-049). When Playwright is missing, the heavy
    `pip install playwright` + `playwright install chromium` provisioning runs
    ONLY when the operator sets ``KIT_ALLOW_BROWSER_INSTALL=1``. Otherwise the
    gate reports "browser unavailable" to stderr and returns False so the caller
    takes its existing skip/degrade path. The diagnostic goes to stderr; stdout
    stays clean for machine-readable output.
    """
    if _playwright_importable():
        return True

    if os.environ.get("KIT_ALLOW_BROWSER_INSTALL") != "1":
        print(
            "browser unavailable — skipping visual diff "
            "(set KIT_ALLOW_BROWSER_INSTALL=1 to auto-install Playwright + Chromium)",
            file=sys.stderr,
        )
        return False

    # Opted in: heavy provisioning (network + subprocess) is expected here.
    try:
        subprocess.run(["pip", "install", "playwright"], capture_output=True, timeout=60)
        subprocess.run(["playwright", "install", "chromium"], capture_output=True, timeout=120)
    except Exception:
        return False
    return _playwright_importable()


# ── Anti-aliasing aware pixel diff ──────────────────────────────────


def _color_distance_sq(c1: tuple, c2: tuple) -> int:
    """Squared color distance (Euclidean in RGB space, ignoring alpha for speed)."""
    return (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2


def _is_antialiased(
    px, x: int, y: int, w: int, h: int, other_px, color_threshold_sq: int,
) -> bool:
    """Detect if a pixel is anti-aliased by checking neighbors.

    A pixel is anti-aliased if:
    - It has ≥2 neighbors in the same image that differ significantly
    - OR it has ≥2 neighbors in the other image that are similar to it

    This is a simplified version of the pixelmatch algorithm.
    """
    same_different = 0
    other_similar = 0
    center = px[x, y]

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                # Check if neighbor in same image is different
                neighbor = px[nx, ny]
                if _color_distance_sq(center, neighbor) > color_threshold_sq:
                    same_different += 1
                # Check if neighbor in other image is similar
                other_neighbor = other_px[nx, ny]
                if _color_distance_sq(center, other_neighbor) < color_threshold_sq:
                    other_similar += 1

    # Anti-aliased: edge pixel (many different neighbors) or blending pixel
    return same_different >= 2 or other_similar >= 2


def _pixel_diff(img1_bytes: bytes, img2_bytes: bytes, output_diff: str | None = None) -> dict:
    """Anti-aliasing aware pixel diff for sub-1% precision.

    Algorithm (inspired by pixelmatch):
    1. Compare each pixel pair
    2. If colors differ beyond threshold, check if anti-aliased
    3. Anti-aliased pixels are NOT counted as diff
    4. Only truly different pixels are counted

    Optionally saves a diff image highlighting mismatched pixels in red.
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
            im1 = im1.resize((w, h), Image.LANCZOS)
        if im2.size != (w, h):
            im2 = im2.resize((w, h), Image.LANCZOS)

        px1 = im1.load()
        px2 = im2.load()
        total = w * h
        diff_count = 0

        # Color threshold: per-channel tolerance of 20 → squared distance = 20²*3 = 1200
        color_threshold = 20
        color_threshold_sq = color_threshold * color_threshold * 3

        # Create diff image if requested
        diff_img = None
        diff_px = None
        if output_diff:
            diff_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            diff_px = diff_img.load()

        for y in range(h):
            for x in range(w):
                c1 = px1[x, y]
                c2 = px2[x, y]
                dist_sq = _color_distance_sq(c1, c2)

                if dist_sq <= color_threshold_sq:
                    # Colors are close enough — match
                    if diff_px is not None:
                        # Dim the pixel in diff image
                        diff_px[x, y] = (c1[0] // 3, c1[1] // 3, c1[2] // 3, 255)
                    continue

                # Colors differ — check anti-aliasing
                aa1 = _is_antialiased(px1, x, y, w, h, px2, color_threshold_sq)
                aa2 = _is_antialiased(px2, x, y, w, h, px1, color_threshold_sq)

                if aa1 or aa2:
                    # Anti-aliased pixel — not a real diff
                    if diff_px is not None:
                        diff_px[x, y] = (255, 255, 0, 128)  # Yellow = AA
                    continue

                # Real diff
                diff_count += 1
                if diff_px is not None:
                    diff_px[x, y] = (255, 0, 0, 255)  # Red = real diff

        if diff_img and output_diff:
            diff_img.save(output_diff)

        pct = (diff_count / total * 100) if total > 0 else 0
        return {
            "diff_percent": round(pct, 3),
            "total_pixels": total,
            "diff_pixels": diff_count,
            "aa_aware": True,
        }

    except ImportError:
        # Fallback: byte-level comparison (less accurate)
        min_len = min(len(img1_bytes), len(img2_bytes))
        max_len = max(len(img1_bytes), len(img2_bytes))
        diff_bytes = sum(1 for i in range(min_len) if img1_bytes[i] != img2_bytes[i])
        diff_bytes += max_len - min_len
        pct = (diff_bytes / max_len * 100) if max_len > 0 else 0
        return {
            "diff_percent": round(pct, 3),
            "total_pixels": max_len,
            "diff_pixels": diff_bytes,
            "aa_aware": False,
            "method": "byte-level (install Pillow for pixel-accurate diff)",
        }


# ── Stable screenshot capture ───────────────────────────────────────


def take_screenshots(
    target: str,
    viewports: list[dict] | None = None,
) -> list[dict]:
    """Take stable screenshots of an HTML file or URL at multiple viewports.

    Stabilization:
    - Disables all CSS animations/transitions
    - Waits for font loading to complete
    - Waits for all images to load
    - Hides scrollbars (OS-dependent appearance)
    - Uses 2x device pixel ratio for sub-pixel accuracy
    """
    if viewports is None:
        viewports = VIEWPORTS

    from playwright.sync_api import sync_playwright

    if target.startswith("http://") or target.startswith("https://"):
        url = target
    else:
        url = f"file://{target}"

    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in viewports:
            page = browser.new_page(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=2,
            )

            page.goto(url, wait_until="networkidle", timeout=30000)

            # Inject stabilization CSS
            page.add_style_tag(content=_STABILIZE_CSS)

            # Wait for fonts to load
            page.evaluate("() => document.fonts.ready")

            # Wait for all images to load
            page.evaluate("""() => {
                const images = Array.from(document.querySelectorAll('img'));
                return Promise.all(images.map(img => {
                    if (img.complete) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                    });
                }));
            }""")

            # Final settle time for layout reflow after font/image load
            page.wait_for_timeout(200)

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


# ── Diff orchestration ──────────────────────────────────────────────


def visual_diff(
    prototype_path: str,
    implementation_path: str,
    viewports: list[dict] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    output_dir: str | None = None,
) -> dict:
    """Compare prototype and implementation at multiple viewports.

    Saves screenshots and diff images for debugging.
    """
    proto_shots = take_screenshots(prototype_path, viewports)
    impl_shots = take_screenshots(implementation_path, viewports)

    results: list[dict] = []
    all_pass = True

    out_path = Path(output_dir) if output_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    for proto, impl in zip(proto_shots, impl_shots):
        diff_img_path = None
        if out_path:
            diff_img_path = str(out_path / f"{proto['viewport_name']}_diff.png")

        diff = _pixel_diff(proto["screenshot"], impl["screenshot"], diff_img_path)
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
            "aa_aware": diff.get("aa_aware", False),
            "pass": passes,
            "threshold": threshold,
        }

        if out_path:
            proto_file = out_path / f"{proto['viewport_name']}_prototype.png"
            impl_file = out_path / f"{proto['viewport_name']}_implementation.png"
            proto_file.write_bytes(proto["screenshot"])
            impl_file.write_bytes(impl["screenshot"])
            entry["prototype_screenshot"] = str(proto_file)
            entry["implementation_screenshot"] = str(impl_file)
            if diff_img_path:
                entry["diff_image"] = diff_img_path

        results.append(entry)

    return {
        "results": results,
        "all_pass": all_pass,
        "viewports_tested": len(results),
    }


def visual_diff_against_renders(
    implementation_path: str,
    figma_renders: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
    output_dir: str | None = None,
) -> dict:
    """Compare implementation screenshots against Figma-rendered PNGs.

    This is the highest-fidelity comparison: the Figma render IS the
    ground truth, with no intermediate conversion (no figma-converter).

    For each Figma render, takes an implementation screenshot at a matching
    viewport width and compares pixels.
    """
    out_path = Path(output_dir) if output_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    # Determine viewport for each render based on width
    render_viewports = []
    for r in figma_renders:
        w = r.get("width", 1440)
        if w <= 0:
            w = 1440
        render_viewports.append({"name": r["name"], "width": int(w), "height": 900})

    impl_shots = take_screenshots(implementation_path, render_viewports)

    results: list[dict] = []
    all_pass = True

    for render, impl in zip(figma_renders, impl_shots):
        render_bytes = Path(render["path"]).read_bytes()
        diff_img_path = None
        if out_path:
            diff_img_path = str(out_path / f"{render['name']}_diff.png")

        diff = _pixel_diff(render_bytes, impl["screenshot"], diff_img_path)
        passes = diff["diff_percent"] <= threshold
        if not passes:
            all_pass = False

        entry = {
            "viewport": render["name"],
            "width": impl["width"],
            "height": impl["height"],
            "diff_percent": diff["diff_percent"],
            "diff_pixels": diff["diff_pixels"],
            "total_pixels": diff["total_pixels"],
            "aa_aware": diff.get("aa_aware", False),
            "pass": passes,
            "threshold": threshold,
            "source": "figma-render",
        }

        if out_path:
            impl_file = out_path / f"{render['name']}_implementation.png"
            impl_file.write_bytes(impl["screenshot"])
            entry["figma_render"] = render["path"]
            entry["implementation_screenshot"] = str(impl_file)
            if diff_img_path:
                entry["diff_image"] = diff_img_path

        results.append(entry)

    return {
        "results": results,
        "all_pass": all_pass,
        "viewports_tested": len(results),
        "source": "figma-render",
    }


# ── File discovery ──────────────────────────────────────────────────


def find_figma_renders(project_path: Path) -> list[dict]:
    """Find Figma-rendered reference images (absolute source of truth).

    Returns list of {path, breakpoint} from figma-export/renders/.
    These are PNG images rendered directly by Figma's Image Export API.
    """
    renders_dir = project_path / "figma-export" / "renders"
    if not renders_dir.is_dir():
        return []

    renders = []
    for png in sorted(renders_dir.glob("*@2x.png")):
        # Detect breakpoint from design_data.json if available
        renders.append({"path": str(png.resolve()), "name": png.stem.replace("@2x", "")})

    # Also check design_data.json for breakpoint mapping
    dd = project_path / "figma-export" / "design_data.json"
    if dd.exists():
        try:
            data = json.loads(dd.read_text(encoding="utf-8"))
            render_meta = {r["name"]: r for r in data.get("summary", {}).get("frame_renders", [])}
            for r in renders:
                meta = render_meta.get(r["name"], {})
                r["breakpoint"] = meta.get("breakpoint", "desktop")
                r["width"] = meta.get("width", 0)
        except (json.JSONDecodeError, OSError):
            pass

    return renders


def find_prototype_html(project_path: Path) -> str | None:
    """Find the main prototype HTML file (fallback when no Figma renders)."""
    candidates = [
        project_path / "prototype" / "index.html",
        project_path / "prototype" / "screens" / "index.html",
        project_path / "prototype-mobile" / "src" / "App.tsx",
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())

    screens = project_path / "prototype" / "screens"
    if screens.is_dir():
        html_files = sorted(screens.glob("*.html"))
        if html_files:
            return str(html_files[0].resolve())

    return None


def _check_dev_server(port: int) -> bool:
    """Check if a dev server is running on a port."""
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(f"http://localhost:{port}", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def find_implementation_html(project_path: Path) -> str | None:
    """Find the implementation entry point.

    Priority: running dev server → built output → static HTML.
    """
    dev_ports = [3000, 5173, 8080, 4200, 3001, 5174]
    for port in dev_ports:
        if _check_dev_server(port):
            return f"http://localhost:{port}"

    candidates = [
        project_path / "dist" / "index.html",
        project_path / "build" / "index.html",
        project_path / "out" / "index.html",
        project_path / ".next" / "server" / "pages" / "index.html",
        project_path / "public" / "index.html",
        project_path / "index.html",
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
    parser.add_argument("--project-path", required=True, help="Path to project root")
    parser.add_argument("--prototype", default=None, help="Path to prototype HTML")
    parser.add_argument("--implementation", default=None, help="Path to implementation HTML")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Max allowed diff %% (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--output-dir", default=None, help="Directory to save debug screenshots")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--viewports", default=None,
                        help="Comma-separated viewport names (default: mobile,tablet,desktop)")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    project_path = Path(args.project_path).resolve()

    # Determine if Figma data exists — if so, visual diff is REQUIRED (not optional)
    has_figma_data = (
        (project_path / "figma-export" / "design_data.json").exists()
        or (project_path / "figma-export" / "renders").is_dir()
    )

    if not _check_playwright():
        if has_figma_data:
            print("FAIL: Playwright not installed but Figma data exists — visual diff is REQUIRED")
            print("  Install: pip install playwright && playwright install chromium")
            return 1
        print("SKIP: Playwright not installed and no Figma data — visual diff skipped")
        return 0

    impl = args.implementation or find_implementation_html(project_path)
    if not impl:
        if has_figma_data:
            print("FAIL: No implementation HTML/URL found but Figma data exists — build the project first")
            return 1
        print("SKIP: No implementation HTML/URL found — visual diff skipped")
        return 0

    output_dir = args.output_dir or str(project_path / "figma-export" / "visual-diff")

    viewports = VIEWPORTS
    if args.viewports:
        names = [n.strip() for n in args.viewports.split(",")]
        viewports = [v for v in VIEWPORTS if v["name"] in names]

    # Priority: prototype HTML (same Chromium renderer = fair comparison)
    proto = args.prototype or find_prototype_html(project_path)

    if proto:
        # BEST: Both rendered by Chromium — no renderer differences
        print(f"Same-renderer comparison: prototype HTML vs implementation (both Chromium)")
        result = visual_diff(proto, impl, viewports, args.threshold, output_dir)
    else:
        # Fallback: compare against Figma render PNGs (cross-renderer, higher threshold)
        figma_renders = find_figma_renders(project_path)
        if figma_renders:
            cross_threshold = max(args.threshold, 5.0)  # Cross-renderer needs higher tolerance
            print(f"Cross-renderer comparison: Figma PNG vs implementation (threshold: {cross_threshold}%)")
            result = visual_diff_against_renders(impl, figma_renders, cross_threshold, output_dir)
        else:
            if has_figma_data:
                print("FAIL: Figma data exists but no prototype HTML or renders found")
                return 1
            print("SKIP: No prototype HTML or Figma renders found — visual diff skipped")
            return 0

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        aa_label = " (AA-aware)" if result["results"] and result["results"][0].get("aa_aware") else ""
        print(f"Visual Diff{aa_label}: {result['viewports_tested']} viewport(s) (threshold: {args.threshold}%)")
        print()
        for r in result["results"]:
            icon = "PASS" if r["pass"] else "FAIL"
            print(f"  {icon}: {r['viewport']} ({r['width']}x{r['height']}) — {r['diff_percent']}% diff")
            if not r["pass"] and r.get("diff_image"):
                print(f"        Diff image: {r['diff_image']}")
        print()
        if result["all_pass"]:
            print(f"PASS: Implementation matches prototype within {args.threshold}% at all viewports")
        else:
            print("FAIL: Visual mismatch — review diff images in figma-export/visual-diff/")
            print("  Red pixels = real differences, Yellow pixels = anti-aliasing (ignored)")

    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
