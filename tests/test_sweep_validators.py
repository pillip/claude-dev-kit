"""Tests for the SPEC-056 sweep validators (ISSUE-056).

Covers:
  - scripts/verify_design_sweeps.py  (literal-quote / signature-move /
    ai-tell / all subcommands)
  - scripts/verify_hollow_tests.py   (Python AST + JS segment heuristic)

Pattern (ISSUE-045 verify-family): pinned PASS fixtures under
tests/fixtures/sweeps/; mutations are derived in-test by replacing the
ACTUAL load-bearing strings of the pass fixture (review lesson: absence
guards are mutation-tested with actually-removed strings, and presence
assertions are paired with absence assertions). AC-4: no validator may
pass vacuously on an empty input set.

Exit-code contract (verify_* family): 0 pass / 1 violations / 2 usage error.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import verify_design_sweeps as vds
from scripts import verify_hollow_tests as vht

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sweeps"
PROTO_PASS = FIXTURES / "proto_pass"
TESTS_PASS = FIXTURES / "tests_pass"

QUOTE = "47.2-A"
SIG_CLASS = "signature-ledger-rule"


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


@pytest.fixture()
def testdir(tmp_path: Path) -> Path:
    """Fresh copy of the pinned hollow-test pass fixture.

    Both pinned files carry a .txt suffix (so pytest collection, the kit's
    test-file checkpoints, and the autotest hook never treat the input data
    as real tests) and are renamed into runnable names here.
    """
    root = tmp_path / "sample_tests"
    shutil.copytree(TESTS_PASS, root)
    (root / "sample_test_py.txt").rename(root / "test_sample.py")
    (root / "sample.test.ts.txt").rename(root / "sample.test.ts")
    return root


# ════════════════════════════════════════════════════════════════════
# literal-quote (AC-1)
# ════════════════════════════════════════════════════════════════════


class TestLiteralQuote:
    def _run(self, proto: Path, *extra: str) -> int:
        return vds.main(["literal-quote", "--project-path", str(proto), *extra])

    def test_pass_fixture_exits_zero(self, proto, capsys):
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0
        assert "MISSING" not in out  # paired absence assertion

    def test_one_char_alteration_fails_naming_quote(self, proto, capsys):
        _mutate(proto / "prototype/screens/order-detail.html", QUOTE, "47-2-A")
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert QUOTE in out  # failure names the missing quote

    def test_quote_moved_into_comment_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/order-detail.html",
            '<span class="mono">47.2-A</span>',
            "<!-- 47.2-A -->",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert QUOTE in out

    def test_whitespace_insensitive_match_passes(self, proto):
        # Quote with an internal space; the screen splits it across a newline.
        _mutate(
            proto / "docs/design_philosophy.md",
            'literal_quote: "47.2-A"',
            'literal_quote: "Plate 47"',
        )
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Plate\n          47</h1>",
        )
        assert self._run(proto) == 0

    def test_explicit_skip_marker_exits_zero(self, proto, capsys):
        _mutate(
            proto / "docs/design_philosophy.md",
            'literal_quote: "47.2-A" — sample order ID, shown in mono on the order detail screen',
            "literal_quote: (skipped — interview not run)",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0
        assert "skip" in out.lower()

    def test_missing_field_fails(self, proto, capsys):
        _mutate(
            proto / "docs/design_philosophy.md",
            "literal_quote:",
            "reference_quote:",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "literal_quote" in out

    def test_empty_screens_dir_never_passes(self, proto):
        for f in (proto / "prototype/screens").glob("*.html"):
            f.unlink()
        assert self._run(proto) == 1

    def test_missing_philosophy_is_usage_error(self, proto):
        (proto / "docs/design_philosophy.md").unlink()
        assert self._run(proto) == 2


# ════════════════════════════════════════════════════════════════════
# signature-move (AC-2)
# ════════════════════════════════════════════════════════════════════


class TestSignatureMove:
    def _run(self, proto: Path, *extra: str) -> int:
        return vds.main(
            ["signature-move", "--class", SIG_CLASS, "--project-path", str(proto), *extra]
        )

    def test_pass_fixture_exits_zero(self, proto, capsys):
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0
        assert "home.html" not in out or "not applied" not in out

    def test_screen_missing_class_fails_naming_screen(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            f'class="card {SIG_CLASS}"',
            'class="card"',
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "home.html" in out  # names the offending screen
        assert "order-detail.html" not in out  # paired absence: compliant screen not named

    def test_class_absent_from_css_fails_naming_css(self, proto, capsys):
        _mutate(
            proto / "prototype/styles.css",
            f".{SIG_CLASS} {{",
            ".some-other-rule {",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "styles.css" in out

    def test_class_token_match_is_not_substring(self, proto, capsys):
        # signature-ledger-rule-xl must NOT satisfy signature-ledger-rule.
        _mutate(
            proto / "prototype/screens/home.html",
            f'class="card {SIG_CLASS}"',
            f'class="card {SIG_CLASS}-xl"',
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "home.html" in out

    def test_empty_screens_dir_never_passes(self, proto):
        for f in (proto / "prototype/screens").glob("*.html"):
            f.unlink()
        assert self._run(proto) == 1


# ════════════════════════════════════════════════════════════════════
# ai-tell (occurrence-whitelist over RENDERED patterns)
# ════════════════════════════════════════════════════════════════════


class TestAiTellSweep:
    def _run(self, proto: Path, *extra: str) -> int:
        return vds.main(["ai-tell", "--project-path", str(proto), *extra])

    def test_clean_fixture_passes(self, proto, capsys):
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0
        assert "em-dash" not in out  # paired absence assertion

    def test_em_dash_inserted_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Open — ledgers</h1>",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "em-dash" in out
        assert "home.html" in out

    def test_em_dash_inside_html_comment_not_flagged(self, proto):
        # Rendered-only semantics: comments are stripped before sweeping.
        _mutate(
            proto / "prototype/screens/home.html",
            "</body>",
            "<!-- draft note — internal -->\n</body>",
        )
        assert self._run(proto) == 0

    def test_100vh_without_space_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/styles.css",
            "min-height: 100dvh;",
            "height:100vh;",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "100vh" in out

    def test_100vh_with_space_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/styles.css",
            "min-height: 100dvh;",
            "height: 100vh;",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "100vh" in out

    def test_100dvh_is_not_flagged(self, proto):
        # The clean fixture uses min-height: 100dvh (the allowed form).
        assert self._run(proto) == 0

    def test_100vh_inside_css_comment_not_flagged(self, proto):
        _mutate(
            proto / "prototype/styles.css",
            "/* signature move: offset ledger rule */",
            "/* fallback for height: 100vh engines */",
        )
        assert self._run(proto) == 0

    def test_flex_calc_width_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/styles.css",
            "border: 1px solid var(--ink-navy);",
            "width: calc(33% - 1rem);",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "flex-calc-width" in out

    def test_generic_name_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "Open ledgers",
            "John Doe's ledgers",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "generic-name" in out

    def test_fake_perfect_number_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "3 ledgers reconciled this week",
            "99.99% reconciled this week",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "fake-perfect-number" in out

    def test_filler_verb_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "Open ledgers",
            "Seamless ledgers",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "filler-verb" in out

    def test_scroll_cue_fails(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "Open ledgers",
            "Scroll to explore",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1
        assert "scroll-cue" in out

    def test_exempt_em_dash_passes_and_reports_exemption(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Open — ledgers</h1>",
        )
        rc = self._run(proto, "--exempt", "em-dash")
        out = capsys.readouterr().out
        assert rc == 0
        assert "exempt" in out.lower()
        assert "em-dash" in out

    def test_exemption_does_not_cover_other_tells(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Open — ledgers</h1>",
        )
        _mutate(
            proto / "prototype/screens/home.html",
            "3 ledgers reconciled this week",
            "99.99% reconciled this week",
        )
        rc = self._run(proto, "--exempt", "em-dash")
        out = capsys.readouterr().out
        assert rc == 1
        assert "fake-perfect-number" in out

    def test_unknown_exempt_id_is_usage_error(self, proto):
        assert self._run(proto, "--exempt", "not-a-tell") == 2

    def test_empty_target_set_never_passes(self, proto):
        for f in (proto / "prototype/screens").glob("*.html"):
            f.unlink()
        (proto / "prototype/styles.css").unlink()
        assert self._run(proto) == 1


# ════════════════════════════════════════════════════════════════════
# all subcommand (aggregate)
# ════════════════════════════════════════════════════════════════════


class TestAllSubcommand:
    def test_all_three_sweeps_pass_on_clean_fixture(self, proto):
        rc = vds.main(["all", "--class", SIG_CLASS, "--project-path", str(proto)])
        assert rc == 0

    def test_all_fails_when_quote_mutated(self, proto, capsys):
        _mutate(proto / "prototype/screens/order-detail.html", QUOTE, "47-2-A")
        rc = vds.main(["all", "--class", SIG_CLASS, "--project-path", str(proto)])
        out = capsys.readouterr().out
        assert rc == 1
        assert QUOTE in out

    def test_all_without_class_skips_signature_move_loudly(self, proto, capsys):
        rc = vds.main(["all", "--project-path", str(proto)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "signature-move" in out
        assert "skip" in out.lower()


# ════════════════════════════════════════════════════════════════════
# hollow tests (AC-3)
# ════════════════════════════════════════════════════════════════════


class TestHollowTests:
    def test_all_asserting_fixture_passes(self, testdir, capsys):
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "HOLLOW" not in out  # paired absence assertion

    def test_assertion_free_python_function_fails_naming_it(self, testdir, capsys):
        _mutate(testdir / "test_sample.py", "assert result == 5", "_ = result")
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "test_addition" in out  # names the hollow function
        assert "test_raises_on_bad_input" not in out  # asserting tests not named

    def test_string_literal_assert_does_not_count(self, testdir, capsys):
        # AST semantics: the word "assert" inside a string is not an assertion.
        _mutate(
            testdir / "test_sample.py",
            "assert result == 5",
            'print("assert nothing")',
        )
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "test_addition" in out

    def test_js_expect_removed_fails_naming_title(self, testdir, capsys):
        _mutate(
            testdir / "sample.test.ts",
            "expect(sum(1, 2)).toEqual(3);",
            "sum(1, 2);",
        )
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "adds two numbers" in out  # hollow block named by title
        assert "handles zero" not in out  # asserting block not named

    def test_test_file_without_test_functions_is_hollow(self, testdir, capsys):
        (testdir / "test_empty.py").write_text(
            "def helper():\n    return 1\n", encoding="utf-8"
        )
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "test_empty.py" in out

    def test_empty_dir_never_passes(self, tmp_path):
        empty = tmp_path / "no_tests_here"
        empty.mkdir()
        assert vht.main(["--tests-dir", str(empty)]) == 1

    def test_nonexistent_dir_is_usage_error(self, tmp_path):
        assert vht.main(["--tests-dir", str(tmp_path / "missing")]) == 2

    def test_explicit_file_arguments_mode(self, testdir):
        assert vht.main([str(testdir / "test_sample.py")]) == 0


# ════════════════════════════════════════════════════════════════════
# --json output
# ════════════════════════════════════════════════════════════════════


class TestJsonOutput:
    def test_ai_tell_json_violations_are_pinned_to_fixture_paths(self, proto, capsys):
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Open — ledgers</h1>",
        )
        rc = vds.main(["ai-tell", "--project-path", str(proto), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert payload["status"] == "fail"
        tells = [v for v in payload["violations"] if v["tell_id"] == "em-dash"]
        assert tells, payload["violations"]
        # Path pinned relative to the project root (not an arbitrary suffix match).
        assert tells[0]["file"] == "prototype/screens/home.html"
        assert isinstance(tells[0]["line"], int) and tells[0]["line"] > 0

    def test_hollow_json_names_file_and_function(self, testdir, capsys):
        _mutate(testdir / "test_sample.py", "assert result == 5", "_ = result")
        rc = vht.main(["--tests-dir", str(testdir), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert payload["status"] == "fail"
        entries = [h for h in payload["hollow"] if h["test"] == "test_addition"]
        assert entries, payload["hollow"]
        assert entries[0]["file"] == str(testdir / "test_sample.py")


# ════════════════════════════════════════════════════════════════════
# CLI exit-code contract (end-to-end, subprocess)
# ════════════════════════════════════════════════════════════════════


class TestCliContract:
    def _run_cli(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / script), *args],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )

    def test_design_sweeps_cli_pass_then_mutated_fail(self, proto):
        ok = self._run_cli(
            "verify_design_sweeps.py", "literal-quote", "--project-path", str(proto)
        )
        assert ok.returncode == 0, ok.stdout + ok.stderr
        _mutate(proto / "prototype/screens/order-detail.html", QUOTE, "47-2-A")
        bad = self._run_cli(
            "verify_design_sweeps.py", "literal-quote", "--project-path", str(proto)
        )
        assert bad.returncode == 1
        assert QUOTE in bad.stdout

    def test_hollow_cli_pass_then_mutated_fail(self, testdir):
        ok = self._run_cli("verify_hollow_tests.py", "--tests-dir", str(testdir))
        assert ok.returncode == 0, ok.stdout + ok.stderr
        _mutate(testdir / "test_sample.py", "assert result == 5", "_ = result")
        bad = self._run_cli("verify_hollow_tests.py", "--tests-dir", str(testdir))
        assert bad.returncode == 1
        assert "test_addition" in bad.stdout
