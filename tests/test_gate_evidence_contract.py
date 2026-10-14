"""ISSUE-081 — a gate-adding PR must evidence BOTH directions.

The pattern "a newly added defence fails OPEN" was measured at High severity in
four consecutive sprints (ISSUE-068/PR #121, ISSUE-076/PR #128, ISSUE-078/PR
#133, ISSUE-072/PR #135). Every instance tested that its gate FIRES and shipped
without a test that it cannot be DISARMED, or that it holds through the real
consumer rather than only at the helper it was unit-tested against.

SPEC-081 chose Option C: a blocking ``review/gate-evidence`` checkpoint backed by
``scripts/verify_gate_evidence.py``. These tests replay the two REAL diffs of
ISSUE-078 — pre-fix (``d328a6c^``) and post-fix (``d328a6c``) — plus a real
non-gate PR diff (ISSUE-074 / PR #132), from frozen fixtures whose provenance is
recorded in ``tests/fixtures/gate_evidence/README.md``.

AC coverage map:

* AC-1 → ``TestAC1ArmOnlyGateIsRefused``
* AC-2 → ``TestAC2HelperConsumerDisagreementIsSurfaced``
* AC-3 → ``TestAC3NonGateDiffPaysNoTax``,
  ``TestTheTestPathOracleIsImportedNotRetyped`` (the re-typed test-path
  classifier charged a fabricated finding to any repo laid out with ``test/``
  or ``__tests__/``) (+ the phase-partition pins in
  ``tests/test_verify_checkpoint_contract.py``)
* AC-4 → ``TestAC4AGateAddingDiffPassesCleanly`` — the worked example, a
  constructed gate-adding diff carrying both directions that reaches exit 0
  through the real consumer. ``TestAC4BothDirectionsEvidencedPasses`` is the
  REAL-fixture half and is weaker than its name suggests: the ISSUE-078
  post-fix diff adds a second, genuinely unevidenced gate, so it exits 1 and
  is not an instance of AC-4's premise at all.
* AC-5 → ``TestAC5TheMechanismIsSubjectToItsOwnRule`` (disarm battery),
  ``TestAC5CompositePinThroughTheRealConsumer`` (composite, via the
  ``verify_checkpoint.py`` CLI), ``TestAC5MutationMatrix`` (both directions)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_checkpoint as vc  # noqa: E402
import verify_gate_evidence as vge  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "gate_evidence"
PRE_FIX = FIXTURES / "issue_078_pre_fix.diff"
POST_FIX = FIXTURES / "issue_078_post_fix.diff"
NON_GATE = FIXTURES / "issue_074_non_gate.diff"
#: PR #101 (ISSUE-056) — a real merged diff that adds SIX gates across two new
#: scripts, two of them both named `main`. The natural instance of the
#: bare-symbol collision; see the fixture README.
COLLIDING = FIXTURES / "issue_056_colliding_main.diff"

# The gate ISSUE-078's review fix repaired: the ARMING predicate that returned
# `valid: true` / exit 0 for 22 of 23 inputs containing `- Status: running`.
ARMING_GATE = "sprint_status_is_running"
# The second gate the same PR added: the CLI leg that turns the verdict into
# exit 3 and therefore withholds dispatch. Its boundary-field rejection battery
# is consumer-level but carries no input-side vacuity guard, so it stays
# unevidenced in BOTH diffs — a residual, not a separation signal.
# (`check_roster_boundary` itself is a pure verdict BUILDER: it blocks nothing,
# so the enforcement point `cmd_validate` is correctly the detected gate.)
VERDICT_GATE = "cmd_validate"

# Wall-clock ceiling for the subprocess CLI invocations in this module. A
# test-local constant, stated plainly because the comment that stood here was
# false in three ways: it claimed to "reuse" `verify_checkpoint._run`'s default
# "rather than re-type a new constant", but the value is 120 and not that
# default's 30, it IS a new constant, and that 30 is a bare parameter default
# with no env knob — the only documented timeout knobs in README.md are
# `KIT_CHECKPOINT_TEST_TIMEOUT` and `KIT_SPRINT_QUEUE_GH_TIMEOUT`, so nothing
# documented was being reused.
#
# This is the same untrue-provenance defect as the deleted `_GIT_TIMEOUT`'s
# (review lesson 2: a new timing constant needs a doc line where it is defined,
# and a provenance claim has to be checkable). Kept generous rather than tuned:
# it only has to exceed a local `git diff` plus interpreter start-up, and a
# ceiling that is too tight turns an unrelated slow runner into a test failure.
_CLI_TIMEOUT = 120


def _diff(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _symbols(findings) -> set[str]:
    return {f.symbol for f in findings}


def _finding_for(report, symbol: str):
    matches = [f for f in report.findings if f.symbol == symbol]
    assert len(matches) <= 1, f"{symbol}: expected at most one finding, got {matches}"
    return matches[0] if matches else None


def _verdict(report, symbol: str) -> dict:
    """The one evidence record for <symbol>, which is keyed ``(path, symbol)``.

    Path-qualified keying is what stops two same-named gates in two files from
    collapsing into one record, so this helper asserts the symbol resolves to
    exactly ONE key rather than silently picking a winner.
    """
    matches = {key: value for key, value in report.evidence.items() if key[1] == symbol}
    assert len(matches) == 1, f"{symbol}: expected one evidence key, got {matches}"
    return next(iter(matches.values()))


#: The gate-free verdict is read from the module, never re-typed here. Ten of
#: the assertions below guard it in the NEGATIVE ("a disarmed run must not read
#: like a clean one"); a `not in` guard whose literal has drifted from the
#: implementation passes vacuously, which is review lesson 4's second clause and
#: lesson 16's "import the oracle rather than re-implementing it".
GATE_FREE = vge.GATE_FREE_VERDICT


# ── Gate detection ───────────────────────────────────────────────────


class TestGateDetection:
    """"Adds a gate" must be decidable from the diff alone, and over-detect."""

    @pytest.mark.parametrize("fixture", [PRE_FIX, POST_FIX], ids=["pre-fix", "post-fix"])
    def test_both_issue_078_gates_are_detected(self, fixture):
        report = vge.analyze(_diff(fixture))
        symbols = {g.symbol for g in report.gates}
        assert ARMING_GATE in symbols, symbols
        assert VERDICT_GATE in symbols, symbols

    def test_detected_gates_name_their_source_file_and_line(self):
        report = vge.analyze(_diff(PRE_FIX))
        gate = next(g for g in report.gates if g.symbol == ARMING_GATE)
        assert gate.path == "scripts/sprint_queue.py", gate.path
        assert gate.line > 0

    def test_a_direct_call_battery_can_satisfy_the_composite_half(self):
        """Attribution comes from a direct call OR a name-matched guard.

        Not every gate's input vocabulary echoes its own name (a gate reached
        through a CLI rarely does), so requiring name attribution alone would
        make the composite half unreachable for them. The vacuity guard is
        still required — it is what makes the battery non-vacuous — but it no
        longer has to carry the attribution when the battery calls the gate.
        """
        diff = (
            "diff --git a/scripts/demo_cli.py b/scripts/demo_cli.py\n"
            "--- a/scripts/demo_cli.py\n"
            "+++ b/scripts/demo_cli.py\n"
            "@@ -0,0 +1,4 @@\n"
            "+def refuse_unmarked(text: str) -> bool:\n"
            "+    if \"ZZMARK\" not in text:\n"
            "+        return True\n"
            "+    return False\n"
            "diff --git a/tests/test_demo_cli.py b/tests/test_demo_cli.py\n"
            "--- a/tests/test_demo_cli.py\n"
            "+++ b/tests/test_demo_cli.py\n"
            "@@ -0,0 +1,8 @@\n"
            "+_CASES = [\"a\", \"bb\", \"ccc\"]\n"
            "+\n"
            "+@pytest.mark.parametrize(\"case\", _CASES)\n"
            "+def test_cli_refuses(case):\n"
            "+    text = f\"{case}\\n\"\n"
            "+    assert \"ZZMARK\" not in text\n"
            "+    assert refuse_unmarked(text) is True\n"
            "+    assert exit_code == 1\n"
        )
        report = vge.analyze(diff)
        # `is True` is NOT what credits the disarm half here — `refuse_unmarked`
        # is detector-shaped, so its refusal reads as `True` and the direction
        # check cannot know that. `assert exit_code == 1` is what carries the
        # refusal direction. That asymmetry is the disclosed polarity class, and
        # it is pinned deliberately rather than papered over.
        assert report.evidence[("scripts/demo_cli.py", "refuse_unmarked")] == {
            "disarm": True,
            "composite": True,
        }
        assert report.findings == ()

    def test_a_test_file_predicate_is_not_a_gate(self):
        """Gate detection is scoped to the SOURCE half of the diff.

        Every added `assert` in a test file is a predicate with a refusing
        branch; crediting them would make every PR a gate-adding PR and destroy
        AC-3. Disclosed limit: a guard implemented AS a test (ISSUE-072's shape)
        is therefore invisible to this phase.
        """
        diff = (
            "diff --git a/tests/test_thing.py b/tests/test_thing.py\n"
            "--- a/tests/test_thing.py\n"
            "+++ b/tests/test_thing.py\n"
            "@@ -1,0 +1,4 @@\n"
            "+def check_it(value) -> bool:\n"
            "+    if not value:\n"
            "+        return False\n"
            "+    return True\n"
        )
        report = vge.analyze(diff)
        assert report.gates == (), report.gates


# ── AC-1 ─────────────────────────────────────────────────────────────


class TestAC1ArmOnlyGateIsRefused:
    """An arm-only gate-adding diff is refused, and the finding names the gate."""

    def test_pre_fix_replay_reports_a_blocking_finding_naming_the_gate(self):
        report = vge.analyze(_diff(PRE_FIX))
        assert ARMING_GATE in _symbols(report.findings), _symbols(report.findings)
        finding = _finding_for(report, ARMING_GATE)
        assert ARMING_GATE in finding.message
        assert finding.path == "scripts/sprint_queue.py"

    def test_pre_fix_replay_exits_non_zero_through_the_cli(self):
        assert vge.main(["--diff-file", str(PRE_FIX)]) == 1

    def test_the_finding_is_rendered_so_a_reviewer_can_act_on_it(self, capsys):
        rc = vge.main(["--diff-file", str(PRE_FIX)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL" in out
        assert ARMING_GATE in out
        assert "scripts/sprint_queue.py" in out


# ── AC-2 ─────────────────────────────────────────────────────────────


class TestAC2HelperConsumerDisagreementIsSurfaced:
    """A gate correct in isolation and wrong through its consumer must not pass.

    This is the measured ISSUE-078 shape: `sprint_status_is_running`'s own unit
    assertions all passed, and `validate` / `next-action` disagreed with it on
    the same bytes. The pre-fix diff therefore has helper-level disarm evidence
    and NO composite pin, and the finding must say exactly that.
    """

    def test_helper_evidence_is_acknowledged_and_the_composite_is_not(self):
        report = vge.analyze(_diff(PRE_FIX))
        evidence = _verdict(report, ARMING_GATE)
        assert evidence["disarm"] is True, (
            "the pre-fix diff DOES batter the helper (RUNNING_VALUES / "
            "RUNNING_LINES); crediting nothing would make this a trivial pass"
        )
        assert evidence["composite"] is False

    def test_the_finding_kind_is_the_missing_composite_pin(self):
        finding = _finding_for(vge.analyze(_diff(PRE_FIX)), ARMING_GATE)
        assert finding.kind == "missing-composite-pin", finding.kind

    def test_the_message_names_both_halves_of_the_disagreement(self):
        finding = _finding_for(vge.analyze(_diff(PRE_FIX)), ARMING_GATE)
        lowered = finding.message.lower()
        assert "helper" in lowered
        assert "consumer" in lowered


# ── AC-3 ─────────────────────────────────────────────────────────────


class TestAC3NonGateDiffPaysNoTax:
    """An ordinary PR must leave the review output untouched."""

    def test_a_real_non_gate_pr_diff_detects_no_gate(self):
        report = vge.analyze(_diff(NON_GATE))
        assert report.gates == (), [g.symbol for g in report.gates]
        assert report.findings == (), [f.symbol for f in report.findings]

    def test_a_real_non_gate_pr_diff_exits_zero(self):
        assert vge.main(["--diff-file", str(NON_GATE)]) == 0

    def test_the_output_for_a_non_gate_diff_is_exactly_one_pass_line(self, capsys):
        """Byte-identical pin: no new obligation text is added to the review."""
        rc = vge.main(["--diff-file", str(NON_GATE)])
        out = capsys.readouterr().out
        assert rc == 0
        assert out == GATE_FREE + "\n", repr(out)

    def test_the_gate_free_verdict_claims_only_detection(self):
        """It must not claim the diff ADDED no gate — it cannot know that.

        SPEC-081 amendment, decision 3: a gate is seen only inside an added
        `def` in a changed non-test `.py` file, so four classes of real gate are
        invisible and used to print this line byte-identically to a genuinely
        gate-free PR. Commit `7949ccb` on this very branch added four blocking
        refusals and this line is what the detector printed. The per-boundary
        widen-or-bound decisions are ISSUE-087's; the wording is this PR's.
        """
        assert "DETECTED" in GATE_FREE, GATE_FREE
        assert "no gate-adding change" not in GATE_FREE, GATE_FREE
        # Points at the boundary by reference rather than inlining the list,
        # and names the carrier so a reader can find the open decisions.
        assert "SPEC-081" in GATE_FREE and "ISSUE-087" in GATE_FREE, GATE_FREE
        assert GATE_FREE.count("\n") == 0, "must stay a single review line"

    def test_the_non_gate_fixture_is_substantial_not_empty(self):
        """Vacuity guard: an empty diff would pass for the wrong reason."""
        text = _diff(NON_GATE)
        assert text.count("\n+") > 1000, text.count("\n+")
        assert "tests/test_registry_lock_contract.py" in text


# ── AC-3, part two: ONE definition of "test file" ────────────────────
#
# `is_test_path` re-typed a classifier `verify_checkpoint` already owned
# BYTE-IDENTICALLY IN TWO PLACES, and dropped `tests?` SINGULAR and `__tests__`
# while doing it. Review lesson 16's second clause is verbatim: "A guard that
# re-implements an oracle the suite already owns must import it instead."
#
# This is an AC-3 obligation, not new scope. Measured: the IDENTICAL helper was
# exempt under `tests/` (`is_test_path=True`, `gates=[]`) and a reported gate
# under `test/` (`is_test_path=False`,
# `gates=[('assert_guard','test/helpers.py')]`), so any repo laid out with
# `test/` or `__tests__/` — standard outside Python — paid a fabricated-finding
# tax on a diff that adds no gate. Added batteries under those directories also
# never entered `_blocks`, so evidence for a REAL gate could go missing too.

#: Distinctive fragments of the two regexes that now have exactly one home.
#: Counted as plain substrings across `scripts/` so the pin is immune to how the
#: one surviving definition is line-wrapped, and so a FIFTH copy fails here.
_DIR_FRAGMENT = r"(?:tests?|__tests__)/"
_FILE_FRAGMENT = r"(?:spec|test)\.(?:ts|tsx|js|jsx)"

#: The five disagreements MEASURED between the re-typed predicate and the
#: oracle, with the ORACLE's verdict — which is the one that now holds. The
#: first three are the AC-3 defect above. The last two move the other way
#: (True -> False) and are inert for gate DETECTION, because `detect_gates`
#: filters on `.py`; recorded so the direction of each row is on the record
#: rather than implied by a one-line summary.
_MEASURED_DISAGREEMENTS = [
    ("test/helpers.py", True),
    ("__tests__/helpers.py", True),
    ("pkg/test/gate.py", True),
    ("config.test.yaml", False),
    ("openapi.spec.yaml", False),
]

#: One helper file, same bytes, one directory name apart.
_HELPER_IN = (
    "diff --git a/{d}/helpers.py b/{d}/helpers.py\n"
    "--- a/{d}/helpers.py\n"
    "+++ b/{d}/helpers.py\n"
    "@@ -0,0 +1,3 @@\n"
    "+def assert_guard(value):\n"
    "+    if value is None:\n"
    '+        raise ValueError("missing")\n'
)


class TestTheTestPathOracleIsImportedNotRetyped:
    """Exactly ONE definition of "test file" in the repo, and it is the oracle."""

    @pytest.mark.parametrize(
        "path,expected",
        _MEASURED_DISAGREEMENTS,
        ids=[case[0] for case in _MEASURED_DISAGREEMENTS],
    )
    def test_the_measured_disagreements_resolve_toward_the_oracle(
        self, path, expected
    ):
        assert vge.is_test_path(path) is expected, path

    def test_the_identical_helper_is_classified_the_same_under_test_and_tests(self):
        """The AC-3 harm, stated as the observable it produced."""
        plural = vge.analyze(_HELPER_IN.format(d="tests"))
        singular = vge.analyze(_HELPER_IN.format(d="test"))
        # Vacuity guard: the same bytes under a name NEITHER spelling exempts
        # really are a detected gate, so "both empty" is not trivially true.
        control = vge.analyze(_HELPER_IN.format(d="pkg"))
        assert [g.symbol for g in control.gates] == ["assert_guard"], control.gates
        assert plural.gates == (), plural.gates
        assert singular.gates == plural.gates, (singular.gates, plural.gates)

    def test_the_two_regexes_have_exactly_one_home_in_scripts(self):
        counts = {}
        for script in sorted((ROOT / "scripts").glob("*.py")):
            text = script.read_text(encoding="utf-8")
            for fragment in (_DIR_FRAGMENT, _FILE_FRAGMENT):
                hit = text.count(fragment)
                if hit:
                    counts[(script.name, fragment)] = hit
        assert counts == {
            ("verify_gate_evidence.py", _DIR_FRAGMENT): 1,
            ("verify_gate_evidence.py", _FILE_FRAGMENT): 1,
        }, counts

    def test_the_checkpoint_phases_consume_the_shared_constants(self):
        """`verify_checkpoint` holds no local re-typing of either regex."""
        text = (ROOT / "scripts" / "verify_checkpoint.py").read_text(
            encoding="utf-8"
        )
        assert "test_pattern = re.compile" not in text
        assert "test_dir_pattern = re.compile" not in text
        assert "vge.TEST_FILE_PATTERN" in text and "vge.TEST_DIR_PATTERN" in text

    def test_is_test_path_is_exactly_the_two_shared_regexes(self):
        """No third rule hides inside the predicate: it IS the disjunction."""
        corpus = [
            "tests/helpers.py",
            "test/helpers.py",
            "__tests__/a.tsx",
            "pkg/test/gate.py",
            "scripts/verify_checkpoint.py",
            "foo_test.py",
            "foo.test.ts",
            "foo.spec.tsx",
            "config.test.yaml",
            "docs/test_plan.md",
            "scripts/test_runner.py",
            "a/b/c.py",
        ]
        for path in corpus:
            expected = bool(
                vge.TEST_FILE_PATTERN.search(path)
                or vge.TEST_DIR_PATTERN.search(path)
            )
            assert vge.is_test_path(path) is expected, path

    def test_no_import_cycle_on_any_invocation_route(self):
        """All three routes, empirically — `checkpoint.sh` is the hard one.

        `verify_checkpoint` now imports `verify_gate_evidence` at MODULE level,
        and `checkpoint.sh` `exec`s `verify_checkpoint.py` as a script, so the
        importer is `__main__` with `sys.path[0] = scripts/`. The inverse
        direction (the detector importing the checkpoint) was measured to
        execute `verify_checkpoint`'s 2371-line module body TWICE in that route
        — once as `__main__` and once as `verify_checkpoint`, each capturing its
        own `_GATE_PROCESS_START` — which is why the single definition lives in
        the detector and the dependency edge keeps the direction it already had
        for `unquote_c_style`.
        """
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}

        detector = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate_evidence.py"),
             "--diff-file", str(NON_GATE)],
            capture_output=True, text=True, timeout=_CLI_TIMEOUT, env=env,
        )
        assert detector.returncode == 0, (detector.stdout, detector.stderr)

        wrapper = subprocess.run(
            ["bash", str(ROOT / "scripts" / "checkpoint.sh"), "--skill", "review",
             "--phase", "gate-evidence", "--issue", "ISSUE-000"],
            capture_output=True, text=True, timeout=_CLI_TIMEOUT, cwd=str(ROOT),
            env=env,
        )
        # A missing worktree is a legitimate FAIL (exit 1); an import cycle is
        # a traceback (exit 1 too), so the discriminator is stderr.
        assert wrapper.returncode == 1, (wrapper.stdout, wrapper.stderr)
        assert "Traceback" not in wrapper.stderr, wrapper.stderr
        assert "ImportError" not in wrapper.stderr, wrapper.stderr

        imported = subprocess.run(
            [sys.executable, "-c",
             "import verify_checkpoint as vc, verify_gate_evidence as vge; "
             "print(vc.vge is vge)"],
            capture_output=True, text=True, timeout=_CLI_TIMEOUT,
            cwd=str(ROOT / "scripts"), env=env,
        )
        assert imported.returncode == 0, (imported.stdout, imported.stderr)
        assert imported.stdout.strip() == "True", imported.stdout


class TestTheTestQualityWalkerKeepsItsOwnBehaviour:
    """`review/test-quality`'s walker is deliberately NOT unified. Measured.

    Review lesson 8: "Relaxing a shared contract for a new caller class must be
    scoped to that class, with legacy failure modes pinned." The walker inside
    `verify_review_test_quality` is rooted at `tests/` and keeps a NAME-only
    rule (`test_` prefix / `_test.py` suffix). Adopting the unified predicate
    there is not a no-op: `TEST_DIR_PATTERN` matches `tests/` itself, so EVERY
    `.py` under `tests/` would enter the hollow-test scan while `_has_real_tests`
    requires a `def test_*`. Measured on this repo: 72 files -> 73, and the one
    added file is `tests/conftest.py`, which has no `def test_*` and would turn
    the blocking `review/test-quality` phase RED for every issue. That is a
    DIFFERENT phase's observable behaviour, so it is left alone and pinned here.

    Green both ways BY DESIGN: this pins behaviour ISSUE-081 does not change. It
    fails only if a later change unifies the walker without re-measuring.
    """

    def test_a_non_test_py_file_under_tests_is_not_charged_as_hollow(
        self, tmp_path, monkeypatch, capsys
    ):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "conftest.py").write_text(
            "import pytest\n\n\n@pytest.fixture\ndef thing():\n    return 1\n",
            encoding="utf-8",
        )
        (tmp_path / "tests" / "test_real.py").write_text(
            "def test_real():\n    assert True\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            vc, "_find_worktree_path", lambda issue_id: str(tmp_path)
        )
        assert vc.verify_review_test_quality("ISSUE-000") is True
        out = capsys.readouterr().out
        assert "conftest.py" not in out, out

        # Fixture pin: the unified predicate really WOULD have charged it, so
        # the pass above is a scoping decision rather than a coincidence.
        assert vge.is_test_path("tests/conftest.py")
        assert not vc._has_real_tests("tests/conftest.py", str(tmp_path))


# ── AC-4 ─────────────────────────────────────────────────────────────


class TestAC4BothDirectionsEvidencedPasses:
    """The repaired gate stops being a finding — on the REAL post-fix diff.

    This class is narrower than its name: it asserts that ISSUE-078's post-fix
    diff clears the gate ITS review repaired (`sprint_status_is_running`), and
    the diff as a whole still exits 1 because it adds a second, genuinely
    unevidenced gate. So it is not an instance of AC-4's premise ("a gate-adding
    PR with both directions evidenced passes without the finding") and must not
    be read as one. The worked example that IS an instance — a gate-adding diff
    reaching exit 0 through the real consumer — is
    `TestAC4AGateAddingDiffPassesCleanly`.
    """

    def test_post_fix_replay_has_no_finding_for_the_repaired_gate(self):
        report = vge.analyze(_diff(POST_FIX))
        assert _finding_for(report, ARMING_GATE) is None, [
            f.message for f in report.findings
        ]

    def test_post_fix_evidence_is_complete_for_the_repaired_gate(self):
        evidence = _verdict(vge.analyze(_diff(POST_FIX)), ARMING_GATE)
        assert evidence == {"disarm": True, "composite": True}, evidence

    def test_the_fix_is_what_moved_the_needle(self):
        """The separation is the review fix, not fixture luck.

        Pre-fix findings must STRICTLY contain post-fix findings, and the one
        symbol that drops out must be the gate ISSUE-078's review repaired.
        """
        pre = _symbols(vge.analyze(_diff(PRE_FIX)).findings)
        post = _symbols(vge.analyze(_diff(POST_FIX)).findings)
        assert post < pre, (pre, post)
        assert pre - post == {ARMING_GATE}, pre - post

    def test_the_residual_gate_is_reported_honestly_in_both_diffs(self):
        """`cmd_validate` is unevidenced before AND after the fix.

        Recorded rather than hidden: its boundary-field rejection battery is
        consumer-level but carries no input-side vacuity guard, so this phase
        asks for one. That is the disclosed cost in SPEC-081's Trade-offs
        Accepted, not a separation signal.
        """
        for fixture in (PRE_FIX, POST_FIX):
            report = vge.analyze(_diff(fixture))
            assert VERDICT_GATE in _symbols(report.findings), fixture.name


# ── AC-5: the mechanism is subject to its own rule ───────────────────

# Mutations of the PRE-FIX diff that a careless or hostile author could use to
# make the gate-adding change invisible to this checker. Each must still produce
# the finding. The vacuity guard inside the test proves each mutation really
# kept the gate definition in the diff.
_DISARM_MUTATIONS = [
    ("crlf_line_endings", lambda t: t.replace("\n", "\r\n")),
    ("no_newline_markers", lambda t: t + "\\ No newline at end of file\n"),
    (
        "hunk_headers_lose_their_function_hint",
        lambda t: _strip_hunk_hints(t),
    ),
    ("trailing_whitespace_on_added_lines", lambda t: _pad_added_lines(t)),
    ("extra_blank_context", lambda t: t.replace("\n@@", "\n \n@@")),
    ("index_lines_removed", lambda t: _drop_lines(t, "index ")),
    ("mode_lines_added", lambda t: t.replace("diff --git ", "old mode 100644\ndiff --git ", 1)),
    # Everything above varies the diff's BODY. These two vary the `+++`/`---`
    # HEADER, which is the ONLY thing `_parse` reads to decide which file a hunk
    # belongs to — and which this matrix had never varied. A header rendering
    # `git diff` produces BY DEFAULT (`core.quotePath` defaults to true and git
    # then C-quotes the path INSIDE the field) made the checker skip the file
    # entirely and PASS on this very fixture.
    ("c_quoted_paths", lambda t: _c_quoted_paths(t)),
    ("tab_timestamp_headers", lambda t: _tab_timestamp_headers(t)),
]


def _strip_hunk_hints(text: str) -> str:
    out = []
    for line in text.splitlines(keepends=True):
        if line.startswith("@@"):
            parts = line.split("@@")
            out.append(f"@@{parts[1]}@@\n" if len(parts) > 2 else line)
        else:
            out.append(line)
    return "".join(out)


def _pad_added_lines(text: str) -> str:
    out = []
    for line in text.splitlines(keepends=True):
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line.rstrip("\n") + "   \n")
        else:
            out.append(line)
    return "".join(out)


def _drop_lines(text: str, prefix: str) -> str:
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not line.startswith(prefix)
    )


# ── Header RENDERING, as the real tools render it ────────────────────
#
# `_c_quote` is a hand-rolled imitation of git's `quote_c_style`, so it is
# pinned character-for-character against REAL `git diff` output by
# `TestHeaderRenderings.test_the_c_quote_renderer_matches_real_git`. A
# hand-rolled renderer that is never checked against its oracle is how the
# defect it is pinning got in (review lesson 4).

_HEADER_FIELD_RE = re.compile(r"^(--- |\+\+\+ )(a/.*|b/.*|/dev/null)$")
_GIT_LINE_RE = re.compile(r"^diff --git a/(.*) b/\1$")


def _c_quote(path: str) -> str:
    """Render <path> the way git's ``quote_c_style`` renders it, quotes included.

    git quotes a pathname iff some byte of it must be escaped — a byte >= 0x80
    (so: any non-ASCII name), a control character, ``"`` or ``\\``. An
    all-ASCII path is returned verbatim, which is why the ``c_quoted_paths``
    mutation has to rename the path first: quoting a path git would never quote
    would pin a rendering that cannot occur.
    """
    raw = path.encode("utf-8")
    named = {0x07: "a", 0x08: "b", 0x0C: "f", 0x0A: "n", 0x0D: "r",
             0x09: "t", 0x0B: "v", 0x22: '"', 0x5C: "\\"}
    if not any(byte >= 0x80 or byte < 0x20 or byte in (0x22, 0x5C) for byte in raw):
        return path
    out = ['"']
    for byte in raw:
        if byte in named:
            out.append("\\" + named[byte])
        elif byte < 0x20 or byte >= 0x80:
            out.append("\\%03o" % byte)
        else:
            out.append(chr(byte))
    out.append('"')
    return "".join(out)


def _rewrite_header_paths(text: str, render) -> str:
    """Re-render every `diff --git` / `--- ` / `+++ ` path field through <render>."""
    out = []
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        newline = line[len(stripped):]
        git_line = _GIT_LINE_RE.match(stripped)
        if git_line:
            path = git_line.group(1)
            out.append(
                f"diff --git {render('a/' + path)} {render('b/' + path)}{newline}"
            )
            continue
        field = _HEADER_FIELD_RE.match(stripped)
        if field:
            out.append(f"{field.group(1)}{render(field.group(2))}{newline}")
            continue
        out.append(line)
    return "".join(out)


def _c_quote_headers(text: str) -> str:
    return _rewrite_header_paths(text, _c_quote)


def _accent(path: str) -> str:
    """Give the path a non-ASCII basename, extension preserved."""
    if path == "/dev/null":
        return path
    head, slash, name = path.rpartition("/")
    stem, dot, ext = name.rpartition(".")
    renamed = f"{stem}é{dot}{ext}" if dot else f"{name}é"
    return f"{head}{slash}{renamed}"


def _c_quoted_paths(text: str) -> str:
    """The diff as `git diff` renders it when the paths are non-ASCII.

    Two steps, both of them git's own behaviour and neither of them an exotic
    configuration: rename each header path so it NEEDS quoting, then render
    every header field with ``quote_c_style``. ``core.quotePath`` defaults to
    true, so this is git's DEFAULT output for any repo holding such a file —
    and the kit ships to arbitrary repos where non-ASCII filenames are
    ordinary. Measured before the fix: the leading ``"`` defeated the ``b/``
    strip, the path no longer ended in ``.py``, `detect_gates` skipped the file,
    and this fixture reported the gate-free verdict (then worded "PASS: no
    gate-adding change in the diff"; now `vge.GATE_FREE_VERDICT`).
    """
    return _c_quote_headers(_rewrite_header_paths(text, _accent))


def _tab_timestamp_headers(text: str) -> str:
    """Headers the way plain `diff -u` writes them: no prefix, TAB, timestamp.

    Reachable through the documented ``--diff-file``. Measured before the fix:
    the whole ``scripts/gate.py\\t2026-01-02 10:00:00`` payload became the path,
    so no file ended in ``.py`` and the same bytes that FAIL with a git-style
    header reported the gate-free verdict (`vge.GATE_FREE_VERDICT`).
    """

    def render(path: str) -> str:
        bare = path[2:] if path[:2] in ("a/", "b/") else path
        return f"{bare}\t2026-01-02 10:00:00.000000000 +0000"

    return _rewrite_header_paths(text, render)


class TestAC5TheMechanismIsSubjectToItsOwnRule:
    """The disarm direction OF THIS GATE, batteried over input variation."""

    @pytest.mark.parametrize(
        "label,mutate",
        _DISARM_MUTATIONS,
        ids=[case[0] for case in _DISARM_MUTATIONS],
    )
    def test_a_mutated_diff_still_arms_the_finding(self, label, mutate):
        text = mutate(_diff(PRE_FIX))

        # VACUITY GUARD: the mutation must leave the gate definition in the
        # diff, or the case proves nothing about disarming detection.
        assert "def sprint_status_is_running" in text, label
        assert "+def sprint_status_is_running" in text.replace("\r\n", "\n"), label

        report = vge.analyze(text)
        assert ARMING_GATE in _symbols(report.findings), label

    @pytest.mark.parametrize(
        "label,mutate",
        _DISARM_MUTATIONS,
        ids=[case[0] for case in _DISARM_MUTATIONS],
    )
    def test_a_mutated_post_fix_diff_still_passes(self, label, mutate):
        """Both directions: a mutation must not manufacture a finding either.

        The assertion is an ABSENCE, so it needs a guard that proves the
        detector is alive — review lesson 4's second clause, and an
        occurrence-whitelist rather than a phrasing check. The text guard below
        only proves the gate's definition survived the MUTATION; measured, with
        detection fully dead (`_CONDITIONAL` neutralised) the text guard still
        held and this assertion still passed (`gates: 0 | arming-gate finding:
        [] | PASS`). `DETECTION LIVENESS` is what closes that, and
        `test_the_detection_liveness_guard_is_load_bearing` mutation-proves it
        with the string actually removed.
        """
        text = mutate(_diff(POST_FIX))
        assert "def sprint_status_is_running" in text, label
        report = vge.analyze(text)
        # DETECTION LIVENESS: the detector must still SEE the gate, not merely
        # the bytes that define it.
        assert ARMING_GATE in {g.symbol for g in report.gates}, (
            f"{label}: detection is dead — an absent finding proves nothing"
        )
        assert _finding_for(report, ARMING_GATE) is None, label

    def test_the_detection_liveness_guard_is_load_bearing(self, monkeypatch):
        """Kill detection: the liveness guard must fail, the old guards must not.

        Both halves matter. If the liveness guard survived a dead detector it
        would be decoration; if the pre-existing guards failed too, the defect
        would never have been reachable in the first place, and it was.
        """
        text = _diff(POST_FIX)
        monkeypatch.setattr(vge, "_CONDITIONAL", _NEVER)
        report = vge.analyze(text)

        # The guards that were already there still hold with detection dead.
        assert "def sprint_status_is_running" in text
        assert _finding_for(report, ARMING_GATE) is None

        # The new one does not. Mutation-tested with the thing actually
        # removed, rather than asserted as prose.
        assert ARMING_GATE not in {g.symbol for g in report.gates}, (
            "mutant SURVIVED: neutralising `_CONDITIONAL` must make the "
            "detection-liveness assertion fail, or it is not load-bearing"
        )


class TestAC5CompositePinThroughTheRealConsumer:
    """Drive this gate end to end through `verify_checkpoint.py`, not the helper.

    The helper is `verify_gate_evidence.analyze`; the real consumer is the
    blocking `review/gate-evidence` checkpoint reached through
    `verify_checkpoint.main`. ISSUE-078's defect was exactly a helper that was
    right and a consumer that disagreed, so this gate pins both on the same
    bytes.
    """

    @pytest.mark.parametrize(
        "label,mutate",
        _DISARM_MUTATIONS,
        ids=[case[0] for case in _DISARM_MUTATIONS],
    )
    def test_the_cli_refuses_a_mutated_arm_only_diff(self, tmp_path, label, mutate):
        text = mutate(_diff(PRE_FIX))
        assert "def sprint_status_is_running" in text, label

        path = tmp_path / f"{label}.diff"
        path.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate_evidence.py"),
             "--diff-file", str(path)],
            capture_output=True,
            text=True,
            timeout=_CLI_TIMEOUT,
        )
        assert result.returncode == 1, (label, result.stdout, result.stderr)
        assert ARMING_GATE in result.stdout, label

        # Same bytes, in-process entry point: the helper and the CLI must not
        # disagree — that disagreement IS the ISSUE-078 defect.
        assert vge.main(["--diff-file", str(path)]) == 1, label

    @pytest.mark.parametrize(
        "label,mutate",
        _DISARM_MUTATIONS,
        ids=[case[0] for case in _DISARM_MUTATIONS],
    )
    def test_the_checkpoint_phase_refuses_an_arm_only_diff(
        self, monkeypatch, capsys, label, mutate
    ):
        """The composite through the REGISTERED phase, not the module CLI."""
        text = mutate(_diff(PRE_FIX))

        # VACUITY GUARD: the phase can only be charged with catching a gate the
        # mutated diff still contains.
        assert "def sprint_status_is_running" in text, label

        monkeypatch.setattr(vc, "_gate_evidence_diff", lambda issue_id: text)
        assert vc.verify_review_gate_evidence("ISSUE-078") is False, label
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-078"]
        )
        out = capsys.readouterr().out
        assert rc == 1, (label, out)
        assert ARMING_GATE in out, label
        assert "ADVISORY:" not in out, "this phase must be blocking, not advisory"

    def test_the_checkpoint_phase_still_refuses_the_residual_gate_in_a_post_fix_diff(
        self, monkeypatch, capsys
    ):
        """Named for what it asserts: `rc == 1`, NOT an AC-4 demonstration.

        This test used to be called `..._passes_a_post_fix_diff`, so a reader
        scanning test names concluded AC-4 was pinned while the assertion
        encoded a refusal. The post-fix diff is not an instance of AC-4's
        premise — it adds a second, genuinely unevidenced gate. AC-4's actual
        worked example is `TestAC4AGateAddingDiffPassesCleanly`.
        """
        monkeypatch.setattr(
            vc, "_gate_evidence_diff", lambda issue_id: _diff(POST_FIX)
        )
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-078"]
        )
        out = capsys.readouterr().out
        # The residual `cmd_validate` finding is real, so the phase still
        # refuses — what must have changed is the arming gate's finding.
        assert ARMING_GATE not in out, out
        assert VERDICT_GATE in out, out
        assert rc == 1

    def test_the_checkpoint_phase_passes_a_non_gate_diff(self, monkeypatch, capsys):
        monkeypatch.setattr(
            vc, "_gate_evidence_diff", lambda issue_id: _diff(NON_GATE)
        )
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-074"]
        )
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "ADVISORY:" not in out


# One-at-a-time mutations of the CHECKER itself. Each must break a property the
# checker is supposed to secure — if a mutant survives, the corresponding rule
# is not load-bearing and this gate is decoration to that extent.
_NEVER = re.compile(r"(?!x)x")


def _contract_holds() -> bool:
    """The whole observable contract, over the three real fixtures.

    Deliberately a conjunction rather than only the pre/post separation: a rule
    can be load-bearing for the no-false-positive-tax half (AC-3) or for the
    honest-residual half without touching the separation, and a matrix that
    probes only one of them reports false survivors.
    """
    pre = _symbols(vge.analyze(_diff(PRE_FIX)).findings)
    post = _symbols(vge.analyze(_diff(POST_FIX)).findings)
    non_gate = vge.analyze(_diff(NON_GATE))
    return (
        ARMING_GATE in pre
        and ARMING_GATE not in post
        and VERDICT_GATE in post
        and non_gate.findings == ()
    )


# Pinned by the REAL ISSUE-078 / ISSUE-074 diffs.
#
# `("variant_floor_removed", {"MIN_VARIANTS": 0})` used to live here and no
# longer does, because it no longer kills THIS oracle: with the direction
# requirement in place, admitting every block as a battery still leaves
# `cmd_validate` with no refusal-direction evidence in either real diff, so the
# three fixtures' findings are byte-identical at MIN_VARIANTS=0. Recording the
# survivor rather than deleting the pin: the floor is now isolated on a
# constructed single-case diff by
# `TestAC5MutationMatrix::test_the_variant_floor_is_load_bearing`, the same way
# REQUIRE_CONSUMER_OUTCOME and REQUIRE_INPUT_ONLY_PARAMS already are.
#
# `REQUIRE_REFUSAL_DIRECTION` is likewise absent on purpose and for the inverse
# reason — it is the amendment's measured headline that direction detection
# changes NOTHING on the real pair (0 regressions). It is pinned in both
# directions by `TestDirectionIsWhatIsMeasured`, on the arm-only corpus and the
# decisive attack, which are the inputs that can see it.
_REAL_MUTANTS = [
    ("variant_floor_raised_absurdly", {"MIN_VARIANTS": 999}),
    ("vacuity_guard_requirement_dropped", {"REQUIRE_VACUITY_GUARD": False}),
    ("refusal_vocabulary_emptied", {"REFUSAL_PATTERNS": (), "_BOOL_REFUSAL": _NEVER}),
]

# The demo gate the three constructed isolating diffs below share. Written so
# its REFUSAL reads as `False` (`blocked_marker_is_absent` returns False when
# the forbidden marker is there), because the direction check reads polarity
# lexically: a detector-shaped sibling whose refusal reads as `True` would make
# every battery here indistinguishable from an arm-only one, which is the
# disclosed limitation, not the rule under test in this section.
_DEMO_GATE_SOURCE = """diff --git a/scripts/demo_gate.py b/scripts/demo_gate.py
--- a/scripts/demo_gate.py
+++ b/scripts/demo_gate.py
@@ -0,0 +1,5 @@
+def blocked_marker_is_absent(text: str) -> bool:
+    if "BLOCKED-MARKER" in text:
+        return False
+    return True
"""

_DEMO_TEST_HEADER = """diff --git a/tests/test_demo_gate.py b/tests/test_demo_gate.py
--- a/tests/test_demo_gate.py
+++ b/tests/test_demo_gate.py
"""

# A minimal gate whose only evidence is a vacuity-guarded HELPER battery: no
# consumer-level outcome anywhere. Isolates REQUIRE_CONSUMER_OUTCOME, which the
# real fixtures cannot exercise (both already carry consumer batteries).
_HELPER_ONLY_DIFF = _DEMO_GATE_SOURCE + _DEMO_TEST_HEADER + """@@ -0,0 +1,11 @@
+_MARKER_VARIANTS = [
+    "BLOCKED-MARKER",
+    "  BLOCKED-MARKER  ",
+    "**BLOCKED-MARKER**",
+]
+
+@pytest.mark.parametrize("variant", _MARKER_VARIANTS)
+def test_blocked_marker_is_absent_still_refuses(variant):
+    text = f"header\\n{variant}\\nfooter"
+    assert "BLOCKED-MARKER" in text
+    assert blocked_marker_is_absent(text) is False
"""

# The same gate whose only evidence is an OUTCOME MAP (the expected value is
# itself a parameter). Isolates REQUIRE_INPUT_ONLY_PARAMS.
_OUTCOME_MAP_DIFF = _DEMO_GATE_SOURCE + _DEMO_TEST_HEADER + """@@ -0,0 +1,12 @@
+_OUTCOME_MAP = [
+    ("BLOCKED-MARKER here", False),
+    ("clean text here", True),
+    ("another clean one", True),
+]
+
+@pytest.mark.parametrize("variant,expected", _OUTCOME_MAP)
+def test_blocked_marker_outcome_map(variant, expected):
+    text = variant
+    assert isinstance(text, str) is True
+    assert "BLOCKED-MARKER" in text or expected is False
+    assert blocked_marker_is_absent(text) is expected
"""

# The same gate whose only evidence is a SINGLE refusal-direction case — right
# in every respect except that it varied nothing. Isolates MIN_VARIANTS, which
# the real fixtures no longer can: see the note above `_REAL_MUTANTS`.
_SINGLE_CASE_DIFF = _DEMO_GATE_SOURCE + _DEMO_TEST_HEADER + """@@ -0,0 +1,6 @@
+def test_blocked_marker_is_absent_refuses_the_one_case():
+    text = "header\\nBLOCKED-MARKER\\nfooter"
+    assert "BLOCKED-MARKER" in text
+    assert blocked_marker_is_absent(text) is False
+    assert exit_code == 1
"""

_DEMO_GATE = "blocked_marker_is_absent"
_DEMO_GATE_PATH = "scripts/demo_gate.py"


# ── AC-4, the worked example ─────────────────────────────────────────
#
# AC-4 requires that a gate-adding PR with both directions evidenced "passes
# without the finding". The real ISSUE-078 post-fix diff is NOT an instance of
# that premise: it adds a second gate (`cmd_validate`) that genuinely carries no
# input-side vacuity guard, so it exits 1 — correctly. That left AC-4 with no
# demonstration anywhere in the suite, and the test that NAMED it asserted
# `rc == 1`. From the review: "an obligation that no example can be shown to
# satisfy cleanly is the kind that gets routed around rather than met."
#
# This is that example, and it is written to be COPIED. Two batteries over one
# shared variant list:
#
#   * the DISARM battery drives the gate directly and asserts it still REFUSES
#     (`is False`) on every variant;
#   * the COMPOSITE battery drives the gate's real CONSUMER and asserts a
#     consumer-level refusal (`rc == 1`);
#   * BOTH carry the input-side vacuity guard (`assert "<marker>" in text`),
#     which is simultaneously what attributes a battery to a gate and what
#     proves the variant still contains what the gate is supposed to catch.
#
# The refusal-shaped expectations are what the direction requirement that landed
# in `1b2b126` asks for; `_ARM_ONLY_DIFF` below is the same diff with only the
# polarity flipped, and it is refused.
_BOTH_DIRECTIONS_DIFF = _DEMO_GATE_SOURCE + _DEMO_TEST_HEADER + """@@ -0,0 +1,21 @@
+_MARKER_VARIANTS = [
+    "BLOCKED-MARKER",
+    "  BLOCKED-MARKER  ",
+    "**BLOCKED-MARKER**",
+]
+
+@pytest.mark.parametrize("variant", _MARKER_VARIANTS)
+def test_blocked_marker_is_absent_cannot_be_disarmed(variant):
+    text = f"header\\n{variant}\\nfooter"
+    assert "BLOCKED-MARKER" in text
+    assert blocked_marker_is_absent(text) is False
+
+@pytest.mark.parametrize("variant", _MARKER_VARIANTS)
+def test_the_consumer_refuses_every_variant_end_to_end(variant, tmp_path):
+    text = f"header\\n{variant}\\nfooter"
+    assert "BLOCKED-MARKER" in text
+    target = tmp_path / "input.txt"
+    target.write_text(text, encoding="utf-8")
+    rc = demo_gate.main([str(target)])
+    assert rc == 1
"""

#: The same diff with ONLY the two refusal expectations flipped to the arm
#: direction. An arm-only battery no longer passes, which is the whole point of
#: the direction requirement — so this is what makes the example above
#: load-bearing rather than decorative.
_ARM_ONLY_DIFF = (
    _BOTH_DIRECTIONS_DIFF
    .replace("blocked_marker_is_absent(text) is False",
             "blocked_marker_is_absent(text) is True")
    .replace("assert rc == 1", "assert rc == 0")
    .replace("cannot_be_disarmed", "is_armed")
)


class TestAC4AGateAddingDiffPassesCleanly:
    """AC-4's premise, demonstrated end to end — the obligation IS satisfiable."""

    def test_the_demo_gate_is_really_detected(self):
        """Vacuity guard: an exit 0 over a diff with no gate proves nothing."""
        report = vge.analyze(_BOTH_DIRECTIONS_DIFF)
        assert (_DEMO_GATE_PATH, _DEMO_GATE) in {
            (g.path, g.symbol) for g in report.gates
        }, report.gates

    def test_both_directions_are_evidenced_and_nothing_is_waived(self):
        report = vge.analyze(_BOTH_DIRECTIONS_DIFF)
        assert _verdict(report, _DEMO_GATE) == {"disarm": True, "composite": True}
        assert report.findings == (), [f.message for f in report.findings]
        # Not a pass bought with an exemption — the escape hatch is unused.
        assert report.exemptions == (), report.exemptions

    def test_the_module_cli_exits_zero(self, tmp_path, capsys):
        path = tmp_path / "both_directions.diff"
        path.write_text(_BOTH_DIRECTIONS_DIFF, encoding="utf-8")
        rc = vge.main(["--diff-file", str(path)])
        out = capsys.readouterr().out
        assert rc == 0, out
        # It must pass because the gate is EVIDENCED, not because none was seen.
        assert GATE_FREE not in out, out
        assert _DEMO_GATE in out, out

    def test_the_checkpoint_phase_passes_it(self, monkeypatch, capsys):
        """Through the REAL consumer, not `analyze` — this is the AC-4 proof."""
        monkeypatch.setattr(
            vc, "_gate_evidence_diff", lambda issue_id: _BOTH_DIRECTIONS_DIFF
        )
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-081"]
        )
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "FAIL" not in out, out
        assert GATE_FREE not in out, out
        assert f"both directions: {_DEMO_GATE}" in out, out

    def test_the_same_diff_with_the_polarity_flipped_is_refused(
        self, monkeypatch, capsys
    ):
        """One-character-class difference between the pass above and a refusal."""
        assert "is True" in _ARM_ONLY_DIFF and "is False" not in _ARM_ONLY_DIFF
        assert "def blocked_marker_is_absent" in _ARM_ONLY_DIFF
        monkeypatch.setattr(
            vc, "_gate_evidence_diff", lambda issue_id: _ARM_ONLY_DIFF
        )
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-081"]
        )
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "missing-refusal-direction" in out, out
        assert _DEMO_GATE in out, out


class TestAC5MutationMatrix:
    """Mutation-pinned in BOTH directions, with the harness validated first."""

    def test_the_harness_kills_a_known_killing_mutant(self, monkeypatch):
        """Validate the matrix before trusting any SURVIVED verdict.

        Disabling the conditional half of gate detection must collapse the
        contract. If this test passes, a SURVIVED verdict below is real; if
        THIS test fails, the harness never reaches the checker and every
        verdict below is meaningless.
        """
        assert _contract_holds(), "baseline: the real fixtures must separate"
        monkeypatch.setattr(vge, "_CONDITIONAL", _NEVER)
        assert not _contract_holds(), (
            "known-killing mutant SURVIVED — the mutation harness does not "
            "actually reach the checker's logic"
        )

    @pytest.mark.parametrize(
        "label,overrides",
        _REAL_MUTANTS,
        ids=[case[0] for case in _REAL_MUTANTS],
    )
    def test_every_rule_pinned_by_the_real_diffs_is_load_bearing(
        self, monkeypatch, label, overrides
    ):
        for attr, value in overrides.items():
            assert hasattr(vge, attr), f"{label}: {attr} is not a module knob"
            monkeypatch.setattr(vge, attr, value)
        assert not _contract_holds(), (
            f"mutant SURVIVED: {overrides!r} left the whole observable "
            "contract intact, so that rule is not load-bearing"
        )

    def test_the_consumer_outcome_rule_is_load_bearing(self, monkeypatch):
        """Helper-only evidence must NOT satisfy the composite half."""
        armed = vge.analyze(_HELPER_ONLY_DIFF)
        assert _DEMO_GATE in {g.symbol for g in armed.gates}, armed.gates
        assert _verdict(armed, _DEMO_GATE) == {"disarm": True, "composite": False}
        assert _finding_for(armed, _DEMO_GATE).kind == "missing-composite-pin"

        monkeypatch.setattr(vge, "REQUIRE_CONSUMER_OUTCOME", False)
        disarmed = vge.analyze(_HELPER_ONLY_DIFF)
        assert _finding_for(disarmed, _DEMO_GATE) is None, (
            "mutant SURVIVED: dropping the consumer-outcome rule must let a "
            "helper-only battery clear the composite half"
        )

    def test_the_input_only_rule_is_load_bearing(self, monkeypatch):
        """An outcome MAP is a mapping, not a direction battery."""
        armed = vge.analyze(_OUTCOME_MAP_DIFF)
        assert _DEMO_GATE in {g.symbol for g in armed.gates}, armed.gates
        assert _verdict(armed, _DEMO_GATE) == {"disarm": False, "composite": False}
        assert _finding_for(armed, _DEMO_GATE).kind == "missing-disarm-battery"

        monkeypatch.setattr(vge, "REQUIRE_INPUT_ONLY_PARAMS", False)
        disarmed = vge.analyze(_OUTCOME_MAP_DIFF)
        assert _finding_for(disarmed, _DEMO_GATE).kind != "missing-disarm-battery", (
            "mutant SURVIVED: dropping the input-only rule must let an outcome "
            "map count as a disarm battery"
        )

    def test_the_variant_floor_is_load_bearing(self, monkeypatch):
        """One perfect case is not a battery; and the floor is what says so.

        Isolated on a constructed diff because the real fixtures stopped
        separating this knob once the direction requirement landed — see the
        note above `_REAL_MUTANTS`. The single case here is refusal-directed and
        consumer-level, so the ONLY thing between it and a clean pass is
        MIN_VARIANTS.
        """
        armed = vge.analyze(_SINGLE_CASE_DIFF)
        assert _DEMO_GATE in {g.symbol for g in armed.gates}, armed.gates
        assert _verdict(armed, _DEMO_GATE) == {"disarm": False, "composite": False}
        assert _finding_for(armed, _DEMO_GATE).kind == "missing-disarm-battery"

        monkeypatch.setattr(vge, "MIN_VARIANTS", 0)
        disarmed = vge.analyze(_SINGLE_CASE_DIFF)
        assert _finding_for(disarmed, _DEMO_GATE) is None, (
            "mutant SURVIVED: removing the variant floor must let a single "
            "case clear both halves"
        )


# ── DIRECTION: the requirement this gate is named after ──────────────
#
# Review lesson 16, which ISSUE-081 is the mechanical carrier for, fired on
# ISSUE-081 itself: "a newly added defence must be tested in the DISARM
# direction and through its real consumer, not only in the arm direction at its
# helper." The implementation measured END-TO-END-NESS — ">= MIN_VARIANTS
# variants that mention the gate, asserting *some* literal" — while the
# requirement names DIRECTION. Neither half of the evidence computation looked
# at what the battery ASSERTS, and `_LITERAL_EXPECTED_RE` matches `True`/`0`
# as readily as `False`/`1`.
#
# Measured consequence, and the baseline these cases are calibrated against:
# `disarm` was True for 7 of the 8 arm-only shapes below (the 8th is held off
# by REQUIRE_INPUT_ONLY_PARAMS, a different rule), i.e. arm-only recall 1/8.
# SPEC-081 amendment, decision 1 (Option E).

#: The gate the arm-only corpus is built around. Written so the ACCEPT outcome
#: reads lexically as success (`is True`) and the REFUSAL reads as `False`, so
#: that "arm-only" and "not refusal-shaped" coincide. A detector-shaped gate
#: would make them diverge — which is the disclosed polarity class, pinned
#: separately by `TestTheKnownWeaknessOfDirectionDetection`.
_ARM_GATE = "zzmark_is_present"
_ARM_GATE_PATH = "scripts/demo_arm.py"

_ARM_GATE_SOURCE = """diff --git a/scripts/demo_arm.py b/scripts/demo_arm.py
--- a/scripts/demo_arm.py
+++ b/scripts/demo_arm.py
@@ -0,0 +1,5 @@
+def zzmark_is_present(text: str) -> bool:
+    if "ZZMARK" not in text:
+        return False
+    return True
"""

#: The `@@` line counts here are nominal: `_parse` reads the hunk header only
#: for its optional function hint and never for its line counts, which is
#: pinned by the `hunk_headers_lose_their_function_hint` disarm mutation.
_ARM_TEST_HEADER = """diff --git a/tests/test_demo_arm.py b/tests/test_demo_arm.py
--- a/tests/test_demo_arm.py
+++ b/tests/test_demo_arm.py
@@ -0,0 +1,40 @@
"""


def _arm_diff(body: str) -> str:
    return _ARM_GATE_SOURCE + _ARM_TEST_HEADER + body


#: Eight batteries over `zzmark_is_present`, every one of them asserting only
#: that the gate ACCEPTS. None is evidence that it cannot be disarmed, and the
#: first is byte-for-byte the shape of all four historical fail-opens (a
#: variant battery, a direct call, no refusal anywhere).
_ARM_ONLY_SHAPES = [
    (
        "direct_call_is_True",
        '+_VARIANTS = ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_zzmark_is_present_accepts(case):\n"
        '+    text = f"{case}\\n"\n'
        "+    assert zzmark_is_present(text) is True\n",
    ),
    (
        "name_attributed_guard_is_True",
        '+_VARIANTS = ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_the_cli_accepts_marked_text(case):\n"
        '+    text = f"{case}\\n"\n'
        '+    assert "ZZMARK" in text\n'
        '+    assert out["valid"] is True\n',
    ),
    (
        "consumer_exit_zero",
        '+_VARIANTS = ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_zzmark_is_present_exits_zero(case):\n"
        '+    text = f"{case}\\n"\n'
        '+    assert "ZZMARK" in text\n'
        "+    assert zzmark_is_present(text) is True\n"
        "+    assert exit_code == 0\n",
    ),
    (
        # The case a naive right-hand-side check gets exactly backwards: the
        # expected VALUE is `False`, and the assertion means "it succeeded".
        "negated_against_False",
        '+_VARIANTS = ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_zzmark_is_present_is_not_false(case):\n"
        '+    text = f"{case}\\n"\n'
        '+    assert "ZZMARK" in text\n'
        "+    assert zzmark_is_present(text) != False\n",
    ),
    (
        "success_verdict_string",
        '+_VARIANTS = ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_zzmark_is_present_reports_valid(case):\n"
        '+    text = f"{case}\\n"\n'
        '+    assert "ZZMARK" in text\n'
        "+    assert zzmark_is_present(text) is True\n"
        '+    assert out["state"] == "valid"\n',
    ),
    (
        "subprocess_returncode_zero",
        '+_VARIANTS = ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_zzmark_is_present_through_the_cli(case):\n"
        '+    text = f"{case}\\n"\n'
        '+    assert "ZZMARK" in text\n'
        "+    assert zzmark_is_present(text) is True\n"
        "+    assert result.returncode == 0\n",
    ),
    (
        "loop_battery_is_True",
        "+def test_zzmark_is_present_accepts_each(case):\n"
        '+    for case in ["ZZMARK a", "ZZMARK bb", "ZZMARK ccc"]:\n'
        '+        text = f"{case}\\n"\n'
        '+        assert "ZZMARK" in text\n'
        "+        assert zzmark_is_present(text) is True\n",
    ),
    (
        # Already caught at baseline, by REQUIRE_INPUT_ONLY_PARAMS rather than
        # by direction — the 1 of the baseline 1-of-8. Kept in the corpus so
        # the two rules are not confused for each other.
        "outcome_map",
        "+_MAP = [\n"
        '+    ("ZZMARK a", True),\n'
        '+    ("plain b", False),\n'
        '+    ("plain c", False),\n'
        "+]\n"
        "+\n"
        '+@pytest.mark.parametrize("case,expected", _MAP)\n'
        "+def test_zzmark_is_present_map(case, expected):\n"
        '+    text = f"{case}\\n"\n'
        "+    assert zzmark_is_present(text) is expected\n",
    ),
]

#: The same gate, battered in the REFUSAL direction, one operator form each.
#: Without these the arm-only result above would be satisfied by a rule that
#: returns False unconditionally (review lesson 4: mutation-test BOTH
#: directions), and `!= 0` vs `!= False` is what proves the operator-awareness
#: is doing work rather than decorating a value lookup.
_REFUSAL_SHAPES = [
    (
        "is_False",
        "+    assert zzmark_is_present(text) is False\n",
    ),
    (
        "equals_nonzero_exit",
        "+    assert exit_code == 1\n",
    ),
    (
        "not_equal_to_zero",
        "+    assert exit_code != 0\n",
    ),
    (
        "screaming_refusal_constant",
        "+    assert exit_code == sq.ROSTER_BOUNDARY_EXIT\n",
    ),
    (
        "refusal_verdict_string",
        '+    assert out["state"] == "rejected"\n',
    ),
    (
        "assert_not",
        "+    assert not zzmark_is_present(text)\n",
    ),
    (
        "pytest_raises",
        "+    with pytest.raises(SystemExit):\n"
        "+        zzmark_is_present(text)\n",
    ),
]


def _refusal_diff(tail: str) -> str:
    """The gate, battered over 3 inputs, with <tail> as its ONLY refusal signal.

    The `isinstance(...) is True` line is deliberate and is not the refusal: it
    is there so the block clears `_is_battery`, which is direction-blind and
    requires *some* constant literal expectation. Without it the `assert not`
    and `pytest.raises` shapes would never become batteries, and the case would
    report a direction failure caused by an unrelated rule.
    """
    return _arm_diff(
        '+_VARIANTS = ["a", "bb", "ccc"]\n'
        "+\n"
        '+@pytest.mark.parametrize("case", _VARIANTS)\n'
        "+def test_zzmark_is_present_refuses_unmarked(case):\n"
        '+    text = f"{case}\\n"\n'
        '+    assert "ZZMARK" not in text\n'
        "+    assert isinstance(text, str) is True\n" + tail
    )


class TestDirectionIsWhatIsMeasured:
    """`disarm` must mean "asserts a refusal", not "mentions the gate"."""

    @pytest.mark.parametrize(
        "label,body",
        _ARM_ONLY_SHAPES,
        ids=[case[0] for case in _ARM_ONLY_SHAPES],
    )
    def test_an_arm_only_battery_is_not_disarm_evidence(self, label, body):
        report = vge.analyze(_arm_diff(body))

        # VACUITY GUARD: a shape whose gate is not even detected would pass
        # this case for the wrong reason.
        assert _ARM_GATE in {g.symbol for g in report.gates}, label

        assert _verdict(report, _ARM_GATE)["disarm"] is False, label
        finding = _finding_for(report, _ARM_GATE)
        assert finding is not None, label
        assert finding.kind in (
            "missing-disarm-battery",
            "missing-refusal-direction",
        ), (label, finding.kind)

    @pytest.mark.parametrize(
        "label,tail",
        _REFUSAL_SHAPES,
        ids=[case[0] for case in _REFUSAL_SHAPES],
    )
    def test_a_refusal_direction_battery_still_counts(self, label, tail):
        """The other direction: the rule must not simply refuse everything."""
        report = vge.analyze(_refusal_diff(tail))
        assert _ARM_GATE in {g.symbol for g in report.gates}, label
        assert _verdict(report, _ARM_GATE)["disarm"] is True, label

    def test_the_operator_is_what_separates_the_two_negated_forms(self):
        """`!= 0` is a refusal expectation; `!= False` is a success one.

        Pinned at the predicate, because the two differ ONLY in the operator's
        interaction with the value and a value-only rule gets both wrong.
        """
        assert vge._refusal_shaped("!=", "0") is True
        assert vge._refusal_shaped("!=", "False") is False
        assert vge._refusal_shaped("==", "False") is True
        assert vge._refusal_shaped("==", "0") is False
        assert vge._refusal_shaped("is not", "True") is True
        assert vge._refusal_shaped("is", "True") is False

    @pytest.mark.parametrize(
        "label,body",
        _ARM_ONLY_SHAPES,
        ids=[case[0] for case in _ARM_ONLY_SHAPES],
    )
    def test_neutralising_the_direction_rule_restores_the_fail_open(
        self, monkeypatch, label, body
    ):
        """Mutation, the other direction: the rule must be load-bearing.

        With `REQUIRE_REFUSAL_DIRECTION` off, 7 of these 8 arm-only shapes go
        back to `disarm=True` — the measured 1-of-8 baseline. The 8th
        (`outcome_map`) stays False because a DIFFERENT rule holds it,
        REQUIRE_INPUT_ONLY_PARAMS, and conflating the two would make this
        matrix report a false survivor.
        """
        monkeypatch.setattr(vge, "REQUIRE_REFUSAL_DIRECTION", False)
        verdict = _verdict(vge.analyze(_arm_diff(body)), _ARM_GATE)
        expected = label == "outcome_map"
        assert verdict["disarm"] is not expected, (
            f"{label}: neutralising the direction rule must restore the "
            f"pre-fix verdict, or the rule is not load-bearing"
        )

    def test_the_composite_half_needs_a_refusing_consumer_outcome(self):
        """`returncode == 0` must not pin a gate through its consumer.

        The composite half's whole claim is that the gate holds end to end; a
        battery that drives the consumer and asserts SUCCESS proves the gate is
        reachable, not that it refuses.
        """
        accepting = vge.analyze(
            _refusal_diff("+    assert exit_code == 0\n")
        )
        assert _verdict(accepting, _ARM_GATE)["composite"] is False
        refusing = vge.analyze(
            _refusal_diff("+    assert exit_code == 1\n")
        )
        assert _verdict(refusing, _ARM_GATE)["composite"] is True


# ── The decisive attack, through the real consumer ───────────────────

#: Two purely arm-direction batteries over the two gates the committed pre-fix
#: fixture adds: three variants each, inputs the gate must ACCEPT, `is True` /
#: `== 0`, and mechanically ZERO refusal assertions. Measured before the fix:
#: appending this to `issue_078_pre_fix.diff` — the diff AC-1/AC-2 require to be
#: BLOCKED — took it to `exit 0` / `PASS — 2 gate(s) carry both directions:
#: cmd_validate, sprint_status_is_running`.
_ARM_ONLY_ATTACK = (
    "diff --git a/tests/test_attack.py b/tests/test_attack.py\n"
    "--- a/tests/test_attack.py\n"
    "+++ b/tests/test_attack.py\n"
    "@@ -0,0 +1,18 @@\n"
    "+_ACCEPTED = [\n"
    '+    "- Status: running",\n'
    '+    "- Status: running  ",\n'
    '+    "  - Status: running",\n'
    "+]\n"
    "+\n"
    '+@pytest.mark.parametrize("variant", _ACCEPTED)\n'
    "+def test_sprint_status_is_running_accepts_a_live_sprint(variant):\n"
    '+    text = f"## Meta\\n{variant}\\n"\n'
    '+    assert "- Status: running" in text\n'
    "+    assert sprint_status_is_running(text) is True\n"
    "+    assert exit_code == 0\n"
    "+\n"
    '+@pytest.mark.parametrize("variant", _ACCEPTED)\n'
    "+def test_cmd_validate_accepts_a_live_sprint(variant):\n"
    '+    text = f"## Meta\\n{variant}\\n"\n'
    '+    assert "- Status: running" in text\n'
    "+    assert cmd_validate(text) == 0\n"
    "+    assert exit_code == 0\n"
)


def _attacked_pre_fix() -> str:
    return _diff(PRE_FIX) + _ARM_ONLY_ATTACK


class TestTheArmOnlyAttackIsBlocked:
    """The pre-fix fixture plus arm-only noise must stay BLOCKED."""

    def test_the_attack_really_adds_arm_only_batteries(self):
        """Fixture pin: the attack must contain no refusal assertion at all.

        Without this the case could pass because the attack was inert rather
        than because the rule caught it.
        """
        text = _ARM_ONLY_ATTACK
        assert text.count("is True") == 1 and "== 0" in text
        assert "is False" not in text
        assert "pytest.raises" not in text
        assert "assert not " not in text
        assert "!= 0" not in text
        # And it must really be attributed to BOTH gates, or it could not have
        # flipped the verdict at baseline.
        assert f"{ARMING_GATE}(text)" in text
        assert f"{VERDICT_GATE}(text)" in text

    def test_the_attacked_pre_fix_diff_still_blocks(self):
        report = vge.analyze(_attacked_pre_fix())
        assert _symbols(report.findings) == {ARMING_GATE, VERDICT_GATE}, (
            _symbols(report.findings)
        )
        assert _finding_for(report, ARMING_GATE).kind == "missing-composite-pin"
        # The unattacked fixture reports `missing-disarm-battery` here, because
        # NO battery is attributed to `cmd_validate` at all. The attack adds
        # one — an arm-only one — so the honest kind is the second of the two
        # separately-named modes. Same gate, same verdict, named for what is
        # actually wrong with it.
        assert (
            _finding_for(report, VERDICT_GATE).kind
            == "missing-refusal-direction"
        )

    def test_the_attack_restores_the_unattacked_evidence_verdicts(self):
        """Per-gate `disarm`/`composite` must be exactly the pre-fix values."""
        attacked = vge.analyze(_attacked_pre_fix())
        clean = vge.analyze(_diff(PRE_FIX))
        assert {
            symbol: verdict
            for (_, symbol), verdict in attacked.evidence.items()
        } == {
            symbol: verdict for (_, symbol), verdict in clean.evidence.items()
        }

    def test_the_attack_exits_non_zero_through_the_module_cli(self, tmp_path):
        path = tmp_path / "attacked.diff"
        path.write_text(_attacked_pre_fix(), encoding="utf-8")
        assert vge.main(["--diff-file", str(path)]) == 1

    def test_the_attack_is_refused_by_the_blocking_checkpoint(
        self, monkeypatch, capsys
    ):
        """Through the REAL consumer, not `analyze` — review lesson 16."""
        monkeypatch.setattr(
            vc, "_gate_evidence_diff", lambda issue_id: _attacked_pre_fix()
        )
        assert vc.verify_review_gate_evidence("ISSUE-078") is False
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-078"]
        )
        out = capsys.readouterr().out
        assert rc == 1, out
        assert "carry both directions" not in out, out
        assert ARMING_GATE in out and VERDICT_GATE in out, out
        assert "ADVISORY:" not in out, "this phase must be blocking"

    def test_the_remedy_for_the_undirected_kind_discloses_its_error_rate(self):
        """The 59% class must be disclosed in the output, not hidden.

        SPEC-081 amendment, decision 1: the two failure modes are named apart
        precisely because this one is unreliable, so its remedy has to say the
        check can misread polarity AND name the escape. A remedy that reads as
        confidently as the reliable kind's is how a reviewer gets told to add a
        battery that already exists.
        """
        finding = _finding_for(vge.analyze(_attacked_pre_fix()), VERDICT_GATE)
        message = finding.message
        assert "16 of 27" in message, message
        lowered = message.lower()
        assert "lexical" in lowered, message
        assert "detector-shaped" in lowered, message
        assert "is none" in lowered, message
        assert f"GATE-EVIDENCE-EXEMPT({VERDICT_GATE})" in message, message
        assert "scripts/sprint_queue.py" in message, message

    def test_the_reliable_kind_does_not_carry_the_caveat(self):
        """The distinction is only useful if the kinds read differently."""
        finding = _finding_for(vge.analyze(_diff(PRE_FIX)), VERDICT_GATE)
        assert finding.kind == "missing-disarm-battery"
        assert "16 of 27" not in finding.message, finding.message


# ── The known weakness, pinned rather than left as prose ─────────────

#: A detector-shaped gate with three attributed batteries. Two of them are
#: GENUINE disarm batteries that this check cannot read — one asserts the
#: refusal as `is True` (for a detector, "the decorated variant is still
#: caught" IS the refusal, and that is not lexically decidable), the other
#: asserts refusal by `is None`. The third is an incidental smoke battery whose
#: `is False` the check does read.
_POLARITY_INVERTED_DIFF_HEAD = """diff --git a/scripts/demo_detect.py b/scripts/demo_detect.py
--- a/scripts/demo_detect.py
+++ b/scripts/demo_detect.py
@@ -0,0 +1,5 @@
+def marker_is_detected(text: str) -> bool:
+    if "MARKER:" in text:
+        return True
+    return False
diff --git a/tests/test_demo_detect.py b/tests/test_demo_detect.py
--- a/tests/test_demo_detect.py
+++ b/tests/test_demo_detect.py
@@ -0,0 +1,30 @@
+_DECORATED = [
+    "MARKER: plain",
+    "**MARKER: bold**",
+    "> MARKER: quoted",
+]
+
+@pytest.mark.parametrize("variant", _DECORATED)
+def test_marker_is_detected_survives_decoration(variant):
+    text = f"prefix\\n{variant}\\nsuffix"
+    assert "MARKER:" in text
+    assert marker_is_detected(text) is True
+
+@pytest.mark.parametrize("variant", _DECORATED)
+def test_parse_marker_withholds_a_value(variant):
+    text = f"prefix\\n{variant}\\nsuffix"
+    assert "MARKER:" in text
+    assert parse_marker(text) is None
"""

#: The one battery whose refusal the check CAN read. Deleting it is a one-line
#: edit a real PR makes all the time.
_INCIDENTAL_SMOKE_BATTERY = (
    "+\n"
    '+@pytest.mark.parametrize("variant", _DECORATED)\n'
    "+def test_marker_is_detected_rejects_empty(variant):\n"
    '+    text = f"prefix\\n{variant}\\nsuffix"\n'
    '+    assert "MARKER:" in text\n'
    '+    assert marker_is_detected("") is False\n'
)

_DETECTOR_GATE = "marker_is_detected"


class TestTheKnownWeaknessOfDirectionDetection:
    """A KNOWN, ACCEPTED false-block, pinned so nobody has to rediscover it.

    Measured on PR #129's diff and reproduced here in miniature: the direction
    check's 16-of-27 per-battery error rate is masked by `any()` semantics, and
    the masking is one deleted battery away from being reachable. Deleting the
    single incidental smoke battery leaves two genuine disarm batteries the
    check cannot read, and the gate flips from evidenced-in-the-disarm-half to
    not.

    This is NOT a bug report. SPEC-081's amendment decided Option E *with this
    cost disclosed*, against Option F (0 of 4) and Option G (0 of 4). What it
    is, is the reason the two finding kinds are named apart: the flipped
    verdict lands on `missing-refusal-direction`, whose remedy says the check
    may be misreading polarity and names the exemption escape — rather than on
    `missing-disarm-battery`, which would tell the author to add a battery that
    already exists twice. The remedy, when this fires on an honest PR, is the
    inline exemption; the durable carrier for a better answer (a per-gate
    polarity declaration) is SPEC-081's last Open Question.
    """

    def test_the_two_genuine_batteries_are_really_genuine(self):
        """Fixture pin: both really are disarm batteries, by construction."""
        head = _POLARITY_INVERTED_DIFF_HEAD
        # The detector gate's refusal IS `True` — that is what makes the first
        # battery's `is True` the refusal direction and not the arm direction.
        assert "+        return True\n" in head
        assert "assert marker_is_detected(text) is True" in head
        assert "assert parse_marker(text) is None" in head
        assert "is False" not in head, "the smoke battery must be separable"

    def test_with_the_smoke_battery_the_gate_is_credited(self):
        report = vge.analyze(
            _POLARITY_INVERTED_DIFF_HEAD + _INCIDENTAL_SMOKE_BATTERY
        )
        assert _DETECTOR_GATE in {g.symbol for g in report.gates}
        assert _verdict(report, _DETECTOR_GATE)["disarm"] is True
        assert _finding_for(report, _DETECTOR_GATE).kind == "missing-composite-pin"

    def test_deleting_the_smoke_battery_reaches_the_false_block(self):
        report = vge.analyze(_POLARITY_INVERTED_DIFF_HEAD)
        assert _verdict(report, _DETECTOR_GATE)["disarm"] is False
        finding = _finding_for(report, _DETECTOR_GATE)
        # The mitigation that makes this an acceptable cost rather than a trap:
        # the author is told that polarity may have been misread, and handed
        # the escape, instead of being told to write a third disarm battery.
        assert finding.kind == "missing-refusal-direction", finding.kind
        assert "2 added battery" in finding.message, finding.message
        assert "GATE-EVIDENCE-EXEMPT" in finding.message
        assert "16 of 27" in finding.message

    def test_the_named_remedy_actually_clears_it(self):
        """The escape has to WORK, or disclosing it is worse than useless."""
        waived = _POLARITY_INVERTED_DIFF_HEAD.replace(
            "+def marker_is_detected(text: str) -> bool:",
            f"+# GATE-EVIDENCE-EXEMPT({_DETECTOR_GATE}): detector-shaped — the "
            "disarm direction is `assert marker_is_detected(text) is True` in "
            "test_marker_is_detected_survives_decoration, which the polarity "
            "check cannot read\n"
            "+def marker_is_detected(text: str) -> bool:",
            1,
        )
        report = vge.analyze(waived)
        assert _finding_for(report, _DETECTOR_GATE) is None, report.findings
        rendered = "\n".join(vge.format_report(report))
        assert "EXEMPT: scripts/demo_detect.py:marker_is_detected" in rendered


# ── Opt-out, and the registry wiring ────────────────────────────────


class TestExemptionIsVisibleNotSilent:
    def test_an_exempted_gate_is_skipped_and_reported(self, capsys):
        text = _diff(PRE_FIX).replace(
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            "+# GATE-EVIDENCE-EXEMPT(sprint_status_is_running): arming predicate "
            "covered by the boundary battery\n"
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            1,
        )
        report = vge.analyze(text)
        assert _finding_for(report, ARMING_GATE) is None
        assert ("scripts/sprint_queue.py", ARMING_GATE) in {
            (path, sym) for path, sym, _ in report.exemptions
        }, report.exemptions
        assert all(reason for _, _, reason in report.exemptions)

        # The unexempted fixture is unaffected — the exemption is scoped to the
        # diff that carries it, not sticky state.
        assert ARMING_GATE in _symbols(vge.analyze(_diff(PRE_FIX)).findings)

    def test_an_exemption_without_a_reason_does_not_count(self):
        text = _diff(PRE_FIX).replace(
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            "+# GATE-EVIDENCE-EXEMPT(sprint_status_is_running):\n"
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            1,
        )
        report = vge.analyze(text)
        assert ARMING_GATE in _symbols(report.findings), "fail-closed on no reason"

    def test_an_exemption_quoted_in_a_TEST_file_does_not_count(self):
        """Measured fail-open in this very gate, found by dogfooding it.

        The exemption scanner originally read every added line, so a test file
        that merely QUOTES the marker in a fixture string — which this module's
        own suite does, three times — silently exempted the symbol named in the
        string. Exemptions are now read from the SOURCE half only.
        """
        text = _diff(PRE_FIX) + (
            "diff --git a/tests/test_quoting.py b/tests/test_quoting.py\n"
            "--- a/tests/test_quoting.py\n"
            "+++ b/tests/test_quoting.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+def test_quotes_the_marker():\n"
            f'+    assert "# GATE-EVIDENCE-EXEMPT({ARMING_GATE}): nope" in doc\n'
        )
        report = vge.analyze(text)
        assert report.exemptions == (), report.exemptions
        assert ARMING_GATE in _symbols(report.findings)

    def test_the_pass_line_distinguishes_evidenced_from_exempted(self):
        """A pass that reads the same whether the rule was met or waived is the
        "legitimate quiet output is identical to defeated output" failure."""
        anchor = "+ROSTER_BOUNDARY_EXIT = 3"
        # Fixture pin: the injection point must exist, or this test would assert
        # the rendering of an unmodified report and prove nothing.
        assert anchor in _diff(POST_FIX)
        text = _diff(POST_FIX).replace(
            anchor,
            f"+# GATE-EVIDENCE-EXEMPT({VERDICT_GATE}): waived for this test\n"
            + anchor,
            1,
        )
        rendered = "\n".join(vge.format_report(vge.analyze(text)))
        assert "carry both directions" in rendered
        assert ARMING_GATE in rendered
        assert "exempted, NOT evidenced" in rendered
        assert VERDICT_GATE in rendered.split("exempted, NOT evidenced")[1]

    def test_an_exemption_for_another_symbol_does_not_transfer(self):
        text = _diff(PRE_FIX).replace(
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            "+# GATE-EVIDENCE-EXEMPT(some_other_symbol): unrelated\n"
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            1,
        )
        assert ARMING_GATE in _symbols(vge.analyze(text).findings)

    def test_exemptions_are_echoed_into_the_review_record(self, capsys, tmp_path):
        text = _diff(PRE_FIX).replace(
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            f"+# GATE-EVIDENCE-EXEMPT({ARMING_GATE}): reason here\n"
            f"+# GATE-EVIDENCE-EXEMPT({VERDICT_GATE}): reason here\n"
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            1,
        )
        path = tmp_path / "exempt.diff"
        path.write_text(text, encoding="utf-8")
        rc = vge.main(["--diff-file", str(path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "EXEMPT" in out
        assert "reason here" in out
        # The waiver names the FILE as well as the symbol. The accidental
        # waiver this provenance fix closed did print; its reason rendered as a
        # truncated fragment of review prose that reads like nothing in
        # particular, so visibility alone was not enough.
        assert f"EXEMPT: scripts/sprint_queue.py:{ARMING_GATE}" in out, out


# ── Exemption PROVENANCE (SPEC-081 amendment, decision 4) ────────────
#
# Decision 1 leaves a permanently undecidable class whose only escape is this
# marker, so the marker stops being a convenience and becomes load-bearing.
# It was not trustworthy, and on this branch it was LIVE rather than latent:
# the exemption loop skipped test paths but applied no `.py` filter, required
# no `#` prefix, and required no locality to the gate — only a non-empty
# reason. Measured on this branch's own merge-base diff through the real
# blocking checkpoint:
#
#   at 7a10422:  PASS — 2 gate(s) carry both directions: main, verify_review... | 5 exempted
#   at ab907ea:  PASS — 1 gate(s) carry both directions: verify_review...      | 6 exempted
#
# `main` moved from evidenced to waived because the review WROTE THE FINDING
# DOWN in `docs/review_notes/ISSUE-081.md`. Review lesson 6: shape validation
# is not provenance.

_GATE_FILE = "scripts/sprint_queue.py"


def _with_marker_file(path: str, body: str) -> str:
    """The pre-fix fixture plus one extra added file carrying <body>."""
    head = (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(body.splitlines())} @@\n"
    )
    return _diff(PRE_FIX) + head + body


class TestExemptionProvenance:
    """An exemption counts only where it can have been written deliberately."""

    def test_a_marker_in_a_markdown_file_does_not_exempt(self):
        """The measured live defect: review PROSE waived a real gate.

        Reproduced in the shape it actually occurred — a review-notes sentence
        describing the hole, naming a real symbol, not `#`-prefixed.
        """
        text = _with_marker_file(
            "docs/review_notes/ISSUE-999.md",
            f"+Consequences: one `GATE-EVIDENCE-EXEMPT({ARMING_GATE}): ...` "
            "anywhere in the source half exempts EVERY matching gate.\n",
        )
        report = vge.analyze(text)
        assert report.exemptions == (), report.exemptions
        assert ARMING_GATE in _symbols(report.findings)

    def test_a_marker_inside_a_fenced_spec_block_does_not_exempt(self):
        """A one-character reason in a code fence used to waive a real gate."""
        text = _with_marker_file(
            "docs/specs/SPEC-999.md",
            "+```\n"
            f"+# GATE-EVIDENCE-EXEMPT({ARMING_GATE}): x\n"
            "+```\n",
        )
        report = vge.analyze(text)
        assert report.exemptions == (), report.exemptions
        assert ARMING_GATE in _symbols(report.findings)

    def test_a_marker_in_a_python_docstring_does_not_exempt(self):
        """`.py` is necessary but not sufficient — it has to be a COMMENT."""
        text = _with_marker_file(
            "scripts/unrelated_helper.py",
            "+def describe() -> str:\n"
            '+    """Explains the marker format.\n'
            f"+    GATE-EVIDENCE-EXEMPT({ARMING_GATE}): illustrative only\n"
            '+    """\n'
            '+    return ""\n',
        )
        report = vge.analyze(text)
        assert report.exemptions == (), report.exemptions
        assert ARMING_GATE in _symbols(report.findings)

    def test_a_marker_in_a_different_python_file_does_not_exempt(self):
        """Locality: a `#` comment in the wrong `.py` file is still inert.

        This is the cross-file leak. `docs/review_notes/ISSUE-081.md` recorded
        it as "one marker anywhere in the source half exempts EVERY matching
        gate", and every validator script in this repo has a `main`.
        """
        text = _with_marker_file(
            "scripts/unrelated_helper.py",
            f"+# GATE-EVIDENCE-EXEMPT({ARMING_GATE}): written in the wrong file\n"
            "+VERSION = 1\n",
        )
        report = vge.analyze(text)
        # Collected and reported — the marker is real — but NOT honoured for a
        # gate in another file.
        assert [
            (path, symbol) for path, symbol, _ in report.exemptions
        ] == [("scripts/unrelated_helper.py", ARMING_GATE)], report.exemptions
        assert ARMING_GATE in _symbols(report.findings), (
            "an exemption in another file must not waive this gate"
        )

    def test_a_commented_marker_in_the_gates_own_file_does_exempt(self):
        """The other direction: the designed escape must still work.

        Without this the four cases above would be satisfied by a rule that
        honours nothing, which is review lesson 4's both-directions clause.
        """
        text = _diff(PRE_FIX).replace(
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            f"+# GATE-EVIDENCE-EXEMPT({ARMING_GATE}): detector polarity — the "
            "disarm direction is asserted as `is True` in the heading battery\n"
            "+def sprint_status_is_running(sprint_text: str) -> bool:",
            1,
        )
        report = vge.analyze(text)
        assert [
            (path, symbol) for path, symbol, _ in report.exemptions
        ] == [(_GATE_FILE, ARMING_GATE)], report.exemptions
        assert _finding_for(report, ARMING_GATE) is None

    def test_a_trailing_comment_marker_also_counts(self):
        """`#` anywhere ahead of the marker, with no quote before it."""
        text = _diff(PRE_FIX).replace(
            "+ROSTER_BOUNDARY_EXIT = 3",
            f"+ROSTER_BOUNDARY_EXIT = 3  # GATE-EVIDENCE-EXEMPT({VERDICT_GATE}): "
            "CLI leg, covered by the boundary battery",
            1,
        )
        report = vge.analyze(text)
        assert (_GATE_FILE, VERDICT_GATE) in {
            (path, symbol) for path, symbol, _ in report.exemptions
        }, report.exemptions
        assert _finding_for(report, VERDICT_GATE) is None

    def test_the_five_intended_self_exemptions_are_well_formed(self):
        """This module's own five waivers must satisfy the new provenance rule.

        They are the concrete instance of SPEC-081's "a gate reached only
        through a CLI will usually need an exemption" trade-off, and they are
        what the branch's own blocking self-run reports. Read off the real
        source file rather than restated, so tightening the rule without
        updating them fails here instead of silently un-waiving five gates and
        blocking the review that tightened it.
        """
        source = ROOT / "scripts" / "verify_gate_evidence.py"
        assert source.name.endswith(".py") and not vge.is_test_path(
            str(source.relative_to(ROOT))
        )
        markers = {}
        for line in source.read_text(encoding="utf-8").splitlines():
            match = vge._EXEMPT_RE.search(line)
            if not match:
                continue
            prefix = line[: match.start()]
            if not vge._COMMENTED_RE.match(prefix):
                continue
            markers[match.group(1)] = match.group("reason").strip()
        assert set(markers) == {
            "_is_predicate_shaped",
            "_is_battery",
            "_attributed",
            "_is_non_vacuous",
            "_has_consumer_outcome",
        }, sorted(markers)
        assert all(markers.values()), markers

    def test_the_md_leak_is_refused_through_the_blocking_checkpoint(
        self, monkeypatch, capsys
    ):
        """Through the real consumer: the `.md` waiver must not clear the gate.

        The defect was confirmed through this exact path, so the fix is pinned
        through it too rather than only at `analyze`.
        """
        text = _with_marker_file(
            "docs/review_notes/ISSUE-999.md",
            f"+prose mentioning GATE-EVIDENCE-EXEMPT({ARMING_GATE}): a reason\n",
        )
        monkeypatch.setattr(vc, "_gate_evidence_diff", lambda issue_id: text)
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-078"]
        )
        out = capsys.readouterr().out
        assert rc == 1, out
        assert ARMING_GATE in out, out
        assert "EXEMPT:" not in out, out


# ── (path, symbol) keying ────────────────────────────────────────────

#: Two `main` gates in two files, one marker, and a battery that evidences
#: beta's. With the gates keyed on the bare symbol, the marker waived both and
#: the summary still printed `1 exempted` — under-reporting the blast radius on
#: the very line SPEC-081's "defeating it is visible" claim rests on.
_TWO_MAIN_GATES = (
    "diff --git a/scripts/alpha_tool.py b/scripts/alpha_tool.py\n"
    "--- a/scripts/alpha_tool.py\n"
    "+++ b/scripts/alpha_tool.py\n"
    "@@ -0,0 +1,5 @@\n"
    "+# GATE-EVIDENCE-EXEMPT(main): alpha's CLI leg, waived here and ONLY here\n"
    "+def main(argv) -> int:\n"
    "+    if not argv:\n"
    "+        return 2\n"
    "+    return 0\n"
    "diff --git a/scripts/beta_tool.py b/scripts/beta_tool.py\n"
    "--- a/scripts/beta_tool.py\n"
    "+++ b/scripts/beta_tool.py\n"
    "@@ -0,0 +1,4 @@\n"
    "+def main(argv) -> int:\n"
    "+    if not argv:\n"
    "+        return 2\n"
    "+    return 0\n"
    "diff --git a/tests/test_beta_tool.py b/tests/test_beta_tool.py\n"
    "--- a/tests/test_beta_tool.py\n"
    "+++ b/tests/test_beta_tool.py\n"
    "@@ -0,0 +1,9 @@\n"
    '+_ARGVS = [[], [""], ["--"]]\n'
    "+\n"
    '+@pytest.mark.parametrize("argv", _ARGVS)\n'
    "+def test_beta_main_refuses(argv):\n"
    '+    text = "beta_tool fixture\\n"\n'
    '+    assert "beta_tool" in text\n'
    "+    assert main(argv) == 2\n"
    "+    assert exit_code == 2\n"
)

_BETA_MARKER = (
    "+++ b/scripts/beta_tool.py\n@@ -0,0 +1,4 @@\n",
    "+++ b/scripts/beta_tool.py\n@@ -0,0 +1,5 @@\n"
    "+# GATE-EVIDENCE-EXEMPT(main): beta's CLI leg, waived separately\n",
)


class TestEvidenceIsKeyedByPathAndSymbol:
    """Two same-named gates in two files are two gates, not one."""

    def test_the_two_main_gates_fixture_really_collides(self):
        """Fixture pin: two gates, one symbol, exactly one marker."""
        report = vge.analyze(_TWO_MAIN_GATES)
        assert [(g.path, g.symbol) for g in report.gates] == [
            ("scripts/alpha_tool.py", "main"),
            ("scripts/beta_tool.py", "main"),
        ], report.gates
        assert len(report.evidence) == 2, report.evidence
        assert _TWO_MAIN_GATES.count("GATE-EVIDENCE-EXEMPT") == 1

    def test_one_marker_waives_exactly_one_and_the_count_says_so(self):
        report = vge.analyze(_TWO_MAIN_GATES)
        assert report.exemptions == (
            (
                "scripts/alpha_tool.py",
                "main",
                "alpha's CLI leg, waived here and ONLY here",
            ),
        ), report.exemptions
        # beta's `main` is evidenced by the battery, alpha's is waived, so the
        # report reaches the PASS summary — which is where the count lives.
        assert report.findings == (), [(f.path, f.kind) for f in report.findings]
        rendered = "\n".join(vge.format_report(report))
        assert "1 gate(s) carry both directions: main" in rendered, rendered
        assert "1 exempted, NOT evidenced: scripts/alpha_tool.py:main" in (
            rendered
        ), rendered
        assert rendered.count("EXEMPT: ") == 1, rendered

    def test_the_marker_does_not_waive_the_other_file(self):
        """Drop beta's battery: beta must block, alpha must stay waived."""
        text = _TWO_MAIN_GATES.split("diff --git a/tests/test_beta_tool.py")[0]
        report = vge.analyze(text)
        assert [(f.path, f.kind) for f in report.findings] == [
            ("scripts/beta_tool.py", "missing-disarm-battery")
        ], [(f.path, f.kind) for f in report.findings]

    def test_two_same_named_gates_need_two_markers(self):
        """The count tracks gates, not markers."""
        both = vge.analyze(_TWO_MAIN_GATES.replace(*_BETA_MARKER, 1))
        assert both.findings == (), both.findings
        rendered = "\n".join(vge.format_report(both))
        assert "2 exempted, NOT evidenced" in rendered, rendered
        assert "scripts/alpha_tool.py:main" in rendered
        assert "scripts/beta_tool.py:main" in rendered

    def test_the_colliding_main_fixture_yields_one_record_per_gate(self):
        """The natural instance: PR #101 detects 6 gates and used to yield 5.

        A real merged diff rather than a constructed one, because the collision
        is not exotic — every validator script in this repo has a `main`, and
        this PR added two of them in one change.
        """
        report = vge.analyze(_diff(COLLIDING))
        gates = [(g.path, g.symbol) for g in report.gates]
        assert len(gates) == 6, gates
        assert sorted(symbol for _, symbol in gates).count("main") == 2, gates
        assert len(report.evidence) == 6, report.evidence
        assert ("scripts/verify_design_sweeps.py", "main") in report.evidence
        assert ("scripts/verify_hollow_tests.py", "main") in report.evidence

    def test_a_marker_for_one_colliding_main_leaves_the_other_blocking(self):
        """Measured consequence of the old keying, on the real diff."""
        anchor = "+def main(argv: list[str] | None = None) -> int:"
        text = _diff(COLLIDING)
        # Fixture pin: both files really do define `main` with this signature,
        # so the replace below has to be scoped to the FIRST occurrence.
        assert text.count(anchor) == 2, text.count(anchor)
        text = text.replace(
            anchor,
            "+# GATE-EVIDENCE-EXEMPT(main): sweeps CLI leg only\n" + anchor,
            1,
        )
        report = vge.analyze(text)
        waived = {(path, symbol) for path, symbol, _ in report.exemptions}
        assert waived == {("scripts/verify_design_sweeps.py", "main")}, waived
        blocked = {(f.path, f.symbol) for f in report.findings}
        assert ("scripts/verify_hollow_tests.py", "main") in blocked, blocked
        assert ("scripts/verify_design_sweeps.py", "main") not in blocked, blocked


class TestPhaseIsRegisteredAndBlocking:
    def test_the_phase_is_in_the_verifier_registry(self):
        assert ("review", "gate-evidence") in vc.VERIFIERS

    def test_the_phase_is_not_advisory(self):
        assert ("review", "gate-evidence") not in vc.ADVISORY_PHASES

    def test_the_review_skill_carries_the_clause_and_the_checkpoint(self):
        for name in ("SKILL.md", "SKILL.md.tmpl"):
            text = (ROOT / "skills" / "review" / name).read_text(encoding="utf-8")
            assert "--phase gate-evidence" in text, name
            assert "disarm" in text.lower(), name
            assert "GATE-EVIDENCE-EXEMPT" in text, name

    def test_the_team_lead_phase_table_lists_it(self):
        text = (ROOT / "agents" / "team-lead.md").read_text(encoding="utf-8")
        row = next(
            line for line in text.splitlines()
            if line.startswith("| review |")
        )
        assert "gate-evidence" in row, row


class TestTheCliIsDiffFileOnlyAndFailsClosed:
    """SPEC-081 amendment, decision 5: the CLI is `--diff-file` and nothing else.

    `--range`/`--repo`/`_diff_from_range`/`_GIT_TIMEOUT` and `--json` are
    deleted. The range path had zero callers and zero tests while the real
    consumer (`verify_checkpoint._gate_evidence_diff`) computes its own diff with
    a merge-base correction that path lacked — and the module docstring
    documented the two-dot form, which PROVABLY disagrees with the consumer (on
    a branch where `main` deleted a gate after the fork point: two-dot `exit=1
    FAIL` vs three-dot `exit=0 PASS` vs consumer `exit=0 PASS`). `--json`'s only
    consumer was the test written for it, and no AC names a machine-readable
    mode.
    """

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["--range", "main..HEAD"], id="range"),
            pytest.param(["--range", "main..HEAD", "--repo", "."], id="range_repo"),
            pytest.param(["--json"], id="json"),
        ],
    )
    def test_the_deleted_cli_surface_stays_deleted(self, argv):
        assert vge.main(argv) == 2, argv

    def test_the_deleted_names_are_gone_from_the_module(self):
        for name in ("_diff_from_range", "_GIT_TIMEOUT"):
            assert not hasattr(vge, name), name
        text = (ROOT / "scripts" / "verify_gate_evidence.py").read_text(
            encoding="utf-8"
        )
        # The docstring must stop documenting a CLI surface that is gone, and
        # the `subprocess`/`json` imports go with the legs that used them.
        for token in ("--range", "--json", "import subprocess", "import json"):
            assert token not in text, token

    def test_diff_file_is_required(self):
        assert vge.main([]) == 2

    def test_a_real_diff_file_still_works(self):
        assert vge.main(["--diff-file", str(NON_GATE)]) == 0
        assert vge.main(["--diff-file", str(PRE_FIX)]) == 1

    @pytest.mark.parametrize(
        "label,payload",
        [
            pytest.param("utf16", None, id="utf16"),
            pytest.param("raw_bytes", b"\x00\x01\x02\xff\xfe\x80\x81", id="raw_bytes"),
            pytest.param("prose", b"this is not a diff at all\n", id="prose"),
        ],
    )
    def test_a_file_that_does_not_decode_to_a_diff_exits_two(
        self, tmp_path, capsys, label, payload
    ):
        """Fail-CLOSED, the same treatment the missing-file path already got.

        `errors="replace"` turned a mis-encoded `--diff-file` into mojibake with
        no `+++ ` header, `analyze` found no files, and the CLI printed the
        gate-free PASS line and exited 0 — fail-OPEN on garbage input.
        """
        path = tmp_path / f"{label}.diff"
        if payload is None:
            path.write_bytes(_diff(NON_GATE).encode("utf-16"))
        else:
            path.write_bytes(payload)

        rc = vge.main(["--diff-file", str(path)])
        captured = capsys.readouterr()
        assert rc == 2, (rc, captured.out, captured.err)
        # A disarmed run must not read like a clean one.
        assert GATE_FREE not in captured.out, captured.out
        assert "+++" in captured.err, captured.err

    def test_a_missing_file_still_exits_two(self, tmp_path, capsys):
        """Positive control: the pre-existing fail-closed path is unchanged."""
        rc = vge.main(["--diff-file", str(tmp_path / "nope.diff")])
        assert rc == 2
        assert "not found" in capsys.readouterr().err


class TestTheNoOpSignatureBranchIsGone:
    """`if "-> bool" in signature.replace(" ", " ")` — a literal no-op.

    Both arguments were ordinary U+0020, and the next line's `replace(" ", "")`
    strictly dominates it on every signature shape. Almost certainly an
    unfinished edit (`.replace("  ", " ")`) shipped inside a blocking gate.

    The parametrized half is green BOTH ways by design — that IS the claim being
    made: deleting the branch changes no classification. It pins the
    equivalence; it does not prove the deletion was necessary.
    """

    _SHAPES = [
        ("annotated", "def f(x) -> bool:", True),
        ("no_space", "def f(x)->bool:", True),
        ("double_space", "def f(x) ->  bool:", True),
        ("union", "def f(x) -> bool | None:", True),
        ("truncated_multiline", "def f(", False),
        ("none_return", "def f(x) -> None:", False),
        ("unannotated", "def f(x):", False),
        ("predicate_name_only", "def is_ready(x):", True),
    ]

    @pytest.mark.parametrize(
        "label,signature,expected",
        _SHAPES,
        ids=[case[0] for case in _SHAPES],
    )
    def test_every_signature_shape_classifies_identically(
        self, label, signature, expected
    ):
        symbol = re.match(r"def (\w*)", signature)
        assert vge._is_predicate_shaped(
            symbol.group(1) if symbol else "", signature
        ) is expected, label

    def test_the_no_op_replace_is_absent_from_the_source(self):
        text = (ROOT / "scripts" / "verify_gate_evidence.py").read_text(
            encoding="utf-8"
        )
        assert 'replace(" ", " ")' not in text


# ── Diff ACQUISITION, in a real repo, through the real consumer ──────
#
# Everything above monkeypatches `vc._gate_evidence_diff` wholesale. That is
# correct seam isolation for the DETECTOR, and it is exactly why diff
# ACQUISITION shipped untested in both directions: two Critical fail-open
# defects (an absent untracked leg, and an author-writable `origin/HEAD` that
# disarms the phase in full) were invisible to a green suite. These tests build
# a real git repo and drive the real `verify_review_gate_evidence`.

_REPO_GATE = "refuse_unmarked"

# Byte-for-byte the gate shape that `TestGateDetection` already proves is
# detected, and whose battery it already proves is credited.
_GATE_SOURCE = (
    "def refuse_unmarked(text: str) -> bool:\n"
    '    if "ZZMARK" not in text:\n'
    "        return True\n"
    "    return False\n"
)

_GATE_EVIDENCE = (
    '_CASES = ["a", "bb", "ccc"]\n'
    "\n"
    '@pytest.mark.parametrize("case", _CASES)\n'
    "def test_cli_refuses(case):\n"
    '    text = f"{case}\\n"\n'
    '    assert "ZZMARK" not in text\n'
    "    assert refuse_unmarked(text) is True\n"
    "    assert exit_code == 1\n"
)

# A non-gate file so the branch sits at its own commit, strictly ahead of the
# fork point: without it `merge-base HEAD main == HEAD` and the new
# base-is-HEAD refusal would fire, masking what these cases measure.
_FILLER = 'VERSION = "0.0.1"\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _rev_parse(repo: Path, rev: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _head_branch(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    (repo / "scripts").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "A: fork point")
    return repo


def _branch_repo(tmp_path: Path, name: str = "repo", branch: str = "work") -> Path:
    """Repo whose branch <branch> is one non-gate commit ahead of main."""
    repo = _init_repo(tmp_path, name)
    _git(repo, "checkout", "-q", "-b", branch)
    (repo / "scripts" / "util.py").write_text(_FILLER, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work: non-gate filler")
    return repo


def _consume(monkeypatch, capsys, repo: Path) -> tuple[bool, str]:
    """Run the REAL consumer against a real repo; return (verdict, output)."""
    monkeypatch.setattr(vc, "_find_worktree_path", lambda issue_id: str(repo))
    verdict = vc.verify_review_gate_evidence("ISSUE-081")
    return verdict, capsys.readouterr().out


class TestUntrackedFilesAreAcquired:
    """The untracked leg the module's own oracle already owned (ISSUE-048).

    `/implement` step 10 does NOT precede this phase: `skills/review/SKILL.md`
    puts "apply minimal fixes" at step 4, this checkpoint at 4.6, and the first
    commit at step 6 — so at the moment the phase runs, a file a reviewer just
    created is NORMALLY untracked. The asymmetry fell on the unsafe side: an
    untracked new TEST failed closed, an untracked new SOURCE GATE failed open.
    """

    def test_an_untracked_gate_gets_the_same_verdict_as_a_committed_one(
        self, tmp_path, monkeypatch, capsys
    ):
        """A/B on identical bytes: tracked-ness must not change the verdict."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

        untracked = _branch_repo(tmp_path, "untracked")
        (untracked / "scripts" / "demo_fix.py").write_text(
            _GATE_SOURCE, encoding="utf-8"
        )

        committed = _branch_repo(tmp_path, "committed")
        (committed / "scripts" / "demo_fix.py").write_text(
            _GATE_SOURCE, encoding="utf-8"
        )
        _git(committed, "add", "-A")
        _git(committed, "commit", "-qm", "work: add an unevidenced gate")

        # Vacuity guard: the two repos must really hold the same gate bytes.
        assert (untracked / "scripts" / "demo_fix.py").read_bytes() == (
            committed / "scripts" / "demo_fix.py"
        ).read_bytes()

        verdict_a, out_a = _consume(monkeypatch, capsys, untracked)
        verdict_b, out_b = _consume(monkeypatch, capsys, committed)

        assert verdict_b is False, out_b
        assert _REPO_GATE in out_b, out_b
        assert verdict_a == verdict_b, (
            "identical bytes, different tracked-ness, different verdict:\n"
            f"[A untracked] {out_a}\n[B committed] {out_b}"
        )
        assert _REPO_GATE in out_a, out_a
        assert GATE_FREE not in out_a, out_a

    def test_an_untracked_gate_blocks_through_the_registered_cli(
        self, tmp_path, monkeypatch, capsys
    ):
        """Exit code through `verify_checkpoint.main`, not just the verifier."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        monkeypatch.setattr(vc, "_find_worktree_path", lambda issue_id: str(repo))

        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-081"]
        )
        out = capsys.readouterr().out
        assert rc == 1, out
        assert _REPO_GATE in out, out
        assert "ADVISORY:" not in out, "this phase must be blocking, not advisory"

    def test_an_untracked_test_is_still_credited_as_evidence(
        self, tmp_path, monkeypatch, capsys
    ):
        """The other side of the same asymmetry — fixing one side is not a fix.

        The gate is committed; the battery that evidences it is the untracked
        file the reviewer just wrote. It must be read, or this phase punishes
        the reviewer for the state its own SKILL puts them in.
        """
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work: add a gate")

        # Vacuity guard: without the untracked battery this repo FAILS, so a
        # pass below can only come from crediting the untracked file.
        bare_verdict, bare_out = _consume(monkeypatch, capsys, repo)
        assert bare_verdict is False, bare_out
        assert _REPO_GATE in bare_out, bare_out

        (repo / "tests" / "test_demo_fix.py").write_text(
            _GATE_EVIDENCE, encoding="utf-8"
        )
        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is True, out
        assert "carry both directions" in out, out
        assert _REPO_GATE in out, out

    def test_the_untracked_leg_has_exactly_one_definition(
        self, tmp_path, monkeypatch, capsys
    ):
        """Both consumers must go THROUGH `_untracked_paths`, not re-type it.

        Disarming the single helper must disarm BOTH the path-set oracle
        (`_changed_files_vs_base`) and the diff-text acquisition
        (`_gate_evidence_diff`). If either survives, there are two definitions
        of "the untracked leg" again and this Critical can recur.
        """
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")

        # Armed: the one helper reports the untracked file, both consumers see it.
        assert "scripts/demo_fix.py" in vc._untracked_paths(str(repo))
        armed_verdict, armed_out = _consume(monkeypatch, capsys, repo)
        assert armed_verdict is False, armed_out
        assert "scripts/demo_fix.py" in vc._changed_files_vs_base(str(repo), "main")

        # Disarmed at the single seam: both consumers must lose the file.
        monkeypatch.setattr(vc, "_untracked_paths", lambda wt_path: [])
        assert "scripts/demo_fix.py" not in vc._changed_files_vs_base(
            str(repo), "main"
        )
        _, blind_out = _consume(monkeypatch, capsys, repo)
        assert _REPO_GATE not in blind_out, blind_out


class TestABaseThatEqualsHeadIsRefusedNotPassed:
    """`refs/remotes/origin/HEAD` is author-writable, local, and never pushed.

    Point it at the branch under review and the whole chain collapses:
    merge_base == HEAD -> `git diff` exits 0 with empty stdout -> `analyze("")`
    finds no files -> the gate-free verdict (`vge.GATE_FREE_VERDICT`) -> exit 0,
    byte-identical to a legitimately gate-free PR. The same accident fires with
    no attacker at all when the branch under review IS the default branch.
    Workspace-persisted state a gate reads is untrusted input: validate on read.
    """

    @staticmethod
    def _with_origin(repo: Path, head_branch: str) -> Path:
        """Give the repo a real origin and point origin/HEAD at <head_branch>."""
        bare = repo.parent / f"{repo.name}-origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", str(bare)],
            check=True,
            capture_output=True,
            text=True,
        )
        _git(repo, "remote", "add", "origin", str(bare))
        _git(repo, "push", "-q", "origin", "main", "work")
        _git(repo, "remote", "set-head", "origin", head_branch)
        return repo

    def _repo_with_committed_gate(self, tmp_path: Path) -> Path:
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work: add an unevidenced gate")
        return repo

    def test_origin_head_pointed_at_the_feature_branch_cannot_disarm_the_phase(
        self, tmp_path, monkeypatch, capsys
    ):
        """The real `_default_branch()` chain, against a real manipulated ref."""
        repo = self._with_origin(self._repo_with_committed_gate(tmp_path), "main")
        monkeypatch.chdir(repo)

        # BASELINE: origin/HEAD -> main, the gate is charged.
        assert vc._default_branch() == "main"
        baseline_verdict, baseline_out = _consume(monkeypatch, capsys, repo)
        assert baseline_verdict is False, baseline_out
        assert _REPO_GATE in baseline_out, baseline_out

        # ATTACK: one local, unpushed, PR-invisible ref write.
        _git(repo, "remote", "set-head", "origin", "work")
        assert vc._default_branch() == "work", "fixture pin: the attack landed"

        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert GATE_FREE not in out, out
        assert "origin/HEAD" in out, out

    def test_a_disarmed_run_does_not_read_like_a_clean_one(
        self, tmp_path, monkeypatch, capsys
    ):
        """The refusal must NAME the cause, or it is the same silent pass."""
        repo = self._with_origin(self._repo_with_committed_gate(tmp_path), "work")
        monkeypatch.chdir(repo)
        _, out = _consume(monkeypatch, capsys, repo)
        assert "FAIL: gate-evidence" in out, out
        assert "REFUSED" in out, out
        assert "IS the branch under review" in out, out
        assert "refs/remotes/origin/HEAD" in out, out

    def test_a_base_sha_that_equals_head_is_named_as_its_own_cause(
        self, tmp_path, monkeypatch, capsys
    ):
        """The sha-identity leg, reached without the name leg.

        A branch cut from the default branch with no commit of its own has
        `merge-base HEAD <default> == HEAD` while its NAME still differs — so
        only the sha comparison can catch it, and it must say so.
        """
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _init_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "work")
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")

        # Fixture pins, read straight from git so this test stays RED on the
        # real verdict rather than on a missing helper: the NAME leg cannot be
        # what refuses here, only the sha comparison can.
        assert _head_branch(repo) == "work"
        assert vc._merge_base(str(repo), "main") == _rev_parse(repo, "HEAD")

        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert "same commit as HEAD" in out, out
        assert "IS the branch under review" not in out, out
        assert GATE_FREE not in out, out

    def test_the_branch_under_review_being_the_default_branch_fails_closed(
        self, tmp_path, monkeypatch, capsys
    ):
        """No attacker required: review the default branch and it self-disarms."""
        repo = _init_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "main: add an unevidenced gate")
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert GATE_FREE not in out, out

    def test_the_default_branch_name_check_is_load_bearing_on_its_own(
        self, tmp_path, monkeypatch, capsys
    ):
        """Disarm direction for the name half of the refusal.

        When `merge-base` is unresolvable the base falls back to the branch NAME,
        so the sha-identity check alone does not cover it. Forcing that fallback
        must still refuse rather than diff a branch against itself.
        """
        repo = self._repo_with_committed_gate(tmp_path)
        monkeypatch.setattr(vc, "_default_branch", lambda: "work")
        monkeypatch.setattr(vc, "_merge_base", lambda wt_path, base: None)

        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert "work" in out, out
        assert GATE_FREE not in out, out

    def test_a_zero_byte_diff_is_refused_not_passed(
        self, tmp_path, monkeypatch, capsys
    ):
        """An empty diff is unobtainable evidence, not evidence of innocence."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _init_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "work")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "work: empty commit")

        # Fixture pin: a real, non-degenerate base that is NOT HEAD, whose diff
        # is nonetheless zero bytes — so only the empty-diff leg can refuse.
        assert vc._merge_base(str(repo), "main") != _rev_parse(repo, "HEAD")

        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert GATE_FREE not in out, out


class TestChangedFilesVsBaseIsUnchanged:
    """Legacy pin: the shared oracle's observable semantics must not move.

    `_changed_files_vs_base` and `_default_branch` predate ISSUE-081 and are
    shared with the implement phases. The new refusal is scoped to the
    gate-evidence caller; extracting `_untracked_paths` must be a pure refactor.
    """

    @pytest.fixture()
    def four_leg_repo(self, tmp_path):
        repo = _branch_repo(tmp_path)
        (repo / "committed.py").write_text("a = 1\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work: committed leg")
        (repo / "staged.py").write_text("b = 2\n", encoding="utf-8")
        _git(repo, "add", "staged.py")
        (repo / "committed.py").write_text("a = 11\n", encoding="utf-8")  # unstaged
        (repo / "untracked.py").write_text("c = 3\n", encoding="utf-8")
        (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
        _git(repo, "add", ".gitignore")
        (repo / "ignored.py").write_text("d = 4\n", encoding="utf-8")
        return repo

    def test_all_four_legs_are_still_reported_and_ignores_still_excluded(
        self, four_leg_repo
    ):
        changed = vc._changed_files_vs_base(str(four_leg_repo), "main")
        assert changed == {
            "scripts/util.py",   # committed on the branch (fixture filler)
            "committed.py",      # committed + unstaged modification
            "staged.py",         # staged, never committed
            "untracked.py",      # untracked, not ignored
            ".gitignore",
        }, changed
        assert "ignored.py" not in changed

    def test_it_still_scopes_to_the_branch_delta_and_returns_a_set(
        self, tmp_path, monkeypatch
    ):
        """merge-base scoping (ISSUE-048) and the None fallback both survive."""
        repo = _branch_repo(tmp_path)
        _git(repo, "checkout", "-q", "main")
        (repo / "mainonly.py").write_text("m = 1\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "main: advances past the fork point")
        _git(repo, "checkout", "-q", "work")

        changed = vc._changed_files_vs_base(str(repo), "main")
        assert changed == {"scripts/util.py"}, changed

        monkeypatch.setattr(vc, "_merge_base", lambda wt_path, base: None)
        assert isinstance(vc._changed_files_vs_base(str(repo), "main"), set)

    def test_default_branch_still_prefers_origin_head(self, tmp_path, monkeypatch):
        """`_default_branch` keeps its pre-ISSUE-081 resolution order."""
        repo = _branch_repo(tmp_path)
        monkeypatch.chdir(repo)
        # No origin/HEAD -> falls back to a local main/master.
        assert vc._default_branch() == "main"
        _git(repo, "update-ref", "refs/remotes/origin/work", "refs/heads/work")
        _git(
            repo,
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/work",
        )
        assert vc._default_branch() == "work", (
            "the shared helper must still resolve from origin/HEAD; the new "
            "refusal belongs to the gate-evidence caller, not to this oracle"
        )

    def test_a_non_ascii_untracked_path_keeps_its_quoted_spelling(self, tmp_path):
        """Legacy pin: the gate-evidence unquoting must NOT leak into this set.

        `_changed_files_vs_base` has always put `git ls-files`' C-quoted
        spelling into its path set (`core.quotePath` defaults to true), and
        `_existing()` then drops it because no file of that name exists. That is
        a real pre-ISSUE-081 limitation of the SHARED oracle — recorded here,
        not fixed here: relaxing a shared contract for a new caller class must
        be scoped to that class, and the implement phases that read this set
        have never been measured against a changed spelling.
        """
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "démo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        changed = vc._changed_files_vs_base(str(repo), "main")
        quoted = [path for path in changed if path.startswith('"')]
        assert quoted, changed
        assert re.search(r"\\\d{3}", quoted[0]), quoted
        assert "scripts/démo_fix.py" not in changed, changed


# ── Diff HEADER rendering, and per-line cost ─────────────────────────
#
# Both defects below were invisible to a green 2476-test suite because every
# diff this module hands the detector is hand-written in the ONE rendering the
# parser happens to handle, and because no case measured how long `analyze`
# takes. The blocking consumer `verify_checkpoint._gate_evidence_diff` runs
# plain `git diff`, so the header rendering is the PRODUCTION path.

_NON_ASCII_GATE_FILE = "scripts/démo_fix.py"


def _real_git_diff(repo: Path, *extra: str) -> str:
    """Real `git diff main --` output, with the repo's own default config."""
    return subprocess.run(
        ["git", *extra, "diff", "main", "--"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT,
    ).stdout


def _repo_with_committed_non_ascii_gate(tmp_path: Path, name: str = "repo") -> Path:
    repo = _branch_repo(tmp_path, name)
    (repo / _NON_ASCII_GATE_FILE).write_text(_GATE_SOURCE, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "work: add an unevidenced gate in a non-ASCII file")
    return repo


class TestHeaderRenderings:
    """`_parse` must find the file in every rendering the real tools produce."""

    def test_the_c_quote_renderer_matches_real_git(self, tmp_path):
        """Validate the imitation against the oracle before trusting it.

        `_c_quote` is this module's hand-rolled `quote_c_style`. If it does not
        agree with real `git diff` byte for byte, the `c_quoted_paths` mutation
        pins a rendering git never emits and proves nothing (review lesson 4).
        """
        repo = _repo_with_committed_non_ascii_gate(tmp_path)
        plain = _real_git_diff(repo, "-c", "core.quotePath=false")
        quoted = _real_git_diff(repo, "-c", "core.quotePath=true")

        # Fixture pin: the two renderings must really differ, or this test
        # would assert that a no-op renderer is correct.
        assert plain != quoted, "git did not quote the non-ASCII path at all"
        assert _c_quote_headers(plain) == quoted

        # ...and the ASCII filler path must come through untouched, the way git
        # leaves it: a renderer that quotes everything is not git's.
        assert "+++ b/scripts/util.py" in quoted, quoted

    def test_a_real_git_diff_over_a_non_ascii_path_detects_the_gate(self, tmp_path):
        """Assert on REAL git output, in git's DEFAULT configuration."""
        repo = _repo_with_committed_non_ascii_gate(tmp_path)
        real = _real_git_diff(repo)

        # Fixture pins, read straight from git: the header really is C-quoted
        # (so this test stays RED on the verdict, not on a guessed rendering),
        # and the gate's source really is in the diff.
        header = next(
            line for line in real.split("\n")
            if line.startswith("+++ ") and "mo_fix" in line
        )
        assert header.startswith('+++ "'), header
        assert re.search(r"\\\d{3}", header), header
        assert f"+{_GATE_SOURCE.splitlines()[0]}" in real

        report = vge.analyze(real)
        assert _REPO_GATE in {g.symbol for g in report.gates}, report.gates
        assert _REPO_GATE in _symbols(report.findings), report.findings

        # The decoded path must be the path git itself reports unquoted — the
        # suite's own oracle for "what is this file called", not a guess.
        truth = subprocess.run(
            ["git", "-c", "core.quotePath=false", "diff", "--name-only", "main"],
            cwd=repo, check=True, capture_output=True, text=True,
            timeout=_CLI_TIMEOUT,
        ).stdout.split("\n")
        gate = next(g for g in report.gates if g.symbol == _REPO_GATE)
        assert gate.path in truth, (gate.path, truth)

    def test_a_real_git_diff_over_a_non_ascii_path_blocks_the_consumer(
        self, tmp_path, monkeypatch, capsys
    ):
        """The disarm direction through the REAL consumer, not the helper."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _repo_with_committed_non_ascii_gate(tmp_path)
        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert _REPO_GATE in out, out
        assert GATE_FREE not in out, out

    def test_the_committed_pre_fix_fixture_c_quoted_still_blocks(self):
        """The diff this whole suite exists to refuse, in git's default spelling."""
        text = _c_quoted_paths(_diff(PRE_FIX))

        # Vacuity guards: the mutation must have really re-rendered the headers
        # and really kept the gate definition.
        assert '+++ "b/scripts/sprint_queue' in text, text[:400]
        assert "+def sprint_status_is_running" in text

        report = vge.analyze(text)
        assert ARMING_GATE in _symbols(report.findings), [
            f.symbol for f in report.findings
        ]
        rendered = "\n".join(vge.format_report(report))
        assert GATE_FREE not in rendered, rendered

    def test_a_real_plain_diff_u_header_detects_the_gate(self, tmp_path):
        """`diff -u` appends a TAB and a timestamp to the path field."""
        source = tmp_path / "gate.py"
        source.write_text(_GATE_SOURCE, encoding="utf-8")
        real = subprocess.run(
            ["diff", "-u", os.devnull, "gate.py"],
            cwd=tmp_path, capture_output=True, text=True, timeout=_CLI_TIMEOUT,
        ).stdout

        # Fixture pin: real `diff -u` really does put a TAB in the field.
        header = next(l for l in real.split("\n") if l.startswith("+++ "))
        assert "\t" in header, repr(header)

        report = vge.analyze(real)
        assert _REPO_GATE in {g.symbol for g in report.gates}, report.gates
        gate = next(g for g in report.gates if g.symbol == _REPO_GATE)
        assert gate.path == "gate.py", gate.path

    def test_a_mnemonic_prefix_header_labels_the_path_correctly(self, tmp_path):
        """`diff.mnemonicPrefix=true` substitutes `i/`, `w/`, `c/`, `o/`."""
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work: add an unevidenced gate")
        real = _real_git_diff(repo, "-c", "diff.mnemonicPrefix=true")

        # Fixture pin: git really used the mnemonic prefix, not `b/`.
        assert "+++ w/scripts/demo_fix.py" in real, real
        assert "+++ b/scripts/demo_fix.py" not in real

        report = vge.analyze(real)
        gate = next(g for g in report.gates if g.symbol == _REPO_GATE)
        assert gate.path == "scripts/demo_fix.py", gate.path
        finding = _finding_for(report, _REPO_GATE)
        assert "scripts/demo_fix.py" in finding.message, finding.message
        assert "w/scripts" not in finding.message, finding.message

    def test_a_diff_of_a_diff_mints_no_phantom_file(self):
        """This repo COMMITS `.diff` fixtures, so this is a real PR shape.

        An inner `++ b/<path>` line renders as `+++ b/<path>` once the outer
        diff ADDS it. Read as a header it mints a file that does not exist and
        steals the rest of the real file's hunk. Before the `--- ` anchor the
        only thing standing in the way was the trailing space in `"+++ "`.
        """
        text = (
            "diff --git a/tests/fixtures/x.diff b/tests/fixtures/x.diff\n"
            "--- a/tests/fixtures/x.diff\n"
            "+++ b/tests/fixtures/x.diff\n"
            "@@ -1,0 +1,4 @@\n"
            "+++ b/scripts/phantom.py\n"
            "+@@ -0,0 +1,2 @@\n"
            "++def refuse_unmarked(text):\n"
            '++    raise ValueError("no")\n'
            "diff --git a/scripts/g.py b/scripts/g.py\n"
            "--- a/scripts/g.py\n"
            "+++ b/scripts/g.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def real_guard(text):\n"
            '+    if "ZZMARK" not in text:\n'
            '+        raise ValueError("no")\n'
        )
        files = vge._parse(text)
        paths = [f.path for f in files]
        assert paths == ["tests/fixtures/x.diff", "scripts/g.py"], paths

        # ...and the stolen context is given back: the inner diff's own lines
        # belong to the fixture that contains them.
        fixture = next(f for f in files if f.path == "tests/fixtures/x.diff")
        bodies = [body for _, body in fixture.added]
        assert "++ b/scripts/phantom.py" in bodies, bodies
        assert "+def refuse_unmarked(text):" in bodies, bodies

    @pytest.mark.parametrize(
        "label,text,expected",
        [
            (
                "deletion_to_dev_null",
                "diff --git a/scripts/gone.py b/scripts/gone.py\n"
                "--- a/scripts/gone.py\n"
                "+++ /dev/null\n"
                "@@ -1,2 +0,0 @@\n"
                "-def refuse_unmarked(text):\n"
                '-    raise ValueError("no")\n',
                [],
            ),
            (
                "binary_file",
                "diff --git a/assets/logo.png b/assets/logo.png\n"
                "Binary files /dev/null and b/assets/logo.png differ\n",
                [],
            ),
            (
                "no_newline_marker_inside_a_hunk",
                "diff --git a/scripts/g.py b/scripts/g.py\n"
                "--- a/scripts/g.py\n"
                "+++ b/scripts/g.py\n"
                "@@ -0,0 +1,2 @@\n"
                "+x = 1\n"
                "\\ No newline at end of file\n",
                ["scripts/g.py"],
            ),
            (
                "hunk_heading_whose_own_text_contains_at_at",
                "diff --git a/scripts/g.py b/scripts/g.py\n"
                "--- a/scripts/g.py\n"
                "+++ b/scripts/g.py\n"
                "@@ -1,2 +1,3 @@ def f():  # @@ marker @@\n"
                "+x = 1\n",
                ["scripts/g.py"],
            ),
        ],
    )
    def test_the_renderings_the_review_cleared_are_unchanged(
        self, label, text, expected
    ):
        """Regression pins: green before the fix, and required to stay green."""
        assert [f.path for f in vge._parse(text)] == expected, label

    def test_a_pure_rename_contributes_no_file(self, tmp_path):
        """Real `git diff -M` output, not a hand-written imitation.

        git renders a content-free rename with `rename from`/`rename to` and NO
        `---`/`+++` pair at all, so it contributes no file. Pinned because the
        review cleared this rendering and the `--- ` anchor must not change it.
        """
        repo = _init_repo(tmp_path)
        (repo / "scripts" / "old_name.py").write_text("x = 1\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "main: a file to rename")
        _git(repo, "checkout", "-q", "-b", "work")
        (repo / "scripts" / "util.py").write_text(_FILLER, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "work: non-gate filler")
        _git(repo, "mv", "scripts/old_name.py", "scripts/new_name.py")
        _git(repo, "commit", "-qm", "work: rename it")
        real = _real_git_diff(repo, "-c", "diff.renames=true")

        # Fixture pins: git really emitted rename headers, and really omitted
        # the `+++ ` pair — otherwise this asserts nothing about renames.
        assert "rename from scripts/old_name.py" in real, real
        assert "+++ b/scripts/new_name.py" not in real, real
        assert [f.path for f in vge._parse(real)] == ["scripts/util.py"], real


# ── Per-line cost: a blocking gate must not be hangable ──────────────

#: `if` repetitions that make one added line ~200 KB — the size the review
#: measured `analyze` taking tens of seconds on.
_REDOS_IFS = 21900


def _redos_diff(n_if: int = _REDOS_IFS) -> str:
    """One added line inside a `def`, many `if`, no `else`.

    The quadratic trigger for `_CONDITIONAL`'s third alternative: an unbounded
    `\\bif\\b.+\\belse\\b` restarts `.+` from every `if` and can never succeed,
    so the cost is (number of `if`) x (length of line).
    """
    body = " ".join(f"if a{index}" for index in range(n_if))
    return (
        "diff --git a/scripts/x.py b/scripts/x.py\n"
        "--- a/scripts/x.py\n"
        "+++ b/scripts/x.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def f(z):\n"
        f"+    z = [{body}]\n"
    )


#: Generous enough that a loaded CI box cannot flake it, and still ~8x below the
#: 15.2 s this payload measured before the fix.
_REDOS_BUDGET_SECONDS = 2.0


class TestAPathologicalLineCannotHangTheCheckpoint:
    """`scripts/checkpoint.sh` `exec`s python3 with no wall-clock bound.

    Nothing bounds `analyze`'s wall clock — the module's one timeout constant
    guarded a subprocess leg that SPEC-081's amendment then deleted — so an
    added line an author writes is enough to park the blocking review gate
    indefinitely.
    Three agents in this session were killed by a 600 s no-progress watchdog —
    a hangable blocking gate is an availability defect against the kit's own
    runner, not a theoretical one.
    """

    def test_a_200kb_single_line_completes_well_inside_the_budget(self):
        text = _redos_diff()

        # Fixture pin: the payload really is one ~200 KB physical line, so a
        # fast run cannot be a fast run over a small input.
        longest = max(len(line) for line in text.split("\n"))
        assert longest > 200_000, longest

        start = time.perf_counter()
        vge.analyze(text)
        elapsed = time.perf_counter() - start
        assert elapsed < _REDOS_BUDGET_SECONDS, (
            f"analyze() took {elapsed:.1f}s on a {longest}-byte line "
            f"(budget {_REDOS_BUDGET_SECONDS}s); measured 15.2s before the "
            "bounded `if ... else` quantifier and the per-line scan window"
        )

    def test_the_real_consumer_completes_inside_the_budget_too(
        self, monkeypatch, capsys
    ):
        """Through the blocking checkpoint, which is what actually hangs."""
        text = _redos_diff()
        monkeypatch.setattr(vc, "_gate_evidence_diff", lambda issue_id: text)
        start = time.perf_counter()
        verdict = vc.verify_review_gate_evidence("ISSUE-081")
        elapsed = time.perf_counter() - start
        capsys.readouterr()
        assert verdict is True, "this payload adds no gate; it only costs time"
        assert elapsed < _REDOS_BUDGET_SECONDS, f"{elapsed:.1f}s"

    def test_the_cost_is_linear_in_the_line_length(self, monkeypatch):
        """Pin the SHAPE, not only one point: 8x the input, nowhere near 64x.

        A point measurement is satisfiable by a faster machine. The review
        measured exactly 4x per 2x input before the fix.
        """
        def timed(n_if: int) -> float:
            text = _redos_diff(n_if)
            start = time.perf_counter()
            vge.analyze(text)
            return time.perf_counter() - start

        # Warm the regex cache so the first call is not charged for it.
        timed(100)
        small = max(timed(1200), 1e-4)
        large = timed(9600)
        assert large / small < 16, (
            f"8x the input cost {large / small:.1f}x the time: still "
            f"super-linear ({small:.4f}s -> {large:.4f}s)"
        )


class TestTheScanWindowFailsTowardDetection:
    """A line-length bound is itself a new fail-open unless its direction is
    chosen deliberately, documented, and tested.

    `_MAX_SCAN_CHARS` TRUNCATES rather than drops, so the bound fails toward
    DETECTION: every line-anchored pattern (`^\\s*if`, `^\\s*assert`) and every
    refusal inside the first 2 KB of a physical line still arms the gate. What
    it cannot see is a gate whose conditional AND refusal both live past the
    window on ONE physical line — which is not a shape hand-written Python
    takes. Both directions are pinned here.
    """

    _PAD = " ".join(f"a{index} = {index}" for index in range(30_000))

    def _diff_with(self, line: str) -> str:
        return (
            "diff --git a/scripts/x.py b/scripts/x.py\n"
            "--- a/scripts/x.py\n"
            "+++ b/scripts/x.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+def refuse_unmarked(text):\n"
            f"+{line}\n"
        )

    def test_a_gate_at_the_HEAD_of_a_huge_line_is_still_detected(self):
        """The direction the bound must not break: truncation keeps the head."""
        text = self._diff_with(
            '    bad = 1 if "ZZMARK" not in text else 0; '
            'raise ValueError("no"); ' + self._PAD
        )
        longest = max(len(line) for line in text.split("\n"))
        assert longest > 200_000, longest       # fixture pin
        report = vge.analyze(text)
        assert _REPO_GATE in {g.symbol for g in report.gates}, report.gates

    def test_a_gate_hidden_PAST_the_window_is_the_documented_blind_spot(self):
        """The direction the bound DOES fail — deliberately, and recorded.

        Detected before the bound existed; not detected after. Accepted because
        the alternative is a blocking review gate an author can park for 40 s
        with one line, and because a 200 KB physical line whose only
        conditional and only refusal both sit past offset 2048 is a minified
        artefact, not a gate anybody is trying to ship.
        """
        text = self._diff_with(
            "    " + self._PAD
            + '; bad = 1 if "ZZMARK" not in text else 0; raise ValueError("no")'
        )
        assert "raise ValueError" in text        # fixture pin: it IS in there
        report = vge.analyze(text)
        assert report.gates == (), (
            "the scan window is documented as truncating, not extending; if "
            "this now passes, update the docstring on _MAX_SCAN_CHARS"
        )

    def test_the_window_is_load_bearing(self, monkeypatch):
        """Mutation pin: widening the window must restore the blind-spot gate."""
        text = self._diff_with(
            "    " + self._PAD
            + '; bad = 1 if "ZZMARK" not in text else 0; raise ValueError("no")'
        )
        assert vge.analyze(text).gates == ()
        monkeypatch.setattr(vge, "_MAX_SCAN_CHARS", 10 ** 9)
        assert _REPO_GATE in {
            g.symbol for g in vge.analyze(text).gates
        }, "mutant SURVIVED: _MAX_SCAN_CHARS is not what hides the gate"


# ── Acquisition: untracked paths git C-quotes ────────────────────────


class TestUntrackedNonAsciiPathsAreAcquired:
    """`git ls-files` hands back `"a\\303\\251.py"`, and `--no-index` cannot open it.

    `core.quotePath` defaults to true, so an untracked source file with a
    non-ASCII name produced an empty `git diff --no-index` and was skipped by
    the loop — an untracked non-ASCII GATE was invisible. Fail-OPEN, on the
    path `skills/review/SKILL.md` puts reviewers on (fixes at step 4, this
    checkpoint at 4.6, first commit at step 6).
    """

    def test_an_untracked_non_ascii_gate_blocks_through_the_real_consumer(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _branch_repo(tmp_path)
        (repo / _NON_ASCII_GATE_FILE).write_text(_GATE_SOURCE, encoding="utf-8")

        # Fixture pin, read straight from git: the shared oracle really does
        # hand back the QUOTED spelling, which is the spelling `--no-index`
        # could not open. Without this the test could pass for the wrong reason.
        untracked = vc._untracked_paths(str(repo))
        assert len(untracked) == 1, untracked
        assert untracked[0].startswith('"'), untracked
        assert re.search(r"\\\d{3}", untracked[0]), untracked

        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert _REPO_GATE in out, out
        assert GATE_FREE not in out, out

    def test_an_untracked_non_ascii_gate_blocks_through_the_registered_cli(
        self, tmp_path, monkeypatch, capsys
    ):
        """Exit code through `verify_checkpoint.main`, not just the verifier."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _branch_repo(tmp_path)
        (repo / _NON_ASCII_GATE_FILE).write_text(_GATE_SOURCE, encoding="utf-8")
        monkeypatch.setattr(vc, "_find_worktree_path", lambda issue_id: str(repo))

        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-081"]
        )
        out = capsys.readouterr().out
        assert rc == 1, out
        assert _REPO_GATE in out, out
        assert "ADVISORY:" not in out, "this phase must be blocking, not advisory"

    def test_an_untracked_non_ascii_gate_matches_a_committed_one(
        self, tmp_path, monkeypatch, capsys
    ):
        """A/B on identical bytes: tracked-ness must not change the verdict."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        untracked = _branch_repo(tmp_path, "untracked")
        (untracked / _NON_ASCII_GATE_FILE).write_text(_GATE_SOURCE, encoding="utf-8")
        committed = _repo_with_committed_non_ascii_gate(tmp_path, "committed")

        assert (untracked / _NON_ASCII_GATE_FILE).read_bytes() == (
            committed / _NON_ASCII_GATE_FILE
        ).read_bytes()

        verdict_a, out_a = _consume(monkeypatch, capsys, untracked)
        verdict_b, out_b = _consume(monkeypatch, capsys, committed)
        assert verdict_b is False, out_b
        assert verdict_a == verdict_b, (
            "identical bytes, different tracked-ness, different verdict:\n"
            f"[A untracked] {out_a}\n[B committed] {out_b}"
        )
        assert _REPO_GATE in out_a, out_a

    def test_an_untracked_ascii_gate_is_unaffected(
        self, tmp_path, monkeypatch, capsys
    ):
        """Disarm direction for the unquoting: the ASCII leg must not regress."""
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        repo = _branch_repo(tmp_path)
        (repo / "scripts" / "demo_fix.py").write_text(_GATE_SOURCE, encoding="utf-8")
        assert vc._untracked_paths(str(repo)) == ["scripts/demo_fix.py"]
        verdict, out = _consume(monkeypatch, capsys, repo)
        assert verdict is False, out
        assert _REPO_GATE in out, out


# ── The EVIDENCE half's regex cost is bounded too ─────────────────────


class TestTheConsumerOutcomeScanIsBounded:
    """`_CONSUMER_RE` backtracks quadratically, and the first fix missed it.

    `_MAX_SCAN_CHARS` was applied in `detect_gates` — the SOURCE half — so the
    EVIDENCE half stayed unbounded. `_CONSUMER_RE` opens with
    `\\bassert\\s+[\\w.\\[\\]"'() ]*\\b(?:exit_code|…)`, a permissive char-class
    star retried from every `assert` start on the line. Measured before the
    bound, through `analyze()`:

        12 KB -> 0.017 s | 24 KB -> 0.070 s | 48 KB -> 0.255 s
        96 KB -> 0.99 s  | 192 KB -> 3.96 s          (4x per 2x = O(n^2))

    Reachable only when the battery ALSO carries a registering vacuity guard:
    without one, `_is_non_vacuous` is False and the `composite` conjunct
    short-circuits before `_has_consumer_outcome`, which is why a naive probe
    reports a flat 0.0005 s and a false all-clear. The parameter must be named
    from `_INPUT_ROOTS` (`text`), not something like `case`, or the guard does
    not register and the cost never appears.
    """

    @staticmethod
    def _battery_diff(n_assert_tokens: int, outcome: str = "") -> str:
        payload = ("assert " + "a" * 40 + " ") * n_assert_tokens
        lines = [
            "import pytest",
            '@pytest.mark.parametrize("text", ["- Status: running",'
            ' "- status: RUNNING", "-  Status:  running"])',
            "def test_guard_refuses(text):",
            # Vacuity guard whose root IS in `_INPUT_ROOTS`, so
            # `_is_non_vacuous` is True and the costly call is reached.
            '    assert "- Status: running" in text',
            "    out = run_guard(text)",
            "    assert out is False",
            "    " + payload + outcome,
        ]
        body = "".join("+" + line + "\n" for line in lines)
        src = (
            "diff --git a/scripts/g.py b/scripts/g.py\n"
            "--- a/scripts/g.py\n+++ b/scripts/g.py\n"
            "@@ -1,0 +1,4 @@\n"
            "+def run_guard(text):\n+    if not text:\n"
            "+        return 1\n+    return 0\n"
        )
        tst = (
            "diff --git a/tests/test_g.py b/tests/test_g.py\n"
            "--- a/tests/test_g.py\n+++ b/tests/test_g.py\n"
            f"@@ -1,0 +1,{len(lines)} @@\n" + body
        )
        return src + tst

    def test_the_costly_call_is_actually_reached(self):
        """Guard the guard: if this breaks, the timing tests go vacuous.

        The whole class is meaningless unless `_has_consumer_outcome` really
        runs on the payload line, so pin the two preconditions explicitly
        rather than trusting them.
        """
        text = self._battery_diff(1)
        blocks, module_text = vge._blocks(vge._parse(text))
        batteries = [b for b in blocks if vge._is_battery(b, module_text)]
        assert batteries, "no battery — _has_consumer_outcome is never called"
        assert any(vge._is_non_vacuous(b) for b in batteries), (
            "no registering vacuity guard — the composite conjunct "
            "short-circuits before _has_consumer_outcome and this class "
            "would measure nothing"
        )

    def test_a_pathological_evidence_line_stays_cheap(self):
        import time

        text = self._battery_diff(4000)
        start = time.perf_counter()
        vge.analyze(text)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, (
            f"analyze() took {elapsed:.2f}s on a {len(text)}-byte diff whose "
            f"evidence half carries one long assert-dense line (budget 2.0s); "
            f"measured 3.96s before the evidence-half scan bound"
        )

    def test_the_cost_is_linear_not_quadratic(self):
        import time

        def cost(n):
            text = self._battery_diff(n)
            start = time.perf_counter()
            vge.analyze(text)
            return time.perf_counter() - start

        small, large = cost(500), cost(4000)
        # 8x the input. Quadratic would be ~64x; allow generous slack for a
        # loaded runner while still failing on a quadratic regression.
        assert large < max(small * 20, 0.5), (
            f"8x the input cost {large / max(small, 1e-9):.1f}x the time "
            f"({small:.4f}s -> {large:.4f}s): still super-linear"
        )

    def test_the_bound_fails_closed(self):
        """A consumer outcome past the window is NOT credited.

        Fail-closed means MORE findings, never fewer: the gate is reported as
        missing its composite pin rather than silently passing.
        """
        pad = "assert " + "a" * 40 + " "
        beyond = self._battery_diff(
            (vge._MAX_SCAN_CHARS // len(pad)) + 40, outcome="; assert rc == 1"
        )
        report = vge.analyze(beyond)
        assert report.evidence[("scripts/g.py", "run_guard")]["composite"] is False, (
            "an outcome past the scan window was credited — the bound must "
            "fail CLOSED"
        )
        assert report.findings, "fail-closed must yield a finding, not silence"

    def test_an_outcome_inside_the_window_is_still_credited(self):
        """The arm direction: truncation must not break the normal case."""
        near = self._battery_diff(1, outcome="; assert rc == 1")
        report = vge.analyze(near)
        assert report.evidence[("scripts/g.py", "run_guard")]["composite"] is True, (
            "a consumer outcome within the first _MAX_SCAN_CHARS must still "
            "be credited"
        )

    def test_the_evidence_half_bound_is_load_bearing(self, monkeypatch):
        """Mutation pin: widening the window must restore the quadratic cost."""
        import time

        text = self._battery_diff(4000)
        monkeypatch.setattr(vge, "_MAX_SCAN_CHARS", 10 ** 9)
        start = time.perf_counter()
        vge.analyze(text)
        elapsed = time.perf_counter() - start
        assert elapsed > 0.5, (
            f"mutant SURVIVED in {elapsed:.3f}s: widening _MAX_SCAN_CHARS did "
            f"not restore the quadratic cost, so this bound is not what makes "
            f"the evidence half cheap — find what is before trusting it"
        )
