"""Unit tests for scripts/spec_gate.py — covers every row of the decision table."""

import errno
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.spec_gate import (
    INCOMPLETE_MARKER,
    MARKER_REDACTION,
    PRESENCE_ONLY_NOTICE,
    checkout_roots,
    decide,
    main,
    parse_issue,
    scan_signals,
)
from scripts.validate_spec import parse_spec, validate

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

#: A second, UNRELATED issue block, written BEFORE `_REPRO_BLOCK` in every
#: registry copy the fixture builds. Its `Spec:` value is therefore the FIRST
#: `- Spec:` line in the file, so a sibling-registry read that is not id-scoped
#: selects THIS one — which is the only way the id-scoping claim is exercised
#: at all. With the single-block registry this replaces, "first `- Spec:` in
#: the file" and "ISSUE-500's `Spec:`" were the same string and the mutant that
#: drops id-scoping entirely survived. The value must not be `none`, or the
#: fixture's own `- Spec: none` substitution would rewrite it too.
_DECOY_BLOCK = """### ISSUE-499: Unrelated issue that already produced its SPEC
- Track: platform
- PRD-Ref: none
- Priority: P2
- Estimate: 1d
- Status: done
- Spec-Required: true
- Spec: docs/specs/SPEC-499.md
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Occupy the registry's first `- Spec:` line.
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

    The registry carries `_DECOY_BLOCK` ahead of ISSUE-500 so that every read
    of it has something to mis-select.
    """
    main_ck = tmp_path / "main"
    main_ck.mkdir()
    (main_ck / "issues.md").write_text(
        f"{_DECOY_BLOCK}\n{_REPRO_BLOCK}", encoding="utf-8"
    )
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
    # --allow-empty so the fixture can express `spec_field="none"` — the
    # configuration in which NO checkout declares a SPEC, which is the only one
    # that probes every root's registry copy (the site-D path below). Without
    # it the substitution is a no-op and `git commit` exits 1 on nothing staged.
    _git(main_ck, "commit", "-q", "--allow-empty", "-m",
         "chore(registry): ISSUE-500 Spec field")
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

    def test_sibling_field_read_selects_this_issues_block_not_the_first(
        self, tmp_path: Path
    ):
        """The sibling registry's FIELD read is id-scoped — the test above
        plants another issue's SPEC *file*, which is a different guard.

        The registry holds two issue blocks and the decoy's `Spec:` is the
        first `- Spec:` line in it, so a read that takes the first line instead
        of this issue's selects `SPEC-499.md`, which EXISTS on the branch, and
        the gate flips to `proceed` on an unrelated issue's SPEC. Driven from
        the WORKTREE because that is the only side whose own field reads
        `none`, and therefore the only side that reads a sibling copy at all
        (the M11 lesson, generalised to this guard)."""
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        decoy_spec = wt / "docs" / "specs" / "SPEC-499.md"
        decoy_spec.parent.mkdir(parents=True)
        decoy_spec.write_text("# SPEC-499\n", encoding="utf-8")

        # PREMISE: the decoy's field really does precede this issue's in the
        # copy that gets read, its file really is present, and this issue's
        # SPEC really is absent — otherwise a mis-scoped read has nothing to
        # select and the assertions below hold vacuously.
        sibling = (main_ck / "issues.md").read_text(encoding="utf-8")
        assert sibling.index("- Spec: docs/specs/SPEC-499.md") < sibling.index(
            "- Spec: docs/specs/SPEC-500.md"
        )
        assert "- Spec: none" in (wt / "issues.md").read_text(encoding="utf-8")
        assert decoy_spec.is_file()
        assert not (wt / "docs" / "specs" / "SPEC-500.md").exists()

        result = _decide_at(wt)
        assert result["decision"] == "auto_spec", result["reasons"]
        reasons = " ".join(result["reasons"])
        assert "SPEC-500" in reasons, reasons
        assert "SPEC-499" not in reasons, reasons
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


class TestUnstattableRootIsRefusedNotFatal:
    """A root the widened enumeration merely LISTED must not be able to kill
    the gate when it is statted.

    ``Path.is_file()`` RAISES for EACCES and ENAMETOOLONG — pathlib's
    ``_ignore_error`` ignores only the not-found class (ENOENT/ENOTDIR/ELOOP)
    — while non-strict ``resolve()`` raises on neither, which is why the stat
    is the reachable half. So the stat belongs inside the same guard as the
    resolution: an unstattable root is REFUSED, named as such in ``reasons``,
    and the next checkout is tried.

    Disarm direction, through the real consumer: both tests drive the step-0c
    CLI by subprocess, so removing the guard makes the process exit non-zero
    and ``_gate_cli``'s exit-code assertion fails.
    """

    @staticmethod
    def _premise_the_stat_raises(target: Path, expected_errno: int) -> None:
        """PREMISE assertion — the kernel must really hand this code the
        raiser, and the resolution must really not pre-empt it.

        Without this the probe passes vacuously: with ``docs/specs/`` absent
        the kernel answers ENOENT first, pathlib ignores it and ``is_file()``
        returns ``False`` (measured — the reviewer's PROBE N did exactly that
        before PROBE N4 reached the code).
        """
        with pytest.raises(OSError) as exc:
            target.is_file()
        assert exc.value.errno == expected_errno, exc.value
        target.resolve()  # must NOT raise, or the stat is never reached

    def test_unreadable_sibling_checkout_is_refused_not_fatal(self, tmp_path: Path):
        """EACCES. The CWD's checkout has no ``docs/`` at all; the SIBLING
        holds the declared path under a mode-000 ``docs/specs``. On
        ``origin/main`` this configuration exits 0 with ``auto_spec`` — only
        the widened enumeration reaches the sibling's stat."""
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        specs = wt / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-500.md").write_text("# SPEC-500\n", encoding="utf-8")
        assert not (main_ck / "docs").exists()

        os.chmod(specs, 0o000)
        try:
            self._premise_the_stat_raises(specs / "SPEC-500.md", errno.EACCES)
            result = _gate_cli(main_ck)
        finally:
            os.chmod(specs, 0o700)  # leave the tree readable/removable

        assert result["decision"] == "auto_spec", result["reasons"]
        reasons = " ".join(result["reasons"])
        # "could not determine for this root" is not "the SPEC is absent": the
        # refused root has to be named.
        assert "REFUSED" in reasons, reasons
        assert str(wt.resolve()) in reasons, reasons

    def test_overlong_spec_value_is_refused_not_fatal(self, tmp_path: Path):
        """ENAMETOOLONG — the class PROBE N4 hit with a real 544-byte `Spec:`
        value from this repo's own registry. ``docs/specs/`` is created in BOTH
        checkouts because the parent must exist, or the kernel returns ENOENT
        first and the probe gives a false all-clear."""
        overlong = "docs/specs/" + "L" * 300 + ".md"
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False, spec_field=overlong)
        for root in (main_ck, wt):
            (root / "docs" / "specs").mkdir(parents=True)
        self._premise_the_stat_raises(main_ck / overlong, errno.ENAMETOOLONG)

        result = _gate_cli(main_ck)
        assert result["decision"] == "auto_spec", result["reasons"]
        assert "REFUSED" in " ".join(result["reasons"]), result["reasons"]

    def test_a_refused_root_does_not_end_the_enumeration(self, tmp_path: Path):
        """The refusal must SKIP that checkout, not terminate the lookup.

        The reviewer's PROBE O configuration: the CWD's own checkout has an
        unreadable `docs/specs` — holding a file at the declared path that
        cannot be statted — while ANOTHER checkout holds the SPEC readably, so
        the correct answer is `proceed`. Refusing and stopping would report
        `auto_spec` for a SPEC that exists."""
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        readable = main_ck / "docs" / "specs"
        readable.mkdir(parents=True)
        (readable / "SPEC-500.md").write_text("# SPEC-500\n", encoding="utf-8")
        unreadable = wt / "docs" / "specs"
        unreadable.mkdir(parents=True)
        (unreadable / "SPEC-500.md").write_text("# unstattable\n", encoding="utf-8")

        os.chmod(unreadable, 0o000)
        try:
            self._premise_the_stat_raises(unreadable / "SPEC-500.md", errno.EACCES)
            # Driven from the unreadable checkout, which is always roots[0].
            result = _gate_cli(wt)
        finally:
            os.chmod(unreadable, 0o700)

        assert result["decision"] == "proceed", result["reasons"]
        assert str(main_ck.resolve()) in " ".join(result["reasons"]), result["reasons"]


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
# (hold / bypassed / signal detection) are byte-for-byte unaffected, rather
# than asserting it one key at a time (review lesson 8: scope the relaxation,
# pin the legacy failure modes).
#
# `colocated_proceed` is the ONE row this rework moves, deliberately and in two
# ways: the untrusted value is now `!r`-quoted, and `PRESENCE_ONLY_NOTICE` is
# appended as a second element (SPEC-102 D1 — the gate must stop claiming more
# than it checked). That is safe to re-capture because the pin being updated is
# THIS PR's own: `git show origin/main:tests/test_spec_gate.py | grep 'SPEC
# exists at'` returns nothing, so no pin inherited from main is being relaxed.
# Every other row below is untouched, and the notice is scoped to this single
# branch — the signal and no-signal `proceed` rows assert no SPEC and carry no
# bound.
_PREFIX_RESULTS = {
    "colocated_proceed": {
        "decision": "proceed",
        "reasons": [
            "Spec-Required=true and SPEC exists at 'docs/specs/SPEC-007.md'",
            PRESENCE_ONLY_NOTICE,
        ],
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


# ===========================================================================
# ISSUE-102 rework — one defect CLASS at four I/O sites, closed as a class.
#
# Every site below is an OVER-REFUSAL: an uncaught exception escapes, the
# process dies with a traceback at exit 1, and exit 1 is outside the module's
# own documented `{0, 2}` contract (scripts/spec_gate.py docstring, "Exit
# code"). Step 0c has no branch for a traceback, so each one WEDGES
# `/implement` for a legitimate repository — the gate stops deciding instead of
# deciding to refuse. Three of the four are strict regressions this PR
# introduced: the merge-base `ce44206` exits 0 on identical input.
#
# Every test drives the REAL consumer — `python3 scripts/spec_gate.py
# <ISSUE-ID>`, the command step 0c runs — and pins the exit code itself, not
# just the decision (review lesson 16: a newly added defence must be tested in
# the DISARM direction and through its real consumer). Each carries a PREMISE
# assertion that the kernel genuinely hands the code the raiser, because with
# the parent directory absent the kernel answers ENOENT first, pathlib ignores
# it, and the probe passes vacuously.
# ===========================================================================

#: The module's own documented exit contract. A traceback at exit 1 is the
#: pre-fix failure signature and is outside it.
DOCUMENTED_EXIT_CODES = (0, 2)


def _gate_cli_raw(
    cwd: Path, *, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    """Drive the step-0c CLI and return the RAW process, exit code included.

    ``_gate_cli`` asserts ``returncode == 0`` and parses stdout, which is the
    right shape for a decision test and the wrong one here: these tests exist
    to pin the exit code, so they must be able to SEE a non-zero one.
    """
    env = dict(os.environ)
    env.pop("KIT_SPRINT_MODE", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(GATE), "ISSUE-500", "--issues-md", "issues.md",
         "--force-sprint-mode"],
        cwd=str(cwd), capture_output=True, text=True, env=env,
    )


def _assert_decided_within_contract(
    proc: subprocess.CompletedProcess, expected_decision: str
) -> dict:
    """The gate must DECIDE, inside its documented exit contract."""
    assert proc.returncode in DOCUMENTED_EXIT_CODES, (
        f"gate exited {proc.returncode}, outside its documented "
        f"{DOCUMENTED_EXIT_CODES} contract — step 0c has no branch for this "
        f"and /implement wedges:\n{proc.stderr}"
    )
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["decision"] == expected_decision, out["reasons"]
    return out


def _colocated_checkout(tmp_path: Path, *, write_spec: bool = True) -> Path:
    """A LEGACY co-located configuration: one plain directory, no repository.

    ``issues.md`` and the SPEC sit side by side, which is the pre-ISSUE-102
    caller class AC-3 pins. Site A is measured here deliberately:
    ``spec_lookup`` calls ``checkout_roots`` UNCONDITIONALLY before it ever
    tries the read registry's own root, so an unusable ``git`` regresses
    exactly this class (review lesson 8).
    """
    d = tmp_path / "legacy"
    d.mkdir()
    (d / "issues.md").write_text(
        _REPRO_BLOCK.replace("- Spec: none", "- Spec: docs/specs/SPEC-500.md"),
        encoding="utf-8",
    )
    if write_spec:
        specs = d / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-500.md").write_text("# SPEC-500\n", encoding="utf-8")
    return d


def _only_git_on_path(tmp_path: Path, flavour: str) -> dict:
    """A PATH whose ONLY ``git`` is present but unusable.

    Prepending the shim to a healthy PATH proves nothing: ``execvp`` skips a
    non-executable entry and falls through to the real ``git``, so both
    versions exit 0 and the probe gives a false all-clear. The shim has to be
    the only candidate on PATH.
    """
    bindir = tmp_path / f"bin-{flavour}"
    bindir.mkdir()
    shim = bindir / "git"
    if flavour == "not-executable":
        shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(shim, 0o644)
    elif flavour == "directory":
        shim.mkdir()
    else:  # "not-an-executable-format"
        shim.write_bytes(b"\x00\x01\x02\x03not an executable")
        os.chmod(shim, 0o755)
    return {"PATH": str(bindir)}


class TestPresentButUnusableGitIsNotFatal:
    """SITE A — ``_git``'s except tuple was ``(FileNotFoundError,
    TimeoutExpired)``, which covers only the ENOENT flavour of an exec failure.

    A ``git`` that is present but unusable raises ``PermissionError`` (EACCES)
    or a bare ``OSError`` (ENOEXEC) instead, and both escaped. The fix widens
    to ``OSError``, which SUBSUMES both rather than enumerating them — an
    enumeration is what was short by one here in the first place.
    """

    @pytest.mark.parametrize(
        "flavour,expected_errno",
        [
            ("not-executable", errno.EACCES),
            ("directory", errno.EACCES),
            ("not-an-executable-format", errno.ENOEXEC),
        ],
    )
    def test_unusable_git_degrades_to_a_decision(
        self, tmp_path: Path, flavour: str, expected_errno: int
    ):
        legacy = _colocated_checkout(tmp_path)
        env_extra = _only_git_on_path(tmp_path, flavour)

        # PREMISE: the kernel really raises, and really raises something the
        # pre-fix tuple did NOT name — otherwise this passes vacuously.
        with pytest.raises(OSError) as exc:
            subprocess.run(["git", "--version"], capture_output=True,
                           env={"PATH": env_extra["PATH"]})
        assert exc.value.errno == expected_errno, exc.value
        assert not isinstance(exc.value, FileNotFoundError), (
            "premise changed: this flavour now raises the one class the "
            "pre-fix tuple already caught, so it cannot evidence the fix"
        )

        out = _assert_decided_within_contract(
            _gate_cli_raw(legacy, env_extra=env_extra), "proceed"
        )
        # The legacy co-located reason, byte-for-byte: an unusable git must not
        # change WHAT this caller class is told, only that it is told anything.
        assert out["reasons"][0] == (
            "Spec-Required=true and SPEC exists at 'docs/specs/SPEC-500.md'"
        ), out["reasons"]

    def test_absent_git_still_degrades(self, tmp_path: Path):
        """The ENOENT control: handled before the fix, must stay handled."""
        legacy = _colocated_checkout(tmp_path)
        empty = tmp_path / "empty-path"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            subprocess.run(["git", "--version"], capture_output=True,
                           env={"PATH": str(empty)})
        _assert_decided_within_contract(
            _gate_cli_raw(legacy, env_extra={"PATH": str(empty)}), "proceed"
        )


class TestListedRootThatCannotBeStattedIsSkipped:
    """SITE B — ``checkout_roots``' ``candidate.is_dir()`` sat in NO guard.

    ``git worktree list`` still PRINTS the ``worktree <path>`` record for a
    checkout whose parent directory was later made non-searchable, the parser
    accepts it, and the stat then raises EACCES.

    The fix SKIPS such a path, exactly as it already skips a non-directory. It
    deliberately does NOT mark the enumeration INCOMPLETE: that would add a
    refusal, and the whole point of this rework is that no change may add one.
    The resulting silent gap is declared in SPEC-102 D2 instead — an ``absent``
    verdict is not a proof of absence even when the enumeration is COMPLETE.
    """

    def test_unstattable_listed_worktree_is_skipped_not_fatal(self, tmp_path: Path):
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False)
        holder = tmp_path / "holder"
        holder.mkdir()
        inner = holder / "wt2"
        _git(main_ck, "worktree", "add", "-q", str(inner), "-b", "issue/ISSUE-600-y")

        os.chmod(holder, 0o000)  # non-searchable parent → is_dir() raises
        try:
            # PREMISE: git still lists it, and the stat on it really raises.
            listed = subprocess.run(
                ["git", "-C", str(main_ck), "worktree", "list", "--porcelain"],
                capture_output=True, text=True, check=True,
            )
            assert str(inner) in listed.stdout, listed.stdout
            with pytest.raises(OSError) as exc:
                inner.is_dir()
            assert exc.value.errno == errno.EACCES, exc.value

            out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "auto_spec")
        finally:
            os.chmod(holder, 0o700)

        # D2, pinned: the skip is SILENT by decision, not by accident.
        assert INCOMPLETE_MARKER not in " ".join(out["reasons"]), out["reasons"]


class TestSymlinkLoopInAnEnumeratedRootIsRefusedNotFatal:
    """SITE C — non-strict ``Path.resolve()`` raises ``RuntimeError`` on a
    symlink loop (ELOOP), and ``RuntimeError`` is not an ``OSError``, so
    ``_contain``'s ``(OSError, ValueError)`` tuple did not catch it.

    ``_contain``'s docstring was accurate about EACCES and ENAMETOOLONG and
    SILENT about ELOOP, which is why the tuple looked complete and was not.

    Measured on this repo's supported interpreters rather than assumed:
    3.11.13 → ``RuntimeError``, 3.12.7 → ``RuntimeError`` (both CI versions,
    both escaping the pre-fix tuple), 3.13.6 → does not raise at all. On an
    interpreter that does not raise there is genuinely nothing to disarm, so
    the test SKIPS loudly rather than passing hollowly.
    """

    def test_eloop_in_a_sibling_checkout_is_refused(self, tmp_path: Path):
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        specs = wt / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "SPEC-500.md").symlink_to("SPEC-500.md")  # self-referential

        # PREMISE: the read root is clean, so the loop is reachable ONLY via
        # the enumeration this PR widened (the single-root case crashes on both
        # versions and would not evidence anything).
        assert not (main_ck / "docs").exists()
        try:
            (specs / "SPEC-500.md").resolve()
        except BaseException as exc:  # noqa: BLE001 — the class IS the premise
            assert not isinstance(exc, (OSError, ValueError)), (
                f"premise changed: resolve() now raises {type(exc).__name__}, "
                "which the pre-fix tuple already caught"
            )
        else:
            pytest.skip(
                "non-strict resolve() does not raise on ELOOP on this "
                "interpreter (measured: 3.13.6); no refusal to disarm"
            )

        out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "auto_spec")
        reasons = " ".join(out["reasons"])
        # A root this gate could not look inside is REFUSED, and the reasons
        # already keep that apart from "the SPEC is simply absent".
        assert "REFUSED" in reasons, reasons
        assert str(wt.resolve()) in reasons, reasons


class TestUnreadableSiblingCheckoutIsSkippedNotFatal:
    """SITE D — ``_spec_field_from_other_checkout``'s ``candidate.is_file()``
    sat one line ABOVE the ``try`` that exists to make a bad sibling registry
    non-fatal.

    This is the identical defect the previous rework was dispatched to fix, at
    a second site, on the gate's PRIMARY ``auto_spec`` path: when no checkout
    declares a SPEC, every root's registry copy is probed. Note the
    inconsistency it produced — an unreadable sibling registry FILE was a
    deliberate silent skip while an unreadable sibling registry DIRECTORY
    killed the pipeline, the two differing only in which side of the ``try``
    the stat landed on.
    """

    def test_unreadable_sibling_checkout_directory_is_skipped(self, tmp_path: Path):
        # `spec_field="none"` → NO checkout declares a SPEC, which is the only
        # configuration that probes every root's registry.
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False, spec_field="none")
        assert "- Spec: none" in (main_ck / "issues.md").read_text(encoding="utf-8")

        os.chmod(wt, 0o000)
        try:
            # PREMISE: the stat on the sibling's registry really raises.
            with pytest.raises(OSError) as exc:
                (wt / "issues.md").is_file()
            assert exc.value.errno == errno.EACCES, exc.value

            out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "auto_spec")
            # BOTH call sites: the in-process API raised identically pre-fix.
            api = _decide_at(main_ck)
        finally:
            os.chmod(wt, 0o700)

        assert api["decision"] == "auto_spec", api["reasons"]
        # No checkout declares a SPEC → the pre-ISSUE-102 string, unchanged.
        assert out["reasons"] == [
            "Spec-Required=true, SPEC missing, sprint mode → auto-run /spec"
        ], out["reasons"]

    def test_a_fifo_sibling_registry_is_skipped_rather_than_blocking_forever(
        self, tmp_path: Path
    ):
        """The guard must stay a REGULAR-FILE check, not be replaced by the
        handler alone.

        This PR's own Over-Engineering note recommended deleting
        ``if not candidate.is_file(): continue`` as redundant with the adjacent
        ``except OSError``, citing a surviving mutant. It is not redundant:
        ``except OSError`` does not cover a non-regular file that OPENS
        SUCCESSFULLY. Nothing bounds ``parse_issue`` — ``GIT_QUERY_TIMEOUT``
        covers only ``_git`` — so on a FIFO the read blocks forever.

        Measured both ways before this test was written: as shipped, rc 0 with
        ``auto_spec``; with the guard deleted, the process HUNG until killed.
        The ``timeout`` below is what turns that hang into a test failure
        instead of a hung suite.
        """
        main_ck, wt = _two_checkouts(tmp_path, write_spec=False, spec_field="none")
        sibling_registry = wt / "issues.md"
        sibling_registry.unlink()
        try:
            os.mkfifo(sibling_registry)
        except (AttributeError, OSError) as exc:  # pragma: no cover
            pytest.skip(f"os.mkfifo unavailable here: {exc}")

        # PREMISE: it really is a non-regular file that really does open.
        assert not sibling_registry.is_file()
        assert sibling_registry.exists()

        env = dict(os.environ)
        env.pop("KIT_SPRINT_MODE", None)
        proc = subprocess.run(
            [sys.executable, str(GATE), "ISSUE-500", "--issues-md", "issues.md",
             "--force-sprint-mode"],
            cwd=str(main_ck), capture_output=True, text=True, env=env, timeout=30,
        )
        _assert_decided_within_contract(proc, "auto_spec")


class TestForgedIncompleteMarkerCannotSynthesiseTheControlSignal:
    """``INCOMPLETE_MARKER`` is a CONTROL SIGNAL that step 0c substring-matches
    in ``reasons``, and the ``Spec:`` value it is interpolated next to is
    untrusted markdown-registry input (review lesson 5).

    The harmful direction, demonstrated rather than asserted: step 0c reads the
    marker ONLY on the non-``proceed`` branch, so a forged marker on a
    ``proceed`` is inert. But a ``Spec:`` value carrying the marker **with the
    SPEC genuinely absent** forges it into the ABSENT reason, and step 0c then
    reports an "unresolved environment problem" and is instructed **not to
    re-run `/spec`** — a genuinely missing SPEC misrouted, the pipeline halted
    while refusing the very remedy it demands.

    ``!r``-quoting does NOT close this. Measured: ``repr()`` escapes quotes,
    backslashes and non-printables, not plain substrings, so a quoted marker is
    still a marker to a substring grep. The neutralisation is what closes it.
    """

    #: A `Spec:` value that embeds the control marker step 0c greps for.
    FORGED = f"docs/{INCOMPLETE_MARKER} (git could not be run) SPEC.md"

    def test_a_forged_value_does_not_synthesise_the_marker(self, tmp_path: Path):
        """git healthy, 2 checkouts enumerated COMPLETE, SPEC genuinely absent.
        The decision is already right and must stay right; what must not happen
        is the marker reaching ``reasons``."""
        main_ck, wt = _two_checkouts(
            tmp_path, write_spec=False, spec_field=self.FORGED
        )
        # PREMISE: the enumeration really is COMPLETE and really saw both
        # checkouts, so any marker in `reasons` could only be the forged one.
        listed = subprocess.run(
            ["git", "-C", str(main_ck), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        assert listed.stdout.count("worktree ") == 2, listed.stdout

        out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "auto_spec")
        reasons = " ".join(out["reasons"])
        # PREMISE: the value really did reach the reasons, or the assertion
        # below holds for the wrong reason.
        assert MARKER_REDACTION in reasons, reasons
        assert INCOMPLETE_MARKER not in reasons, reasons

    def test_redaction_is_display_only_and_never_moves_a_decision(
        self, tmp_path: Path
    ):
        """The neutralisation renders a value safe to PRINT. It must not touch
        the value used to RESOLVE the path, or redacting would silently change
        which file the gate looks for — a defence that breaks the thing it
        guards.

        Same forged value, but the SPEC genuinely EXISTS at exactly that path.
        The decision must still be ``proceed``: redacting ``declared`` as well
        as the reason rendering would make the lookup miss its own file.

        This also covers the ``proceed`` side of the channel. A forged marker
        here is INERT — step 0c reads the marker only on the non-``proceed``
        branch — but the single derivation means the present reason inherits
        the neutralisation anyway, and nothing should quietly re-introduce a
        bare interpolation at that one site.
        """
        main_ck, wt = _two_checkouts(
            tmp_path, write_spec=False, spec_field=self.FORGED
        )
        target = wt / self.FORGED
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# SPEC-500\n", encoding="utf-8")
        # PREMISE: the file really is at the forged path, so a redacted lookup
        # would genuinely miss it.
        assert target.is_file()

        out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "proceed")
        reasons = " ".join(out["reasons"])
        assert MARKER_REDACTION in reasons, reasons
        assert INCOMPLETE_MARKER not in reasons, reasons

    def test_the_legacy_present_reason_also_inherits_the_neutralisation(
        self, tmp_path: Path
    ):
        """The co-located branch renders a DIFFERENT string from the
        cross-checkout one, so it needs its own row or the single-derivation
        claim rests on one of the two paths.

        This is the branch whose bytes are closest to the pre-ISSUE-102 string,
        which makes it the most likely place for someone to restore a bare
        interpolation while "keeping the legacy reason".
        """
        legacy = _colocated_checkout(tmp_path, write_spec=False)
        (legacy / "issues.md").write_text(
            _REPRO_BLOCK.replace("- Spec: none", f"- Spec: {self.FORGED}"),
            encoding="utf-8",
        )
        target = legacy / self.FORGED
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# SPEC-500\n", encoding="utf-8")
        assert target.is_file()

        out = _assert_decided_within_contract(_gate_cli_raw(legacy), "proceed")
        reasons = " ".join(out["reasons"])
        # PREMISE: this really is the LEGACY branch — the co-located string has
        # no "checkout(s) consulted" tail.
        assert "checkout(s) consulted" not in out["reasons"][0], out["reasons"]
        assert MARKER_REDACTION in reasons, reasons
        assert INCOMPLETE_MARKER not in reasons, reasons

    def test_a_genuine_incomplete_enumeration_still_emits_the_marker(
        self, tmp_path: Path
    ):
        """The other direction: neutralising the forgery must not cost the real
        signal. Without this the channel could be 'closed' by deleting it."""
        main_ck, _wt = _two_checkouts(tmp_path, write_spec=False)
        empty = tmp_path / "no-git"
        empty.mkdir()
        out = _assert_decided_within_contract(
            _gate_cli_raw(main_ck, env_extra={"PATH": str(empty)}), "auto_spec"
        )
        assert INCOMPLETE_MARKER in " ".join(out["reasons"]), out["reasons"]

    def test_neutralisation_runs_upstream_of_the_genuine_append(self, tmp_path: Path):
        """ORDERING PIN — review lesson 12's shape: a gate call site must stay
        downstream of every step that mutates the surface it gates, and
        POSITION must be pinned, not just presence.

        Here it is the mirror image: the neutralisation must stay UPSTREAM of
        the ``if lookup["incomplete"]:`` append that emits the genuine marker.
        Both halves are live in this single run — the value carries a forged
        marker AND the enumeration genuinely failed — so a neutralisation
        relocated BELOW the append would strip the genuine signal and leave
        zero markers, which is what the count below fails on.
        """
        main_ck, _wt = _two_checkouts(
            tmp_path, write_spec=False, spec_field=self.FORGED
        )
        empty = tmp_path / "no-git"
        empty.mkdir()
        out = _assert_decided_within_contract(
            _gate_cli_raw(main_ck, env_extra={"PATH": str(empty)}), "auto_spec"
        )
        reasons = out["reasons"]
        joined = " ".join(reasons)

        # PREMISE: both halves really are live in this one run.
        assert MARKER_REDACTION in joined, reasons
        value_lines = [r for r in reasons if MARKER_REDACTION in r]
        marker_lines = [r for r in reasons if INCOMPLETE_MARKER in r]
        assert value_lines, reasons

        # Exactly one marker, and it is the GENUINE one. A whole-list
        # neutralisation placed after the append yields 0 here; a missing
        # neutralisation yields 2 (one forged, one genuine).
        assert joined.count(INCOMPLETE_MARKER) == 1, reasons
        assert len(marker_lines) == 1, reasons
        assert marker_lines[0] not in value_lines, reasons


class TestProceedDisclosesItsOwnBound:
    """SPEC-102 D1 — ``proceed`` means *a regular file exists at the declared
    relative path inside the containment boundary of some enumerated
    checkout*. It does NOT mean the file is a valid SPEC: this gate never
    invokes ``validate_spec.py``, so an empty file satisfies it.

    A gate that overstates itself manufactures false assurance, which is worse
    than a gate that admits a gap — so the bound is in the gate's own output,
    not only in the SPEC.
    """

    def test_proceed_carries_the_presence_only_bound(self, tmp_path: Path):
        main_ck, _wt = _two_checkouts(tmp_path)
        out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "proceed")
        assert PRESENCE_ONLY_NOTICE in out["reasons"], out["reasons"]
        assert "docs/specs/SPEC-102.md" in PRESENCE_ONLY_NOTICE

    def test_the_bound_is_additive_not_folded_into_the_existing_reason(
        self, tmp_path: Path
    ):
        """Review lesson 8: the standing line is its OWN element, so every
        pre-existing reason string stays byte-identical and the co-located
        caller class keeps its pinned contract."""
        main_ck, _wt = _two_checkouts(tmp_path)
        out = _assert_decided_within_contract(_gate_cli_raw(main_ck), "proceed")
        assert len(out["reasons"]) == 2, out["reasons"]
        assert out["reasons"][-1] == PRESENCE_ONLY_NOTICE
        assert PRESENCE_ONLY_NOTICE not in out["reasons"][0]

    def test_an_empty_file_proceeds_and_says_contents_were_not_validated(
        self, tmp_path: Path
    ):
        """D1 made concrete: a zero-byte file satisfies the gate — and the gate
        now SAYS that is all it checked."""
        _main_ck, wt = _two_checkouts(tmp_path, write_spec=False)
        (wt / "docs" / "specs").mkdir(parents=True)
        target = wt / "docs" / "specs" / "SPEC-500.md"
        target.write_text("", encoding="utf-8")
        assert target.stat().st_size == 0
        out = _assert_decided_within_contract(_gate_cli_raw(wt), "proceed")
        assert PRESENCE_ONLY_NOTICE in out["reasons"], out["reasons"]

    def test_the_non_spec_proceed_paths_do_not_claim_a_bound_they_never_checked(
        self, tmp_path: Path
    ):
        """The notice belongs ONLY to the branch that asserts a SPEC exists.
        The signal and no-signal ``proceed`` rows make no SPEC claim, and
        ``_PREFIX_RESULTS`` pins them byte-for-byte."""
        p = _write_issues(
            tmp_path, [_issue_block(spec_required="false", spec_path="none")]
        )
        issue = parse_issue(p, "ISSUE-007")
        assert issue is not None
        result = decide(issue, p.resolve().parent, sprint_mode=True, skip_gate=False)
        assert result["decision"] == "proceed"
        assert PRESENCE_ONLY_NOTICE not in result["reasons"]


class TestSpec102IsACommittedValidDecision:
    """The gate's own standing reason CITES ``docs/specs/SPEC-102.md``, which
    makes the path a live cross-file contract rather than a doc reference: it
    has to exist and it has to be a structurally valid SPEC.

    CI does not cover this. ``.github/workflows/ci.yml`` runs
    ``validate_spec.py docs/specs/`` without ``--strict``, and
    ``validate_spec.py``'s ``main()`` ends with ``return 1 if args.strict or
    target.is_file() else 0`` — so a DIRECTORY target exits 0 even with
    violations (measured, and already recorded in SPEC-088's own contract
    tests).
    """

    SPEC = KIT_ROOT / "docs" / "specs" / "SPEC-102.md"

    def test_the_cited_spec_exists_and_passes_the_real_validator(self):
        assert self.SPEC.is_file(), f"the gate cites a path that does not exist: {self.SPEC}"
        text = self.SPEC.read_text(encoding="utf-8")
        assert validate(parse_spec(text), str(self.SPEC)) == []

    def test_a_decisionless_spec_102_is_refused(self):
        """Disarm: the arm assertion above must not be a hollow pass. ISSUE-102
        reached this rework by DECLINING two properties, so the Decision
        section is the deliverable — a SPEC-102 without one must not validate.
        """
        text = self.SPEC.read_text(encoding="utf-8")
        start = text.index("\n## Decision\n") + 1
        nxt = text.find("\n## ", start + 1)
        mutated = text[:start] + (text[nxt + 1:] if nxt != -1 else "")
        assert "\n## Decision\n" not in mutated, "mutation did not apply"
        errors = validate(parse_spec(mutated), str(self.SPEC))
        assert any("`## Decision` is missing or empty" in e for e in errors), errors
