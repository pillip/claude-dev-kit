#!/usr/bin/env python3
"""Deterministic validators for the three design sweeps (SPEC-056 / ISSUE-056).

Promotes the model-executed sweeps from the uiux / mobile-uiux / desktop-uiux
Phase 5.5 prose into scripts with exit codes, so a skipped or hallucinated
model self-check can no longer pass the gate:

  literal-quote   the exact characters of every `literal_quote: "<string>"`
                  field in docs/design_philosophy.md appear in at least one
                  prototype/screens/*.html OUTSIDE HTML comments. Matching is
                  whitespace-insensitive (runs of whitespace collapse to one
                  space on both sides) - the only permitted normalization; no
                  substring widening. The explicit skip marker
                  `literal_quote: (skipped ...)` is a recorded skip -> pass.
  signature-move  the named reusable class (--class) exists as a selector in
                  prototype/styles.css AND appears as a whole class-attribute
                  token in EVERY screen file.
  ai-tell         occurrence-whitelist sweep of banned RENDERED patterns over
                  prototype/screens/*.html + prototype/styles.css. Comments
                  (HTML <!-- --> and CSS /* */) are blanked first - rendered-
                  only semantics. Recorded Brief overrides are passed as
                  --exempt TELL_ID (repeatable); each exemption is reported.
                  Judgment tells (div-based fake product UI, three equal
                  cards, ...) are NOT deterministically decidable and remain
                  in skill prose.
  all             runs the three sweeps against one prototype tree
                  (signature-move only when --class is given; otherwise it is
                  skipped loudly).

No validator passes vacuously: an empty screen/target set is a violation.

Exit codes (verify_* family convention):
  0 - pass
  1 - violations found (including vacuous/empty input)
  2 - usage error (missing philosophy file, unknown --exempt id, no --class)

Usage:
    python3 scripts/verify_design_sweeps.py literal-quote  [--project-path P]
    python3 scripts/verify_design_sweeps.py signature-move --class NAME [--project-path P]
    python3 scripts/verify_design_sweeps.py ai-tell        [--project-path P] [--exempt ID ...]
    python3 scripts/verify_design_sweeps.py all            [--class NAME] [--project-path P]
Options: --philosophy / --screens-dir / --css override the default paths;
--json emits a machine-readable result.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

# ── Shared text helpers ─────────────────────────────────────────────

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _blank(match: re.Match) -> str:
    """Replace a comment with spaces, preserving newlines (line numbers)."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_html_comments(text: str) -> str:
    return _HTML_COMMENT.sub(_blank, text)


def strip_css_comments(text: str) -> str:
    return _CSS_COMMENT.sub(_blank, text)


def collapse_ws(text: str) -> str:
    """Collapse every whitespace run to a single space (both needle and haystack)."""
    return re.sub(r"\s+", " ", text)


# ── literal-quote ───────────────────────────────────────────────────

QUOTE_FIELD = re.compile(r'literal_quote:\s*"([^"]+)"')
SKIP_MARKER = re.compile(r"literal_quote:\s*\(skipped[^)\n]*\)")


def run_literal_quote(
    philosophy: Path, screens: list[Path], project: Path, json_out: bool
) -> int:
    if not philosophy.exists():
        print(f"ERROR: philosophy file not found: {philosophy}")
        return 2

    text = philosophy.read_text(encoding="utf-8")
    quotes = QUOTE_FIELD.findall(text)  # collect ALL occurrences

    if not quotes:
        if SKIP_MARKER.search(text):
            result = {"sweep": "literal-quote", "status": "skip", "violations": []}
            _emit(json_out, result, "literal-quote: SKIP (recorded marker: interview not run)")
            return 0
        result = {
            "sweep": "literal-quote",
            "status": "fail",
            "violations": [
                {"quote": None, "reason": "no literal_quote field in philosophy"}
            ],
        }
        _emit(
            json_out,
            result,
            f'MISSING literal_quote field in {_rel(philosophy, project)} '
            "(expected literal_quote: \"<exact string>\" or the recorded skip marker)",
        )
        return 1

    violations: list[dict] = []
    if not screens:
        violations.append({"quote": None, "reason": "no screen files found"})
    else:
        haystacks = {
            s: collapse_ws(strip_html_comments(s.read_text(encoding="utf-8")))
            for s in screens
        }
        for quote in quotes:
            needle = collapse_ws(quote)
            if not any(needle in h for h in haystacks.values()):
                violations.append(
                    {
                        "quote": quote,
                        "reason": "not rendered verbatim in any screen (comments excluded)",
                    }
                )

    if violations:
        lines = []
        for v in violations:
            if v["quote"] is None:
                lines.append(f"MISSING: {v['reason']} under {_rel_dirname(screens, project)}")
            else:
                lines.append(
                    f'MISSING literal_quote "{v["quote"]}": {v["reason"]} '
                    f"({len(screens)} screen file(s) checked, whitespace-insensitive)"
                )
        _emit(
            json_out,
            {"sweep": "literal-quote", "status": "fail", "violations": violations},
            "\n".join(lines),
        )
        return 1

    _emit(
        json_out,
        {"sweep": "literal-quote", "status": "pass", "violations": []},
        f"literal-quote: PASS ({len(quotes)} quote(s) rendered verbatim)",
    )
    return 0


# ── signature-move ──────────────────────────────────────────────────

_CLASS_ATTR = re.compile(r"""class\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def run_signature_move(
    class_name: str | None,
    css_path: Path,
    screens: list[Path],
    project: Path,
    json_out: bool,
) -> int:
    if not class_name:
        print("ERROR: --class <name> is required for signature-move")
        return 2

    violations: list[dict] = []

    if not css_path.exists():
        violations.append(
            {"file": _rel(css_path, project), "reason": f"stylesheet missing, selector .{class_name} not defined"}
        )
    else:
        css = strip_css_comments(css_path.read_text(encoding="utf-8"))
        selector = re.compile(r"\." + re.escape(class_name) + r"(?![\w-])")
        if not selector.search(css):
            violations.append(
                {
                    "file": _rel(css_path, project),
                    "reason": f"selector .{class_name} not defined",
                }
            )

    if not screens:
        violations.append({"file": None, "reason": "no screen files found"})
    for screen in screens:
        html = strip_html_comments(screen.read_text(encoding="utf-8"))
        applied = any(
            class_name in (m.group(1) or m.group(2) or "").split()
            for m in _CLASS_ATTR.finditer(html)
        )
        if not applied:
            violations.append(
                {
                    "file": _rel(screen, project),
                    "reason": f"class {class_name} not applied on this screen",
                }
            )

    if violations:
        text = "\n".join(
            f"{v['file'] or '(screens)'}: {v['reason']}" for v in violations
        )
        _emit(
            json_out,
            {"sweep": "signature-move", "status": "fail", "violations": violations},
            text,
        )
        return 1

    _emit(
        json_out,
        {"sweep": "signature-move", "status": "pass", "violations": []},
        f"signature-move: PASS (.{class_name} defined and applied on all {len(screens)} screen(s))",
    )
    return 0


# ── ai-tell ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Tell:
    tell_id: str
    pattern: re.Pattern
    kinds: tuple[str, ...]  # file kinds this tell applies to: "html", "css"
    description: str


# Occurrence-whitelist of banned RENDERED patterns (review lesson: lint for
# the presence of the actual banned strings in output artifacts, never a
# phrasing blacklist over prose). Extend by adding entries, not CLI flags.
TELLS: tuple[Tell, ...] = (
    Tell(
        "em-dash",
        re.compile(r"[—–]"),
        ("html", "css"),
        "em-dash / en-dash separator (use '-', comma, period, colon)",
    ),
    Tell(
        "100vh",
        re.compile(r"\b100vh\b"),
        ("html", "css"),
        "100vh full-height (use min-height: 100dvh)",
    ),
    Tell(
        "flex-calc-width",
        re.compile(r"width\s*:\s*calc\(\s*[^)]*%"),
        ("html", "css"),
        "flex percentage column math (use CSS Grid)",
    ),
    Tell(
        "generic-name",
        re.compile(r"\b(?:John Doe|Jane Doe|Sarah Chan|Acme|Nexus|SmartFlow|Cloudly)\b"),
        ("html",),
        "generic person/brand name",
    ),
    Tell(
        "fake-perfect-number",
        re.compile(r"99\.99%|1,234,567"),
        ("html",),
        "fake-perfect number (use organic values)",
    ),
    Tell(
        "filler-verb",
        re.compile(r"\b(?:Elevate|Seamless|Unleash|Next-Gen|Revolutionize)\b", re.I),
        ("html",),
        "filler verb (use concrete verbs)",
    ),
    Tell(
        "scroll-cue",
        re.compile(r"scroll\s+to\s+explore|↓\s*scroll", re.I),
        ("html",),
        "scroll cue",
    ),
)

KNOWN_TELL_IDS = {t.tell_id for t in TELLS}


def run_ai_tell(
    screens: list[Path],
    css_path: Path,
    project: Path,
    exempt: list[str],
    json_out: bool,
) -> int:
    unknown = sorted(set(exempt) - KNOWN_TELL_IDS)
    if unknown:
        print(
            f"ERROR: unknown --exempt tell id(s): {', '.join(unknown)} "
            f"(known: {', '.join(sorted(KNOWN_TELL_IDS))})"
        )
        return 2

    targets: list[tuple[Path, str]] = [(s, "html") for s in screens]
    if css_path.exists():
        targets.append((css_path, "css"))

    violations: list[dict] = []
    exemptions = sorted(set(exempt))

    if not targets:
        violations.append(
            {
                "file": _rel(css_path, project),
                "line": 0,
                "tell_id": "empty-input",
                "snippet": "no sweep target files found (screens + stylesheet)",
            }
        )

    active = [t for t in TELLS if t.tell_id not in exemptions]
    for path, kind in targets:
        raw = path.read_text(encoding="utf-8")
        stripped = (
            strip_html_comments(raw) if kind == "html" else strip_css_comments(raw)
        )
        for lineno, line in enumerate(stripped.splitlines(), 1):
            for tell in active:
                if kind in tell.kinds and tell.pattern.search(line):
                    violations.append(
                        {
                            "file": _rel(path, project),
                            "line": lineno,
                            "tell_id": tell.tell_id,
                            "snippet": line.strip()[:100],
                        }
                    )

    lines = [f"exempt: {e} (recorded Brief override)" for e in exemptions]
    lines += [
        f"{v['file']}:{v['line']}: [{v['tell_id']}] {v['snippet']}" for v in violations
    ]
    status = "fail" if violations else "pass"
    if not violations:
        lines.append(f"ai-tell: PASS ({len(targets)} file(s) swept, comments stripped)")
    _emit(
        json_out,
        {
            "sweep": "ai-tell",
            "status": status,
            "violations": violations,
            "exemptions": exemptions,
        },
        "\n".join(lines),
    )
    return 1 if violations else 0


# ── plumbing ────────────────────────────────────────────────────────


def _rel(path: Path, project: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def _rel_dirname(screens: list[Path], project: Path) -> str:
    if screens:
        return _rel(screens[0].parent, project)
    return "prototype/screens"


def _emit(json_out: bool, payload: dict, text: str) -> None:
    if json_out:
        print(json.dumps(payload, indent=2))
    else:
        print(text)


def _discover_screens(screens_dir: Path) -> list[Path]:
    if not screens_dir.is_dir():
        return []
    return sorted(screens_dir.glob("*.html"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic design-sweep validators (SPEC-056)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("literal-quote", "signature-move", "ai-tell", "all"):
        p = sub.add_parser(name)
        p.add_argument("--project-path", default=".", help="project root (default: .)")
        p.add_argument("--philosophy", default=None, help="override docs/design_philosophy.md")
        p.add_argument("--screens-dir", default=None, help="override prototype/screens")
        p.add_argument("--css", default=None, help="override prototype/styles.css")
        p.add_argument("--json", action="store_true", dest="json_out")
        if name in ("signature-move", "all"):
            p.add_argument("--class", dest="class_name", default=None)
        if name in ("ai-tell", "all"):
            p.add_argument("--exempt", action="append", default=[], metavar="TELL_ID")

    args = parser.parse_args(argv)
    project = Path(args.project_path)
    philosophy = Path(args.philosophy) if args.philosophy else project / "docs" / "design_philosophy.md"
    screens_dir = Path(args.screens_dir) if args.screens_dir else project / "prototype" / "screens"
    css_path = Path(args.css) if args.css else project / "prototype" / "styles.css"
    screens = _discover_screens(screens_dir)

    if args.command == "literal-quote":
        return run_literal_quote(philosophy, screens, project, args.json_out)
    if args.command == "signature-move":
        return run_signature_move(args.class_name, css_path, screens, project, args.json_out)
    if args.command == "ai-tell":
        return run_ai_tell(screens, css_path, project, args.exempt, args.json_out)

    # all
    codes = [run_literal_quote(philosophy, screens, project, args.json_out)]
    if args.class_name:
        codes.append(
            run_signature_move(args.class_name, css_path, screens, project, args.json_out)
        )
    else:
        print("signature-move: SKIPPED (no --class provided)")
    codes.append(run_ai_tell(screens, css_path, project, args.exempt, args.json_out))
    if 2 in codes:
        return 2
    return 1 if 1 in codes else 0


if __name__ == "__main__":
    raise SystemExit(main())
