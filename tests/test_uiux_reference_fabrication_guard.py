"""Regression guard for ISSUE-011.

WebFetch returns parsed text, not pixels. The uiux skills must not instruct
the model to "WebFetch a URL and extract hex colors / fonts / proportions" —
that pattern fabricates values regardless of the disclaimer.

This test scans the three uiux skill templates and the docs for any
remaining "WebFetch ... extract" instruction shape. Any explicit negation
("NO WebFetch for visual extraction") is allowed; the goal is to prevent
re-introduction of the fabrication shape.
"""

from __future__ import annotations

import re
from pathlib import Path

UIUX_TMPL_PATHS = [
    Path("skills/uiux/SKILL.md.tmpl"),
    Path("skills/mobile-uiux/SKILL.md.tmpl"),
    Path("skills/desktop-uiux/SKILL.md.tmpl"),
]

# Forbidden shape: WebFetch followed (within a few words) by extract/extracting,
# in a context where the model is being told to derive visual specifics.
FABRICATION_SHAPE = re.compile(
    r"WebFetch[^.\n]{0,80}\bextract\b",
    re.IGNORECASE,
)

# Allowed negations — these explicitly tell the model NOT to use WebFetch this way.
NEGATION_TOKENS = ("NO WebFetch", "not WebFetch", "no longer uses WebFetch")


def _is_negation_line(line: str) -> bool:
    return any(tok.lower() in line.lower() for tok in NEGATION_TOKENS)


def test_no_webfetch_extract_pattern_in_uiux_templates():
    offenders: list[tuple[str, int, str]] = []
    for tmpl in UIUX_TMPL_PATHS:
        assert tmpl.exists(), f"missing template: {tmpl}"
        text = tmpl.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if FABRICATION_SHAPE.search(line) and not _is_negation_line(line):
                offenders.append((str(tmpl), line_no, line.strip()))

    assert not offenders, (
        "WebFetch-extract pattern resurfaced in uiux templates "
        "(should be image-grounded only — see ISSUE-011):\n"
        + "\n".join(f"  {p}:{n}: {ln}" for p, n, ln in offenders)
    )


def test_uiux_templates_reference_capture_script():
    """Every uiux template should mention scripts/capture_reference.py so users
    have a non-WebFetch path for URL-based references."""
    for tmpl in UIUX_TMPL_PATHS:
        text = tmpl.read_text(encoding="utf-8")
        assert "capture_reference.py" in text, (
            f"{tmpl} does not mention scripts/capture_reference.py; "
            "Path (b) URL → PNG fallback is missing."
        )


def test_uiux_templates_have_skip_path():
    """Every uiux template must allow proceeding without references (Path c)
    so missing browser backend / no images doesn't silently fabricate."""
    for tmpl in UIUX_TMPL_PATHS:
        text = tmpl.read_text(encoding="utf-8")
        # Look for the canonical skip warning shape.
        assert "Reference Anchor skipped" in text, (
            f"{tmpl} does not provide an explicit skip path for the case "
            "where no images are available."
        )


def test_webfetch_removed_from_allowed_tools():
    """The three uiux skills should not include WebFetch in allowed-tools —
    removing the affordance is the strongest guard against regression."""
    for tmpl in UIUX_TMPL_PATHS:
        text = tmpl.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1] if text.startswith("---") else text
        m = re.search(r"^allowed-tools:\s*(.+)$", frontmatter, re.MULTILINE)
        assert m, f"{tmpl} has no allowed-tools line"
        tools = [t.strip() for t in m.group(1).split(",")]
        assert "WebFetch" not in tools, (
            f"{tmpl} still lists WebFetch in allowed-tools — removing the "
            "affordance is the structural guarantee against ISSUE-011 regression."
        )
