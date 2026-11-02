"""Unit tests for scripts/spec_gate.py — covers every row of the decision table."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.spec_gate import checkout_roots, decide, main, parse_issue, scan_signals

KIT_ROOT = Path(__file__).resolve().parents[1]
GATE = KIT_ROOT / "scripts" / "spec_gate.py"


def _issue_block(
    num: str = "007",
    spec_required: str = "false",
    spec_path: str = "none",
    estimate: str = "1d",
    status: str = "doing",
    extra_body: str = "",
) -> str:
    return f"""### ISSUE-{num}: Sample task
- Track: platform
- PRD-Ref: FR-1
- Priority: P1
- Estimate: {estimate}
- Status: {status}
- Spec-Required: {spec_required}
- Spec: {spec_path}
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
{extra_body if extra_body else "Add feature X."}

#### Scope (In/Out)
- In: stuff
- Out: nothing
"""


def _write_issues(tmp_path: Path, blocks: list[str]) -> Path:
    p = tmp_path / "issues.md"
    p.write_text("\n\n".join(blocks), encoding="utf-8")
    return p


class TestParseIssue:
    def test_finds_issue(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        issue = parse_issue(p, "ISSUE-007")
        assert issue is not None
        assert issue["estimate"] == "1d"
        assert issue["spec_required"] == "false"

    def test_returns_none_when_missing(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        assert parse_issue(p, "ISSUE-999") is None


class TestScanSignals:
    def test_detects_api_keyword(self):
        sigs = scan_signals("This changes the API surface")
        assert any(s["signal"] == "API surface" for s in sigs)

    def test_detects_schema_and_migration(self):
        sigs = scan_signals("Adds a new schema and a migration step")
        labels = {s["signal"] for s in sigs}
        assert "schema" in labels
        assert "migration" in labels

    def test_detects_estimate_at_cap(self):
        body = "- Estimate: 1.5d\n"
        sigs = scan_signals(body)
        assert any("1.5d cap" in s["signal"] for s in sigs)

    def test_no_signals_on_clean_body(self):
        sigs = scan_signals("Rename a variable in a single function.")
        assert sigs == []


class TestDecideTable:
    """One test per row of the decision table from conversation 2026-06-13."""

    def _gate(self, tmp_path, **issue_kwargs):
        sprint = issue_kwargs.pop("sprint", False)
        skip = issue_kwargs.pop("skip", False)
        block = _issue_block(**issue_kwargs)
        p = _write_issues(tmp_path, [block])
        issue = parse_issue(p, f"ISSUE-{issue_kwargs.get('num', '007')}")
        assert issue is not None
        return decide(issue, p.resolve().parent, sprint_mode=sprint, skip_gate=skip)

    # Row 1: sprint + Spec-Required=true + SPEC exists → proceed
    def test_sprint_required_with_spec(self, tmp_path: Path):
        specs = tmp_path / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-007.md").write_text("# SPEC-007", encoding="utf-8")
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="docs/specs/SPEC-007.md",
            sprint=True,
        )
        assert result["decision"] == "proceed"

    # Row 2: sprint + Spec-Required=true + SPEC missing → auto_spec
    def test_sprint_required_no_spec(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="none",
            sprint=True,
        )
        assert result["decision"] == "auto_spec"

    # Row 3: sprint + Spec-Required=false + signals → proceed (with recommendation)
    def test_sprint_signals_only(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Adds an API schema migration.",
            sprint=True,
        )
        assert result["decision"] == "proceed"
        assert len(result["signals"]) >= 1

    # Row 4: sprint + Spec-Required=false + no signals → proceed (silent)
    def test_sprint_no_signal_no_required(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Rename a function in one file.",
            sprint=True,
        )
        assert result["decision"] == "proceed"
        assert result["signals"] == []

    # Row 5: non-sprint + Spec-Required=true + SPEC missing → hold
    def test_nonsprint_required_no_spec(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="none",
            sprint=False,
        )
        assert result["decision"] == "hold"

    # Row 6: non-sprint + Spec-Required=true + SPEC exists → proceed
    def test_nonsprint_required_with_spec(self, tmp_path: Path):
        specs = tmp_path / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-007.md").write_text("# SPEC-007", encoding="utf-8")
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="docs/specs/SPEC-007.md",
            sprint=False,
        )
        assert result["decision"] == "proceed"

    # Row 7: non-sprint + Spec-Required=false + signals → hold (no default)
    def test_nonsprint_signals_only(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Touches the API protocol and adds a migration.",
            sprint=False,
        )
        assert result["decision"] == "hold"
        assert len(result["signals"]) >= 2

    # Row 8: non-sprint + Spec-Required=false + no signals → proceed (silent)
    def test_nonsprint_no_signal(self, tmp_path: Path):
        result = self._gate(
            tmp_path,
            spec_required="false",
            spec_path="none",
            extra_body="Rename a variable.",
            sprint=False,
        )
        assert result["decision"] == "proceed"

    # Row 9: any mode + --skip-spec-gate → bypassed
    @pytest.mark.parametrize("sprint", [True, False])
    def test_skip_gate_bypasses(self, tmp_path: Path, sprint: bool):
        result = self._gate(
            tmp_path,
            spec_required="true",
            spec_path="none",
            sprint=sprint,
            skip=True,
        )
        assert result["decision"] == "bypassed"


class TestMainCli:
    def test_emits_json_decision(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        p = _write_issues(tmp_path, [_issue_block()])
        rc = main(["ISSUE-007", "--issues-md", str(p)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert "decision" in out
        assert out["issue_id"] == "ISSUE-007"

    def test_invalid_issue_id_exits_2(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        rc = main(["not-an-id", "--issues-md", str(p)])
        assert rc == 2

    def test_missing_issue_exits_2(self, tmp_path: Path):
        p = _write_issues(tmp_path, [_issue_block()])
        rc = main(["ISSUE-999", "--issues-md", str(p)])
        assert rc == 2

    def test_force_sprint_mode_flag(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        # Spec-Required=true with no SPEC, force-sprint → auto_spec.
        p = _write_issues(
            tmp_path,
            [_issue_block(spec_required="true", spec_path="none")],
        )
        rc = main(
            ["ISSUE-007", "--issues-md", str(p), "--force-sprint-mode"]
        )
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["decision"] == "auto_spec"
        assert out["sprint_mode"] is True


# ---------------------------------------------------------------------------
# ISSUE-102 — the gate must be SATISFIABLE for the configuration the kit's own
# two rules force. See the module docstring of scripts/spec_gate.py.
#
# Shared-Registry rule : the `Spec:` field is committed on MAIN's issues.md and
#                        registry files are never committed to a feature branch.
# /spec Output Contract: the SPEC file is written on the BRANCH.
#
# So the two artifacts the gate must see together never co-locate until merge,
# and the pre-fix single-root resolution could never return `proceed` for the
# issues it fires on. Reproduced from BOTH call sites before this fix:
#   - CWD=main     → `Spec:` known, file not in main's tree      → auto_spec
#   - CWD=worktree → file present, branch's issues.md reads none → auto_spec
# Both directions are asserted below because the defect was invisible from
# either one alone.
# ---------------------------------------------------------------------------

#: Registry block for the two-checkout fixture. `Spec:` starts at `none`, which
#: is what a feature branch's frozen copy keeps forever.
_REPRO_BLOCK = """### ISSUE-500: Reproduction issue
- Track: platform
- PRD-Ref: none
- Priority: P1
- Estimate: 1d
- Status: doing
- Spec-Required: true
- Spec: none
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Produce a SPEC on the branch while the registry field lives on main.
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )


def _two_checkouts(
    tmp_path: Path,
    *,
    write_spec: bool = True,
    spec_field: str = "docs/specs/SPEC-500.md",
    spec_rel: str = "docs/specs/SPEC-500.md",
) -> tuple[Path, Path]:
    """Build `main` + a linked worktree in the field-on-main/file-on-branch shape.

    Returns ``(main_checkout, worktree)``. The `Spec:` field is committed on
    ``main`` ONLY — committing it on the branch is exactly what the kit's
    Shared-Registry rule forbids, so the fixture must not do it either or the
    test would pin a configuration that cannot occur.
    """
    main_ck = tmp_path / "main"
    main_ck.mkdir()
    (main_ck / "issues.md").write_text(_REPRO_BLOCK, encoding="utf-8")
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(main_ck)], check=True, capture_output=True
    )
    _git(main_ck, "config", "user.email", "test@test.com")
    _git(main_ck, "config", "user.name", "Test")
    _git(main_ck, "add", "-A")
    _git(main_ck, "commit", "-qm", "init")

    wt = tmp_path / "wt"
    _git(main_ck, "worktree", "add", "-q", str(wt), "-b", "issue/ISSUE-500-x")

    if write_spec:
        target = wt / spec_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# SPEC-500\n", encoding="utf-8")
        _git(wt, "add", spec_rel)
        _git(wt, "commit", "-qm", "docs(spec): SPEC-500")

    registry = main_ck / "issues.md"
    registry.write_text(
        registry.read_text(encoding="utf-8").replace("- Spec: none", f"- Spec: {spec_field}"),
        encoding="utf-8",
    )
    _git(main_ck, "add", "issues.md")
    _git(main_ck, "commit", "-qm", "chore(registry): ISSUE-500 Spec field")
    return main_ck, wt


def _gate_cli(cwd: Path) -> dict:
    """Drive the REAL consumer: the command skills/implement step 0c runs.

    Not ``decide()`` with fixtures and not ``checkout_roots()`` at its helper —
    the script, by subprocess, with the relative ``--issues-md issues.md`` the
    skill passes, from the CWD the skill is standing in. Review lesson 16: a
    repaired gate has to be exercised through its real consumer, in the
    direction that was broken.
    """
    env = dict(os.environ)
    env.pop("KIT_SPRINT_MODE", None)
    proc = subprocess.run(
        [sys.executable, str(GATE), "ISSUE-500", "--issues-md", "issues.md",
         "--force-sprint-mode"],
        cwd=str(cwd), capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"gate exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def _decide_at(checkout: Path, *, sprint: bool = True) -> dict:
    """Same configuration, driven through ``decide()`` for reason inspection."""
    registry = checkout / "issues.md"
    issue = parse_issue(registry, "ISSUE-500")
    assert issue is not None
    return decide(
        issue, registry.resolve().parent, sprint_mode=sprint, skip_gate=False,
        registry_name=registry.name,
    )


class TestSatisfiableFromBothCheckouts:
    """AC-1 — field on main, SPEC file on the branch → `proceed`, both CWDs."""

    def test_proceed_from_main_checkout_via_cli(self, tmp_path: Path):
        main_ck, _wt = _two_checkouts(tmp_path)
        assert not (main_ck / "docs/specs/SPEC-500.md").exists()
        result = _gate_cli(main_ck)
        assert result["decision"] == "proceed", result["reasons"]

    def test_proceed_from_worktree_via_cli(self, tmp_path: Path):
        _main_ck, wt = _two_checkouts(tmp_path)
        # The blocker from THIS side is the FIELD, not the path: the branch's
        # frozen registry copy still reads `none`.
        assert "- Spec: none" in (wt / "issues.md").read_text(encoding="utf-8")
        assert (wt / "docs/specs/SPEC-500.md").exists()
        result = _gate_cli(wt)
        assert result["decision"] == "proceed", result["reasons"]

    def test_reason_names_which_checkout_supplied_each_artifact(self, tmp_path: Path):
        """Counter-evidence: a cross-checkout `proceed` must not look identical
        to a co-located one, or the relaxation is invisible in the output."""
        main_ck, wt = _two_checkouts(tmp_path)
        reason = " ".join(_decide_at(wt)["reasons"])
        assert "docs/specs/SPEC-500.md" in reason
        assert str(main_ck.resolve()) in reason, reason
        assert str(wt.resolve()) in reason, reason


class TestStillRefusesWhenSpecAbsentEverywhere:
    """AC-2 — the disarm direction. The fix must not be bought by vacuity."""

    @pytest.mark.parametrize("where", ["main", "wt"])
    def test_auto_spec_when_spec_absent_from_every_checkout(self, tmp_path: Path, where: str):
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        cwd = main_ck if where == "main" else wt
        assert not (main_ck / "docs/specs/SPEC-500.md").exists()
        assert not (wt / "docs/specs/SPEC-500.md").exists()
        result = _gate_cli(cwd)
        assert result["decision"] == "auto_spec", result["reasons"]

    @pytest.mark.parametrize("where", ["main", "wt"])
    def test_deleting_the_spec_file_flips_the_decision(self, tmp_path: Path, where: str):
        """The mutation pin AC-2 names explicitly: same fixture, one artifact
        removed, decision MUST change. Without this, 'resolve against either
        root' and 'resolve against anything' are indistinguishable."""
        main_ck, wt = _two_checkouts(tmp_path)
        cwd = main_ck if where == "main" else wt
        before = _gate_cli(cwd)["decision"]
        assert before == "proceed"

        (wt / "docs/specs/SPEC-500.md").unlink()
        after = _gate_cli(cwd)["decision"]
        assert after == "auto_spec", "deleting the only SPEC left the gate satisfied"
        assert after != before

    def test_refusal_names_the_checkouts_it_consulted(self, tmp_path: Path):
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        reasons = " ".join(_decide_at(main_ck)["reasons"])
        assert "docs/specs/SPEC-500.md" in reasons
        assert str(wt.resolve()) in reasons, reasons

    def test_an_unrelated_issues_spec_does_not_satisfy_this_issue(self, tmp_path: Path):
        """The cross-checkout field read is id-scoped: another issue's SPEC on
        the branch must not stand in for this one's."""
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        other = wt / "docs" / "specs"
        other.mkdir(parents=True)
        (other / "SPEC-999.md").write_text("# SPEC-999\n", encoding="utf-8")
        assert _gate_cli(wt)["decision"] == "auto_spec"


class TestUntrustedSpecFieldUnderWidenedRoots:
    """Widening the resolution roots widens what a traversal in the untrusted
    `Spec:` value can reach, so containment is checked per root (lesson 5).
    These pin the REFUSAL, and the refusal is made visible in `reasons` so it
    cannot be mistaken for 'the SPEC is simply absent'."""

    def test_absolute_spec_path_is_refused(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        planted = outside / "SPEC-500.md"
        planted.write_text("# not a branch artifact\n", encoding="utf-8")
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False, spec_field=str(planted))
        result = _decide_at(main_ck)
        assert planted.exists()
        assert result["decision"] == "auto_spec", result["reasons"]
        assert "REFUSED" in " ".join(result["reasons"])

    def test_dotdot_traversal_is_refused(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "SPEC-500.md").write_text("# not a branch artifact\n", encoding="utf-8")
        main_ck, _wt = _two_checkouts(
            tmp_path, write_spec=False, spec_field="../outside/SPEC-500.md"
        )
        result = _decide_at(main_ck)
        assert result["decision"] == "auto_spec", result["reasons"]
        assert "REFUSED" in " ".join(result["reasons"])

    def test_symlink_leaving_the_checkout_is_refused(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        real = outside / "SPEC-500.md"
        real.write_text("# not a branch artifact\n", encoding="utf-8")
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        link_dir = wt / "docs" / "specs"
        link_dir.mkdir(parents=True)
        (link_dir / "SPEC-500.md").symlink_to(real)
        result = _decide_at(wt)
        assert result["decision"] == "auto_spec", result["reasons"]
        assert "REFUSED" in " ".join(result["reasons"])

    def test_spec_value_with_an_embedded_nul_is_refused(self, tmp_path: Path):
        """A NUL in the registry value makes pathlib raise, not return False."""
        main_ck, _wt = _two_checkouts(
            tmp_path, write_spec=False, spec_field="docs/specs/\x00SPEC.md"
        )
        result = _decide_at(main_ck)
        assert result["decision"] == "auto_spec", result["reasons"]
        assert "REFUSED" in " ".join(result["reasons"])

    def test_undecodable_sibling_registry_is_skipped_not_raised(self, tmp_path: Path):
        """Another checkout's registry copy is untrusted input: an undecodable
        one must be skipped, leaving the gate to refuse, never to crash.

        Driven from the WORKTREE, whose own field reads `none` — that is the
        only direction in which the sibling registry is read at all, so
        corrupting main's copy and deciding from main would never reach the
        handler (an earlier draft of this test did exactly that and SURVIVED
        the mutation that deletes it)."""
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        (main_ck / "issues.md").write_bytes(b"\xff\xfe not utf-8 \x80\x81")
        assert "- Spec: none" in (wt / "issues.md").read_text(encoding="utf-8")
        result = _decide_at(wt)
        assert result["decision"] == "auto_spec", result["reasons"]
        # And through the real consumer, from that same side.
        assert _gate_cli(wt)["decision"] == "auto_spec"

    def test_spec_path_naming_a_directory_is_refused(self, tmp_path: Path):
        """A `Spec:` value naming a DIRECTORY resolves and `.exists()`, which the
        pre-fix check accepted as a SPEC. Only a regular file counts."""
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False, spec_field="docs/specs")
        (main_ck / "docs" / "specs").mkdir(parents=True)
        assert (main_ck / "docs" / "specs").is_dir()
        result = _decide_at(main_ck, sprint=True)
        assert result["decision"] == "auto_spec", result["reasons"]


class TestComputedEmptyVersusCouldNotCompute:
    """'absent from every checkout I consulted' and 'I could not determine the
    checkouts to consult' are DIFFERENT outcomes and must not collapse."""

    def test_plain_directory_is_a_complete_single_root(self, tmp_path: Path):
        """A directory that is not in a repository has exactly ONE checkout —
        that is a COMPLETE enumeration, so no incompleteness may be reported."""
        roots, incomplete = checkout_roots(tmp_path)
        assert [r.resolve() for r in roots] == [tmp_path.resolve()]
        assert incomplete is None

    def test_repo_enumeration_lists_every_checkout(self, tmp_path: Path):
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        roots, incomplete = checkout_roots(main_ck)
        assert incomplete is None
        resolved = {r.resolve() for r in roots}
        assert main_ck.resolve() in resolved
        assert wt.resolve() in resolved

    def test_unavailable_git_is_reported_as_incomplete_not_as_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """With git unreachable the gate cannot know what it did not see. It
        still refuses (fail-closed), but the refusal must SAY the enumeration
        was incomplete rather than claim the SPEC is absent."""
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False)

        def _no_git(*args, **kwargs):
            raise FileNotFoundError("git")

        monkeypatch.setattr(subprocess, "run", _no_git)
        roots, incomplete = checkout_roots(main_ck)
        assert [r.resolve() for r in roots] == [main_ck.resolve()]
        assert incomplete is not None
        assert "git" in incomplete

        result = _decide_at(main_ck)
        assert result["decision"] == "auto_spec"
        assert "INCOMPLETE" in " ".join(result["reasons"]), result["reasons"]

    def test_absent_everywhere_does_not_claim_incompleteness(self, tmp_path: Path):
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False)
        reasons = " ".join(_decide_at(main_ck)["reasons"])
        assert "INCOMPLETE" not in reasons, reasons


class TestDisclosedResidual:
    """A disclosed residual is a CLAIM — measure it. The fix establishes that
    SOME checkout of this repository holds a regular file at the declared path.
    It does NOT establish that the issue's branch produced it: file existence
    is a weak attestation, not provenance (lesson 6)."""

    def test_spec_planted_in_an_unrelated_checkout_satisfies_the_gate(self, tmp_path: Path):
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False)
        stale = tmp_path / "stale"
        _git(main_ck, "worktree", "add", "-q", str(stale), "-b", "issue/ISSUE-777-unrelated")
        planted = stale / "docs" / "specs"
        planted.mkdir(parents=True)
        (planted / "SPEC-500.md").write_text("# left over\n", encoding="utf-8")

        assert _gate_cli(main_ck)["decision"] == "proceed"

    def test_an_empty_file_at_the_declared_path_satisfies_the_gate(self, tmp_path: Path):
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        (wt / "docs" / "specs").mkdir(parents=True)
        (wt / "docs" / "specs" / "SPEC-500.md").write_text("", encoding="utf-8")
        assert _gate_cli(wt)["decision"] == "proceed"


# Pre-fix full result objects, captured by executing the UNFIXED decide() on
# 2026-11-03 at ce44206. Equality against these PROVES the out-of-scope rows
# (hold / bypassed / signal detection) and the legacy co-located `proceed` are
# byte-for-byte unaffected, rather than asserting it one key at a time
# (review lesson 8: scope the relaxation, pin the legacy failure modes).
_PREFIX_RESULTS = {
    "colocated_proceed": {
        "decision": "proceed",
        "reasons": ["Spec-Required=true and SPEC exists at docs/specs/SPEC-007.md"],
        "signals": [],
        "spec_path": "docs/specs/SPEC-007.md",
        "sprint_mode": True,
        "issue_id": "ISSUE-007",
    },
    "spec_none_sprint_auto_spec": {
        "decision": "auto_spec",
        "reasons": ["Spec-Required=true, SPEC missing, sprint mode → auto-run /spec"],
        "signals": [],
        "spec_path": "none",
        "sprint_mode": True,
        "issue_id": "ISSUE-007",
    },
    "spec_empty_sprint_auto_spec": {
        "decision": "auto_spec",
        "reasons": ["Spec-Required=true, SPEC missing, sprint mode → auto-run /spec"],
        "signals": [],
        "spec_path": "",
        "sprint_mode": True,
        "issue_id": "ISSUE-007",
    },
    "spec_required_absent_nonsprint_hold": {
        "decision": "hold",
        "reasons": [
            "Spec-Required=true, SPEC missing, non-sprint mode → HOLD for user choice"
        ],
        "signals": [],
        "spec_path": "none",
        "sprint_mode": False,
        "issue_id": "ISSUE-007",
    },
    "bypassed_sprint": {
        "decision": "bypassed",
        "reasons": ["--skip-spec-gate was passed; bypassing gate"],
        "signals": [],
        "spec_path": "none",
        "sprint_mode": True,
        "issue_id": "ISSUE-007",
    },
    "bypassed_nonsprint": {
        "decision": "bypassed",
        "reasons": ["--skip-spec-gate was passed; bypassing gate"],
        "signals": [],
        "spec_path": "none",
        "sprint_mode": False,
        "issue_id": "ISSUE-007",
    },
    "signals_sprint_proceed": {
        "decision": "proceed",
        "reasons": [
            "Spec-Required=false; signals detected (API surface, schema, migration); "
            "sprint mode → log recommendation, proceed"
        ],
        "signals": [
            {
                "signal": "API surface",
                "evidence": "s-On: none  #### Goal Adds an API schema migration.  #### Scope",
            },
            {
                "signal": "schema",
                "evidence": ": none  #### Goal Adds an API schema migration.  #### Scope (In/Ou",
            },
            {
                "signal": "migration",
                "evidence": "#### Goal Adds an API schema migration.  #### Scope (In/Out) - In: s",
            },
        ],
        "spec_path": "none",
        "sprint_mode": True,
        "issue_id": "ISSUE-007",
    },
    "signals_nonsprint_hold": {
        "decision": "hold",
        "reasons": [
            "Spec-Required=false; signals detected (API surface, migration, protocol); "
            "non-sprint mode → HOLD for user choice"
        ],
        "signals": [
            {
                "signal": "API surface",
                "evidence": ": none  #### Goal Touches the API protocol and adds a migration",
            },
            {
                "signal": "migration",
                "evidence": "s the API protocol and adds a migration.  #### Scope (In/Out) - In: s",
            },
            {
                "signal": "protocol",
                "evidence": "ne  #### Goal Touches the API protocol and adds a migration.  #### S",
            },
        ],
        "spec_path": "none",
        "sprint_mode": False,
        "issue_id": "ISSUE-007",
    },
    "no_signal_nonsprint_proceed": {
        "decision": "proceed",
        "reasons": ["Spec-Required=false and no signals; proceeding silently"],
        "signals": [],
        "spec_path": "none",
        "sprint_mode": False,
        "issue_id": "ISSUE-007",
    },
}

#: (fixture key, decide kwargs, issue kwargs, SPEC basenames to create).
_PREFIX_CASES = [
    ("colocated_proceed", dict(sprint=True, skip=False),
     dict(spec_required="true", spec_path="docs/specs/SPEC-007.md"), ("SPEC-007.md",)),
    ("spec_none_sprint_auto_spec", dict(sprint=True, skip=False),
     dict(spec_required="true", spec_path="none"), ()),
    ("spec_empty_sprint_auto_spec", dict(sprint=True, skip=False),
     dict(spec_required="true", spec_path=""), ()),
    ("spec_required_absent_nonsprint_hold", dict(sprint=False, skip=False),
     dict(spec_required="true", spec_path="none"), ()),
    ("bypassed_sprint", dict(sprint=True, skip=True),
     dict(spec_required="true", spec_path="none"), ()),
    ("bypassed_nonsprint", dict(sprint=False, skip=True),
     dict(spec_required="true", spec_path="none"), ()),
    ("signals_sprint_proceed", dict(sprint=True, skip=False),
     dict(spec_required="false", spec_path="none",
          extra_body="Adds an API schema migration."), ()),
    ("signals_nonsprint_hold", dict(sprint=False, skip=False),
     dict(spec_required="false", spec_path="none",
          extra_body="Touches the API protocol and adds a migration."), ()),
    ("no_signal_nonsprint_proceed", dict(sprint=False, skip=False),
     dict(spec_required="false", spec_path="none",
          extra_body="Rename a variable."), ()),
]


class TestLegacyRowsAreByteForByteUnaffected:
    @pytest.mark.parametrize(
        "key,gate_kwargs,issue_kwargs,specs",
        _PREFIX_CASES,
        ids=[c[0] for c in _PREFIX_CASES],
    )
    def test_result_object_equals_the_prefix_capture(
        self, tmp_path: Path, key, gate_kwargs, issue_kwargs, specs
    ):
        specs_dir = tmp_path / "docs" / "specs"
        specs_dir.mkdir(parents=True)
        for name in specs:
            (specs_dir / name).write_text("# spec\n", encoding="utf-8")
        p = _write_issues(tmp_path, [_issue_block(**issue_kwargs)])
        issue = parse_issue(p, "ISSUE-007")
        assert issue is not None
        result = decide(
            issue, p.resolve().parent,
            sprint_mode=gate_kwargs["sprint"], skip_gate=gate_kwargs["skip"],
        )
        assert result == _PREFIX_RESULTS[key]


class TestLegacySpecValueSemanticsUnchanged:
    """The `Spec:` value is still ONE path, matched whole. Widening the roots
    must not start splitting or trimming real registry values: issues.md
    carries both a comma-joined pair (ISSUE-029) and values with trailing
    prose, and NEITHER resolved before this change."""

    @pytest.mark.parametrize(
        "spec_field,created",
        [
            ("docs/specs/SPEC-018.md, docs/specs/SPEC-019.md",
             ("SPEC-018.md", "SPEC-019.md")),
            ("docs/specs/SPEC-500.md (existing — no new spec)", ("SPEC-500.md",)),
        ],
    )
    def test_multi_token_spec_value_does_not_resolve(
        self, tmp_path: Path, spec_field: str, created: tuple
    ):
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False, spec_field=spec_field)
        specs = wt / "docs" / "specs"
        specs.mkdir(parents=True)
        for name in created:
            (specs / name).write_text("# spec\n", encoding="utf-8")
        assert _gate_cli(main_ck)["decision"] == "auto_spec"
        assert _gate_cli(wt)["decision"] == "auto_spec"


class TestImplementStep0cStopInstruction:
    """AC-4 — step 0c's STOP must not be reachable for a configuration the
    kit's own rules make unavoidable. Occurrence-whitelist, not a phrasing
    blacklist: the exact pre-fix sentence is pinned absent and the qualifying
    contract is pinned present, both in the generated skill and in its
    template (`skills/implement/SKILL.md` is AUTO-GENERATED)."""

    #: The pre-fix sentence, verbatim. Unconditional: any non-`proceed` re-run
    #: halts, which for every Spec-Required sprint issue meant always.
    PREFIX_SENTENCE = "If it is still not `proceed`, STOP and report."

    @pytest.mark.parametrize("name", ["SKILL.md", "SKILL.md.tmpl"])
    def test_unconditional_stop_sentence_is_gone(self, name: str):
        text = (KIT_ROOT / "skills" / "implement" / name).read_text(encoding="utf-8")
        assert self.PREFIX_SENTENCE not in text

    @pytest.mark.parametrize("name", ["SKILL.md", "SKILL.md.tmpl"])
    def test_step_0c_states_the_multi_checkout_resolution(self, name: str):
        text = (KIT_ROOT / "skills" / "implement" / name).read_text(encoding="utf-8")
        assert "every checkout of the repository" in text
        assert "`Spec:` field on main's `issues.md`, SPEC file on the branch" in text

    @pytest.mark.parametrize("name", ["SKILL.md", "SKILL.md.tmpl"])
    def test_stop_is_scoped_to_a_spec_that_was_never_produced(self, name: str):
        text = (KIT_ROOT / "skills" / "implement" / name).read_text(encoding="utf-8")
        assert "STOP and report ONLY when no checkout holds the SPEC" in text

    @pytest.mark.parametrize("name", ["SKILL.md", "SKILL.md.tmpl"])
    def test_incomplete_enumeration_is_not_reported_as_a_missing_spec(self, name: str):
        text = (KIT_ROOT / "skills" / "implement" / name).read_text(encoding="utf-8")
        assert "INCOMPLETE" in text
