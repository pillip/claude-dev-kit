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
* AC-3 → ``TestAC3NonGateDiffPaysNoTax`` (+ the phase-partition pins in
  ``tests/test_verify_checkpoint_contract.py``)
* AC-4 → ``TestAC4BothDirectionsEvidencedPasses``
* AC-5 → ``TestAC5TheMechanismIsSubjectToItsOwnRule`` (disarm battery),
  ``TestAC5CompositePinThroughTheRealConsumer`` (composite, via the
  ``verify_checkpoint.py`` CLI), ``TestAC5MutationMatrix`` (both directions)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
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

# `git diff` on a feature branch is a local, in-memory operation; the project's
# own `verify_checkpoint._run` default (30 s, documented at its definition) is
# reused rather than re-typed as a new constant.
_CLI_TIMEOUT = 120


def _diff(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _symbols(findings) -> set[str]:
    return {f.symbol for f in findings}


def _finding_for(report, symbol: str):
    matches = [f for f in report.findings if f.symbol == symbol]
    assert len(matches) <= 1, f"{symbol}: expected at most one finding, got {matches}"
    return matches[0] if matches else None


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
        assert report.evidence["refuse_unmarked"] == {
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
        evidence = report.evidence[ARMING_GATE]
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
        assert out == "PASS: gate-evidence — no gate-adding change in the diff\n", (
            repr(out)
        )

    def test_the_non_gate_fixture_is_substantial_not_empty(self):
        """Vacuity guard: an empty diff would pass for the wrong reason."""
        text = _diff(NON_GATE)
        assert text.count("\n+") > 1000, text.count("\n+")
        assert "tests/test_registry_lock_contract.py" in text


# ── AC-4 ─────────────────────────────────────────────────────────────


class TestAC4BothDirectionsEvidencedPasses:
    """The requirement is satisfiable — asserted on the real post-fix diff."""

    def test_post_fix_replay_has_no_finding_for_the_repaired_gate(self):
        report = vge.analyze(_diff(POST_FIX))
        assert _finding_for(report, ARMING_GATE) is None, [
            f.message for f in report.findings
        ]

    def test_post_fix_evidence_is_complete_for_the_repaired_gate(self):
        evidence = vge.analyze(_diff(POST_FIX)).evidence[ARMING_GATE]
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
        """`check_roster_boundary` is unevidenced before AND after the fix.

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
        """Both directions: a mutation must not manufacture a finding either."""
        text = mutate(_diff(POST_FIX))
        assert "def sprint_status_is_running" in text, label
        report = vge.analyze(text)
        assert _finding_for(report, ARMING_GATE) is None, label


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

    def test_the_checkpoint_phase_passes_a_post_fix_diff(self, monkeypatch, capsys):
        monkeypatch.setattr(
            vc, "_gate_evidence_diff", lambda issue_id: _diff(POST_FIX)
        )
        rc = vc.main(
            ["--skill", "review", "--phase", "gate-evidence", "--issue", "ISSUE-078"]
        )
        out = capsys.readouterr().out
        # The residual `check_roster_boundary` finding is real, so the phase
        # still refuses — what must have changed is the arming gate's finding.
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
_REAL_MUTANTS = [
    ("variant_floor_removed", {"MIN_VARIANTS": 0}),
    ("variant_floor_raised_absurdly", {"MIN_VARIANTS": 999}),
    ("vacuity_guard_requirement_dropped", {"REQUIRE_VACUITY_GUARD": False}),
    ("refusal_vocabulary_emptied", {"REFUSAL_PATTERNS": (), "_BOOL_REFUSAL": _NEVER}),
]

# A minimal gate whose only evidence is a vacuity-guarded HELPER battery: no
# consumer-level outcome anywhere. Isolates REQUIRE_CONSUMER_OUTCOME, which the
# real fixtures cannot exercise (both already carry consumer batteries).
_HELPER_ONLY_DIFF = """diff --git a/scripts/demo_gate.py b/scripts/demo_gate.py
--- a/scripts/demo_gate.py
+++ b/scripts/demo_gate.py
@@ -0,0 +1,5 @@
+def blocked_marker_is_present(text: str) -> bool:
+    if "BLOCKED-MARKER" in text:
+        return True
+    return False
diff --git a/tests/test_demo_gate.py b/tests/test_demo_gate.py
--- a/tests/test_demo_gate.py
+++ b/tests/test_demo_gate.py
@@ -0,0 +1,11 @@
+_MARKER_VARIANTS = [
+    "BLOCKED-MARKER",
+    "  BLOCKED-MARKER  ",
+    "**BLOCKED-MARKER**",
+]
+
+@pytest.mark.parametrize("variant", _MARKER_VARIANTS)
+def test_blocked_marker_is_present_still_refuses(variant):
+    text = f"header\\n{variant}\\nfooter"
+    assert "BLOCKED-MARKER" in text
+    assert blocked_marker_is_present(text) is True
"""

# The same gate whose only evidence is an OUTCOME MAP (the expected value is
# itself a parameter). Isolates REQUIRE_INPUT_ONLY_PARAMS.
_OUTCOME_MAP_DIFF = """diff --git a/scripts/demo_gate.py b/scripts/demo_gate.py
--- a/scripts/demo_gate.py
+++ b/scripts/demo_gate.py
@@ -0,0 +1,5 @@
+def blocked_marker_is_present(text: str) -> bool:
+    if "BLOCKED-MARKER" in text:
+        return True
+    return False
diff --git a/tests/test_demo_gate.py b/tests/test_demo_gate.py
--- a/tests/test_demo_gate.py
+++ b/tests/test_demo_gate.py
@@ -0,0 +1,12 @@
+_OUTCOME_MAP = [
+    ("BLOCKED-MARKER here", True),
+    ("clean text here", False),
+    ("another clean one", False),
+]
+
+@pytest.mark.parametrize("variant,expected", _OUTCOME_MAP)
+def test_blocked_marker_outcome_map(variant, expected):
+    text = variant
+    assert isinstance(text, str) is True
+    assert "BLOCKED-MARKER" in text or expected is False
+    assert blocked_marker_is_present(text) is expected
"""

_DEMO_GATE = "blocked_marker_is_present"


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
        assert armed.evidence[_DEMO_GATE] == {"disarm": True, "composite": False}
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
        assert armed.evidence[_DEMO_GATE] == {"disarm": False, "composite": False}
        assert _finding_for(armed, _DEMO_GATE).kind == "missing-disarm-battery"

        monkeypatch.setattr(vge, "REQUIRE_INPUT_ONLY_PARAMS", False)
        disarmed = vge.analyze(_OUTCOME_MAP_DIFF)
        assert _finding_for(disarmed, _DEMO_GATE).kind != "missing-disarm-battery", (
            "mutant SURVIVED: dropping the input-only rule must let an outcome "
            "map count as a disarm battery"
        )


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
        assert ARMING_GATE in {sym for sym, _ in report.exemptions}
        assert all(reason for _, reason in report.exemptions)

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


class TestJsonOutputIsStable:
    def test_json_mode_emits_the_findings_machine_readably(self, capsys):
        rc = vge.main(["--diff-file", str(PRE_FIX), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert ARMING_GATE in {f["symbol"] for f in payload["findings"]}
        assert payload["evidence"][ARMING_GATE] == {
            "disarm": True,
            "composite": False,
        }
