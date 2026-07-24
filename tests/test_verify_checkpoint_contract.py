"""ISSUE-031 blocking/advisory contract for checkpoint phases.

Predictability guard: the FULL partition of checkpoint phases into blocking
vs advisory is enumerated here. Changing any phase's tier (or adding a phase
without classifying it) fails this test — no gate can be demoted silently.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_checkpoint as vc  # noqa: E402

# Existence-style checks: steps modern models perform reliably; hard-STOPping
# them forbids autonomous recovery (ISSUE-031).
EXPECTED_ADVISORY = {
    ("implement", "issue"),
    ("implement", "worktree"),
    ("implement", "code"),
    ("implement", "push"),
    ("implement", "pr"),
    ("implement", "registry"),
    ("review", "checkout"),
    ("review", "push"),
    ("diagnose", "worktree"),
    ("diagnose", "push"),
    ("refactor", "worktree"),
    ("refactor", "push"),
    ("devops", "worktree"),
    ("devops", "push"),
    ("migrate", "worktree"),
    ("migrate", "push"),
    ("testgen", "worktree"),
    ("testgen", "push"),
}

# Behavior gates: verify what a model cannot self-certify. These MUST exit
# non-zero on failure. (review/debt is advisory by internal design — it always
# returns ok — but stays out of ADVISORY_PHASES to keep that explicit.)
EXPECTED_BLOCKING = {
    ("implement", "test-plan"),
    ("implement", "figma"),
    ("implement", "tests-written"),
    ("implement", "red"),
    ("implement", "test"),
    ("review", "review"),
    ("review", "synthesis-audit"),
    ("review", "ui-review"),
    ("review", "figma-compliance"),
    ("review", "computed-styles"),
    ("review", "visual-diff"),
    ("review", "structural-match"),
    ("review", "layout"),
    ("review", "test-quality"),
    ("review", "debt"),
    ("review", "test"),
    ("ship", "checks"),
    ("ship", "merge"),
    ("ship", "smoke"),
    ("ship", "cleanup"),
    ("diagnose", "test"),
    ("refactor", "test"),
    ("devops", "validate"),
    ("migrate", "test"),
    ("testgen", "test"),
    ("uiux", "context"),
    ("uiux", "philosophy"),
    ("uiux", "system"),
    ("mobile-uiux", "context"),
    ("mobile-uiux", "philosophy"),
    ("mobile-uiux", "system"),
}


def test_partition_is_exact():
    registered = set(vc.VERIFIERS.keys())
    assert EXPECTED_ADVISORY | EXPECTED_BLOCKING == registered, (
        "unclassified or stale phases: "
        f"missing={registered - (EXPECTED_ADVISORY | EXPECTED_BLOCKING)}, "
        f"stale={(EXPECTED_ADVISORY | EXPECTED_BLOCKING) - registered}"
    )
    assert not (EXPECTED_ADVISORY & EXPECTED_BLOCKING)


def test_advisory_set_matches_implementation():
    assert vc.ADVISORY_PHASES == EXPECTED_ADVISORY, (
        "ADVISORY_PHASES changed — a gate was promoted/demoted; update the "
        "contract table deliberately if intended"
    )


def _run_main(monkeypatch, key, ok):
    monkeypatch.setitem(vc.VERIFIERS, key, lambda issue_id, **_: ok)
    return vc.main(["--skill", key[0], "--phase", key[1], "--issue", "ISSUE-999"])


def test_advisory_phase_failure_exits_zero_with_advisory_line(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ("implement", "registry"), ok=False)
    out = capsys.readouterr().out
    assert rc == 0
    assert "ADVISORY:" in out
    assert "continue" in out


def test_advisory_phase_success_is_silent_about_advisory(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ("implement", "registry"), ok=True)
    assert rc == 0
    assert "ADVISORY:" not in capsys.readouterr().out


def test_blocking_phase_failure_still_exits_nonzero(monkeypatch, capsys):
    rc = _run_main(monkeypatch, ("implement", "red"), ok=False)
    assert rc == 1
    assert "ADVISORY:" not in capsys.readouterr().out


def test_generated_skill_text_matches_tier():
    """Every checkpoint invocation in generated skills carries the wording of
    its tier: advisory blocks say report-and-continue, blocking blocks keep
    the STOP semantics."""
    import re
    run_re = re.compile(r"--skill ([\w-]+) --phase ([\w-]+)")
    for md in ROOT.glob("skills/*/SKILL.md"):
        lines = md.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = run_re.search(line)
            if not m or "checkpoint.sh" not in line:
                continue
            key = (m.group(1), m.group(2))
            if key == ("review", "debt"):
                continue  # advisory by internal design since ISSUE-020; own wording
            block = "\n".join(lines[max(0, i - 2): i + 3])
            if key in EXPECTED_ADVISORY:
                assert "ADVISORY" in block, f"{md.parent.name}: {key} lacks advisory wording"
                assert "NEVER SKIP" not in block, f"{md.parent.name}: {key} still marked NEVER SKIP"
            elif key in EXPECTED_BLOCKING:
                assert "MANDATORY" in block or "STOP" in block, (
                    f"{md.parent.name}: {key} lost its blocking wording"
                )
