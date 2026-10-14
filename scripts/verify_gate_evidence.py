#!/usr/bin/env python3
"""Require paired evidence for every gate a diff adds (ISSUE-081 / SPEC-081).

"A newly added defence fails OPEN" was measured at High severity in four
consecutive sprints — ISSUE-068/PR #121, ISSUE-076/PR #128, ISSUE-078/PR #133,
ISSUE-072/PR #135. The common shape is a missing **test direction**: every one
tested that its gate FIRES and shipped without a test that it cannot be
DISARMED, or that it holds end to end through the real consumer rather than
only at the helper it was unit-tested against.

This module answers two questions over unified-diff text, with no knowledge of
the repository it came from:

1. **Does this diff add a gate?** A gate is a function in a changed non-test
   source file whose *diff-added* lines contain both a conditional and a
   refusal. The definition deliberately over-detects (SPEC-081); the escape
   hatch is an explicit inline exemption, which is reported rather than
   silently honoured.
2. **Is the gate evidenced in both directions?**
   * ``disarm`` — an added test battery (>= ``MIN_VARIANTS`` input-only
     variants, constant literal expectations) that exercises the gate.
   * ``composite`` — an added battery that asserts a **consumer-level**
     outcome (an exit code / return code / a refusal constant) and carries an
     input-side **vacuity guard** whose literal is attributable to the gate.

Why the vacuity guard carries the attribution: a syntactic checker cannot infer
input *families*, and the two real ISSUE-078 diffs are indistinguishable at
every coarser metric (added blocks referencing the gate 7 vs 8; consumer-driving
blocks 2 vs 2; both already carry consumer-level refusal batteries). The guard
is simultaneously what ties a battery to a gate and what makes the battery
non-vacuous — without it, 8 heading mutations are indistinguishable from 8
copies of a case that already passed.

Usage::

    python3 scripts/verify_gate_evidence.py --diff-file path/to.diff
    python3 scripts/verify_gate_evidence.py --range main..HEAD --repo .
    python3 scripts/verify_gate_evidence.py --diff-file path/to.diff --json

Exit code: 0 when the diff adds no gate, or every added gate is evidenced or
exempted; 1 when an added gate lacks its paired evidence; 2 on a usage error.

The tunables below are module-level and read at call time *on purpose*: the
test suite mutates them one at a time to prove each rule is load-bearing
(ISSUE-081 AC-5). Do not inline them into the functions that read them.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ── Tunables (mutation-pinned by tests/test_gate_evidence_contract.py) ──

#: Minimum distinct input variants before a parametrized/looped test counts as
#: a *battery* rather than a single case. 3 is the smallest count at which
#: "varied the input" is a claim rather than a coincidence; SPEC-081's Open
#: Questions schedules re-tuning this on measured false positives only.
MIN_VARIANTS = 3

#: Require a composite battery to carry an input-side vacuity guard. This is
#: also what attributes the battery to a specific gate.
REQUIRE_VACUITY_GUARD = True

#: Require a battery's parameters to feed only the INPUT. A table whose
#: *expected* value is itself a parameter is an outcome mapping, not a
#: direction battery.
REQUIRE_INPUT_ONLY_PARAMS = True

#: Require a composite battery to assert a consumer-level outcome (exit code,
#: return code, or a refusal constant), not merely to mention one.
REQUIRE_CONSUMER_OUTCOME = True

# ── Vocabulary ───────────────────────────────────────────────────────

#: A refusal: the gate's blocking branch. Matched against *de-stringed* code so
#: prose inside a docstring or a generated skill fragment cannot manufacture a
#: gate. Boolean returns are only a refusal in a predicate-shaped function
#: (see ``_PREDICATE_SHAPE``) — otherwise every accessor would be a gate.
REFUSAL_PATTERNS = (
    re.compile(r"\breturn\s+[1-9]\d*\b"),
    re.compile(r"\bsys\.exit\(\s*[1-9]"),
    re.compile(r"\bos\._exit\(\s*[1-9]"),
    re.compile(r"\braise\s+SystemExit\(\s*[1-9]"),
    re.compile(r"\braise\s+\w*(?:Error|Exception)\b"),
    re.compile(r"\breturn\s+\w*EXIT\w*\b"),
    re.compile(r"\b(?:valid|ok|allowed|permitted|passed)[\"']?\s*[:=]\s*False\b"),
)

#: A boolean return counts as a refusal only here.
_BOOL_REFUSAL = re.compile(r"\breturn\s+(?:True|False)\b")

_CONDITIONAL = re.compile(
    r"(?:^\s*(?:if|elif|while)\b)|(?:^\s*assert\b)|(?:\bif\b.+\belse\b)"
)

_PREDICATE_SHAPE = re.compile(
    r"^(?:is|has|was|can|should|must|are)_"
    r"|_is_|_has_"
    r"|^(?:check|verify|validate|ensure|require|assert|guard|refuse|reject"
    r"|allow|permit|detect)"
    r"|_valid|valid$|_ok$",
    re.IGNORECASE,
)

_DEF_RE = re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\(")
_HUNK_RE = re.compile(r"^@@[^@]*@@(.*)$")

#: Root identifiers that name the *input* under test. An occurrence whitelist,
#: not a phrasing blacklist: a guard over ``out`` / ``result`` / ``captured``
#: asserts something about the gate's OUTPUT and proves nothing about the
#: fixture, so it must not attribute a battery to a gate.
_INPUT_ROOTS = frozenset(
    {
        "text",
        "content",
        "contents",
        "src",
        "source",
        "raw",
        "body",
        "doc",
        "document",
        "data",
        "diff",
        "diff_text",
        "fixture",
        "payload",
        "rendered",
        "tmpl",
        "template",
        "markdown",
        "blob",
        "generated",
        "sprint_text",
        "file_text",
    }
)

_GENERIC_TOKENS = frozenset(
    {
        "the",
        "and",
        "get",
        "set",
        "has",
        "can",
        "not",
        "for",
        "all",
        "any",
        "run",
        "add",
        "new",
        "one",
        "two",
        "old",
        "was",
        "are",
        "its",
        "use",
        "with",
        "from",
        "this",
        "that",
        "out",
        "value",
        "line",
        "test",
    }
)

_EXEMPT_RE = re.compile(
    r"GATE-EVIDENCE-EXEMPT\(\s*([\w.]+)\s*\)\s*:\s*(?P<reason>.*)"
)

_VACUITY_RE = re.compile(
    r"\bassert\s+(?P<q>[\"'])(?P<lit>(?:[^\"'\\]|\\.)*)(?P=q)"
    r"\s+(?:not\s+)?in\s+(?P<expr>[^,\n]+)"
)

_CONSUMER_RE = re.compile(
    r"\bassert\s+[\w.\[\]\"'() ]*\b"
    r"(?:exit_code|exitcode|returncode|return_code|status_code|rc)\b"
    r"\s*(?:==|!=|is(?:\s+not)?)\s*(?P<expected>[^,\n]+)"
)

_ASSERT_EXPECTED_RE = re.compile(r"(?:\bis\s+(?:not\s+)?|==|!=)\s*([^,\n]+)")

_LITERAL_EXPECTED_RE = re.compile(
    r"^(?:True|False|None|-?\d+|[\"'].*|[\w.]*\b[A-Z][A-Z0-9_]{2,}\b.*)$"
)

#: `git diff` on a feature branch is local and fast; this reuses the project's
#: documented 30 s subprocess default rather than introducing a new knob.
_GIT_TIMEOUT = 30


# ── Result types ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Gate:
    symbol: str
    path: str
    line: int


@dataclass(frozen=True)
class Finding:
    symbol: str
    path: str
    line: int
    kind: str
    message: str


@dataclass(frozen=True)
class Report:
    gates: tuple[Gate, ...]
    findings: tuple[Finding, ...]
    exemptions: tuple[tuple[str, str], ...]
    evidence: dict[str, dict[str, bool]]


# ── Diff parsing ─────────────────────────────────────────────────────


def _destring(line: str) -> str:
    """Blank string-literal *prose* while keeping identifier-like literals.

    ``"valid": False`` must stay matchable (it is a verdict value), while a
    skill fragment that happens to contain the words of a refusal must not
    manufacture a gate. A literal whose content is a single bare word survives;
    everything else becomes an empty literal.
    """

    def repl(match: re.Match) -> str:
        quote, inner = match.group(1), match.group(2)
        if re.fullmatch(r"\w{1,24}", inner):
            return f"{quote}{inner}{quote}"
        return f"{quote}{quote}"

    return re.sub(r"([\"'])((?:[^\"'\\]|\\.)*?)\1", repl, line)


def is_test_path(path: str) -> bool:
    """True for paths the suite owns (where every assert has a refusing branch)."""
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith("tests/")
        or "/tests/" in path
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


@dataclass
class _FileDiff:
    path: str
    added: list[tuple[int, str]]            # (diff line number, text)
    added_by_def: dict[str, list[str]]      # enclosing def -> added code lines
    def_line: dict[str, int]                # enclosing def -> first added line
    signatures: dict[str, str]              # enclosing def -> its `def` line


def _parse(diff_text: str) -> list[_FileDiff]:
    files: list[_FileDiff] = []
    current: _FileDiff | None = None
    enclosing: str | None = None

    for number, raw in enumerate(diff_text.split("\n"), start=1):
        line = raw.rstrip("\r")

        if line.startswith("+++ "):
            target = line[4:].strip()
            path = target[2:] if target.startswith("b/") else target
            current = None if path == "/dev/null" else _FileDiff(path, [], {}, {}, {})
            if current is not None:
                files.append(current)
            enclosing = None
            continue
        if line.startswith("--- ") or line.startswith("diff --git "):
            continue
        if current is None:
            continue

        hunk = _HUNK_RE.match(line)
        if hunk:
            hint = _DEF_RE.match(hunk.group(1).lstrip())
            enclosing = hint.group(2) if hint else None
            continue

        if line.startswith("\\"):       # "\ No newline at end of file"
            continue

        if line.startswith("+"):
            body = line[1:]
            found = _DEF_RE.match(body)
            if found:
                enclosing = found.group(2)
                current.signatures[enclosing] = body
                current.def_line.setdefault(enclosing, number)
            current.added.append((number, body))
            if enclosing:
                current.added_by_def.setdefault(enclosing, []).append(body)
                current.def_line.setdefault(enclosing, number)
            continue

        if line.startswith("-"):
            continue

        # context line
        found = _DEF_RE.match(line[1:] if line.startswith(" ") else line)
        if found:
            enclosing = found.group(2)
            current.signatures.setdefault(enclosing, line.lstrip())


    return files


# ── Gate detection ───────────────────────────────────────────────────


# GATE-EVIDENCE-EXEMPT(_is_predicate_shaped): private gate-detection reach; exercised in both directions by the three fixture replays (it is what admits `sprint_status_is_running` and leaves the non-gate diff empty) and killed by the `refusal_vocabulary_emptied` mutant, which disables the boolean-refusal path it guards.
def _is_predicate_shaped(symbol: str, signature: str) -> bool:
    if "-> bool" in signature.replace(" ", " "):
        return True
    if "->bool" in signature.replace(" ", ""):
        return True
    return bool(_PREDICATE_SHAPE.search(symbol))


def detect_gates(files: list[_FileDiff]) -> tuple[Gate, ...]:
    gates: list[Gate] = []
    for file in files:
        if is_test_path(file.path) or not file.path.endswith(".py"):
            continue
        for symbol, lines in file.added_by_def.items():
            code = [_destring(line) for line in lines]
            if not any(_CONDITIONAL.search(line) for line in code):
                continue
            refusal = any(
                pattern.search(line) for line in code for pattern in REFUSAL_PATTERNS
            )
            if not refusal and _is_predicate_shaped(
                symbol, file.signatures.get(symbol, "")
            ):
                refusal = any(_BOOL_REFUSAL.search(line) for line in code)
            if refusal:
                gates.append(
                    Gate(symbol, file.path, file.def_line.get(symbol, 0))
                )
    return tuple(gates)


# ── Test-side evidence ───────────────────────────────────────────────


@dataclass
class _Block:
    head: str
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _blocks(files: list[_FileDiff]) -> tuple[list[_Block], str]:
    """Split added TEST lines into per-test blocks, plus the module-level text.

    A block is one added ``def test_*`` plus its body and any decorators that
    precede it — including a decorator's continuation lines, which do not start
    with ``@`` and were the first thing a naive splitter dropped.
    """
    blocks: list[_Block] = []
    module_lines: list[str] = []
    for file in files:
        if not is_test_path(file.path):
            continue
        module_lines.extend(text for _, text in file.added)

        pending: list[str] = []
        depth = 0
        current: _Block | None = None
        for _, text in file.added:
            stripped = text.strip()
            if depth > 0:
                pending.append(text)
                if current is not None:
                    current.lines.append(text)
                depth += text.count("(") + text.count("[") - text.count(")") - text.count("]")
                depth = max(depth, 0)
                continue
            if stripped.startswith("@"):
                pending.append(text)
                if current is not None:
                    current.lines.append(text)
                depth = max(
                    text.count("(") + text.count("[")
                    - text.count(")") - text.count("]"),
                    0,
                )
                continue
            found = _DEF_RE.match(text)
            if found or stripped.startswith("class "):
                name = found.group(2) if found else ""
                if name.startswith("test"):
                    current = _Block(stripped, list(pending) + [text])
                    blocks.append(current)
                else:
                    current = None
                pending = []
                continue
            pending = []
            if current is not None:
                current.lines.append(text)
    return blocks, "\n".join(module_lines)


def _count_bracket_elements(text: str, start: int) -> int:
    """Count top-level elements of the bracketed list opening at ``text[start]``.

    Scans with its own quote state rather than pre-stripping literals: the
    de-stringing pass changes the string's LENGTH, so indices computed against
    the original text no longer address the same characters (measured: this
    silently returned 0 for every named argvalues list).
    """
    depth = 0
    commas = 0
    seen = False
    quote: str | None = None
    last_significant = ""
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
            if depth == 1:
                seen = True
                last_significant = char
            index += 1
            continue
        if char in "([{":
            depth += 1
            if depth > 1:
                seen = True
                last_significant = char
            index += 1
            continue
        if char in ")]}":
            depth -= 1
            if depth == 0:
                break
            last_significant = char
            index += 1
            continue
        if depth == 1 and not char.isspace():
            if char == ",":
                commas += 1
            else:
                seen = True
            last_significant = char
        index += 1

    if not seen:
        return 0
    return commas if last_significant == "," else commas + 1


def _argnames(decorator: str) -> list[str]:
    match = re.search(r"parametrize\(\s*[\"']([^\"']+)[\"']", decorator)
    if not match:
        return []
    return [name.strip() for name in match.group(1).split(",") if name.strip()]


def _variant_count(block: _Block, module_text: str) -> int:
    text = block.text
    match = re.search(r"parametrize\(\s*[\"'][^\"']+[\"']\s*,", text)
    if match:
        rest = text[match.end():]
        offset = len(text) - len(rest)
        bracket = re.match(r"\s*[\[(]", rest)
        if bracket:
            return _count_bracket_elements(text, offset + bracket.end() - 1)
        named = re.match(r"\s*([A-Za-z_]\w*)", rest)
        if named:
            return _named_list_length(named.group(1), module_text)
        return 0

    loop = re.search(r"\bfor\s+[\w, ]+\s+in\s+(?!range)", text)
    if loop:
        rest = text[loop.end():]
        if rest.lstrip().startswith("["):
            offset = loop.end() + (len(rest) - len(rest.lstrip()))
            return _count_bracket_elements(text, offset)
        named = re.match(r"\s*([A-Za-z_]\w*)", rest)
        if named:
            return _named_list_length(named.group(1), module_text)
    return 0


def _named_list_length(name: str, module_text: str) -> int:
    """Element count of a named argvalues list, resolved from the diff's own lines.

    A name the diff does not define (a pre-existing table such as
    ``RUNNING_VALUES``) is PRESUMED to be a battery and credited exactly
    ``MIN_VARIANTS``. Counting it as zero would classify every PR that batteries
    against a table the suite already owns as arm-only, which is both wrong and
    the opposite of the behaviour ISSUE-081 wants to encourage. The presumption
    is deliberately confined to the *count*: a presumed battery still has to
    clear the vacuity-guard and consumer-outcome requirements before it can
    satisfy the composite half, so the presumption cannot by itself clear a gate.
    """
    match = re.search(rf"^{re.escape(name)}\s*[:=]", module_text, re.MULTILINE)
    if not match:
        return MIN_VARIANTS
    opening = re.match(r"\s*=?\s*[\[(]", module_text[match.end() - 1:])
    if not opening:
        return MIN_VARIANTS
    return _count_bracket_elements(
        module_text, match.end() - 1 + opening.end() - 1
    )


def _expected_sides(block: _Block) -> list[str]:
    sides: list[str] = []
    for line in block.lines:
        if "assert" not in line:
            continue
        sides.extend(
            match.group(1).strip()
            for match in _ASSERT_EXPECTED_RE.finditer(line)
        )
    return sides


# GATE-EVIDENCE-EXEMPT(_is_battery): private predicate; mutation-pinned in BOTH directions through MIN_VARIANTS=0 and MIN_VARIANTS=999, and through REQUIRE_INPUT_ONLY_PARAMS on a constructed isolating diff.
def _is_battery(block: _Block, module_text: str) -> bool:
    if _variant_count(block, module_text) < MIN_VARIANTS:
        return False
    if not any(
        _LITERAL_EXPECTED_RE.match(side) for side in _expected_sides(block)
    ):
        return False
    if REQUIRE_INPUT_ONLY_PARAMS:
        joined = " ".join(_expected_sides(block))
        for name in _argnames(block.text):
            if re.search(rf"\b{re.escape(name)}\b", joined):
                return False
    return True


def _tokens(name: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    parts = re.split(r"[^A-Za-z0-9]+", spaced)
    return {
        part.lower()
        for part in parts
        if len(part) >= 3 and part.lower() not in _GENERIC_TOKENS
    }


def _guard_literals(block: _Block) -> list[str]:
    """Input-side vacuity-guard literals in this block."""
    literals: list[str] = []
    for line in block.lines:
        for match in _VACUITY_RE.finditer(line):
            expr = match.group("expr")
            root = re.match(r"\s*([A-Za-z_]\w*)", expr)
            if "read_text(" in expr or (root and root.group(1) in _INPUT_ROOTS):
                literals.append(match.group("lit"))
    return literals


# GATE-EVIDENCE-EXEMPT(_attributed): private predicate; mutation-pinned through REQUIRE_VACUITY_GUARD, which is the knob that makes attribution load-bearing.
def _attributed(block: _Block, symbol: str) -> bool:
    """True when a vacuity guard in this block names the gate's input."""
    if not REQUIRE_VACUITY_GUARD:
        return True
    symbol_tokens = _tokens(symbol)
    if not symbol_tokens:
        return False
    needed = 2 if len(symbol_tokens) >= 3 else 1
    for literal in _guard_literals(block):
        if len(symbol_tokens & _tokens(literal)) >= needed:
            return True
    return False


def _calls(block: _Block, symbol: str) -> bool:
    return bool(re.search(rf"\b{re.escape(symbol)}\s*\(", block.text))


# GATE-EVIDENCE-EXEMPT(_is_non_vacuous): private predicate; mutation-pinned through REQUIRE_VACUITY_GUARD together with _attributed.
def _is_non_vacuous(block: _Block) -> bool:
    """True when the block proves its own fixtures still carry what they claim.

    A battery of 8 mutations with no input-side guard is indistinguishable from
    8 copies of a case that already passed, which is why this is required of a
    composite pin even when the gate is attributed by a direct call.
    """
    if not REQUIRE_VACUITY_GUARD:
        return True
    return bool(_guard_literals(block))


# GATE-EVIDENCE-EXEMPT(_has_consumer_outcome): private predicate; mutation-pinned through REQUIRE_CONSUMER_OUTCOME on a constructed helper-only diff.
def _has_consumer_outcome(block: _Block) -> bool:
    if not REQUIRE_CONSUMER_OUTCOME:
        return True
    for line in block.lines:
        match = _CONSUMER_RE.search(line)
        if match and _LITERAL_EXPECTED_RE.match(match.group("expected").strip()):
            return True
    return False


# ── Analysis ─────────────────────────────────────────────────────────

_DISARM_MESSAGE = (
    "{symbol} ({path}:{line}) adds a gate with no disarm-direction battery. "
    "Add a test that drives {symbol} over at least {minimum} adversarial-but-"
    "plausible input variants (value vocabulary, line shape, encoding, "
    "placement, fencing, duplication) and asserts it still refuses every one."
)

_COMPOSITE_MESSAGE = (
    "{symbol} ({path}:{line}) is evidenced at the HELPER only — no composite "
    "battery drives it through its real CONSUMER. ISSUE-078 is the motivating "
    "case: the helper's own assertions all passed while `validate` and "
    "`next-action` disagreed with it on the same bytes. Add a battery of at "
    "least {minimum} input variants that asserts a consumer-level outcome (an "
    "exit code or a refusal constant) and carries an input-side vacuity guard "
    "proving each variant still contains what {symbol} is supposed to catch."
)


def analyze(diff_text: str) -> Report:
    """Classify a unified diff: which gates it adds, and what evidences them."""
    files = _parse(diff_text)
    gates = detect_gates(files)

    # Exemptions are read from the SOURCE half only. Scanning test files too
    # was a measured fail-open in this very gate: a test that merely QUOTES the
    # marker (this module's own suite does) silently exempted the symbol named
    # in its fixture string. An exemption annotates a gate, and gates live in
    # source, so that is where the marker belongs.
    exemptions: list[tuple[str, str]] = []
    for file in files:
        if is_test_path(file.path):
            continue
        for _, text in file.added:
            match = _EXEMPT_RE.search(text)
            if match and match.group("reason").strip():
                exemptions.append((match.group(1), match.group("reason").strip()))
    exempted = {symbol for symbol, _ in exemptions}

    blocks, module_text = _blocks(files)
    batteries = [block for block in blocks if _is_battery(block, module_text)]

    evidence: dict[str, dict[str, bool]] = {}
    findings: list[Finding] = []
    for gate in gates:
        disarm = any(
            _calls(block, gate.symbol) or _attributed(block, gate.symbol)
            for block in batteries
        )
        composite = any(
            (_calls(block, gate.symbol) or _attributed(block, gate.symbol))
            and _is_non_vacuous(block)
            and _has_consumer_outcome(block)
            for block in batteries
        )
        evidence[gate.symbol] = {"disarm": disarm, "composite": composite}

        if gate.symbol in exempted:
            continue
        context = {
            "symbol": gate.symbol,
            "path": gate.path,
            "line": gate.line,
            "minimum": MIN_VARIANTS,
        }
        if not disarm:
            findings.append(
                Finding(
                    gate.symbol,
                    gate.path,
                    gate.line,
                    "missing-disarm-battery",
                    _DISARM_MESSAGE.format(**context),
                )
            )
        elif not composite:
            findings.append(
                Finding(
                    gate.symbol,
                    gate.path,
                    gate.line,
                    "missing-composite-pin",
                    _COMPOSITE_MESSAGE.format(**context),
                )
            )

    return Report(gates, tuple(findings), tuple(exemptions), evidence)


def format_report(report: Report) -> list[str]:
    """Render a report as the lines the review checkpoint prints."""
    lines = [
        f"EXEMPT: {symbol} — {reason}" for symbol, reason in report.exemptions
    ]
    if not report.gates:
        lines.append("PASS: gate-evidence — no gate-adding change in the diff")
        return lines
    if not report.findings:
        exempted = {symbol for symbol, _ in report.exemptions}
        evidenced = sorted(
            {gate.symbol for gate in report.gates} - exempted
        )
        # Say WHICH gates were evidenced and which were merely exempted. A pass
        # that reads the same whether the rule was satisfied or waived is the
        # "legitimate quiet output is identical to defeated output" failure.
        summary = (
            f"PASS: gate-evidence — {len(evidenced)} gate(s) carry both "
            f"directions: {', '.join(evidenced) or 'none'}"
        )
        charged = sorted(exempted & {gate.symbol for gate in report.gates})
        if charged:
            summary += (
                f" | {len(charged)} exempted, NOT evidenced: "
                f"{', '.join(charged)}"
            )
        lines.append(summary)
        return lines
    lines.append(
        f"FAIL: gate-evidence — {len(report.findings)} gate(s) added without "
        "paired evidence (ISSUE-081 / SPEC-081)"
    )
    for finding in report.findings:
        lines.append(f"  - [{finding.kind}] {finding.message}")
    lines.append(
        "  Opt out only with an inline `# GATE-EVIDENCE-EXEMPT(<symbol>): "
        "<reason>` in the diff, justified in the PR body."
    )
    return lines


# ── CLI ──────────────────────────────────────────────────────────────


def _diff_from_range(rev_range: str, repo: str) -> str | None:
    result = subprocess.run(
        ["git", "diff", rev_range, "--"],
        capture_output=True,
        text=True,
        cwd=repo,
        timeout=_GIT_TIMEOUT,
    )
    return result.stdout if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that a diff's added gates carry paired evidence"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--diff-file", help="unified diff to analyze")
    source.add_argument("--range", dest="rev_range", help="git revision range")
    parser.add_argument("--repo", default=".", help="repo root for --range")
    parser.add_argument("--json", action="store_true", help="machine-readable output")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.diff_file:
        path = Path(args.diff_file)
        if not path.is_file():
            print(f"ERROR: diff file not found: {path}", file=sys.stderr)
            return 2
        diff_text = path.read_text(encoding="utf-8", errors="replace")
    else:
        diff_text = _diff_from_range(args.rev_range, args.repo)
        if diff_text is None:
            print(
                f"ERROR: `git diff {args.rev_range}` failed in {args.repo}",
                file=sys.stderr,
            )
            return 2

    report = analyze(diff_text)

    if args.json:
        print(
            json.dumps(
                {
                    "gates": [
                        {"symbol": g.symbol, "path": g.path, "line": g.line}
                        for g in report.gates
                    ],
                    "findings": [
                        {
                            "symbol": f.symbol,
                            "path": f.path,
                            "line": f.line,
                            "kind": f.kind,
                            "message": f.message,
                        }
                        for f in report.findings
                    ],
                    "exemptions": [
                        {"symbol": s, "reason": r} for s, r in report.exemptions
                    ],
                    "evidence": report.evidence,
                },
                indent=2,
            )
        )
    else:
        for line in format_report(report):
            print(line)

    return 1 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
