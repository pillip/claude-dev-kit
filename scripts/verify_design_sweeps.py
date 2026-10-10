#!/usr/bin/env python3
"""Deterministic validators for the three design sweeps (SPEC-056 / ISSUE-056).

Promotes the model-executed sweeps from the uiux / mobile-uiux / desktop-uiux
Phase 5.5 prose into scripts with exit codes, so a skipped or hallucinated
model self-check can no longer pass the gate:

  literal-quote   the exact characters of every `literal_quote: "<string>"`
                  field in docs/design_philosophy.md appear in at least one
                  prototype/screens/*.html as RENDERED text: outside HTML
                  comments, <script> element bodies, and data-* attribute
                  values (ISSUE-064 - those surfaces are blanked before the
                  search; other attribute text such as alt stays accepted).
                  Matching is
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
                  only semantics. HTML entities are decoded (html.unescape)
                  AFTER comment stripping, per line, and tell matching is
                  case-insensitive - encoded or case-varied tells are
                  detected like literal ones (ISSUE-064). CSS mechanics tells (flex-calc-width) are
                  matched at declaration level - whitespace/newlines collapse
                  after comment blanking - so a declaration split across
                  lines cannot evade the sweep; the violation reports the
                  line where the declaration starts. On HTML targets the
                  declaration-level pass ALSO blanks CSS /* */ comments
                  (inline style="" and <style> contexts mirror the browser's
                  CSS parsing; ISSUE-064) - scoped to that pass only, so
                  literal /* */ in rendered body text keeps line-wise
                  rendered-text semantics. Recorded Brief overrides
                  are passed as --exempt TELL_ID (repeatable); each exemption
                  is reported. Judgment tells (div-based fake product UI,
                  three equal cards, ...) are NOT deterministically decidable
                  and remain in skill prose.
  all             runs the three sweeps against one prototype tree.
                  --class NAME is REQUIRED: the signature-move sweep cannot
                  be enforced without it, so `all` fails closed with a usage
                  error (exit 2) instead of silently skipping the sweep.
                  With --json, `all` emits exactly ONE top-level JSON object
                  keyed by sweep (literal-quote / signature-move / ai-tell),
                  each value in the per-sweep result shape; nothing but that
                  document is written to stdout.

No validator passes vacuously: an empty screen/target set is a violation.

Exit codes (verify_* family convention):
  0 - pass
  1 - violations found (including vacuous/empty input)
  2 - usage error (missing philosophy file, unknown --exempt id, missing
      --class for signature-move or all, input resolving outside the
      project tree - ISSUE-064 containment); usage errors print to stderr

Usage:
    python3 scripts/verify_design_sweeps.py literal-quote  [--project-path P]
    python3 scripts/verify_design_sweeps.py signature-move --class NAME [--project-path P]
    python3 scripts/verify_design_sweeps.py ai-tell        [--project-path P] [--exempt ID ...]
    python3 scripts/verify_design_sweeps.py all            --class NAME [--project-path P]
Options: --philosophy / --screens-dir / --css override the default paths;
--json emits a machine-readable result.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
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


def collapse_ws_with_lines(text: str) -> tuple[str, list[int]]:
    """collapse_ws plus a per-character map to 1-based source line numbers.

    Lets declaration-level scans (DECLARATION_LEVEL_TELLS) report the line
    where a matched declaration starts, even when it spans several lines.
    """
    chars: list[str] = []
    lines: list[int] = []
    lineno = 1
    for ch in text:
        if ch.isspace():
            if not (chars and chars[-1] == " "):
                chars.append(" ")
                lines.append(lineno)
            if ch == "\n":
                lineno += 1
        else:
            chars.append(ch)
            lines.append(lineno)
    return "".join(chars), lines


# ── literal-quote ───────────────────────────────────────────────────

QUOTE_FIELD = re.compile(r'literal_quote:\s*"([^"]+)"')
SKIP_MARKER = re.compile(r"literal_quote:\s*\(skipped[^)\n]*\)")

# ISSUE-064 F3: quote characters placed in a <script> element body or a
# data-* attribute value are not rendered text and must not satisfy the
# sweep. Exactly these two surfaces are blanked (newline-preserving, like
# comments); other attribute text (alt, aria-label) and <style> bodies
# stay accepted rendered surfaces.
_SCRIPT_BODY = re.compile(r"(<script\b[^>]*>)(.*?)(?=</script\b)", re.S | re.I)
_DATA_ATTR_VALUE = re.compile(r"""(\bdata-[\w-]+\s*=\s*)("[^"]*"|'[^']*')""", re.I)


def blank_non_rendered(html_text: str) -> str:
    blanked = _SCRIPT_BODY.sub(
        lambda m: m.group(1) + re.sub(r"[^\n]", " ", m.group(2)), html_text
    )
    return _DATA_ATTR_VALUE.sub(
        lambda m: m.group(1) + re.sub(r"[^\n]", " ", m.group(2)), blanked
    )


def run_literal_quote(
    philosophy: Path,
    screens: list[Path],
    project: Path,
    json_out: bool,
    collect: dict | None = None,
) -> int:
    if not philosophy.exists():
        print(f"ERROR: philosophy file not found: {philosophy}", file=sys.stderr)
        return 2

    text = philosophy.read_text(encoding="utf-8")
    quotes = QUOTE_FIELD.findall(text)  # collect ALL occurrences

    if not quotes:
        if SKIP_MARKER.search(text):
            result = {"sweep": "literal-quote", "status": "skip", "violations": []}
            _emit(
                json_out,
                result,
                "literal-quote: SKIP (recorded marker: interview not run)",
                collect,
            )
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
            collect,
        )
        return 1

    violations: list[dict] = []
    if not screens:
        violations.append({"quote": None, "reason": "no screen files found"})
    else:
        haystacks = {
            s: collapse_ws(
                blank_non_rendered(strip_html_comments(s.read_text(encoding="utf-8")))
            )
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
            collect,
        )
        return 1

    _emit(
        json_out,
        {"sweep": "literal-quote", "status": "pass", "violations": []},
        f"literal-quote: PASS ({len(quotes)} quote(s) rendered verbatim)",
        collect,
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
    collect: dict | None = None,
) -> int:
    if not class_name:
        print("ERROR: --class <name> is required for signature-move", file=sys.stderr)
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
            collect,
        )
        return 1

    _emit(
        json_out,
        {"sweep": "signature-move", "status": "pass", "violations": []},
        f"signature-move: PASS (.{class_name} defined and applied on all {len(screens)} screen(s))",
        collect,
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
        re.compile(r"\b100vh\b", re.I),
        ("html", "css"),
        "100vh full-height (use min-height: 100dvh)",
    ),
    Tell(
        "flex-calc-width",
        re.compile(r"width\s*:\s*calc\(\s*[^)]*%", re.I),
        ("html", "css"),
        "flex percentage column math (use CSS Grid)",
    ),
    Tell(
        "generic-name",
        re.compile(r"\b(?:John Doe|Jane Doe|Sarah Chan|Acme|Nexus|SmartFlow|Cloudly)\b", re.I),
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

# SPEC-056 contract 3: CSS mechanics patterns are matched after whitespace
# normalization, at declaration level - a `width: calc(...)` split across
# lines (or around a blanked comment) is the SAME declaration and must not
# evade the sweep. These tell ids scan the whitespace-collapsed file text
# instead of line-wise; the reported line is where the declaration starts.
DECLARATION_LEVEL_TELLS = frozenset({"flex-calc-width"})


def run_ai_tell(
    screens: list[Path],
    css_path: Path,
    project: Path,
    exempt: list[str],
    json_out: bool,
    collect: dict | None = None,
) -> int:
    unknown = sorted(set(exempt) - KNOWN_TELL_IDS)
    if unknown:
        print(
            f"ERROR: unknown --exempt tell id(s): {', '.join(unknown)} "
            f"(known: {', '.join(sorted(KNOWN_TELL_IDS))})",
            file=sys.stderr,
        )
        return 2

    targets: list[tuple[Path, str]] = [(s, "html") for s in screens]
    if css_path.exists():
        targets.append((css_path, "css"))

    violations: list[dict] = []
    exemptions = sorted(set(exempt))

    # ISSUE-064 F4: an empty screens set is a violation regardless of the
    # stylesheet's presence - the no-vacuous-pass AC applies uniformly,
    # never half-passed on the css half alone. (`targets` can only be
    # empty when `screens` is, so this subsumes the old all-targets check
    # without double-reporting when both halves are missing.)
    if not screens:
        violations.append(
            {
                "file": _rel_dirname(screens, project),
                "line": 0,
                "tell_id": "empty-input",
                "snippet": "no screen files found (empty input set never passes)",
            }
        )

    active = [t for t in TELLS if t.tell_id not in exemptions]
    line_wise = [t for t in active if t.tell_id not in DECLARATION_LEVEL_TELLS]
    declaration_level = [t for t in active if t.tell_id in DECLARATION_LEVEL_TELLS]
    for path, kind in targets:
        raw = path.read_text(encoding="utf-8")
        stripped = (
            strip_html_comments(raw) if kind == "html" else strip_css_comments(raw)
        )
        source_lines = stripped.splitlines()
        hits: list[dict] = []
        for lineno, line in enumerate(source_lines, 1):
            if kind == "html":
                # ISSUE-064 F1: decode entities AFTER comment stripping and
                # per line - entity-encoded tells (&mdash;) are rendered text,
                # entity-encoded <!-- markers never become strippable comments,
                # and a decoded &NewLine; cannot shift reported line numbers.
                line = html.unescape(line)
            for tell in line_wise:
                if kind in tell.kinds and tell.pattern.search(line):
                    hits.append(
                        {
                            "file": _rel(path, project),
                            "line": lineno,
                            "tell_id": tell.tell_id,
                            "snippet": line.strip()[:100],
                        }
                    )
        # ISSUE-064 F6 (folded ISSUE-063 Medium): the declaration-level scan
        # mirrors the browser's CSS parsing, so on HTML targets CSS comments
        # (inline style="" / <style> contexts) are blanked for THIS pass
        # only - a comment interleaved inside the declaration cannot split
        # it. The line-wise scan above keeps rendered-text semantics.
        decl_text = strip_css_comments(stripped) if kind == "html" else stripped
        collapsed, line_of = collapse_ws_with_lines(decl_text)
        for tell in declaration_level:
            if kind not in tell.kinds:
                continue
            for match in tell.pattern.finditer(collapsed):
                lineno = line_of[match.start()]
                hits.append(
                    {
                        "file": _rel(path, project),
                        "line": lineno,
                        "tell_id": tell.tell_id,
                        "snippet": source_lines[lineno - 1].strip()[:100],
                    }
                )
        hits.sort(key=lambda v: v["line"])  # keep source order across both scans
        violations.extend(hits)

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
        collect,
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


def _emit(
    json_out: bool, payload: dict, text: str, collect: dict | None = None
) -> None:
    """Print one sweep result, or store it when aggregating (`all --json`).

    `collect` keeps `all --json` stdout to exactly ONE JSON document: each
    sweep's payload is stored under its sweep id and main() prints the
    aggregate once, instead of concatenating per-sweep objects.
    """
    if collect is not None:
        collect[payload["sweep"]] = payload
    elif json_out:
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

    # ISSUE-064 F5: input containment. Every file the sweep would read must
    # resolve inside a sanctioned root: the resolved project path plus any
    # explicitly passed override (--philosophy/--screens-dir/--css are the
    # caller's decision). A path escaping every root (e.g. via a symlink)
    # fails closed as a usage error BEFORE the file is read; resolved-to-
    # resolved comparison, so in-tree symlinks never false-trip.
    roots = [project.resolve()]
    roots += [
        Path(override).resolve()
        for override in (args.philosophy, args.screens_dir, args.css)
        if override
    ]
    would_read = {
        "literal-quote": [philosophy, *screens],
        "signature-move": [css_path, *screens],
        "ai-tell": [css_path, *screens],
        "all": [philosophy, css_path, *screens],
    }[args.command]
    for target in would_read:
        resolved = target.resolve()
        if not any(resolved.is_relative_to(root) for root in roots):
            print(
                f"ERROR: {target} resolves outside the project tree "
                f"({resolved} is under none of the sanctioned roots); pass "
                "the path explicitly (--philosophy/--screens-dir/--css) to "
                "sanction it",
                file=sys.stderr,
            )
            return 2

    if args.command == "literal-quote":
        return run_literal_quote(philosophy, screens, project, args.json_out)
    if args.command == "signature-move":
        return run_signature_move(args.class_name, css_path, screens, project, args.json_out)
    if args.command == "ai-tell":
        return run_ai_tell(screens, css_path, project, args.exempt, args.json_out)

    # all: --class is required - without it the signature-move sweep cannot
    # be enforced, and an unenforced sweep must fail closed, never exit 0.
    if not args.class_name:
        print(
            "ERROR: `all` requires --class NAME: the signature-move sweep "
            "cannot be enforced without it (fail-closed)",
            file=sys.stderr,
        )
        return 2
    collect: dict[str, dict] | None = {} if args.json_out else None
    codes = [
        run_literal_quote(philosophy, screens, project, args.json_out, collect),
        run_signature_move(
            args.class_name, css_path, screens, project, args.json_out, collect
        ),
        run_ai_tell(screens, css_path, project, args.exempt, args.json_out, collect),
    ]
    if collect is not None:
        print(json.dumps(collect, indent=2))
    if 2 in codes:
        return 2
    return 1 if 1 in codes else 0


if __name__ == "__main__":
    raise SystemExit(main())
