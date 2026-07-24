#!/usr/bin/env python3
"""Synthesize /deep-research output into the kit's fixed section template.

ISSUE-018 / SPEC-018 primary path: when /deep-research is exposed by the
runtime, /brainstorm and /bizanalysis delegate the heavy research lift to
it. The kit's job shrinks to (a) mapping its cited report into the kit's
fixed 5-section bizanalysis template (or the Existing Landscape section
of brainstorm_notes), (b) preserving every cited quote verbatim, and
(c) rendering the literal "Data: not available …" line for sections the
report does NOT cover (no fabricated fill-in).

The LLM-y extraction (turning /deep-research prose into structured claims
per section) happens in the SKILL.md.tmpl prompt itself; this Python
module is the deterministic writer that takes a structured intermediate
and renders the kit-shaped markdown. The synthesizer-auditor (separate
Task invocation, refute-first prompt) then verifies the rendering did
not drop or distort any upstream claim.

Input contract (Python dict / JSON):
    {
      "title":   "Business Analysis: <topic>",  # or None for brainstorm
      "sections": [
        {
          "name":       "Market Analysis",      # MUST match template
          "claims":     [
            {
              "text":       "...kit-side framing of the finding...",
              "quote":      "...verbatim from /deep-research report...",
              "source_url": "https://...",
              "tags":       ["single-source", "contested"]  # optional
            }
          ]
        },
        {
          "name":       "Competitive Landscape",
          "claims":     []   # empty → render no-data literal
        }
      ]
    }

Output: markdown string.

Exit codes (when invoked as CLI):
    0 = render succeeded, written to stdout (or --out path)
    2 = bad input (malformed JSON, missing required field, unknown section name)

Usage:
    python3 scripts/synthesize_from_deep_research.py < input.json
    python3 scripts/synthesize_from_deep_research.py --input input.json --out docs/business_analysis.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Kit's fixed bizanalysis section order, per agents/business-analyst.md
# Output Format. The synthesizer rejects unknown section names so that
# /deep-research's prose can't accidentally introduce new sections.
BIZANALYSIS_SECTIONS: list[str] = [
    "Executive Summary",
    "Market Analysis",
    "Competitive Landscape",
    "Business Model",
    "Risks & Mitigations",
]

# Brainstorm: only Existing Landscape is grounded by /deep-research; the
# rest stay free-form (Problem Space, Idea Candidates, Decisions).
BRAINSTORM_GROUNDED_SECTIONS: list[str] = [
    "Existing Landscape",
]

NO_DATA_LINE = (
    'Data: not available — re-run /deep-research with a sharper question '
    'or accept "no data".'
)


def _validate_input(payload: dict, allowed_sections: list[str]) -> list[str]:
    """Return a list of validation errors (empty if input is well-formed)."""
    errors: list[str] = []
    if "sections" not in payload or not isinstance(payload["sections"], list):
        errors.append("input must contain 'sections' as a list")
        return errors

    seen = set()
    for i, section in enumerate(payload["sections"]):
        if not isinstance(section, dict):
            errors.append(f"section[{i}] is not a dict")
            continue
        name = section.get("name")
        if not name:
            errors.append(f"section[{i}] missing 'name'")
            continue
        if name not in allowed_sections:
            errors.append(
                f"section[{i}].name {name!r} is not in the allowed set "
                f"{allowed_sections}"
            )
        if name in seen:
            errors.append(f"section[{i}].name {name!r} duplicated")
        seen.add(name)

        claims = section.get("claims")
        if claims is None or not isinstance(claims, list):
            errors.append(f"section[{name!r}].claims must be a list (may be empty)")
            continue
        for j, claim in enumerate(claims):
            if not isinstance(claim, dict):
                errors.append(f"section[{name!r}].claims[{j}] is not a dict")
                continue
            for required in ("text", "quote", "source_url"):
                value = claim.get(required)
                if not value or not isinstance(value, str):
                    errors.append(
                        f"section[{name!r}].claims[{j}] missing or empty "
                        f"{required!r}"
                    )
    return errors


def _render_claim(claim: dict[str, Any]) -> str:
    """Render one claim as a kit-shaped bullet with verbatim quote + citation."""
    text = claim["text"].rstrip()
    quote = claim["quote"]
    url = claim["source_url"]
    tags = claim.get("tags") or []
    tag_suffix = "".join(f" [{t}]" for t in tags) if tags else ""
    return (
        f"- {text}{tag_suffix}\n"
        f"  > {quote}\n"
        f"  Source: {url}\n"
    )


def render(payload: dict[str, Any], *, allowed_sections: list[str]) -> str:
    """Pure function. Returns the rendered markdown string. Raises ValueError
    on invalid input — callers translate to exit code 2."""
    errors = _validate_input(payload, allowed_sections)
    if errors:
        raise ValueError("; ".join(errors))

    lines: list[str] = []
    title = payload.get("title")
    if title:
        lines.append(f"# {title}")
        lines.append("")

    sections_by_name = {s["name"]: s for s in payload["sections"]}

    for section_name in allowed_sections:
        section = sections_by_name.get(section_name)
        lines.append(f"## {section_name}")
        lines.append("")
        if section is None or not section.get("claims"):
            lines.append(NO_DATA_LINE)
            lines.append("")
            continue
        for claim in section["claims"]:
            lines.append(_render_claim(claim).rstrip())
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_bizanalysis(payload: dict[str, Any]) -> str:
    return render(payload, allowed_sections=BIZANALYSIS_SECTIONS)


def render_brainstorm_landscape(payload: dict[str, Any]) -> str:
    return render(payload, allowed_sections=BRAINSTORM_GROUNDED_SECTIONS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render /deep-research output into kit-shaped sections."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="JSON file containing the structured intermediate (stdin if omitted).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Write rendered markdown to this path (stdout if omitted).",
    )
    parser.add_argument(
        "--mode",
        choices=["bizanalysis", "brainstorm"],
        default="bizanalysis",
        help="Section template to use.",
    )
    args = parser.parse_args()

    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading input: {exc}", file=sys.stderr)
        return 2

    renderer = render_bizanalysis if args.mode == "bizanalysis" else render_brainstorm_landscape
    try:
        rendered = renderer(payload)
    except ValueError as exc:
        print(f"Input validation failed: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"wrote: {args.out}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
