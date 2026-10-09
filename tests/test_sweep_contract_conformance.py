"""ISSUE-063: SPEC-056 contract conformance for scripts/verify_design_sweeps.py.

Sibling of tests/test_sweep_validators.py, same conventions (pinned PASS
fixture under tests/fixtures/sweeps/proto_pass; mutations derived in-test
by replacing the ACTUAL load-bearing strings; subprocess invocation via
sys.executable with the TestCliContract settings).

Two kinds of tests live here:

PINS (pass against the current implementation and must KEEP passing —
the issue constraint is that `all` WITH --class in text mode and every
per-sweep CLI stay byte-identical):
  - `all --class` text-mode golden output + exit code
  - per-sweep subcommand pass outputs (literal-quote / signature-move /
    ai-tell), byte-identical
  - single-line flex-calc-width still detected

RED (fail against the current implementation; each names a SPEC-056
contract deviation the fix must close):
  - AC-1  multi-line flex-calc-width declarations (plain split AND split
          with an interleaved CSS comment inside the declaration) evade
          the line-wise regex; must fail naming the tell the same way the
          single-line form does, and exit 0 once the declaration is
          removed (mutation pair, both directions in one test).
  - AC-2  `all --json` emits concatenated JSON objects; must be ONE
          top-level object keyed by sweep, parseable with a single
          json.loads, containing every sweep's contract-5 result shape —
          on a passing tree AND on a failing tree.
  - AC-3  `all` without --class exits 0 while silently skipping
          signature-move; must fail closed (non-zero, family codes 1/2)
          and name the unenforced sweep — with and without --json.

AC-4 is the pairing discipline: every defect is asserted in both
directions (defect present -> non-zero; defect removed -> 0).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify_design_sweeps.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sweeps"
PROTO_PASS = FIXTURES / "proto_pass"

QUOTE = "47.2-A"
SIG_CLASS = "signature-ledger-rule"

# Load-bearing anchor in the pass fixture's stylesheet that mutations
# replace (same anchor test_sweep_validators.py uses for this tell).
CSS_ANCHOR = "border: 1px solid var(--ink-navy);"

# flex-calc-width declaration variants. After CSS comment stripping and
# whitespace collapse all three are the SAME declaration; only the first
# is caught by the current line-wise scan.
FLEX_CALC_SINGLE_LINE = "width: calc(33% - 1rem);"
FLEX_CALC_MULTI_LINE = "width:\n    calc(33%\n      - 1rem);"
FLEX_CALC_MULTI_LINE_COMMENT = "width: /* cols */\n    calc(\n      33% - 1rem\n    );"

# Byte-identical pins of today's pass outputs (captured 2026-10-09 from
# the current implementation against tests/fixtures/sweeps/proto_pass).
GOLDEN_LITERAL_QUOTE = "literal-quote: PASS (1 quote(s) rendered verbatim)\n"
GOLDEN_SIGNATURE_MOVE = (
    "signature-move: PASS (.signature-ledger-rule defined and applied on all 2 screen(s))\n"
)
GOLDEN_AI_TELL = "ai-tell: PASS (3 file(s) swept, comments stripped)\n"
GOLDEN_ALL_WITH_CLASS = GOLDEN_LITERAL_QUOTE + GOLDEN_SIGNATURE_MOVE + GOLDEN_AI_TELL


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Invoke the script exactly like test_sweep_validators.TestCliContract."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
    )


def _mutate(path: Path, old: str, new: str) -> None:
    """Replace `old` with `new`, asserting the needle actually existed.

    Guards against fixture drift: a mutation that no longer removes the
    real string would turn the mutation test hollow.
    """
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation needle {old!r} not present in {path} (fixture drift)"
    path.write_text(text.replace(old, new), encoding="utf-8")


@pytest.fixture()
def proto(tmp_path: Path) -> Path:
    """Fresh copy of the pinned prototype pass fixture."""
    root = tmp_path / "proj"
    shutil.copytree(PROTO_PASS, root)
    return root


# ════════════════════════════════════════════════════════════════════
# PINS: `all --class` text mode + per-sweep CLIs stay byte-identical
# ════════════════════════════════════════════════════════════════════


class TestAllTextModeGoldenPin:
    def test_all_with_class_text_output_byte_identical_and_exit_zero(self):
        cp = _run_cli(
            "all", "--class", SIG_CLASS, "--project-path", str(PROTO_PASS)
        )
        assert cp.returncode == 0, cp.stdout + cp.stderr
        assert cp.stdout == GOLDEN_ALL_WITH_CLASS
        assert cp.stderr == ""


class TestPerSweepCliUnchangedPin:
    def test_literal_quote_pass_output_pinned(self):
        cp = _run_cli("literal-quote", "--project-path", str(PROTO_PASS))
        assert cp.returncode == 0, cp.stdout + cp.stderr
        assert cp.stdout == GOLDEN_LITERAL_QUOTE

    def test_signature_move_pass_output_pinned(self):
        cp = _run_cli(
            "signature-move", "--class", SIG_CLASS, "--project-path", str(PROTO_PASS)
        )
        assert cp.returncode == 0, cp.stdout + cp.stderr
        assert cp.stdout == GOLDEN_SIGNATURE_MOVE

    def test_ai_tell_pass_output_pinned(self):
        cp = _run_cli("ai-tell", "--project-path", str(PROTO_PASS))
        assert cp.returncode == 0, cp.stdout + cp.stderr
        assert cp.stdout == GOLDEN_AI_TELL


# ════════════════════════════════════════════════════════════════════
# AC-1: multi-line flex-calc-width declarations (RED)
# ════════════════════════════════════════════════════════════════════


class TestMultilineFlexCalcWidth:
    def test_single_line_declaration_still_fails_naming_tell(self, proto):
        # Pin: the fix must normalize to declarations WITHOUT regressing
        # the single-line detection.
        _mutate(proto / "prototype/styles.css", CSS_ANCHOR, FLEX_CALC_SINGLE_LINE)
        cp = _run_cli("ai-tell", "--project-path", str(proto))
        assert cp.returncode == 1, cp.stdout + cp.stderr
        assert "[flex-calc-width]" in cp.stdout
        assert "prototype/styles.css" in cp.stdout

    @pytest.mark.parametrize(
        "declaration",
        [FLEX_CALC_MULTI_LINE, FLEX_CALC_MULTI_LINE_COMMENT],
        ids=["split-across-lines", "split-with-interleaved-css-comment"],
    )
    def test_multiline_declaration_fails_then_removed_passes(self, proto, declaration):
        css = proto / "prototype/styles.css"

        # Defect present: declaration split across lines must be detected
        # and named the same way the single-line form names it
        # (tell id flex-calc-width against the stylesheet).
        _mutate(css, CSS_ANCHOR, declaration)
        bad = _run_cli("ai-tell", "--project-path", str(proto))
        assert bad.returncode == 1, (
            "multi-line flex-calc-width declaration evaded the sweep:\n"
            + bad.stdout
            + bad.stderr
        )
        assert "[flex-calc-width]" in bad.stdout
        assert "prototype/styles.css" in bad.stdout

        # Defect removed: the SAME tree with the declaration taken back
        # out must exit 0 (mutation pair, reverse direction).
        _mutate(css, declaration, CSS_ANCHOR)
        good = _run_cli("ai-tell", "--project-path", str(proto))
        assert good.returncode == 0, good.stdout + good.stderr
        assert "flex-calc-width" not in good.stdout

    def test_multiline_json_names_tell_and_file_like_single_line_form(self, proto):
        css = proto / "prototype/styles.css"

        # Reference: how the single-line form names the violation.
        _mutate(css, CSS_ANCHOR, FLEX_CALC_SINGLE_LINE)
        single = _run_cli("ai-tell", "--project-path", str(proto), "--json")
        assert single.returncode == 1, single.stdout + single.stderr
        single_hits = [
            v
            for v in json.loads(single.stdout)["violations"]
            if v["tell_id"] == "flex-calc-width"
        ]
        assert single_hits, single.stdout
        assert single_hits[0]["file"] == "prototype/styles.css"

        # Same declaration split across lines must produce the same
        # tell_id + file naming (line number may differ; the naming
        # contract is tell id and file).
        _mutate(css, FLEX_CALC_SINGLE_LINE, FLEX_CALC_MULTI_LINE)
        multi = _run_cli("ai-tell", "--project-path", str(proto), "--json")
        assert multi.returncode == 1, (
            "multi-line declaration evaded the sweep:\n" + multi.stdout + multi.stderr
        )
        multi_hits = [
            v
            for v in json.loads(multi.stdout)["violations"]
            if v["tell_id"] == "flex-calc-width"
        ]
        assert multi_hits, multi.stdout
        assert multi_hits[0]["file"] == single_hits[0]["file"]


# ════════════════════════════════════════════════════════════════════
# AC-2: `all --json` is ONE parseable document keyed by sweep (RED)
# ════════════════════════════════════════════════════════════════════


ALL_SWEEPS = {"literal-quote", "signature-move", "ai-tell"}


class TestAllJsonAggregate:
    def test_all_json_pass_tree_single_loads_keyed_by_sweep(self):
        cp = _run_cli(
            "all", "--class", SIG_CLASS, "--project-path", str(PROTO_PASS), "--json"
        )
        assert cp.returncode == 0, cp.stdout + cp.stderr

        # SPEC-056 contract 5: machine-readable. A SINGLE json.loads must
        # consume the whole stdout (concatenated objects raise here).
        payload = json.loads(cp.stdout)

        assert isinstance(payload, dict)
        assert set(payload) == ALL_SWEEPS
        for sweep in ALL_SWEEPS:
            result = payload[sweep]
            # Contract-5 per-sweep result shape (what each subcommand's
            # own --json emits today).
            assert result["status"] == "pass", (sweep, result)
            assert result["violations"] == [], (sweep, result)
        assert payload["ai-tell"]["exemptions"] == []

    def test_all_json_failing_tree_single_loads_reports_fail_and_all_sweeps(
        self, proto
    ):
        # Mutation direction: one sweep fails, the document must still be
        # one parseable object containing EVERY sweep's result.
        _mutate(proto / "prototype/screens/order-detail.html", QUOTE, "47-2-A")
        cp = _run_cli(
            "all", "--class", SIG_CLASS, "--project-path", str(proto), "--json"
        )
        assert cp.returncode == 1, cp.stdout + cp.stderr

        payload = json.loads(cp.stdout)

        assert set(payload) == ALL_SWEEPS
        assert payload["literal-quote"]["status"] == "fail"
        assert payload["literal-quote"]["violations"], payload["literal-quote"]
        assert payload["signature-move"]["status"] == "pass"
        assert payload["ai-tell"]["status"] == "pass"


# ════════════════════════════════════════════════════════════════════
# AC-3: `all` without --class fails closed (RED)
# ════════════════════════════════════════════════════════════════════


class TestAllWithoutClassFailsClosed:
    def test_all_without_class_exits_nonzero_naming_signature_move(self):
        cp = _run_cli("all", "--project-path", str(PROTO_PASS))
        # Family convention stays 0/1/2 — fail-closed means 1 or 2,
        # NEVER a silent 0 with signature-move unenforced.
        assert cp.returncode in (1, 2), (
            f"`all` without --class exited {cp.returncode} "
            "(fail-open: signature-move silently unenforced)\n"
            + cp.stdout
            + cp.stderr
        )
        combined = cp.stdout + cp.stderr
        assert "signature-move" in combined  # names the unenforced sweep

    def test_all_without_class_fails_closed_with_json_flag_too(self):
        # No flag combination may reopen the fail-open path.
        cp = _run_cli("all", "--project-path", str(PROTO_PASS), "--json")
        assert cp.returncode in (1, 2), (
            f"`all --json` without --class exited {cp.returncode}\n"
            + cp.stdout
            + cp.stderr
        )
        assert "signature-move" in cp.stdout + cp.stderr

    def test_all_with_class_on_pass_tree_still_exits_zero(self):
        # Pair direction (AC-4): providing --class keeps `all` passing.
        cp = _run_cli("all", "--class", SIG_CLASS, "--project-path", str(PROTO_PASS))
        assert cp.returncode == 0, cp.stdout + cp.stderr
