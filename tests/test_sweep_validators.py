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

ISSUE-064 (matcher hardening) adds six finding-scoped classes at the bottom
(F1-F6, provenance docs/review_notes/ISSUE-056.md + ISSUE-063.md): every
evasion gets a mutation pair — evasion present -> non-zero naming the
finding; evasion removed -> pass — plus scope pins so the hardening cannot
flip legitimate passes.
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

    def test_all_without_class_fails_closed_naming_signature_move(self, proto, capsys):
        # ISSUE-063 AC-3 (supersedes the fail-open "skips loudly" pin):
        # `all` without --class must exit non-zero — never a silent 0 with
        # the Signature Move sweep unenforced — and name the sweep. Both
        # a returned usage error and an argparse SystemExit(2) are
        # acceptable fail-closed shapes.
        try:
            rc = vds.main(["all", "--project-path", str(proto)])
        except SystemExit as exc:
            rc = exc.code
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert rc in (1, 2), f"fail-open: `all` without --class exited {rc}\n{out}"
        assert "signature-move" in out


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

    def test_js_commented_out_expect_is_hollow(self, testdir, capsys):
        # Gate-bypass class (review PR #101): a commented-out assertion must
        # not vouch for the block (mutation replaces the ACTUAL assertion).
        _mutate(
            testdir / "sample.test.ts",
            "expect(sum(1, 2)).toEqual(3);",
            "sum(1, 2); // expect(sum(1, 2)).toEqual(3); TODO re-enable",
        )
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "adds two numbers" in out  # hollow block named
        assert "handles zero" not in out  # asserting block not named

    def test_js_block_commented_expect_is_hollow(self, testdir, capsys):
        _mutate(
            testdir / "sample.test.ts",
            "expect(sum(1, 2)).toEqual(3);",
            "sum(1, 2); /* expect(sum(1, 2)).toEqual(3); */",
        )
        rc = vht.main(["--tests-dir", str(testdir)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "adds two numbers" in out

    def test_js_url_in_string_is_not_a_comment(self, testdir):
        # Guard the guard: https:// inside a string must not blank the
        # line's real assertion (the (?<!:) lookbehind on line comments).
        _mutate(
            testdir / "sample.test.ts",
            "expect(sum(0, 0)).toBe(0);",
            'const u = "https://example.com"; expect(sum(0, 0)).toBe(0);',
        )
        assert vht.main(["--tests-dir", str(testdir)]) == 0

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


# ════════════════════════════════════════════════════════════════════
# ISSUE-064: matcher hardening (F1-F6)
#
# Provenance: docs/review_notes/ISSUE-056.md (five adjacent Mediums) and
# docs/review_notes/ISSUE-063.md (folded first finding). Convention: each
# finding gets a mutation pair with the ACTUAL probe strings — evasion
# present -> non-zero naming the finding; evasion removed -> 0 — plus
# scope pins so the hardening cannot flip legitimate passes (zero
# contract loosening; the proto_pass golden pins must keep passing).
# ════════════════════════════════════════════════════════════════════

# Load-bearing pass-fixture anchors the ISSUE-064 mutations replace.
H1_ANCHOR = "<h1>Open ledgers</h1>"
CSS_ANCHOR = "border: 1px solid var(--ink-navy);"
RENDERED_QUOTE_SPAN = '<span class="mono">47.2-A</span>'
# Distinctive content of the out-of-tree file in the F5 containment tests:
# proving it appears NOWHERE in output proves the file was never read.
OUTSIDE_MARKER = "OUT-OF-TREE-MARKER-9f3c"


class TestAiTellEntityAndCaseNormalization:
    """F1: HTML entities decode (html.unescape, AFTER comment stripping,
    per-line in the line-wise scan) and all tell matching case-folds."""

    def _run(self, proto: Path, *extra: str) -> int:
        return vds.main(["ai-tell", "--project-path", str(proto), *extra])

    @pytest.mark.parametrize("entity", ["&mdash;", "&#8212;", "&#x2014;"])
    def test_entity_encoded_em_dash_fails_then_removed_passes(
        self, proto, entity, capsys
    ):
        screen = proto / "prototype/screens/home.html"
        probe = f"<h1>Fast {entity} reliable</h1>"
        _mutate(screen, H1_ANCHOR, probe)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, f"entity-encoded em-dash {entity} evaded the sweep:\n{out}"
        assert "em-dash" in out  # names the tell, identically to the literal form
        assert "home.html" in out

        _mutate(screen, probe, H1_ANCHOR)  # reverse direction
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "em-dash" not in out

    def test_uppercase_100vh_fails_then_removed_passes(self, proto, capsys):
        css = proto / "prototype/styles.css"
        _mutate(css, "min-height: 100dvh;", "height: 100VH;")
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, f"case-variant 100VH evaded the sweep:\n{out}"
        assert "100vh" in out  # names the tell id
        assert "styles.css" in out

        _mutate(css, "height: 100VH;", "min-height: 100dvh;")
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "100vh" not in out

    def test_uppercase_calc_width_fails_then_removed_passes(self, proto, capsys):
        css = proto / "prototype/styles.css"
        _mutate(css, CSS_ANCHOR, "WIDTH: CALC(33% - 1rem);")
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, f"case-variant CALC() evaded the sweep:\n{out}"
        assert "flex-calc-width" in out
        assert "styles.css" in out

        _mutate(css, "WIDTH: CALC(33% - 1rem);", CSS_ANCHOR)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "flex-calc-width" not in out

    def test_uppercase_generic_name_fails_then_removed_passes(self, proto, capsys):
        # JOHN DOE: case variant of a currently case-sensitive tell.
        screen = proto / "prototype/screens/home.html"
        _mutate(screen, "Open ledgers", "JOHN DOE ledgers")
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, f"case-variant JOHN DOE evaded the sweep:\n{out}"
        assert "generic-name" in out
        assert "home.html" in out

        _mutate(screen, "JOHN DOE ledgers", "Open ledgers")
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "generic-name" not in out

    def test_entity_encoded_comment_markers_are_rendered_text(self, proto, capsys):
        # Decode AFTER comment stripping: &lt;!-- renders as literal text,
        # so it must NOT become a strippable comment — the entity-encoded
        # em-dash between the entity-encoded markers IS rendered.
        screen = proto / "prototype/screens/home.html"
        probe = "<h1>Example: &lt;!-- draft &mdash; note --&gt;</h1>"
        _mutate(screen, H1_ANCHOR, probe)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, (
            "em-dash inside an entity-encoded (rendered) comment was not "
            f"flagged — decode must run AFTER comment stripping:\n{out}"
        )
        assert "em-dash" in out

        _mutate(screen, probe, H1_ANCHOR)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "em-dash" not in out

    def test_benign_amp_entity_not_flagged(self, proto, capsys):
        # Negative pin: entity decoding must not invent violations.
        _mutate(
            proto / "prototype/screens/home.html",
            H1_ANCHOR,
            "<h1>Ledgers &amp; orders</h1>",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "ai-tell: PASS" in out

    def test_em_dash_entity_inside_real_html_comment_not_flagged(self, proto, capsys):
        # Negative pin: comments are stripped BEFORE decoding, so an
        # entity-encoded em-dash inside a real <!-- --> is never rendered.
        _mutate(
            proto / "prototype/screens/home.html",
            "</body>",
            "<!-- draft &mdash; internal -->\n</body>",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "em-dash" not in out

    def test_entity_decode_keeps_reported_line_numbers_exact(self, proto, capsys):
        # Per-line decode in the line-wise scan: a &NewLine;-style entity on
        # an earlier line must not shift the line reported for a violation.
        screen = proto / "prototype/screens/home.html"
        _mutate(
            screen,
            "<p>3 ledgers reconciled this week. Next close: Friday 18:40.</p>",
            "<p>3 ledgers&NewLine;reconciled.</p>\n      <p>Fast &mdash; reliable</p>",
        )
        source = screen.read_text(encoding="utf-8").splitlines()
        expected_line = next(
            i for i, line in enumerate(source, 1) if "&mdash;" in line
        )
        rc = self._run(proto, "--json")
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1, payload
        hits = [v for v in payload["violations"] if v["tell_id"] == "em-dash"]
        assert hits, payload["violations"]
        assert hits[0]["file"] == "prototype/screens/home.html"
        assert hits[0]["line"] == expected_line


class TestHollowMockNameRule:
    """F2: a bare name/attribute merely containing "mock" is not an
    assertion mechanism; mock tests still count via assert_* attributes."""

    HOLLOW_REPROS = {
        "mock-name-assigned": (
            "def test_loads_data():\n"
            '    mock_data = {"a": 1}\n'
            "    print(mock_data)\n"
        ),
        "mock-fixture-param-unasserted": (
            "def test_x(mock_db):\n    mock_db.start()\n"
        ),
        "mock-name-trivial": "def test_trivial():\n    mocked = None\n",
    }
    HOLLOW_NAMES = {
        "mock-name-assigned": "test_loads_data",
        "mock-fixture-param-unasserted": "test_x",
        "mock-name-trivial": "test_trivial",
    }

    # Legitimate mock usage: counts via the untouched attr.startswith
    # ("assert") rule, exactly how the pinned tests_pass fixture passes.
    LEGIT_MOCK_TEST = (
        "from unittest.mock import Mock\n"
        "\n"
        "\n"
        "def test_mock_asserts_delegation():\n"
        "    m = Mock()\n"
        '    m("x")\n'
        "    m.assert_called_once()\n"
    )

    @pytest.mark.parametrize("key", sorted(HOLLOW_REPROS))
    def test_bare_mock_name_does_not_vouch(self, tmp_path, key, capsys):
        f = tmp_path / "test_mock_rule.py"
        f.write_text(
            self.HOLLOW_REPROS[key] + "\n\n" + self.LEGIT_MOCK_TEST,
            encoding="utf-8",
        )
        rc = vht.main([str(f)])
        out = capsys.readouterr().out
        assert rc == 1, f"mock-anywhere-in-name false pass ({key}):\n{out}"
        assert self.HOLLOW_NAMES[key] in out  # names the hollow test function
        assert "test_mock_asserts_delegation" not in out  # legit test not named

    def test_mock_with_assert_attribute_still_passes(self, tmp_path, capsys):
        # Scope pin: ONLY the bare mock-name rule is dropped — a mock test
        # asserting via m.assert_called_once() keeps passing.
        f = tmp_path / "test_mock_rule.py"
        f.write_text(self.LEGIT_MOCK_TEST, encoding="utf-8")
        rc = vht.main([str(f)])
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "HOLLOW" not in out


class TestLiteralQuoteNonRenderedPlacements:
    """F3: <script> element bodies and data-* attribute VALUES are blanked
    before the quote search — exactly those two surfaces, nothing more."""

    def _run(self, proto: Path) -> int:
        return vds.main(["literal-quote", "--project-path", str(proto)])

    def test_quote_only_in_data_attribute_fails_then_rendered_restores(
        self, proto, capsys
    ):
        screen = proto / "prototype/screens/order-detail.html"
        probe = '<span class="mono" data-note="47.2-A">(redacted)</span>'
        _mutate(screen, RENDERED_QUOTE_SPAN, probe)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, (
            f"quote only in a data-* attribute satisfied literal-quote:\n{out}"
        )
        assert QUOTE in out  # names the quote as not rendered

        _mutate(screen, probe, RENDERED_QUOTE_SPAN)  # reverse direction
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "MISSING" not in out

    def test_quote_only_in_script_block_fails_then_rendered_restores(
        self, proto, capsys
    ):
        screen = proto / "prototype/screens/order-detail.html"
        probe = "<script>// 47.2-A</script>"
        _mutate(screen, RENDERED_QUOTE_SPAN, probe)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, (
            f"quote only in a <script> body satisfied literal-quote:\n{out}"
        )
        assert QUOTE in out

        _mutate(screen, probe, RENDERED_QUOTE_SPAN)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "MISSING" not in out

    def test_quote_in_alt_attribute_still_satisfies(self, proto, capsys):
        # Scope pin: other attributes (alt/aria-label text) stay accepted
        # rendered surfaces — only data-* values are blanked.
        _mutate(
            proto / "prototype/screens/order-detail.html",
            RENDERED_QUOTE_SPAN,
            '<img alt="47.2-A" src="order.png">',
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "MISSING" not in out

    def test_quote_in_style_block_still_satisfies(self, proto, capsys):
        # Scope pin: <style> bodies are NOT blanked by this finding.
        _mutate(
            proto / "prototype/screens/order-detail.html",
            RENDERED_QUOTE_SPAN,
            '<style>.order-id::after { content: "47.2-A"; }</style>',
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "MISSING" not in out


class TestAiTellZeroScreenVacuity:
    """F4: an empty screens list is a violation in run_ai_tell, independent
    of styles.css presence (no vacuous half-pass)."""

    def test_zero_screens_with_css_present_fails_reporting_empty_input(
        self, proto, capsys
    ):
        for f in (proto / "prototype/screens").glob("*.html"):
            f.unlink()
        assert (proto / "prototype/styles.css").is_file()  # css half IS present
        rc = vds.main(["ai-tell", "--project-path", str(proto)])
        out = capsys.readouterr().out
        assert rc == 1, f"vacuous half-pass: ai-tell exited {rc} with zero screens\n{out}"
        assert "screen" in out.lower()  # reports the empty input set
        assert "PASS" not in out

    def test_zero_screens_with_css_present_json_keeps_violation_key_shape(
        self, proto, capsys
    ):
        for f in (proto / "prototype/screens").glob("*.html"):
            f.unlink()
        rc = vds.main(["ai-tell", "--project-path", str(proto), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1, payload
        assert payload["status"] == "fail"
        assert payload["violations"], payload
        for v in payload["violations"]:
            # Existing violation key shape, unchanged by the hardening.
            assert set(v) == {"file", "line", "tell_id", "snippet"}, v


class TestInputContainment:
    """F5: any file the script would read whose resolve() falls outside
    every sanctioned root (resolved --project-path + explicitly passed
    --philosophy/--screens-dir/--css) is never read; the run fails closed
    as a usage error (exit 2, ERROR line on stderr, no JSON)."""

    CONTAINMENT_MSG = "resolves outside the project tree"

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_design_sweeps.py"), *args],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )

    @pytest.fixture()
    def outside_dir(self, tmp_path: Path) -> Path:
        """Directory OUTSIDE the proto project tree (sibling of tmp_path/proj)
        holding an .html with a distinctive marker string and an em-dash tell."""
        outside = tmp_path / "outside_tree"
        outside.mkdir()
        (outside / "evil.html").write_text(
            f"<p>{OUTSIDE_MARKER} — leaked</p>\n", encoding="utf-8"
        )
        return outside

    def _symlink_screens_outside(
        self, proto: Path, outside_dir: Path
    ) -> tuple[Path, Path]:
        screens = proto / "prototype" / "screens"
        parked = proto / "prototype" / "screens_parked"
        screens.rename(parked)
        screens.symlink_to(outside_dir, target_is_directory=True)
        return screens, parked

    def test_symlinked_screens_outside_tree_fails_closed_then_removed_passes(
        self, proto, outside_dir
    ):
        screens, parked = self._symlink_screens_outside(proto, outside_dir)
        cp = self._run_cli("ai-tell", "--project-path", str(proto))
        assert cp.returncode == 2, (
            f"out-of-tree symlinked screens dir was scanned (exit {cp.returncode}, "
            f"want usage error 2)\n{cp.stdout}{cp.stderr}"
        )
        assert "ERROR" in cp.stderr
        assert self.CONTAINMENT_MSG in cp.stderr
        # Names the resolved-outside path (the containment decision).
        assert str(outside_dir.resolve()) in cp.stderr
        # The out-of-tree file was NEVER read: its content appears nowhere.
        assert OUTSIDE_MARKER not in cp.stdout + cp.stderr

        # Removing the symlink restores normal behavior.
        screens.unlink()
        parked.rename(screens)
        ok = self._run_cli("ai-tell", "--project-path", str(proto))
        assert ok.returncode == 0, ok.stdout + ok.stderr

    def test_all_with_outside_symlink_fails_closed(self, proto, outside_dir):
        self._symlink_screens_outside(proto, outside_dir)
        cp = self._run_cli("all", "--class", SIG_CLASS, "--project-path", str(proto))
        assert cp.returncode == 2, (
            f"`all` scanned an out-of-tree symlink (exit {cp.returncode})\n"
            f"{cp.stdout}{cp.stderr}"
        )
        assert self.CONTAINMENT_MSG in cp.stderr
        assert OUTSIDE_MARKER not in cp.stdout + cp.stderr

    def test_containment_usage_error_emits_no_json(self, proto, outside_dir):
        # Exit-2 convention (existing precedent): ERROR on stderr, NO JSON.
        self._symlink_screens_outside(proto, outside_dir)
        cp = self._run_cli("ai-tell", "--project-path", str(proto), "--json")
        assert cp.returncode == 2, cp.stdout + cp.stderr
        assert cp.stdout == ""
        assert self.CONTAINMENT_MSG in cp.stderr

    def test_symlink_resolving_inside_tree_is_scanned_not_rejected(self, proto):
        # Resolved-to-resolved comparison: an in-tree symlink must neither
        # false-trip containment (macOS /tmp -> /private/tmp class) nor be
        # silently skipped.
        real = proto / "prototype" / "real.html"
        real.write_text(
            (proto / "prototype" / "screens" / "home.html").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        link = proto / "prototype" / "screens" / "link.html"
        link.symlink_to(Path("..") / "real.html")

        ok = self._run_cli("ai-tell", "--project-path", str(proto))
        assert ok.returncode == 0, ok.stdout + ok.stderr
        assert self.CONTAINMENT_MSG not in ok.stderr  # no false positive

        # ...and the linked file is genuinely swept, not silently skipped:
        _mutate(real, H1_ANCHOR, "<h1>Open — ledgers</h1>")
        bad = self._run_cli("ai-tell", "--project-path", str(proto))
        assert bad.returncode == 1, bad.stdout + bad.stderr
        assert "em-dash" in bad.stdout

    def test_explicit_screens_dir_outside_project_is_sanctioned(
        self, proto, outside_dir
    ):
        # Sanctioned roots include explicitly passed targets: pointing
        # --screens-dir outside the project is the caller's decision and
        # must keep scanning normally (evil.html carries an em-dash tell).
        cp = self._run_cli(
            "ai-tell", "--project-path", str(proto), "--screens-dir", str(outside_dir)
        )
        assert cp.returncode == 1, cp.stdout + cp.stderr
        assert "em-dash" in cp.stdout
        assert self.CONTAINMENT_MSG not in cp.stderr


class TestAiTellHtmlDeclarationCssCommentBlanking:
    """F6 (folded from ISSUE-063 review): the declaration-level scan on
    HTML targets blanks CSS comments first — scoped to that pass ONLY."""

    INLINE_STYLE_PROBE = '<div style="width: /* cols */ calc(33% - 1rem)">Open ledgers</div>'
    STYLE_BLOCK_PROBE = "<style>.col { width: /* c */ calc(33% - 1rem); }</style>"

    def _run(self, proto: Path) -> int:
        return vds.main(["ai-tell", "--project-path", str(proto)])

    def test_inline_style_comment_interleaved_calc_fails_then_removed_passes(
        self, proto, capsys
    ):
        screen = proto / "prototype/screens/home.html"
        _mutate(screen, H1_ANCHOR, self.INLINE_STYLE_PROBE)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, (
            f"comment-interleaved inline-style calc evaded the sweep:\n{out}"
        )
        assert "flex-calc-width" in out
        assert "home.html" in out

        _mutate(screen, self.INLINE_STYLE_PROBE, H1_ANCHOR)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "flex-calc-width" not in out

    def test_style_block_comment_interleaved_calc_fails_then_removed_passes(
        self, proto, capsys
    ):
        screen = proto / "prototype/screens/home.html"
        probe = self.STYLE_BLOCK_PROBE + "\n      " + H1_ANCHOR
        _mutate(screen, H1_ANCHOR, probe)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, (
            f"comment-interleaved <style> block calc evaded the sweep:\n{out}"
        )
        assert "flex-calc-width" in out
        assert "home.html" in out

        _mutate(screen, probe, H1_ANCHOR)
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "flex-calc-width" not in out

    def test_em_dash_between_literal_comment_markers_in_body_text_still_flagged(
        self, proto, capsys
    ):
        # Semantics pin: CSS-comment blanking is scoped to the declaration-
        # level pass ONLY — rendered body text between literal /* */ keeps
        # line-wise rendered-text semantics, so the em-dash stays flagged.
        _mutate(
            proto / "prototype/screens/home.html",
            H1_ANCHOR,
            "<h1>note /* — */ aside</h1>",
        )
        rc = self._run(proto)
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "em-dash" in out
