"""ISSUE-103 — the implement/red checkpoint must be scoped to the branch's own tests.

`verify_implement_red` has deliberately inverted logic: a non-zero test-run exit
is the expected ("RED") outcome. Before this contract it ran the WHOLE worktree
suite, so **any** pre-existing unrelated failure certified the TDD RED phase even
when the branch's new tests passed — a control whose defeated output was
byte-identical to its healthy output.

**Unit of attribution: the changed test FILE.** The scoping input is the one the
verifier already computes for its file-existence and hollow-assertion checks
(`_existing(wt_path, _changed_files_vs_base(wt_path, base))`) — no second oracle
is derived here. The failure modes this unit accepts are listed in
`verify_checkpoint._failed_test_files`' docstring and in the PR body.

**Added contract: attribution is REQUIRED for a pytest RED pass (F1).** No
ISSUE-103 AC named this surface and that is where the review found the defect
(review lesson 14), so the criteria are stated here and each has its own test:

* ``F1-a`` pytest exits non-zero and at least one SCOPED file is blamed → PASS,
  naming the file. (``TestRedScopeRealConsumer::test_arm_*``)
* ``F1-b`` pytest exits non-zero and the blamed files are all OUTSIDE the
  branch's delta → **refuse as inconclusive**, naming the scope *and* the
  out-of-scope files. Measured route: the project's own ``addopts`` inject an
  extra test path, so the scoped run collects unrelated files and an unrelated
  failure certifies RED — the ISSUE-103 defect itself.
  (``TestRedAttributionRequired::test_blamed_only_outside_the_delta_*``)
* ``F1-c`` pytest exits non-zero and NOTHING is blamed → **refuse as
  inconclusive**, naming the scope. Measured routes: a ``--cov-fail-under``
  threshold in the project's ``addopts`` (exit 1 with ``1 passed`` and zero test
  failures), and pytest not installed (exit 1 having run nothing).
  (``TestRedAttributionRequired::test_nothing_blamed_*``)
* ``F1-d`` the tightening is **scoped to pytest** (review lesson 8). The npm
  branch has no attribution parser at all, so requiring attribution there would
  refuse every JS RED; npm keeps its legacy "non-zero is RED" contract, the
  rendered line says attribution was unavailable, and the hazard note states the
  residual. (``TestRedAttributionRequired::test_js_keeps_its_legacy_*``)

**The failure mode F1-b/F1-c accept**, stated rather than implied: if a runner
reports nodeids under a prefix that does not match the paths the verifier passed
in, a genuine RED is refused as inconclusive. Measured on both pytest versions
the parser was built against (8.3.4 and 9.0.3): with the verifier's call shape
(``cwd`` = the worktree root, relative scope paths) nodeids come back relative to
the INVOCATION dir, not to ``rootdir`` — so hoisting ``rootdir`` above the
worktree still yields ``tests/test_branch_feature.py`` and still attributes.
The refusal is fail-CLOSED and its message names both the scope and whatever the
runner blamed, so the case is diagnosable from the gate's own output.

**SPEC-103 bounds what a green verdict means (``docs/specs/SPEC-103.md``).**
Attribution by stdout parsing is **declined**: five independent writers forge a
``FAILED <in-scope path>`` line, three of them ordinary project configuration
(``conftest``'s ``pytest_unconfigure``, an ``atexit`` handler, ``os.write(1)``
from one), and they write AFTER pytest's own reporter has finished — so no parse
position is a fixed point. What a green ``implement/red`` licenses is only:

> a test-runner invocation whose arguments were the branch's own changed test
> files exited non-zero, and the exit code was not one of the measured no-run
> codes.

Attribution survives as an additional **refusal filter** only. It is monotone —
it can remove a PASS, never add one beyond the declared property — so forging it
buys nothing. The gate's rendered output must therefore not claim a branch test
failed; the classes added below pin that, and pin the four over-refusals
SPEC-103 removes (forced colour, ``--no-summary``, a non-``main`` default
branch, and a polyglot repo's Python-only delta).

**ISSUE-117 re-decides what a 124 or a 127 MEANS.** SPEC-103 refused both codes
on the bare integer. Re-measured (the table in
``TestSynthesisedVersusChosenExitCodes``), npm forwards its test script's exit
code **verbatim** on npm 9.8.1/node v18.18.0 and npm 11.5.2/node v22.18.0
alike, so a runner reporting exactly 124 or 127 failures was being refused for
counting — an over-refusal, which no declaration may license. ``_run`` now tags
the 124 it synthesises on timeout and the 127 it synthesises on a missing
binary, the gate reads the tag rather than the number, and the one chosen-127
case that still means "nothing ran" (npm's ``test`` script naming an absent
binary) is refused on the shell's **evidence** instead. Every test that pinned
the old integer-based behaviour was updated in place with its disarm direction
measured — none was deleted.

Coverage layers:

* ``TestSynthesisedVersusChosenExitCodes`` — ISSUE-117's seam, in both
  directions, at the unit seam and (for npm, with the real binary) at the real
  consumer.
* ``TestRedScopeRealConsumer`` / ``TestRedAttributionRequired`` /
  ``TestUncomputableDeltaPosition`` — drive the REAL consumer
  (``bash scripts/checkpoint.sh --skill implement --phase red``) as a subprocess
  against throwaway git repos with registered worktrees and REAL pytest
  children, in both the arm and the disarm direction (review lesson 16).
  These are bounded: each child run collects one or two short test files, so
  this is **not** the recursive full-suite spawn TC-047g removed.
* ``TestRedScopeArgv`` / ``TestRedScopeLegacyRoutes`` / ``TestFailedTestFiles``
  — unit pins with ``vc._run`` mocked at the subprocess seam.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import verify_checkpoint as vc  # noqa: E402

KIT_ROOT = Path(__file__).resolve().parents[1]

BRANCH_TEST = "tests/test_branch_feature.py"
UNRELATED_TEST = "tests/test_unrelated.py"


def scoped_arg(path: str) -> str:
    """How a scoped path appears in the pytest argv: ``./``-prefixed.

    ISSUE-114 route (c) prefixes every scoped path so a flag-shaped filename
    cannot be consumed as an option. The prefix lives here rather than inline
    at each assertion so that a change to it fails one place loudly instead of
    turning a dozen membership assertions **vacuously true** — the hollow-pass
    direction, which is how a negative pin like ``BRANCH_TEST not in argv``
    stops testing anything the moment the argv's spelling changes.
    """
    return f"./{path}"


def npm_argv(*scoped: str) -> list[str]:
    """The npm argv the gate builds for a scoped RED run.

    Exists so the real-vitest probe
    (:class:`TestSecondSeparatorDeletesScopeOnRealVitest`) runs the shape the
    gate actually sends instead of a copy that can drift away from it. The
    structural pin still asserts the argv as a LITERAL as well — if only this
    helper were asserted against, both sides would move together and the pin
    would certify whatever the gate happened to build.
    """
    return ["npm", "test", "--", "--passWithNoTests", *scoped]
# A failing test outside `tests/`, so a project whose addopts inject this path
# adds a failure the branch never touched. Kept DISJOINT from the scoped argv on
# purpose: measured, pytest 8.3.4 deduplicates an addopts path that CONTAINS the
# scoped file (collecting only the file, exit 0) where 9.0.3 collects both, so an
# overlapping path would make the construction version-dependent.
EXTRA_TEST = "extra_tests/test_extra.py"


def _mock_run(returncode: int, stdout: str = "", stderr: str = ""):
    """Mirror of tests/test_verify_checkpoint.py's _mock_run helper.

    ISSUE-117 semantics: a bare ``CompletedProcess`` carries no synthesis tag,
    so under the post-ISSUE-117 contract a result built here means **the child
    chose this code**. Tests that want the kit's own synthesised 124/127 must
    use :func:`_synthesised`, which returns an object ``vc._run`` really made.
    """
    result = subprocess.CompletedProcess([], returncode)
    result.stdout = stdout
    result.stderr = stderr
    return result


# A binary that must not exist on any machine running this suite. Shared by the
# `_run`-synthesises-127 fixture and the npm-script-names-an-absent-binary
# construction, so the two routes are built from the same premise.
ABSENT_BINARY = "definitely-not-a-real-binary-xyz"
# An interpreter that must not exist either. Used for the `#!/usr/bin/env ...`
# shim whose interpreter is absent — the route where the 127 diagnostic is
# written by the EXEC LAYER rather than by the shell.
ABSENT_INTERPRETER = "definitely-not-a-real-interp-xyz"


def _synthesised(kind: str):
    """A result ``vc._run`` REALLY synthesised — the fixture pin for AC-2.

    Deliberately not a hand-built ``CompletedProcess``: review lesson 3 asks
    that a mock at a delegation seam be the shape it claims to be, and after
    ISSUE-117 the *tag* is what tells the two routes apart, not the integer. A
    test that hand-built ``CompletedProcess(…, 124)`` and called it "the kit's
    timeout" would silently become a *chosen*-124 test.

    The premise is asserted here, so a regression in ``_run``'s tagging fails
    the fixture rather than quietly re-routing every test that uses it.
    """
    if kind == "timeout":
        result = vc._run(["sleep", "10"], timeout=1)
        expected_rc = 124
    elif kind == "binary-absent":
        result = vc._run([ABSENT_BINARY])
        expected_rc = 127
    else:  # pragma: no cover - guards a typo in a caller
        raise AssertionError(f"unknown synthesis kind: {kind}")

    assert result.returncode == expected_rc, result
    assert vc._synthesised_reason(result) == kind, (
        f"fixture pin failed: _run did not tag this result as {kind!r}"
    )
    return result


# ── Real-consumer probes ─────────────────────────────────────────────


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert r.returncode == 0, f"git {args} failed in {cwd}: {r.stderr}"
    return r.stdout.strip()


@pytest.fixture(scope="module")
def probe_repo(tmp_path_factory):
    """A throwaway repo with one worktree per measured construction.

    ``main`` gets two commits: the unrelated test green, then the unrelated test
    red. A branch forked from the GREEN commit therefore sees a suite that is
    green apart from its own test; a branch forked from the RED commit sees a
    pre-existing unrelated failure that is NOT part of its own delta. The later
    configs additionally vary the consumer project's own ``pyproject.toml``,
    because three of the four routes measured in review are reached through the
    project's ``addopts`` rather than through its tests.

    Read-only once built, so the tests below stay order-independent.
    """
    root = tmp_path_factory.mktemp("red-scope-probe")
    repo = root / "repo"
    repo.mkdir()

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "probe@example.com")
    _git(repo, "config", "user.name", "Probe")
    _git(repo, "config", "commit.gpgsign", "false")

    # [tool.pytest.ini_options] anchors rootdir at the worktree, so pytest
    # nodeids come back as the same relative paths the verifier passed in.
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (repo / "tests").mkdir()
    unrelated = repo / UNRELATED_TEST

    # `src/` exists at every fork point so the `cov` config has something to be
    # 0% of: 43 statements, none of them reachable from the branch's own test.
    (repo / "src").mkdir()
    (repo / "src" / "lib.py").write_text(
        "def f(x):\n"
        + "".join(f"    x = x + {i}\n" for i in range(1, 42))
        + "    return x\n"
    )

    # A failing test outside `tests/`, present at every fork point and in no
    # branch's delta — the subject of the `addopts_path` config.
    (repo / "extra_tests").mkdir()
    (repo / EXTRA_TEST).write_text("def test_extra():\n    assert False\n")

    unrelated.write_text("def test_unrelated():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base: unrelated test green")
    green_base = _git(repo, "rev-parse", "HEAD")

    unrelated.write_text(
        "def test_unrelated():\n    assert False  # pre-existing, unrelated\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base: unrelated test red")
    red_base = _git(repo, "rev-parse", "HEAD")

    fails = "def test_branch_feature():\n    assert False  # implementation absent\n"
    passes = "def test_branch_feature():\n    assert True  # vacuously green\n"

    worktrees: dict[str, Path] = {}
    # (name, issue number, fork point, tests/test_branch_feature.py source,
    #  pyproject override or None, extra files or None)
    configs = (
        ("arm", "901", green_base, fails, None, None),
        ("disarm", "902", red_base, passes, None, None),
        ("both", "903", red_base, fails, None, None),
        # A project whose own addopts suppress pytest's short summary. Measured:
        # `addopts = "-rN"` prints no `FAILED <nodeid>` line at all, so per-file
        # attribution only survives because the verifier requests `-rfE` itself.
        ("quiet", "904", green_base, fails,
         '[tool.pytest.ini_options]\naddopts = "-rN"\n', None),
        # F1-c: exit 1 from a COVERAGE threshold, with zero test failures. The
        # branch's own test passes and covers nothing, so the scoped run prints
        # `1 passed` and `FAIL Required test coverage of 50% not reached` and
        # exits 1. Measured pre-fix: certified as RED.
        ("cov", "905", green_base, passes,
         '[tool.pytest.ini_options]\naddopts = "--cov=src --cov-fail-under=50"\n',
         None),
        # F1-b: the project's own addopts inject an extra test PATH, so the
        # scoped run collects `extra_tests/` too. The branch's own test passes
        # and the pre-existing unrelated one there fails — AC-1's defect,
        # reached through a route scoping the argv alone does not close.
        # Measured pre-fix: certified as RED with "per-file attribution
        # unavailable".
        ("addopts_path", "906", green_base, passes,
         '[tool.pytest.ini_options]\naddopts = "extra_tests"\n', None),
        # ISSUE-114: the SAME positional-addopts project, with the branch's own
        # test genuinely FAILING — so the gate PASSES and the row is legitimate
        # work rather than a refusal. That is what makes it the disarm row for
        # route (c)'s pytest separator, which was measured to turn this exact
        # PASS into `exit 4: nothing collected / usage error` on pytest 8.3.4.
        ("addopts_path_red", "946", green_base, fails,
         '[tool.pytest.ini_options]\naddopts = "extra_tests"\n', None),
        # Item 3: the exit-5 route that actually reproduces. The project's own
        # addopts DESELECT the branch's test, so the scoped run collects it and
        # evaluates nothing: `1 deselected`, exit 5.
        ("deselect", "907", green_base,
         "import pytest\n\n\n@pytest.mark.slow\n"
         "def test_branch_feature():\n    assert False  # implementation absent\n",
         "[tool.pytest.ini_options]\n"
         "addopts = \"-m 'not slow'\"\nmarkers = [\"slow: marked slow\"]\n", None),
        # H3: the project forces colour, so every summary line starts with an
        # SGR escape and the ^-anchored parser matches nothing. Measured: a
        # GENUINE RED was refused. `--color=no` on the command line overrides it.
        ("colour", "908", green_base, fails,
         '[tool.pytest.ini_options]\naddopts = "--color=yes"\n', None),
        # Change 4: `addopts = "--no-summary"` removes the summary section AND
        # the traceback, so no per-file oracle exists anywhere in the stream.
        # Measured (8.3.4 and 9.0.3): stdout is `F ... [100%]` + `1 failed in
        # 0.01s`, exit 1 — attribution is UNCOMPUTABLE, not computed-and-empty.
        ("nosummary", "909", green_base, fails,
         '[tool.pytest.ini_options]\naddopts = "--no-summary"\n', None),
        # Change 6: a polyglot repo — `package.json` declares `scripts.test`
        # AND the project is Python. The branch's delta is `.py` only, so the
        # JS branch must not win; before this change there was no route to a
        # RED pass at all for such a branch.
        ("polyglot", "910", green_base, fails, None,
         {"package.json": '{"name": "p", "version": "1.0.0", '
                          '"scripts": {"test": "vitest run"}}'}),
    )
    for name, num, base, test_src, pyproject, extra in configs:
        wt = root / f"issue-{num}-{name}"
        _git(repo, "worktree", "add", "-q", "-b", f"issue/ISSUE-{num}-{name}",
             str(wt), base)
        (wt / BRANCH_TEST).write_text(test_src)
        if pyproject:
            (wt / "pyproject.toml").write_text(pyproject)
        for rel, content in (extra or {}).items():
            (wt / rel).write_text(content)
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "test: branch test")
        worktrees[name] = wt

    return worktrees


def _run_red_checkpoint(wt: Path, issue_id: str, env_overlay: dict | None = None):
    """Invoke the real consumer from inside ``wt``.

    ``CLAUDE_PLUGIN_ROOT`` is cleared so ``checkpoint.sh`` resolves its kit root
    from its own location — i.e. the tree this test ships in, not an installed
    plugin copy. The colour vars are cleared unconditionally so a developer
    shell that exports ``FORCE_COLOR`` cannot silently turn the control rows
    into the forced-colour rows; ``env_overlay`` is how a test asks for them.
    """
    env = {
        k: v for k, v in os.environ.items()
        if k not in ("CLAUDE_PLUGIN_ROOT", "FORCE_COLOR", "PY_COLORS", "NO_COLOR")
    }
    env["KIT_CHECKPOINT_TEST_TIMEOUT"] = "120"
    env.update(env_overlay or {})
    return subprocess.run(
        [
            "bash", str(KIT_ROOT / "scripts" / "checkpoint.sh"),
            "--skill", "implement", "--phase", "red", "--issue", issue_id,
        ],
        cwd=str(wt), capture_output=True, text=True, timeout=300, env=env,
    )


class TestRedScopeRealConsumer:
    """AC-1/AC-2/AC-3 through `bash scripts/checkpoint.sh` on a real worktree."""

    def test_disarm_branch_tests_pass_while_unrelated_test_fails(self, probe_repo):
        """AC-1: branch tests pass, unrelated pre-existing test fails → non-zero.

        Pre-fix this exits 0 with `PASS: RED phase — tests fail as expected
        (exit 1)`, certified by `tests/test_unrelated.py`.
        """
        r = _run_red_checkpoint(probe_repo["disarm"], "ISSUE-902")
        out = r.stdout + r.stderr

        assert r.returncode != 0, f"expected refusal, got 0:\n{out}"
        assert "FAIL: RED phase" in out, out
        # The message must say the BRANCH's tests passed, and must not have been
        # decided by the unrelated failure.
        assert BRANCH_TEST in out, out
        assert UNRELATED_TEST not in out, out

    def test_arm_branch_tests_fail_names_the_failing_branch_file(self, probe_repo):
        """AC-2: branch tests genuinely fail → exit 0, naming the branch file.

        AC-2 asks the output to name which of the branch's own test files
        failed. SPEC-103 bounds HOW that may be said: the runner's summary
        blamed the path, and that is heuristic rather than established. The
        path is still named; the claim is not made.
        """
        r = _run_red_checkpoint(probe_repo["arm"], "ISSUE-901")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"expected RED pass, got {r.returncode}:\n{out}"
        assert "PASS: RED phase" in out, out
        assert BRANCH_TEST in out, out
        # Fixture pin: a missing-pytest or empty-run child would exit non-zero
        # too, so assert the attribution actually came from a test failure.
        assert "summary blamed" in out, out

    def test_arm_still_passes_when_an_unrelated_test_also_fails(self, probe_repo):
        """AC-3: branch tests fail AND an unrelated test fails → still exit 0.

        The fix must not be bought by refusing whenever the suite is imperfect.
        """
        r = _run_red_checkpoint(probe_repo["both"], "ISSUE-903")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"expected RED pass, got {r.returncode}:\n{out}"
        assert "PASS: RED phase" in out, out
        assert BRANCH_TEST in out, out

    def test_attribution_survives_a_project_that_suppresses_the_summary(
        self, probe_repo
    ):
        """AC-2 under a project whose `addopts = "-rN"` hides the summary.

        Attribution must come from a format the verifier requests itself, not
        from whatever the consumer project happens to configure.
        """
        r = _run_red_checkpoint(probe_repo["quiet"], "ISSUE-904")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"expected RED pass, got {r.returncode}:\n{out}"
        assert f"summary blamed: {BRANCH_TEST}" in out, out


# ── Unit pins: the run must be argv-scoped ───────────────────────────


def _py_worktree(tmp_path: Path) -> Path:
    """Python worktree with one changed test file and one pre-existing one."""
    wt = tmp_path / "wt" / "issue" / "issue-001-slug"
    wt.mkdir(parents=True)
    (wt / "pyproject.toml").write_text("[tool.pytest]\n")
    (wt / "tests").mkdir()
    (wt / BRANCH_TEST).write_text(
        "def test_branch_feature():\n    assert False\n"
    )
    (wt / UNRELATED_TEST).write_text(
        "def test_unrelated():\n    assert False\n"
    )
    return wt


def _side_effect(wt: Path, changed: str, runs: list, result):
    """Mock `_run`: git answers the delta, the test runner records its argv."""

    def run(cmd, **kwargs):
        if cmd[:2] == ["git", "worktree"]:
            return _mock_run(0, stdout=f"worktree {wt}\n")
        if cmd[:2] == ["git", "diff"] and "main" in cmd:
            return _mock_run(0, stdout=changed)
        if "pytest" in cmd or cmd[:2] == ["npm", "test"]:
            runs.append(cmd)
            return result
        return _mock_run(0, stdout="")

    return run


class TestRedScopeArgv:
    """The structural pin: the test run's argv carries the branch's own files."""

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def test_pytest_argv_is_scoped_to_the_branch_delta(self, tmp_path):
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(1, stdout=f"FAILED {BRANCH_TEST}::test_branch_feature - x"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert len(runs) == 1, runs
        assert scoped_arg(BRANCH_TEST) in runs[0], runs[0]
        # Both spellings, so this stays a real exclusion rather than becoming
        # vacuously true the moment the argv's prefix changes.
        assert UNRELATED_TEST not in runs[0], runs[0]
        assert scoped_arg(UNRELATED_TEST) not in runs[0], runs[0]

    def test_js_runner_is_scoped_and_pytest_never_runs(self, tmp_path):
        """Legacy JS-mis-run pin: a JS repo goes to npm, never to pytest."""
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        (wt / "tests").mkdir()
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs, _mock_run(1, stdout="1 failed")
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert len(runs) == 1, runs
        assert runs[0][:2] == ["npm", "test"], runs[0]
        assert "tests/feature.test.ts" in runs[0], runs[0]
        assert not any("pytest" in c for c in runs[0]), runs[0]

    def test_refuses_when_no_changed_test_file_is_runnable_by_the_runner(
        self, tmp_path, capsys
    ):
        """A Python worktree whose only changed test file is a .ts → refuse.

        Measured: pytest handed a `.ts` path exits 4 ("no tests ran"), which is
        non-zero and would be a fake RED. The runner must not be handed files it
        cannot execute.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "tests").mkdir()
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs, _mock_run(4)
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        assert runs == [], runs  # refused before running anything
        assert "tests/feature.test.ts" in capsys.readouterr().out


class TestRedScopeLegacyRoutes:
    """Review lesson 8 — every pre-existing refusal route still behaves as before."""

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def _red(self, wt, changed, result, runs=None):
        runs = runs if runs is not None else []
        with patch.object(
            vc, "_run", side_effect=_side_effect(wt, changed, runs, result)
        ):
            return vc.verify_implement_red("ISSUE-001")

    def test_timeout_124_still_fails_inconclusive(self, tmp_path, capsys):
        """Updated by ISSUE-117 (AC-3), premise changed, verdict unchanged.

        This used to feed ``_mock_run(124)`` — a bare ``CompletedProcess``,
        which after ISSUE-117 means *the child chose 124* and now certifies RED.
        Measured: left as it was, this test flips to a failure and the honest
        repair is to supply the route it always meant, the kit's OWN timeout.
        The disarm twin is
        ``TestSynthesisedVersusChosenExitCodes::
        test_child_chosen_code_is_the_runners_verdict_for_npm[124]``.
        """
        wt = _py_worktree(tmp_path)
        assert self._red(wt, f"{BRANCH_TEST}\n", _synthesised("timeout")) is False
        out = capsys.readouterr().out.lower()
        assert "inconclusive" in out
        assert "timed out" in out

    def test_exit_zero_still_fails_tests_should_not_pass(self, tmp_path, capsys):
        wt = _py_worktree(tmp_path)
        assert self._red(wt, f"{BRANCH_TEST}\n", _mock_run(0)) is False
        out = capsys.readouterr().out
        assert "passed but should fail" in out
        assert BRANCH_TEST in out

    def test_no_test_files_still_fails_with_the_write_tests_message(
        self, tmp_path, capsys
    ):
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        assert self._red(wt, "", _mock_run(1)) is False
        out = capsys.readouterr().out
        assert "no test files found" in out
        # paired absence: a computable-but-empty delta is NOT the uncomputable one
        assert "cannot compute" not in out

    def test_hollow_test_file_still_fails(self, tmp_path, capsys):
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "tests").mkdir()
        (wt / "tests/test_hollow.py").write_text("def test_nothing():\n    pass\n")
        assert self._red(wt, "tests/test_hollow.py\n", _mock_run(1)) is False
        assert "no real assertions" in capsys.readouterr().out

    @pytest.mark.parametrize("rc", [5, 4])
    def test_run_that_evaluated_nothing_is_inconclusive_not_red(
        self, tmp_path, capsys, rc
    ):
        """Scoping makes pytest's exit 5 reachable — it must not certify RED.

        The route that reproduces is a branch test the project's own ``addopts``
        **deselect** (measured: ``addopts = "-m 'not slow'"`` with a
        ``@pytest.mark.slow`` test → ``1 deselected``, exit 5) — pinned end to
        end by ``test_addopts_deselect_the_branch_test_is_inconclusive``. Exit 4
        is pytest's usage error, same class. Both are "could not compute", not
        "the branch's tests failed".
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "tests").mkdir()
        (wt / BRANCH_TEST).write_text(
            "import pytest\n\n\n@pytest.mark.slow\n"
            "def test_branch_feature():\n    assert False\n"
        )
        assert self._red(wt, f"{BRANCH_TEST}\n", _mock_run(rc)) is False
        out = capsys.readouterr().out
        assert "inconclusive" in out
        assert str(rc) in out
        assert BRANCH_TEST in out

    def test_addopts_deselect_the_branch_test_is_inconclusive(self, probe_repo):
        """The exit-5 route, measured through the real consumer (item 3).

        The hazard note previously justified this guard with a conftest-only
        branch. That example does not reproduce on either shipped pytest: a
        `tests/conftest.py` with no test function is refused UPSTREAM by the
        hollow-assertion check, and one WITH a test function collects it and
        exits 0 (`1 passed`) — the exit-0 branch, never exit 5. The guard is
        still load-bearing, via a route neither the PR nor the review used:
        `addopts` that deselect the branch's own test.
        """
        r = _run_red_checkpoint(probe_repo["deselect"], "ISSUE-907")
        out = r.stdout + r.stderr

        assert r.returncode != 0, f"expected refusal, got 0:\n{out}"
        assert "FAIL: RED phase" in out, out
        assert "exit 5" in out, out
        assert "inconclusive" in out, out
        assert BRANCH_TEST in out, out

    def test_uncomputable_delta_is_distinct_from_an_empty_delta(
        self, tmp_path, capsys
    ):
        """No merge-base and an unresolvable base ref → its own message.

        "Computed and empty" (write tests) and "could not compute" (the gate's
        subject is unknown) must not collapse into the same message.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)

        def run(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt}\n")
            return _mock_run(128, stderr="fatal: bad revision")

        with patch.object(vc, "_run", side_effect=run):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "cannot compute" in out
        assert "no test files found" not in out


# ── F2: the could-not-compute refusal must sit UPSTREAM ──────────────


@pytest.fixture(scope="module")
def unresolvable_base_repo(tmp_path_factory):
    """A worktree whose diff base does not resolve, with a committed test file.

    The repo's only branch is ``trunk``, so the kit's base ref (``main``) has
    neither a merge-base nor a resolvable ref — i.e. the branch's own delta is
    genuinely UNKNOWN, not empty. Measured in review in exactly this shape:
    ``default_branch=main, merge_base=None``.
    """
    root = tmp_path_factory.mktemp("red-uncomputable-probe")
    repo = root / "repo"
    repo.mkdir()

    _git(repo, "init", "-q", "-b", "trunk")
    _git(repo, "config", "user.email", "probe@example.com")
    _git(repo, "config", "user.name", "Probe")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (repo / "tests").mkdir()
    (repo / "tests/test_base.py").write_text("def test_base():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    wt = root / "issue-911-pos"
    _git(repo, "worktree", "add", "-q", "-b", "issue/ISSUE-911-pos", str(wt), "trunk")
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "main"],
        cwd=str(wt), capture_output=True,
    ).returncode != 0, "fixture pin: 'main' must NOT resolve in this worktree"
    return wt


class TestUncomputableDeltaPosition:
    """F2 — "could not compute" must be decided BEFORE the delta is trusted.

    Review lesson 12, verbatim: *a relocated gate call site must stay downstream
    of every step that mutates the surface it gates — pin position, not just
    presence.* `_changed_files_vs_base` includes **untracked** paths, so while
    this check was nested inside ``if not all_test_files:`` a single stray
    ``tests/test_stray.py`` made the delta non-empty, skipped the check, and an
    unresolvable base was silently treated as a known delta.

    Every test in this class fails if the check is moved back inside the
    emptiness branch — presence alone is what let the defect through. The fix
    is deliberately NOT "restrict the delta to tracked paths": during a genuine
    RED the new test file is routinely still untracked.
    """

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def _unresolvable_run(self, wt: Path, untracked: str, runs: list):
        """`_run` for: no merge-base, no resolvable base ref, ONE untracked test.

        The measured git state of review probe B — every rev-walk fails while
        ``git ls-files --others`` still answers, which is precisely how an
        UNKNOWN base acquires a non-empty delta.
        """

        def run(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt}\n")
            if cmd[:2] == ["git", "ls-files"]:
                return _mock_run(0, stdout=f"{untracked}\n")
            if "pytest" in cmd or cmd[:2] == ["npm", "test"]:
                runs.append(cmd)
                return _mock_run(1, stdout=f"FAILED {untracked}::test_stray - boom")
            return _mock_run(128, stderr="fatal: bad revision")

        return run

    def test_untracked_test_file_does_not_mask_the_refusal(self, tmp_path, capsys):
        """Position pin: a non-empty delta must not skip the check.

        Measured pre-fix at the real consumer, same worktree: empty delta →
        correct refusal, exit 1; plus one untracked `tests/test_stray.py` →
        `PASS … failing: tests/test_stray.py`, exit 0.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "tests/test_stray.py").write_text("def test_stray():\n    assert False\n")
        runs: list = []

        with patch.object(
            vc, "_run",
            side_effect=self._unresolvable_run(wt, "tests/test_stray.py", runs),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "cannot compute" in out, out
        assert "inconclusive" in out, out
        # The gate must not claim the stray file is "the branch's own".
        assert "PASS" not in out, out
        # Upstream of the run: nothing was executed on an unknown subject.
        assert runs == [], runs

    def test_refusal_is_upstream_of_the_hollow_assertion_gate(self, tmp_path, capsys):
        """Position pin, second step: an UNKNOWN delta is not a hollow-test report.

        Measured pre-fix at the real consumer: the same worktree with a HOLLOW
        untracked stray answered `FAIL: test files have no real assertions`,
        sending the implementer after a file the branch may not even own.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "tests/test_stray.py").write_text("def test_stray():\n    pass\n")
        runs: list = []

        with patch.object(
            vc, "_run",
            side_effect=self._unresolvable_run(wt, "tests/test_stray.py", runs),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "cannot compute" in out, out
        assert "no real assertions" not in out, out

    def test_position_pin_through_the_real_consumer(self, unresolvable_base_repo):
        """F2 through `bash scripts/checkpoint.sh`, both delta shapes.

        Review lesson 16: the disarm direction, at the real consumer. The stray
        file is created and removed inside this test so the module fixture stays
        read-only and the two tests stay order-independent.
        """
        wt = unresolvable_base_repo
        stray = wt / "tests/test_stray.py"

        r_empty = _run_red_checkpoint(wt, "ISSUE-911")
        out_empty = r_empty.stdout + r_empty.stderr
        assert r_empty.returncode != 0, out_empty
        assert "cannot compute" in out_empty, out_empty

        stray.write_text("def test_stray():\n    assert False\n")
        try:
            r_stray = _run_red_checkpoint(wt, "ISSUE-911")
        finally:
            stray.unlink()
        out_stray = r_stray.stdout + r_stray.stderr

        assert r_stray.returncode != 0, f"untracked file masked the refusal:\n{out_stray}"
        assert "cannot compute" in out_stray, out_stray
        assert "tests/test_stray.py" not in out_stray, out_stray


# ── Unit pins: the attribution parser (review lesson 4) ──────────────


class TestFailedTestFiles:
    """`_failed_test_files` must match pytest's measured summary format exactly."""

    def test_parses_failed_summary_line(self):
        out = (
            "=== short test summary info ===\n"
            f"FAILED {BRANCH_TEST}::test_branch_feature - assert False\n"
            "1 failed in 0.01s\n"
        )
        assert vc._failed_test_files(out, [BRANCH_TEST]) == [BRANCH_TEST]

    def test_parses_collection_error_summary_line(self):
        """Measured form for a collection error: `ERROR <path>`, no `::`."""
        out = f"ERROR {BRANCH_TEST}\n1 error in 0.06s\n"
        assert vc._failed_test_files(out, [BRANCH_TEST]) == [BRANCH_TEST]

    def test_out_of_scope_path_is_not_attributed(self):
        """Boundary: the summary may name files outside the branch's delta."""
        out = f"FAILED {UNRELATED_TEST}::test_unrelated - assert False\n"
        assert vc._failed_test_files(out, [BRANCH_TEST]) == []

    def test_mid_line_failed_token_is_not_a_summary_line(self):
        """Boundary: only line-anchored summary lines count.

        The path here is bare (no trailing quote), so dropping the `^` anchor
        really does attribute it — the mutation that removes the anchor must be
        killed by behaviour, not by the fixture's punctuation.
        """
        out = f"    # regression note: see FAILED {BRANCH_TEST} in the old log\n"
        assert vc._failed_test_files(out, [BRANCH_TEST]) == []

    def test_unparseable_output_yields_no_attribution(self):
        """Degradation: a runner with another format attributes nothing."""
        out = "Tests:       1 failed, 1 total\n"
        assert vc._failed_test_files(out, [BRANCH_TEST]) == []

    def test_multiple_failures_collect_all_without_duplicates(self):
        out = (
            f"FAILED {BRANCH_TEST}::test_a - boom\n"
            f"FAILED {BRANCH_TEST}::test_b - boom\n"
            "FAILED tests/test_other.py::test_c - boom\n"
        )
        assert vc._failed_test_files(out, [BRANCH_TEST, "tests/test_other.py"]) == [
            BRANCH_TEST,
            "tests/test_other.py",
        ]

    def test_blamed_paths_ignore_scope_but_keep_order_and_dedup(self):
        """`_blamed_test_files` answers the second question off the SAME parse.

        `_failed_test_files` asks "which of the scope did the runner blame";
        the caller also needs "did the runner blame anything at all", to tell
        `computed and empty` from `could not compute`. One regex, two questions
        — no second oracle (ISSUE-103's own Implementation Notes).
        """
        out = (
            f"FAILED {UNRELATED_TEST}::test_a - boom\n"
            f"FAILED {UNRELATED_TEST}::test_b - boom\n"
            f"ERROR {BRANCH_TEST}\n"
        )
        assert vc._blamed_test_files(out) == [UNRELATED_TEST, BRANCH_TEST]
        assert vc._failed_test_files(out, [BRANCH_TEST]) == [BRANCH_TEST]

    def test_blamed_paths_empty_when_nothing_was_reported(self):
        """Paired absence: the coverage-failure shape blames nothing.

        Verbatim from the measured child run — `ERROR:` (with a colon, so the
        summary regex must not match it) and `FAIL Required test coverage`.
        """
        out = (
            "ERROR: Coverage failure: total of 0 is less than fail-under=50\n"
            "FAIL Required test coverage of 50% not reached. Total coverage: 0.00%\n"
            "1 passed in 0.01s\n"
        )
        assert vc._blamed_test_files(out) == []


# ── F1: a pytest RED pass requires attribution ───────────────────────


class TestRedAttributionRequired:
    """F1 — a non-zero exit with ZERO attributed failures is NOT a RED pass.

    The criteria F1-a..F1-d are stated in this module's docstring, because no
    ISSUE-103 AC names this surface and review lesson 14 predicted that is
    exactly where the defects would be.

    Pre-fix, every test here passed through the `else` arm of the verdict —
    relabelled as "per-file attribution unavailable" and certified as RED.
    """

    # ── F1-c: nothing blamed at all ──────────────────────────────────

    def test_nothing_blamed_coverage_threshold_real_consumer(self, probe_repo):
        """F1-c through the real consumer, with REAL pytest-cov.

        The branch's own test PASSES and covers nothing, so exit 1 comes from
        `--cov-fail-under` alone and zero tests failed. Measured pre-fix:
        `PASS: RED phase — the branch's own tests fail as expected (exit 1)`.
        """
        r = _run_red_checkpoint(probe_repo["cov"], "ISSUE-905")
        out = r.stdout + r.stderr

        if "--cov" in out and "unrecognized arguments" in out:
            pytest.fail(
                "pytest-cov is absent from the child runner, so this probe "
                f"measured a usage error instead of a coverage failure:\n{out}"
            )
        assert r.returncode != 0, f"expected refusal, got 0:\n{out}"
        assert "FAIL: RED phase" in out, out
        assert "inconclusive" in out, out
        # The refusal must say WHY and name the scope.
        assert BRANCH_TEST in out, out
        # Fixture pin: the child really did run and really did pass its test,
        # so this is the zero-failures route and not some other non-zero exit.
        assert "1 passed" in out or "no test failure" in out, out

    def test_nothing_blamed_runner_absent(self, tmp_path, capsys):
        """F1-c, second measured route: `python3 -m pytest` with pytest absent.

        Measured: `No module named pytest` on stderr, empty stdout, exit 1 —
        nothing ran at all, and pre-fix that certified RED.
        """
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(1, stdout="", stderr="/usr/bin/python3: No module named pytest"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "inconclusive" in out, out
        assert BRANCH_TEST in out, out

    # ── F1-b: blamed, but nothing inside the branch's delta ──────────

    def test_blamed_only_outside_the_delta_real_consumer(self, probe_repo):
        """F1-b through the real consumer: AC-1's defect via the project's addopts.

        `addopts = "extra_tests"` prepends an extra test PATH, so the scoped run
        collects `extra_tests/` as well. The branch's own test PASSES and the
        pre-existing failing one there fails. Measured pre-fix: `PASS: RED phase
        … (per-file attribution unavailable from pytest's output)`, exit 0 — the
        whole-suite defect, surviving the scoping fix.
        """
        r = _run_red_checkpoint(probe_repo["addopts_path"], "ISSUE-906")
        out = r.stdout + r.stderr

        assert r.returncode != 0, f"expected refusal, got 0:\n{out}"
        assert "FAIL: RED phase" in out, out
        assert "inconclusive" in out, out
        # Both halves of the diagnosis: what was in scope, and what was blamed.
        assert BRANCH_TEST in out, out
        assert EXTRA_TEST in out, out

    def test_blamed_only_outside_the_delta_unit(self, tmp_path, capsys):
        """F1-b at the seam, with the measured summary line verbatim."""
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(
                    1,
                    stdout=f"FAILED {UNRELATED_TEST}::test_unrelated - assert False\n"
                           "1 failed, 1 passed in 0.01s\n",
                ),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "inconclusive" in out, out
        assert UNRELATED_TEST in out, out

    def test_the_two_empty_cases_are_told_apart(self, tmp_path, capsys):
        """Both refuse, but "blamed nothing" and "blamed elsewhere" differ.

        The governing rule is that a gate whose subject is COMPUTED must
        distinguish "computed and empty" from "could not compute". Here the
        decision is the same (refuse) and the DIAGNOSIS is not, so an
        implementer can tell a coverage threshold from an addopts-injected path
        without re-running anything.
        """
        def render(slug: str, result) -> str:
            wt = _py_worktree(tmp_path / slug)
            runs: list = []
            with patch.object(
                vc, "_default_branch", lambda: "main"
            ), patch.object(
                vc, "_run",
                side_effect=_side_effect(wt, f"{BRANCH_TEST}\n", runs, result),
            ):
                assert vc.verify_implement_red("ISSUE-001") is False
            return capsys.readouterr().out

        nothing = render("a", _mock_run(1, stdout="1 passed in 0.01s\n"))
        elsewhere = render(
            "b", _mock_run(1, stdout=f"FAILED {UNRELATED_TEST}::test_u - boom\n")
        )
        assert nothing != elsewhere
        assert UNRELATED_TEST in elsewhere and UNRELATED_TEST not in nothing
        for out in (nothing, elsewhere):
            assert "inconclusive" in out, out
            assert BRANCH_TEST in out, out

    # ── F1-d: the tightening is scoped to pytest (review lesson 8) ───

    def test_js_keeps_its_legacy_non_zero_is_red_contract(self, tmp_path, capsys):
        """F1-d: npm has no attribution parser, so requiring one would refuse
        every JS RED. The legacy contract stays and the output says so.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        (wt / "tests").mkdir()
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(1, stdout="Tests:  1 failed, 1 total\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert "unavailable" in out, out
        assert "tests/feature.test.ts" in out, out

    @pytest.mark.parametrize("code", [4, 5])
    def test_npm_keeps_its_contract_at_the_pytest_no_run_codes(
        self, tmp_path, capsys, code
    ):
        """ISSUE-115: npm's `no_run_codes` must stay EMPTY, pinned behaviourally.

        Mutant ``M20`` sets npm's tuple to ``(4, 5)`` — pytest's values, where 4
        is a usage error and 5 is "no tests collected", so both genuinely mean
        no test ran. For npm they mean nothing of the kind: **ISSUE-117 measured
        that npm forwards child exit codes verbatim**, so a mocha/tap-convention
        runner reporting 4 or 5 *failures* would be refused as "did not run".
        That is an over-refusal, and a declaration can never license blocking
        legitimate work.

        This pins the contract **behaviourally** — npm at each code still
        certifies RED and still says attribution is unavailable. The
        comment-text guard that used to sit here was removed rather than kept
        alongside: a test asserting on prose about `no_run_codes` is a
        record-accuracy test, and those manufacture issues instead of catching
        them. SPEC-103 required exactly this substitution.

        Note what is NOT claimed: 4 and 5 are not special for npm. They are
        tested because they are the codes the mutant borrows from pytest, and
        the point is that npm treats them like any other non-zero code.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        (wt / "tests").mkdir()
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(code, stdout=f"Tests:  {code} failed, {code} total\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True, (
                f"npm at exit {code} must certify RED — it is a failure count, "
                "not a no-run signal"
            )

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert "unavailable" in out, out
        assert "tests/feature.test.ts" in out, out


def _npm_probe_worktree(
    tmp_path: Path,
    number: str,
    slug: str,
    test_script: str,
    npmrc: str | None = None,
    extra_files: dict[str, tuple[str, int]] | None = None,
) -> Path:
    """A throwaway npm repo + registered worktree, for the REAL-consumer probes.

    The worktree's delta is one ``.ts`` test file, which is what routes
    ``verify_implement_red`` to the npm branch. ``test_script`` is the project's
    ``scripts.test``; ``npmrc`` pins ``script-shell`` where the construction
    depends on how a particular shell words "binary absent" (measured below —
    four shells, four wordings). ``extra_files`` maps a worktree-relative path
    to ``(content, mode)``, for constructions that need the ``test`` script to
    point at a file — e.g. a shim whose shebang interpreter is absent.
    """
    repo = tmp_path / f"repo-{slug}"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "probe@example.com")
    _git(repo, "config", "user.name", "Probe")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "package.json").write_text(
        '{"name": "p", "version": "1.0.0", "scripts": {"test": %s}}'
        % json.dumps(test_script)
    )
    if npmrc:
        (repo / ".npmrc").write_text(npmrc)
    (repo / "tests").mkdir()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    wt = tmp_path / f"issue-{number}-{slug}"
    _git(repo, "worktree", "add", "-q", "-b", f"issue/ISSUE-{number}-{slug}",
         str(wt), "HEAD")
    # git does not track empty directories, so `tests/` is absent from the
    # checkout even though it exists in the source repo.
    (wt / "tests").mkdir(exist_ok=True)
    (wt / "tests" / "feature.test.ts").write_text(
        'it("branch feature", () => { expect(1).toBe(2); });\n'
    )
    for rel, (content, mode) in (extra_files or {}).items():
        path = wt / rel
        path.write_text(content)
        path.chmod(mode)
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "test: branch test")
    return wt


def _runner_script(wt: Path, body: str) -> str:
    """Write an executable ``runner.sh`` into ``wt`` and return its npm script.

    Measured, and the reason the runner is a shell script rather than
    ``node -e``: the gate injects ``--passWithNoTests`` into the npm argv, and
    ``node -e`` consumes it as a *node* option and exits **9** — the "rejects
    the injected jest-specific flag" route the hazard note already names. A
    shell script simply ignores the extra argv, so the construction measures
    the exit code it means to.
    """
    runner = wt / "runner.sh"
    runner.write_text("#!/usr/bin/env bash\n" + body)
    runner.chmod(0o755)
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "chore: runner")
    return "./runner.sh"


class TestRunnerNotExecutableIsRefused:
    """F1-d, the half that was closable — **re-decided by ISSUE-117**.

    ISSUE-103 refused the bare integer 127 for both runners. ISSUE-117 measured
    that this is an **over-refusal**: npm forwards its test script's exit code
    verbatim, so a mocha/tap-convention runner reporting exactly 127 failures
    was refused as "could not be executed". The refusal is now narrowed to the
    two things that really mean *nothing ran*:

    1. ``_run`` **synthesised** the 127 (the runner binary is not on PATH) —
       the kit knows this because it produced the code itself; and
    2. the child chose 127 **and** the shell said ``command not found`` on
       stderr — npm's ``test`` script naming an absent binary.

    ================================================  ====  ================
    measured route                                    exit  refused now?
    ================================================  ====  ================
    npm, no ``test`` script ("nothing ran")              1  NO — collides
    npm, ``test`` script's binary absent               127  yes (evidence)
    runner binary absent (``_run`` synthesises)        127  yes (tag)
    npm, a genuine JS test failure (GENUINE RED)         1  no (stays RED)
    npm, runner chose 127 cleanly (127 failures)       127  **no** (ISSUE-117)
    npm, runner chose 124 cleanly (124 failures)       124  **no** (ISSUE-117)
    ================================================  ====  ================

    npm uses exit 1 for BOTH ``Missing script: "test"`` and a real test
    failure, so refusing exit 1 would refuse every JS RED — that route is a
    genuine design limit, unchanged. The disarm direction for every row that
    flipped lives in :class:`TestSynthesisedVersusChosenExitCodes`.
    """

    def test_npm_exit_127_real_consumer(self, tmp_path):
        """The arm direction at the REAL consumer, with REAL npm (lesson 16).

        The project's ``test`` script names a binary that does not exist. npm
        **forwards** the shell's 127 (measured below), so from the kit's seam
        this is a *child-chosen* code — yet nothing ran, which is why
        ISSUE-117 keeps the refusal and bases it on the shell's **evidence**
        rather than on the bare integer.

        **No ``script-shell`` pin, deliberately.** The first version of this
        test pinned ``/bin/sh`` *for determinism* and asserted the literal
        words ``command not found``. That was wrong twice over: ``/bin/sh`` is
        bash-in-sh-mode on macOS and **dash** on Debian/Ubuntu, and dash words
        it ``not found`` — so the pin made the probe host-DEPENDENT rather than
        host-independent, and it passed locally while CI (ubuntu, python 3.11
        and 3.12) reported, literally::

            AssertionError: exit 127 certified RED:
              PASS: RED phase — the branch's own tests fail as expected (exit 127)

        That was not a flaky test: it was the predicate genuinely doing nothing
        on Linux. This probe now runs under whatever ``/bin/sh`` the host has
        and asserts the VERDICT, not the wording; every shell is driven
        explicitly by
        ``test_absent_binary_is_refused_under_each_real_shell``.
        """
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed; this probe needs the real runner")

        wt = _npm_probe_worktree(tmp_path, "930", "npm127", ABSENT_BINARY)
        r = _run_red_checkpoint(wt, "ISSUE-930")
        out = r.stdout + r.stderr

        assert r.returncode != 0, f"exit 127 certified RED:\n{out}"
        assert "FAIL: RED phase" in out, out
        assert "could not be executed" in out, out
        assert "inconclusive" in out, out
        # Fixture pin: this really is the 127 route and not some other refusal,
        # and it really is the EVIDENCE route and not the synthesis route — the
        # two are different code paths after ISSUE-117 and a test that could not
        # tell them apart would pass on either.
        #
        # Measured while writing this: asserting `"command not found" in out`
        # does NOT discriminate — the pre-ISSUE-117 message spelled the phrase
        # itself, in `(exit 127: command not found)`, so the assertion passed on
        # the old integer-based refusal too. It is ALSO host-dependent, per the
        # docstring. The discriminator is the ABSENT BINARY's NAME: only an
        # evidence-based refusal quotes what the shell actually said, every
        # measured shell names the binary, and the child's stderr is captured by
        # `_run` rather than inherited, so it cannot reach this stream any other
        # way.
        assert "127" in out, out
        assert ABSENT_BINARY in out, out
        assert "tests/feature.test.ts" in out, out

    @pytest.mark.parametrize("code", [124, 127])
    def test_npm_chosen_code_without_evidence_is_red_real_consumer(
        self, tmp_path, code
    ):
        """The DISARM twin of the test above (AC-1, AC-3) — REAL npm.

        Same runner, same exit code, same real consumer; the only thing removed
        is the shell's ``command not found``. A tap/mocha-convention runner
        reporting exactly 127 failures exits 127 cleanly, and that must certify
        RED. Pre-ISSUE-117 this was refused as "could not be executed" — the
        over-refusal the issue was filed against.

        **Parametrised over 124 as well by the ISSUE-117 review.** AC-1 names
        127, but the 124 refusal changed in the same commit and had no
        real-consumer disarm twin — its only coverage was the unit seam, while
        the 127 half had both. The two chosen codes are one decision and are
        pinned alike.
        """
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed; this probe needs the real runner")

        wt = _npm_probe_worktree(
            tmp_path, f"9{code}", f"npm{code}red", "PLACEHOLDER"
        )
        script = _runner_script(wt, f'echo "# fail {code}"; exit {code}\n')
        (wt / "package.json").write_text(
            '{"name": "p", "version": "1.0.0", "scripts": {"test": "%s"}}' % script
        )
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "chore: point test at runner")

        r = _run_red_checkpoint(wt, f"ISSUE-9{code}")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"a clean child-chosen {code} was refused:\n{out}"
        assert "PASS: RED phase" in out, out
        assert "could not be executed" not in out, out
        assert "timed out" not in out.lower(), out
        # Fixture pin: the run really did exit with the code under test and
        # really did reach the legacy npm pass, not some other PASS route.
        assert f"exit {code}" in out, out
        assert "unavailable" in out, out

    @pytest.mark.parametrize("runner_files,changed,label", [
        ({"pyproject.toml": "[tool.pytest]\n"}, BRANCH_TEST, "pytest"),
        ({"package.json": '{"scripts": {"test": "vitest run"}}'},
         "tests/feature.test.ts", "npm"),
    ])
    def test_synthesised_127_is_refused_for_both_runners(
        self, tmp_path, capsys, runner_files, changed, label
    ):
        """AC-2 — a 127 the KIT produced is refused for pytest AND npm.

        Unchanged in intent from the ISSUE-103 pin this replaces ("the
        tightening is not runner-local"); changed in its premise. It used to
        feed a hand-built ``CompletedProcess(…, 127)``, which after ISSUE-117
        means *the child chose 127* and no longer exercises this branch at all.
        The result now comes from :func:`_synthesised`, i.e. from a real
        ``vc._run`` call against an absent binary, so the test pins the route
        it names.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        for name, content in runner_files.items():
            (wt / name).write_text(content)
        (wt / changed).write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
            if changed.endswith(".ts")
            else "def test_branch_feature():\n    assert False\n"
        )
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{changed}\n", runs, _synthesised("binary-absent"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False, label

        out = capsys.readouterr().out
        assert "could not be executed" in out, out
        assert "inconclusive" in out, out
        assert changed in out, out
        # AC-2: the reason must be NAMED, not merely the number reported.
        assert "not on PATH" in out, out

    def test_npm_exit_1_is_still_red_because_it_collides(self, tmp_path, capsys):
        """The negative control for the tightening: exit 1 must stay RED for npm.

        This is the measured reason npm's ``no_run_codes`` stays empty. If a
        future change "closes the npm hole" by refusing exit 1, this test fails
        — which is the point: it would refuse every genuine JS RED.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(1, stdout="Tests:  1 failed, 1 total\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert "could not be executed" not in out, out

    def test_hazard_note_records_the_measured_collision(self):
        """The residual's STATED REASON must be the measured one.

        The note previously implied npm's whole no-run class was unrefusable.
        Measured, only the exit-1 half is. Asserting the mechanism keeps the
        note honest rather than merely mentioning npm.

        **Updated by ISSUE-117 (AC-4).** The note now also carries the
        measurement that *corrected* it, and a version-specific figure has to
        say which version it was taken against — the figure this one replaces
        was wrong precisely because it did not.
        """
        note = _hazard_note()
        assert "no_run_codes" in note, note
        assert "127" in note, note
        # The collision is the reason exit 1 is NOT refused; it must be stated.
        assert "exits 1 for BOTH" in note or "exit 1 would" in note, note
        # AC-4: the table's provenance. Both npm/node pairs the forwarding was
        # measured against, since one of them is the version the corrected
        # figure came from and the other is the one it was re-measured on.
        assert "npm 11.5.2" in note and "node v22.18.0" in note, note
        assert "npm 9.8.1" in note and "node v18.18.0" in note, note


class TestSynthesisedVersusChosenExitCodes:
    """ISSUE-117 — a 124/127 the kit PRODUCED is not a 124/127 the child CHOSE.

    **The correction this class exists for.** SPEC-103 was dispatched with the
    figure "npm collapses its test script's exit code to 1". That was true of
    the single construction it was taken from and false in general. Re-measured
    here, with a ``test`` script that just exits with a requested code:

    ====================  =====================  =====================
    script exit           npm 9.8.1 / v18.18.0   npm 11.5.2 / v22.18.0
    ====================  =====================  =====================
    0                     0                      0
    1                     1                      1
    2                     2                      2
    4                     4                      4
    5                     5                      5
    9                     9                      9
    42                    42                     42
    124                   124                    124
    127                   127                    127
    ====================  =====================  =====================

    npm **forwards verbatim** on both. So the ISSUE-103 refusals — any 124 is
    "timed out", any 127 is "could not be executed" — were **over-refusals**: a
    mocha/tap-convention runner reporting exactly 124 or 127 failures was
    blocked for counting. An over-refusal cannot be declared away, so it is
    fixed here.

    **The seam.** ``_run`` is the only writer of a 124 or a 127 the child never
    chose: it synthesises 124 on ``TimeoutExpired`` and 127 on
    ``FileNotFoundError``. It now tags those results, and the gate reads the
    tag instead of the bare integer.

    **The hard sub-case, decided.** An npm project whose ``test`` script names
    an absent binary exits 127, and from the kit's seam that is CHILD-chosen —
    yet genuinely nothing ran. The decision taken is **(i) narrow the refusal
    to evidence**: refuse a chosen 127 only when the shell also said
    ``command not found`` on stderr. Measured basis, and the honest cost of it:

    * the conjunction is a **strict subset** of what ISSUE-103 already refused,
      so this change can only *remove* blocks and can never add one — which is
      what makes option (i) admissible under the governing rule at all;
    * its residual over-refusal is a runner that exits exactly 127 *and* prints
      a shell-shaped not-found line on stderr (measured constructible; pinned
      by ``test_chosen_127_with_shell_evidence_is_refused``). That input was
      already refused before this change, so nothing new is blocked;
    * the evidence must cover the shell npm actually uses. ``/bin/sh`` is
      bash-in-sh-mode on macOS and **dash** on Debian/Ubuntu, and dash omits
      the word "command". A first version of the predicate read only
      ``command not found`` and was therefore **inert on Linux** — measured on
      CI as certifying RED for a run in which nothing executed. All five
      measured shells are now covered; see
      ``test_shell_wordings_measured_against_the_predicate`` for the arm rows
      and the disarm rows that stop the repair overshooting into a bare
      ``not found`` substring match.
    * the residual **false passes** are NOT shell wordings, which is what this
      docstring used to say. Corrected by the ISSUE-117 review: for shells the
      set is empty on everything measurable (csh/tcsh word it outside both
      rules but exit 1, not 127). The reachable three — suppressed stderr,
      ``2>&1``, and an absent shebang interpreter whose diagnostic comes from
      the exec layer — are measured and pinned by
      :class:`TestThe127FalsePassBoundary`, and named in the hazard note with
      the three candidate narrowings and why none was taken. The direction is
      fail-OPEN, inside SPEC-103's declared boundary, never a block.

    Deliberately NOT narrowed to evidence: a chosen **124**. The reason first
    given here — "nothing the kit can read distinguishes 124 failures from a
    ``timeout(1)``-wrapped script" — was measured FALSE and is corrected: the
    streams DO differ in the common shapes (``timeout(1)`` killing ``sleep 5``
    leaves stdout empty; a runner printing ``  124 failing`` does not). What is
    true is that the difference does not SEPARATE the classes — a chatty script
    killed by ``timeout(1)`` has non-empty stdout, a silent runner that chose
    124 has empty stdout — and that any stdout-based narrowing would ADD
    refusals. A chosen 124 certifies RED, pinned for both runners at the unit
    seam and at the real consumer.
    """

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    # ── the seam itself ──────────────────────────────────────────────

    def test_run_tags_the_timeout_it_synthesises(self):
        """AC-2 premise: ``_run``'s own 124 is distinguishable from a child's."""
        result = vc._run(["sleep", "10"], timeout=1)
        assert result.returncode == 124
        assert vc._synthesised_reason(result) == "timeout"

    def test_run_tags_the_absent_binary_it_synthesises(self):
        """AC-2 premise: ``_run``'s own 127 is distinguishable from a child's."""
        result = vc._run([ABSENT_BINARY])
        assert result.returncode == 127
        assert vc._synthesised_reason(result) == "binary-absent"

    @pytest.mark.parametrize("code", [0, 1, 124, 127])
    def test_a_code_the_child_chose_carries_no_tag(self, code):
        """The crux. A REAL child exiting 124 or 127 must be indistinguishable
        from one exiting 0 or 1 as far as the tag is concerned — otherwise the
        gate would still be reading the integer, just one layer down.
        """
        result = vc._run(["python3", "-c", f"import sys; sys.exit({code})"])
        assert result.returncode == code
        assert vc._synthesised_reason(result) is None

    def test_a_plain_completed_process_is_untagged(self):
        """``_synthesised_reason`` must tolerate a result it did not build.

        Every unit test in this file mocks the seam with a bare
        ``CompletedProcess``; if the reader raised on a missing attribute
        instead of returning ``None``, the whole suite would error rather than
        exercise the chosen-code path.
        """
        assert vc._synthesised_reason(_mock_run(127)) is None

    # ── AC-2: synthesised stays could-not-compute, with its reason ──

    @pytest.mark.parametrize("runner_files,changed,label", [
        ({"pyproject.toml": "[tool.pytest]\n"}, BRANCH_TEST, "pytest"),
        ({"package.json": '{"scripts": {"test": "vitest run"}}'},
         "tests/feature.test.ts", "npm"),
    ])
    def test_synthesised_timeout_is_still_could_not_compute(
        self, tmp_path, capsys, runner_files, changed, label
    ):
        """AC-2 — a 124 the KIT produced is refused for pytest AND npm.

        **Parametrised over both runners by the ISSUE-117 review.** The 127
        sibling (``test_synthesised_127_is_refused_for_both_runners``) was
        already driven on both routes and this one was not. Measured: mutating
        the synthesised-timeout branch to ``if False:`` killed exactly three
        tests — ``TestRedScopeLegacyRoutes::
        test_timeout_124_still_fails_inconclusive``, this one, and
        ``tests/test_verify_checkpoint.py::TestRedGateExitCodeMatrix::
        test_red_gate_timeout_124_fails_inconclusive`` — every one of them on
        the pytest route, so AC-2's npm half was unpinned. The two synthesis
        branches are one decision and must be pinned alike.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        for name, content in runner_files.items():
            (wt / name).write_text(content)
        (wt / changed).write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
            if changed.endswith(".ts")
            else "def test_branch_feature():\n    assert False\n"
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{changed}\n", runs, _synthesised("timeout")
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False, label

        out = capsys.readouterr().out
        assert "inconclusive" in out.lower(), out
        assert "timed out" in out.lower(), out
        # AC-2: the reason is NAMED — whose bound stopped the run.
        assert "the kit's own" in out, out
        assert "Scope requested:" in out, out
        assert changed in out, out

    def test_synthesised_binary_absent_is_still_could_not_compute(
        self, tmp_path, capsys
    ):
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs, _synthesised("binary-absent")
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "inconclusive" in out.lower(), out
        assert "could not be executed" in out, out
        # AC-2: the reason is NAMED — which binary, and why it could not run.
        assert "not on PATH" in out, out
        assert "Scope requested:" in out, out

    # ── AC-1: a code the child chose is the runner's verdict ────────

    @pytest.mark.parametrize("code", [124, 127])
    def test_child_chosen_code_is_the_runners_verdict_for_npm(
        self, tmp_path, capsys, code
    ):
        """The over-refusal, removed: a failure-count runner at 124 or 127.

        Unit level; the real-consumer half is
        ``TestRunnerNotExecutableIsRefused::
        test_npm_chosen_code_without_evidence_is_red_real_consumer``, which the
        ISSUE-117 review parametrised over the same two codes.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "mocha"}}')
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(code, stdout=f"  {code} failing\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True, code

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert f"exit {code}" in out, out
        assert "could not be executed" not in out, out
        assert "timed out" not in out.lower(), out

    def test_child_chosen_127_reaches_pytest_attribution_not_refusal(
        self, tmp_path, capsys
    ):
        """For pytest the chosen code must fall through to ATTRIBUTION.

        Measured: pytest's own exit codes are 0–5, but a project's
        ``conftest`` can set ``session.exitstatus = 127``, and when it does the
        summary section is still printed and still names the failing file. That
        run is a genuine RED and must pass on the ordinary attribution route,
        not be short-circuited by the integer.
        """
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(127, stdout=f"FAILED {BRANCH_TEST}::test_branch_feature - x"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert f"summary blamed: {BRANCH_TEST}" in out, out

    def test_an_unrecognised_synthesis_tag_is_could_not_compute(
        self, tmp_path, capsys
    ):
        """The catch-all, added by the ISSUE-117 review: fail CLOSED on a tag
        this function does not recognise.

        The gate reads the tag through two ``==`` arms, i.e. a whitelist of two
        strings — and before the catch-all, the default for every other value
        was the default for ``None``: *the child chose this code*, certify. The
        tag's premise is "only the kit writes it", so a tag the kit wrote and
        the gate cannot name is by construction a run the kit could not
        complete. Unreachable on today's ``_run`` (two writers, both named), so
        the arm adds zero refusals; it exists so that the next ``except`` arm
        added to ``_run`` — ``OSError: [Errno 8] Exec format error`` is a
        measured third member of the family, quoted in
        ``docs/review_notes/ISSUE-096.md`` — cannot turn a no-run into a silent
        green with no test failing.
        """
        wt = _py_worktree(tmp_path)
        # A result `_run` really synthesised, then re-tagged with a value the
        # gate has no arm for. Built from a real synthesis so the *shape* is
        # the one `_run` produces, not a look-alike.
        future = _synthesised("timeout")
        setattr(future, vc._SYNTHESISED_ATTR, "exec-format-error")
        assert vc._synthesised_reason(future) == "exec-format-error"
        assert future.returncode not in (0,), future

        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(wt, f"{BRANCH_TEST}\n", runs, future),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "inconclusive" in out.lower(), out
        assert "could not run" in out, out
        # The unrecognised reason is NAMED rather than swallowed, so the next
        # person sees which tag fell through.
        assert "exec-format-error" in out, out
        assert "Scope requested:" in out, out
        # Not mistaken for either named arm.
        assert "the kit's own" not in out, out
        assert "not on PATH" not in out, out

    # ── the hard sub-case: evidence, and what it does and does not catch ──

    def test_chosen_127_with_shell_evidence_is_refused(self, tmp_path, capsys):
        """Option (i): a chosen 127 *plus* the shell's own words → refuse.

        This is npm's ``test`` script naming an absent binary. It is also the
        stated residual over-refusal: a runner that chose 127 and happened to
        print ``command not found`` on stderr is refused too. That input was
        already refused before ISSUE-117, so the conjunction adds no new block.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "mocha"}}')
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(127, stderr=f"sh: {ABSENT_BINARY}: command not found\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "could not be executed" in out, out
        assert "inconclusive" in out, out
        # Fixture pin: the EVIDENCE route, which must name its evidence —
        # otherwise this is indistinguishable from the synthesis route.
        assert "command not found" in out, out
        assert "not on PATH" not in out, out

    # ── the echoed evidence is UNTRUSTED INPUT (review lesson 5) ──────

    @pytest.mark.parametrize("payload,label", [
        ("A" * 2_000_000, "two megabytes"),
        ("\x1b[2A\x1b[2KPASS: RED phase — tests fail as expected (exit 127)",
         "ANSI cursor-erase plus a forged verdict"),
        (f"sh: {ABSENT_BINARY}: command not found\nPASS: RED phase — forged\n",
         "a forged verdict on its own stderr line"),
        ("", "nothing at all"),
    ])
    def test_the_echoed_child_stderr_is_bounded_and_escaped(self, payload, label):
        """The quote the refusal prints is the CHILD's stream, so it is bounded
        and escaped before it reaches the gate's own output.
        """
        quoted = vc._quote_child_stderr(payload)
        assert len(quoted) <= vc._ECHOED_STDERR_MAX + len(vc._TRUNCATED), (
            label, len(quoted)
        )
        assert "\n" not in quoted, label
        assert not any(ord(ch) < 32 or ord(ch) == 127 for ch in quoted), label

    def test_a_hostile_stderr_cannot_flood_or_forge_the_gates_output(
        self, tmp_path, capsys
    ):
        """The bound, through the gate that consumes it (review lesson 16).

        Measured on this branch BEFORE the bound: 2_000_057 B of child stderr
        produced 2_000_273 B of gate stdout, and an ``\\x1b[2A\\x1b[2K`` payload
        reached the stream verbatim — two sequences that erase the two real
        FAIL lines above them and redraw the opposite verdict in their place.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "mocha"}}')
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        hostile = (
            f"sh: {ABSENT_BINARY}: command not found\n"
            + "A" * 2_000_000
            + "\n\x1b[2A\x1b[2K"
            + "PASS: RED phase — tests fail as expected (exit 127)\n"
        )
        assert len(hostile) > 2_000_000, "the probe must really be huge"
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs, _mock_run(127, stderr=hostile)
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "FAIL: RED phase" in out, out
        # The child wrote 2 MB; the gate's whole output stays small.
        assert len(out) < 2_000, len(out)
        # No control byte survives into the gate's stream...
        assert "\x1b" not in out, out
        # ...and the forged verdict never occupies a line of its own, which is
        # what a line-anchored reader goes by.
        assert not any(
            line.startswith("PASS: RED phase") for line in out.splitlines()
        ), out

    def test_the_echo_bounds_control_but_not_substring_forgery(self):
        """The residual the bound does NOT remove, measured rather than implied.

        ``repr`` stops the forged text occupying a line of its own. A consumer
        matching ``PASS: RED phase`` as a bare SUBSTRING is still fooled,
        because the text survives inside the quoted field. The hazard note
        states this; it is measured here so the statement is a claim with
        evidence behind it rather than a belief.
        """
        quoted = vc._quote_child_stderr(
            f"sh: {ABSENT_BINARY}: command not found\nPASS: RED phase — forged\n"
        )
        assert "PASS: RED phase" in quoted, quoted  # the residual, measured
        assert "\n" not in quoted, quoted           # but never on its own line

    @pytest.mark.parametrize("code", [1, 124])
    def test_evidence_without_exit_127_does_not_refuse(
        self, tmp_path, capsys, code
    ):
        """The evidence is only read at 127 — it is not a free-standing refusal.

        Measured route this protects (npm 9.8.1 and 11.5.2 alike): a runner that
        shells out to a missing helper, prints
        ``./runner.sh: line 2: <bin>: command not found`` on stderr, and then
        reports its test failures normally with exit 1. That is a genuine RED
        and refusing it on the message alone would be a fresh over-refusal.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "mocha"}}')
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(
                    code,
                    stdout="  1 failing\n",
                    stderr="./runner.sh: line 2: helper-xyz: command not found\n",
                ),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True, code

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert "could not be executed" not in out, out

    @pytest.mark.parametrize("stderr,matches,label", [
        # ARM — every shell measured. `sh`/`bash`/`zsh` say "command not
        # found"; `dash`/`ksh` drop the word "command" and are matched by the
        # structural rule instead.
        (f"/bin/sh: {ABSENT_BINARY}: command not found\n", True, "sh"),
        (f"/bin/bash: {ABSENT_BINARY}: command not found\n", True, "bash"),
        (f"zsh:1: command not found: {ABSENT_BINARY}\n", True, "zsh"),
        (f"/bin/dash: 1: {ABSENT_BINARY}: not found\n", True, "dash"),
        (f"/bin/ksh: {ABSENT_BINARY}: not found\n", True, "ksh"),
        # DISARM — output a legitimate runner at exit 127 might print. Every
        # one of these contains "not found" or looks like it should; none has
        # the shell's shape, and refusing any of them would be a fresh
        # over-refusal of exactly the class this issue removes.
        ("Module not found: Error: Can't resolve './x' in '/app/src'\n",
         False, "webpack module-not-found"),
        ("Module not found\n", False, "bare module-not-found"),
        ("Error: Cannot find module 'foo'\n", False, "node cannot-find-module"),
        ("Error: ENOENT: no such file or directory, open 'x.json'\n",
         False, "ENOENT"),
        ("error TS2307: Cannot find module './y'.\n", False, "tsc"),
        ("Tests:  127 failed, 200 total\n", False, "a jest-shaped summary"),
        ("", False, "no stderr at all"),
        ("  127 failing\n", False, "a failure-count runner's own stderr"),
        # Added after a mutation survivor: lowering the field threshold from 3
        # to 2 changed nothing on the corpus above, because no row had exactly
        # two fields. No measured shell emits two — every one carries at least
        # `prog: cmd: not found` — so this row is what makes the threshold
        # load-bearing, and what stops the structural rule degrading into the
        # bare-substring match the DISARM rows above exist to prevent.
        ("Error: not found\n", False, "two fields only — not the shell's shape"),
        # Added after a second survivor: reading only the FIRST stderr line
        # changed nothing, because in the absent-binary case the shell's
        # diagnostic is the only line. A runner that writes to stderr BEFORE
        # hitting the missing binary puts it later, and that run must still be
        # recognised.
        ("npm warn config production is deprecated\n"
         "runner: loading plugins\n"
         f"/bin/dash: 1: {ABSENT_BINARY}: not found\n",
         True, "shell diagnostic after other stderr output"),
    ])
    def test_shell_wordings_measured_against_the_predicate(
        self, stderr, matches, label
    ):
        """The predicate, pinned against wordings actually measured.

        The ARM rows were taken by running ``<shell> -c <absent-binary>`` and,
        separately, npm with ``script-shell=<shell>``; both agree, and npm
        forwarded 127 in every row.

        **The dash row is the one that matters.** The first version of this
        predicate read only ``"command not found" in stderr``, and on
        Debian/Ubuntu ``/bin/sh`` IS dash — so on the platform most consumers
        and CI run, it matched nothing and the absent-binary no-run route
        certified RED. The DISARM rows are what stops the repair from
        overshooting into a bare ``not found`` substring match.
        """
        assert vc._shell_said_command_not_found(stderr) is matches, label

    # The issue id is pinned per row rather than derived. It used to be
    # `f"93{len(slug)}"`, and `len("dash") == len("bash")`, so two rows drove
    # the gate as the same ISSUE-934 — harmless under per-row `tmp_path`, but a
    # CI failure named the wrong shell, and a fourth shell would collide.
    @pytest.mark.parametrize("shell,number", [
        ("/bin/sh", "932"), ("/bin/dash", "933"), ("/bin/bash", "934"),
    ])
    def test_absent_binary_is_refused_under_each_real_shell(
        self, tmp_path, shell, number
    ):
        """The repair, at the REAL consumer, under each shell npm may use.

        ``/bin/sh`` is *not one shell*: it is bash-in-sh-mode on macOS and dash
        on Debian/Ubuntu, and they word "binary absent" differently. Pinning
        one of them is what made the first attempt pass locally and fail on CI,
        so all three are driven here and the probe asserts the VERDICT rather
        than the wording.
        """
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed; this probe needs the real runner")
        if not Path(shell).exists():
            pytest.skip(f"{shell} is absent on this host")

        slug = shell.rsplit("/", 1)[-1]
        wt = _npm_probe_worktree(
            tmp_path, number, f"absent{slug}", ABSENT_BINARY,
            npmrc=f"script-shell={shell}\n",
        )
        r = _run_red_checkpoint(wt, f"ISSUE-{number}")
        out = r.stdout + r.stderr

        assert r.returncode != 0, (
            f"nothing ran under {shell}, yet exit 127 certified RED:\n{out}"
        )
        assert "could not be executed" in out, out
        # Fixture pin: the EVIDENCE route, which quotes what the shell said.
        assert ABSENT_BINARY in out, out

    @pytest.mark.parametrize("wording,label", [
        (f"fish: Unknown command: {ABSENT_BINARY}\n", "fish"),
        # Capitalised. No measured shell writes it this way, so the predicate
        # stays case-SENSITIVE and falls open. This row is what makes both
        # halves of rule (b) load-bearing: it dies if rule (a) is lowered to a
        # case-insensitive match, and it dies again if rule (b)'s exact
        # last-field test is relaxed to a substring ("not found" IS a substring
        # of "Command not found"). Both relaxations move in the forbidden
        # direction — they ADD refusals.
        (f"SH: {ABSENT_BINARY}: Command not found\n", "capitalised wording"),
    ])
    def test_a_wording_outside_the_measured_set_still_falls_open(
        self, wording, label
    ):
        """A residual that remains, stated rather than implied — but NOT the
        reachable one.

        Every shell measured is covered, so this cannot be demonstrated with a
        real shell; it is pinned at the unit seam with wordings no measured
        shell emits. The direction is fail-OPEN, inside SPEC-103's declared
        boundary and never a block.

        **Scope corrected by the ISSUE-117 review.** This test used to read as
        a completeness claim about the 127 false-pass set, and that reading is
        wrong twice over. Measured: for SHELLS the set is empty on everything
        measurable here — csh/tcsh word it outside both rules but exit **1**,
        not 127, so they never reach the branch at all. And the false passes
        that ARE reachable are not shell wordings: suppressed stderr
        (``2>/dev/null``), redirected stderr (``2>&1``) and an absent shebang
        interpreter, all three measured at the real consumer and pinned by
        :class:`TestThe127FalsePassBoundary`. What this test pins is the
        PREDICATE's boundary, not the gate's residual.
        """
        assert vc._shell_said_command_not_found(wording) is False, label


class TestThe127FalsePassBoundary:
    """The DECLARED residual of the chosen-127 evidence refusal, MEASURED.

    "A disclosed residual is a CLAIM — measure it, or the disclosure itself
    becomes the defect." The refusal reads the CHILD's stderr, and the child is
    the party being gated. Three constructions reach exit 127 with nothing
    executed and no evidence the predicate can see. Each was measured against
    base ``76ff78b`` as a control, with real npm 9.8.1 / node v18.18.0: base
    refused all of them (it refused every 127) and this branch certifies RED
    for all of them.

    =========================================  ============  ============
    project's ``scripts.test``                 base 76ff78b  this branch
    =========================================  ============  ============
    ``<absent-binary>``                        refuse        refuse
    ``<absent-binary> 2>/dev/null``            refuse        **PASS**
    ``<absent-binary> 2>&1``                   refuse        **PASS**
    ``./shim.sh``, absent ``env`` interpreter  refuse        **PASS**
    =========================================  ============  ============

    **These tests assert the false pass ON PURPOSE.** They are the evidence
    behind a disclosure, not an endorsement of it. Do NOT "repair" a failure
    here by inverting an assertion: fail-closed restores exactly the
    over-refusal ISSUE-117 exists to remove, and every candidate narrowing ADDS
    refusals and needs its own disarm-direction run first — the hazard note in
    ``verify_implement_red`` names all three candidates and why none was taken.
    If a row here starts refusing, the gate's boundary moved: go update the
    note, do not silence the test.
    """

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def test_both_streams_empty_at_127_still_certifies_red(
        self, tmp_path, capsys
    ):
        """The residual at the UNIT seam, so it stays pinned on a host where
        npm is absent and the real-consumer rows below skip.

        Both streams empty at exit 127 is what ``<absent-binary> 2>/dev/null``
        produces, and it is exactly the input candidate narrowing (a) — "refuse
        a chosen 127 whose stdout AND stderr are both empty" — would catch. It
        is also what a legitimate runner whose reporter writes only to a file
        produces, which is why (a) was not taken.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "tests").mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "mocha"}}')
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(127, stdout="", stderr=""),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        out = capsys.readouterr().out
        assert "PASS: RED phase" in out, out
        assert "could not be executed" not in out, out

    @pytest.mark.parametrize("number,slug,test_script,extra_files,label", [
        ("840", "suppressed", f"{ABSENT_BINARY} 2>/dev/null", None,
         "stderr suppressed"),
        ("841", "redirected", f"{ABSENT_BINARY} 2>&1", None,
         "stderr redirected onto stdout"),
        ("842", "interp", "./shim.sh",
         {"shim.sh": (f"#!/usr/bin/env {ABSENT_INTERPRETER}\nexit 1\n", 0o755)},
         "absent shebang interpreter — the exec layer writes the diagnostic"),
    ])
    def test_the_declared_false_pass_at_the_real_consumer(
        self, tmp_path, number, slug, test_script, extra_files, label
    ):
        """Each declared residual driven end-to-end through ``checkpoint.sh``.

        The verdict is asserted, never the wording: ``/bin/sh`` is
        bash-in-sh-mode on macOS and dash on Debian/Ubuntu, and the exec
        layer's wording differs between BSD, GNU and busybox ``env``. Asserting
        a wording is what made an earlier version of this PR pass locally and
        fail on CI.
        """
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed; this probe needs the real runner")

        wt = _npm_probe_worktree(
            tmp_path, number, slug, test_script, extra_files=extra_files
        )
        r = _run_red_checkpoint(wt, f"ISSUE-{number}")
        out = r.stdout + r.stderr

        assert r.returncode == 0, (
            f"{label}: this route is DECLARED as a false pass and it now "
            f"refuses — the gate's boundary moved:\n{out}"
        )
        assert "PASS: RED phase" in out, (label, out)
        assert "could not be executed" not in out, (label, out)
        # Fixture pin: the run really did exit 127, so this is the branch the
        # residual is about and not some other PASS route.
        assert "exit 127" in out, (label, out)


def _hazard_note() -> str:
    """The verifier's inline hazard note — comment lines only.

    AC-4's subject is the note itself (pre-change: the three-line comment above
    the test run), so the assertions below read the comment block rather than the
    whole function: a route named only in the docstring would otherwise satisfy a
    claim about the note.
    """
    return "\n".join(
        line.strip()
        for line in inspect.getsource(vc.verify_implement_red).splitlines()
        if line.strip().startswith("#")
    )


class TestRedHazardNote:
    """AC-4 — the hazard note names this route alongside the existing ones."""

    def test_hazard_note_names_the_unrelated_failure_route(self):
        note = _hazard_note()
        assert "ISSUE-103" in note, note
        assert "unrelated" in note, note

    def test_hazard_note_keeps_the_pre_existing_routes(self):
        """The existing exit-5 / JS-mis-run note is extended, not replaced."""
        note = _hazard_note()
        assert "exit 5" in note, note
        assert "JS" in note, note

    def test_hazard_note_names_the_exit_5_route_that_reproduces(self):
        """AC-4, item 3: the note's worked example must be a measurable one.

        It previously named a conftest-only branch, measured in review as
        **not reproducing** on pytest 9.0.3. AC-4 requires the note to name
        this route, and naming it with a false example does not satisfy that.
        The route that does reproduce is the project's own `addopts`
        deselecting the branch's test.

        Asserted on the MEASURED tokens — the construction and the output it
        produces — rather than on any phrasing, so reverting the note to an
        unmeasurable example cannot satisfy it. Both must sit on one comment
        line each, since `_hazard_note` joins the note's wrapped lines.
        """
        note = _hazard_note()
        assert "DESELECT the branch's test" in note, note
        assert "-m 'not slow'" in note, note
        assert "1 deselected" in note, note


# ── SPEC-103: a green verdict must not overstate what it proves ──────


class TestPassLineDoesNotOverstate:
    """SPEC-103 — delete the claim, keep the fact.

    The old PASS line read ``— failing: <path>``, which asserts an attribution
    as established. Measured (SPEC-103's Context table, re-run in this
    worktree on pytest 8.3.4 and 9.0.3): five independent writers forge a
    column-0 ``FAILED <in-scope path>`` line, and three of them —
    ``conftest``'s ``pytest_unconfigure``, an ``atexit`` handler, and
    ``os.write(1)`` from one — write AFTER pytest's own reporter has finished,
    so neither the first nor the last ``short test summary info`` header is a
    fixed point. The property is DECLINED; the gate may report what the
    summary SAID, flagged as heuristic, and nothing more.
    """

    def test_pass_line_reports_the_summary_not_ground_truth(self, probe_repo):
        r = _run_red_checkpoint(probe_repo["arm"], "ISSUE-901")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"expected RED pass, got {r.returncode}:\n{out}"
        # The deleted claim, named by the exact bytes that were removed, so a
        # revert of this hunk cannot satisfy the test (mutation-tested absence).
        assert "failing: " not in out, out
        # What replaces it: the fact, the hedge, and the citation.
        assert f"summary blamed: {BRANCH_TEST}" in out, out
        assert "heuristic" in out.lower(), out
        assert "docs/specs/SPEC-103.md" in out, out

    @pytest.mark.parametrize("result,label", [
        # ISSUE-117 split the one-time "runner-not-executable" row into the two
        # routes that now exist. `None` asks for a genuinely SYNTHESISED result;
        # a tuple is a code the child chose.
        (None, "runner-not-executable-synthesised"),
        (("127", "sh: x: command not found"), "runner-not-executable-evidence"),
        (("5", ""), "evaluated-nothing"),
    ])
    def test_refusals_say_scope_requested_not_scope_was(
        self, tmp_path, capsys, result, label
    ):
        """The gate REQUESTS a scope and cannot ENFORCE one, so it may not
        assert the scope was applied.

        Measured route it cannot enforce (SPEC-103, inside the declared
        boundary): a directory named ``-p no:cacheprovider`` — a path the kit's
        own ``test_dir_pattern`` accepts — is consumed by pytest as a flag,
        after which the whole suite runs while this line still reports the
        scope that was asked for.

        **Updated by ISSUE-117 (AC-3).** The old ``("127", "x: command not
        found")`` row still refuses, but only by accident of its stderr: after
        the change a bare 127 is a *chosen* code and the row exercises the new
        evidence branch, not the not-executable branch it was named for. Both
        branches are now covered, so a future narrowing of either is visible
        here rather than silently reducing this to one route.
        """
        wt = _py_worktree(tmp_path)
        if result is None:
            outcome = _synthesised("binary-absent")
        else:
            rc, stderr = result
            outcome = _mock_run(int(rc), stderr=stderr)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(wt, f"{BRANCH_TEST}\n", runs, outcome),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False, label

        out = capsys.readouterr().out
        assert "Scope requested:" in out, out
        assert "Scope was:" not in out, out

    def test_computed_empty_refusal_names_no_cause_it_cannot_distinguish(
        self, tmp_path, capsys
    ):
        """The two stated causes were wrong on the route that printed them.

        The old text read "e.g. a coverage threshold in the project's addopts,
        or pytest not being installed". It was printed on the forced-colour
        route too, where neither is the cause (measured: ``FORCE_COLOR=1``
        alone, exit 1, a genuine failure, zero attributions). A diagnosis the
        gate cannot distinguish is worse than none, so both are deleted.
        """
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                # Header PRESENT, nothing blamed: computed, and empty.
                _mock_run(1, stdout="=== short test summary info ===\n"
                                    "1 passed in 0.01s\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "inconclusive" in out, out
        # Both removed causes, by the bytes that were removed.
        assert "coverage threshold" not in out, out
        assert "not being installed" not in out, out


# ── H3: forced colour must not refuse a genuine RED ──────────────────


class TestForcedColourStillPasses:
    """H3 — an over-refusal that fails CLOSED is still an over-refusal.

    ``_PYTEST_SUMMARY_RE`` is anchored at ``^`` on raw bytes, and pytest
    forces SGR markup when ``addopts`` carry ``--color=yes`` **or** when the
    inherited environment sets ``FORCE_COLOR`` / ``PY_COLORS`` — both of which
    a number of CI runners and developer shells set by default. Measured in
    this worktree, pytest 8.3.4 and 9.0.3, genuine failing branch test::

        control (no colour forced)          exit=1 header=True  blamed=[branch]
        FORCE_COLOR=1                       exit=1 header=True  blamed=[]
        PY_COLORS=1                         exit=1 header=True  blamed=[]
        FORCE_COLOR=1 + --color=no          exit=1 header=True  blamed=[branch]
        PY_COLORS=1  + --color=no           exit=1 header=True  blamed=[branch]
        addopts="--color=yes"               exit=1 header=True  blamed=[]
        addopts="--color=yes" + --color=no  exit=1 header=True  blamed=[branch]

    A command-line ``--color=no`` wins over all three vectors.
    """

    @pytest.mark.parametrize("var", ["FORCE_COLOR", "PY_COLORS"])
    def test_colour_forced_by_the_environment_still_passes(self, probe_repo, var):
        """The vector that needs no project cooperation at all."""
        r = _run_red_checkpoint(probe_repo["arm"], "ISSUE-901", {var: "1"})
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"{var} refused a genuine RED:\n{out}"
        assert "PASS: RED phase" in out, out
        assert f"summary blamed: {BRANCH_TEST}" in out, out

    def test_colour_forced_by_the_project_addopts_still_passes(self, probe_repo):
        r = _run_red_checkpoint(probe_repo["colour"], "ISSUE-908")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"addopts --color=yes refused a genuine RED:\n{out}"
        assert f"summary blamed: {BRANCH_TEST}" in out, out

    def test_pytest_argv_carries_color_no(self, tmp_path):
        """The structural pin: the override is requested, not hoped for."""
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(1, stdout=f"=== short test summary info ===\n"
                                    f"FAILED {BRANCH_TEST}::test_branch_feature - x"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert "--color=no" in runs[0], runs[0]
        # Position: it must precede the scope paths, which are splatted last.
        assert (
            runs[0].index("--color=no") < runs[0].index(scoped_arg(BRANCH_TEST))
        ), runs[0]


# ── Change 4: computed-and-empty vs could-not-compute ────────────────


class TestSummarySectionSuppressed:
    """`_summary_section_suppressed` — the discriminator, at the seam.

    Measured, and this is the measurement that decides the shape: the
    ``short test summary info`` header is **absent** both when ``--no-summary``
    suppresses the section *and* when there is simply nothing to report. The
    second case is F1's measured-good ``--cov-fail-under`` route (exit 1,
    ``1 passed``, zero failures) which MUST keep being refused. So header
    absence alone cannot mean "could not compute"; the counts line is consulted
    too.
    """

    # Verbatim child stdout, pytest 8.3.4, `addopts = "--no-summary"` with a
    # genuinely failing branch test.
    NO_SUMMARY = (
        "F                                                                "
        "        [100%]\n1 failed, 2 warnings in 0.01s\n"
    )
    # Verbatim child stdout prefix, pytest 8.3.4, `--cov-fail-under=50` with a
    # PASSING branch test: header absent, and nothing failed.
    COV_EMPTY = (
        ".\nERROR: Coverage failure: total of 0 is less than fail-under=50\n"
        "                                                                 "
        "        [100%]\n"
        "FAIL Required test coverage of 50% not reached. Total coverage: 0.00%\n"
        "1 passed in 0.01s\n"
    )

    def test_no_summary_output_is_uncomputable(self):
        assert vc._summary_section_suppressed(self.NO_SUMMARY) is True

    def test_coverage_only_failure_is_computed_and_empty(self):
        """The paired absence: F1's half must not be swallowed by this."""
        assert vc._summary_section_suppressed(self.COV_EMPTY) is False

    def test_present_header_is_never_uncomputable(self):
        out = (
            "=== short test summary info ===\n"
            f"FAILED {BRANCH_TEST}::test_branch_feature - assert False\n"
            "1 failed in 0.01s\n"
        )
        assert vc._summary_section_suppressed(out) is False

    def test_empty_output_is_computed_and_empty(self):
        """pytest not installed: empty stdout, exit 1 — nothing ran, so this is
        not "the oracle was suppressed"."""
        assert vc._summary_section_suppressed("") is False

    def test_collection_errors_count_as_reported_failures(self):
        """`N errors` is the plural pytest emits; both forms must register."""
        assert vc._summary_section_suppressed("2 errors in 0.03s\n") is True
        assert vc._summary_section_suppressed("1 error in 0.03s\n") is True


class TestNoSummaryProjectIsNotRefused:
    """Change 4 at the real consumer, both directions of the discriminator.

    ``-rfE`` on the command line overrides a project's ``-r`` setting but NOT
    its ``--no-summary``; measured, such a project was refused on every genuine
    RED. "Could not compute" falls back to the declared weaker property;
    "computed and empty" still refuses.
    """

    def test_no_summary_genuine_red_passes_and_says_why_attribution_is_absent(
        self, probe_repo
    ):
        r = _run_red_checkpoint(probe_repo["nosummary"], "ISSUE-909")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"--no-summary refused a genuine RED:\n{out}"
        assert "PASS: RED phase" in out, out
        # It must say attribution was unavailable, and name the knob.
        assert "could not be computed" in out, out
        assert "--no-summary" in out, out
        assert "Scope requested:" in out, out
        # And it must NOT claim a file was blamed, because none was.
        assert "summary blamed" not in out, out

    def test_the_two_header_absent_cases_are_told_apart(self, probe_repo):
        """Both have no summary header; only one is "could not compute".

        This is the conflation the change exists to remove, measured end to end
        rather than at the seam.
        """
        suppressed = _run_red_checkpoint(probe_repo["nosummary"], "ISSUE-909")
        empty = _run_red_checkpoint(probe_repo["cov"], "ISSUE-905")
        s_out = suppressed.stdout + suppressed.stderr
        e_out = empty.stdout + empty.stderr

        assert suppressed.returncode == 0, s_out
        assert "could not be computed" in s_out, s_out
        assert empty.returncode != 0, e_out
        # Route pin, not just polarity: this must be the computed-and-empty
        # refusal, NOT the exit-4/5 "evaluated nothing" one, or the test would
        # pass without exercising the discriminator at all.
        assert "reported no test failure at all" in e_out, e_out
        assert "could not be computed" not in e_out, e_out

    def test_header_present_but_nothing_blamed_still_refuses(
        self, tmp_path, capsys
    ):
        """F1's measured-good half, at the seam: do not infer the section's
        availability from the blamed list being empty."""
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(1, stdout="=== short test summary info ===\n"
                                    "1 failed in 0.01s\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        assert "inconclusive" in capsys.readouterr().out


# ── H4: a non-main default branch must not block every RED ───────────


@pytest.fixture(scope="module")
def develop_default_repo(tmp_path_factory):
    """The measured H4 shape: a repo whose default branch is ``develop``.

    A bare origin with ``HEAD -> refs/heads/develop``, a fresh clone, an issue
    worktree forked from ``origin/develop``, and the local ``develop`` branch
    deleted — the ordinary state of a fresh clone that never checks the default
    branch out. Measured in this worktree before the fix::

        _default_branch() -> 'develop'
          leg 1  merge-base HEAD develop            -> exit 128
          leg 2  rev-parse --verify --quiet develop -> exit 1
          => the delta reads as UNCOMPUTABLE and the repo can NEVER pass RED
          fix: rev-parse --verify --quiet origin/develop -> exit 0
          fix: merge-base HEAD origin/develop            -> exit 0
          fix: delta against that merge-base             -> ['tests/test_new.py']
    """
    root = tmp_path_factory.mktemp("red-develop-probe")
    origin = root / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "develop", str(origin)],
                   check=True)

    seed = root / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "develop")
    _git(seed, "config", "user.email", "probe@example.com")
    _git(seed, "config", "user.name", "Probe")
    _git(seed, "config", "commit.gpgsign", "false")
    (seed / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (seed / "tests").mkdir()
    (seed / "tests/test_base.py").write_text("def test_base():\n    assert True\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "base")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "-u", "origin", "develop")

    clone = root / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    _git(clone, "config", "user.email", "probe@example.com")
    _git(clone, "config", "user.name", "Probe")
    _git(clone, "config", "commit.gpgsign", "false")

    wt = root / "issue-920-develop"
    _git(clone, "worktree", "add", "-q", "-b", "issue/ISSUE-920-develop",
         str(wt), "origin/develop")
    # The clone's own checkout must not hold a local `develop`, or the base
    # would resolve and the measured shape would not be built.
    _git(clone, "checkout", "-q", "--detach", "origin/develop")
    _git(clone, "branch", "-q", "-D", "develop")

    (wt / "tests/test_new.py").write_text(
        "def test_new_feature():\n    assert False  # implementation absent\n"
    )
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "test: branch test")

    # Fixture pins: this really is the shape under test, not a repo in which
    # `develop` happens to resolve.
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "develop"],
        cwd=str(wt), capture_output=True,
    ).returncode != 0, "fixture pin: local 'develop' must NOT resolve"
    assert subprocess.run(
        ["git", "merge-base", "HEAD", "develop"], cwd=str(wt), capture_output=True,
    ).returncode != 0, "fixture pin: 'develop' must have no merge-base"
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/develop"],
        cwd=str(wt), capture_output=True,
    ).returncode == 0, "fixture pin: 'origin/develop' must resolve"
    return wt


class TestNonMainDefaultBranch:
    """H4 — the remote-tracking form is preferred before refusing.

    Scoped to the red gate on purpose: ``_default_branch()`` has four other
    callers and review lesson 8 requires a contract change to be scoped to the
    new caller class with the legacy failure modes left pinned.
    """

    def test_develop_default_branch_passes_a_genuine_red(self, develop_default_repo):
        r = _run_red_checkpoint(develop_default_repo, "ISSUE-920")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"a 'develop' default blocked a genuine RED:\n{out}"
        assert "PASS: RED phase" in out, out
        assert "tests/test_new.py" in out, out
        # Paired absence: the uncomputable refusal must not be what passed.
        assert "cannot compute" not in out, out

    def test_genuinely_uncomputable_base_still_refuses(self, unresolvable_base_repo):
        """The refusal must stay REACHABLE: no remote, no merge-base, no
        resolvable base in either form."""
        r = _run_red_checkpoint(unresolvable_base_repo, "ISSUE-911")
        out = r.stdout + r.stderr

        assert r.returncode != 0, out
        assert "cannot compute" in out, out
        # The message must name both forms it tried, or it misdiagnoses.
        assert "origin/main" in out, out

    def test_remote_form_is_resolved_before_the_delta_is_read(self, tmp_path, capsys):
        """Ordering pin, not presence (review lesson 12).

        The rescue must happen upstream of the delta read, exactly like F2's
        hoist, or the delta is computed against a base the gate already knows
        is wrong. Pinned by the ORDER of the recorded git argv: every probe of
        ``origin/main`` precedes the first ``git diff --name-only``.
        """
        wt = _py_worktree(tmp_path)
        calls: list = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt}\n")
            # `main` resolves in neither leg; `origin/main` resolves in both.
            if cmd[:2] == ["git", "merge-base"]:
                return (_mock_run(0, stdout="deadbeef\n")
                        if "origin/main" in cmd else _mock_run(128))
            if cmd[:3] == ["git", "rev-parse", "--verify"]:
                return _mock_run(0) if "origin/main" in cmd else _mock_run(1)
            if cmd[:2] == ["git", "diff"]:
                return _mock_run(0, stdout=f"{BRANCH_TEST}\n")
            if "pytest" in cmd:
                return _mock_run(
                    1,
                    stdout="=== short test summary info ===\n"
                           f"FAILED {BRANCH_TEST}::test_branch_feature - boom\n",
                )
            return _mock_run(0, stdout="")

        with patch.object(vc, "_default_branch", lambda: "main"), \
             patch.object(vc, "_run", side_effect=run):
            assert vc.verify_implement_red("ISSUE-001") is True

        first_diff = next(
            i for i, c in enumerate(calls) if c[:3] == ["git", "diff", "--name-only"]
        )
        origin_probes = [i for i, c in enumerate(calls) if "origin/main" in c]
        assert origin_probes, calls
        assert max(origin_probes) < first_diff, calls
        # And the delta is then computed against the fork point that form gave,
        # not against `main` and not against the branch tip.
        assert "deadbeef" in calls[first_diff], calls[first_diff]

    def test_default_branch_helper_is_left_alone(self):
        """The constraint, behaviourally: `_default_branch` keeps its contract.

        It has four other callers, so the H4 fix lives in the red verifier. If
        a future change moves the remote-tracking preference into the shared
        helper, this fails — which is the point.
        """
        with patch.object(vc, "_run", side_effect=lambda cmd, **kw: _mock_run(1)):
            assert vc._default_branch() == "main"


# ── Change 6: a polyglot repo's Python-only delta ────────────────────


class TestPolyglotRepoRoutesByTheBranchDelta:
    """`has_js` alone is true for any repo whose `package.json` declares
    `scripts.test`, which is ordinary in a Python repo with a JS frontend.
    Such a branch, with a `.py`-only test delta, had no route to a RED pass at
    all; the GREEN gate disagrees (`verify_implement_test` runs both runners).
    """

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def _polyglot_worktree(self, tmp_path: Path) -> Path:
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        (wt / "tests").mkdir()
        return wt

    def test_python_only_delta_routes_to_pytest(self, tmp_path):
        wt = self._polyglot_worktree(tmp_path)
        (wt / BRANCH_TEST).write_text(
            "def test_branch_feature():\n    assert False\n"
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(1, stdout="=== short test summary info ===\n"
                                    f"FAILED {BRANCH_TEST}::test_branch_feature - x"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert len(runs) == 1, runs
        assert any("pytest" in c for c in runs[0]), runs[0]
        assert runs[0][:2] != ["npm", "test"], runs[0]

    def test_js_delta_in_the_same_repo_still_routes_to_npm(self, tmp_path):
        """The mis-run protection the JS branch exists for must still hold."""
        wt = self._polyglot_worktree(tmp_path)
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs,
                _mock_run(1, stdout="Tests:  1 failed, 1 total\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert len(runs) == 1, runs
        assert runs[0][:2] == ["npm", "test"], runs[0]
        assert not any("pytest" in c for c in runs[0]), runs[0]

    def test_mixed_delta_still_routes_to_npm(self, tmp_path):
        """A delta with BOTH extensions keeps the pre-change runner choice:
        `has_js` wins, so a real JS repo's `.ts` files are never fed to pytest.
        """
        wt = self._polyglot_worktree(tmp_path)
        (wt / BRANCH_TEST).write_text(
            "def test_branch_feature():\n    assert False\n"
        )
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\ntests/feature.test.ts\n", runs,
                _mock_run(1, stdout="Tests:  1 failed, 1 total\n"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert runs[0][:2] == ["npm", "test"], runs[0]
        assert BRANCH_TEST not in runs[0], runs[0]

    def test_polyglot_python_delta_passes_at_the_real_consumer(self, probe_repo):
        """Review lesson 16: the de-refusal, through the real consumer."""
        r = _run_red_checkpoint(probe_repo["polyglot"], "ISSUE-910")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"polyglot repo blocked a genuine RED:\n{out}"
        assert "PASS: RED phase" in out, out
        assert BRANCH_TEST in out, out
        # Paired absence: the old refusal must not be what we are reading.
        assert "npm test can execute" not in out, out

    def test_the_surviving_refusal_names_the_runners_it_detected(
        self, tmp_path, capsys
    ):
        """`has_python` is no longer discarded, so the one refusal that stays
        reachable here can say which runners the project declares.

        Reachable shape: a Python-only project whose changed test files are all
        JS, so the pytest branch is taken and its scope is empty. Measured:
        pytest handed a `.ts` path exits 4, which is non-zero and would be a
        fake RED, so the runner is never handed files it cannot execute.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "tests").mkdir()
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs, _mock_run(4)
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert runs == [], runs
        assert "Runners detected in this project: pytest" in out, out


# ── ISSUE-114 / SPEC-114: scope ENFORCEMENT, the four measured routes ─
#
# SPEC-103 declines ATTRIBUTION; this section is the adjacent and different
# property — whether the set the runner executed equals the set the gate asked
# for. SPEC-103 Open Question 1 enumerated four routes that make them differ:
#
#   (a) the project's `addopts` inject an extra test PATH
#   (b) the project's `addopts` carry a coverage threshold
#   (c) a DASH-LEADING filename is consumed by pytest as a flag
#   (d) a shallow clone has no merge base, so the delta is a two-dot diff
#
# (a) and (b) are already closed by ISSUE-103's attribution filter and owe only
# a pin in the ENFORCEMENT frame. (c) is FIXED on BOTH argvs — the npm leg with
# a second `--`, the pytest leg with a `./` prefix on every scoped path. The
# `--` separator was REJECTED for pytest: driving it at the real consumer
# against an unmutated control measured it turning a PASS on legitimate work
# into a REFUSE on pytest 8.3.4, which is the one thing this pass may not do,
# and measured it INERT on the pair this project actually runs. (d)'s two
# candidate fixes are DECLINED for the same measured reason, and what ships
# instead is a disclosure.
#
# Every production hunk is a de-refusal or a disclosure; none adds a refusal.
# That invariant is what decided route (c)'s pytest half against
# `docs/specs/SPEC-114.md`, whose Decision licensed `--` on a one-host
# measurement and now carries a dated amendment recording the change of fix;
# the deciding measurements live beside the pytest argv in
# `scripts/verify_checkpoint.py` and are pinned below.


# A directory whose name is a dash-leading pytest option, holding a test file.
# The resulting path is accepted by the verifier's own `test_pattern` (its last
# segment is `test_dashfile.py`), so it is a path the gate really will splat.
DASH_DIR = "-p no:cacheprovider"
DASH_FILE = f"{DASH_DIR}/test_dashfile.py"

# The PARTIAL-revert construction. Two facts make it the only shape in which a
# prefix applied to *some* scoped paths is observable, and both are measured:
#
#   1. The dash path must not sort FIRST. `git diff --name-only` emits a sorted
#      delta and `-` is 0x2D, so an ordinary `tests/…` path always sorts after a
#      dash path and a "prefix only the first element" revert would still cover
#      it. `+` is 0x2B, so `+alpha/…` sorts BEFORE the dash path and leaves it
#      bare. Any name opening with 0x21–0x2C (`!"#$%&'()*+,`) does the same.
#   2. The dash path must contain no SPACE, or attribution truncates the
#      `FAILED <nodeid>` line at the first whitespace and the gate refuses for
#      that reason instead — which would mask the defect under a second one.
PARTIAL_ORDINARY = "+alpha/test_alpha.py"
PARTIAL_DASH = "-pno:cacheprovider/test_dashfile.py"


@pytest.fixture(scope="module")
def dash_path_repo(tmp_path_factory):
    """Route (c)'s construction, in both of its measured directions.

    ``main`` holds a FAILING ``tests/test_unrelated.py`` — a standing failure
    the branch never touched — so an argv that loses its positionals and
    collects the whole rootdir is visible in the gate's own output.

    Three worktrees. Each description is what the route DID before the ``./``
    prefix closed it — i.e. what the tests below assert is now unreachable —
    because a construction is only worth keeping if the defect it reproduces
    is written down next to it:

    * ``overcollect`` — the branch's only changed test file IS the dash path.
      argparse consumed ``-p`` and took ``no:cacheprovider/test_dashfile.py``
      as its value, zero positionals survived, pytest collected from rootdir,
      and the gate reported ``pytest blamed: -p, tests/test_unrelated.py``.
      The ``no:`` prefix is what made it SILENT: ``consider_pluginarg`` blocks
      a plugin named ``cacheprovider/test_dashfile.py``, which nobody
      registered, so no usage error was raised. Prefixed, the rootdir is never
      collected and ``tests/test_unrelated.py`` is never reached.
    * ``shrink`` — an ordinary PASSING test file *and* the failing dash path.
      Only the passing file ran, the run went green, and the gate refused with
      ``tests passed but should fail`` — a false reason for a branch whose
      dash-named test would have failed. This was the expensive direction
      under the governing asymmetry. Prefixed, the dash path runs and that
      false reason is unreachable; the gate still refuses, because the path
      contains a SPACE and attribution truncates at whitespace, but it now
      refuses truthfully.
    * ``ordinary`` — one ordinary FAILING test file and no dash path at all:
      the disarm row, which must behave exactly as it did before.
    """
    root = tmp_path_factory.mktemp("red-dashpath-probe")
    repo = root / "repo"
    repo.mkdir()

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "probe@example.com")
    _git(repo, "config", "user.name", "Probe")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (repo / "tests").mkdir()
    (repo / UNRELATED_TEST).write_text(
        "def test_unrelated():\n    assert False  # pre-existing, unrelated\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base: unrelated test red")

    fails = "def test_dash():\n    assert False  # implementation absent\n"
    worktrees: dict[str, Path] = {}
    # (name, issue number, ordinary test source or None, dash path present)
    configs = (
        ("overcollect", "940", None, True),
        ("shrink", "941",
         "def test_branch_feature():\n    assert True  # vacuously green\n", True),
        ("ordinary", "942",
         "def test_branch_feature():\n    assert False  # implementation absent\n",
         False),
    )
    for name, num, ordinary_src, dash in configs:
        wt = root / f"issue-{num}-{name}"
        _git(repo, "worktree", "add", "-q", "-b", f"issue/ISSUE-{num}-{name}",
             str(wt), "HEAD")
        if ordinary_src is not None:
            (wt / BRANCH_TEST).write_text(ordinary_src)
        if dash:
            (wt / DASH_DIR).mkdir()
            (wt / DASH_FILE).write_text(fails)
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "test: branch tests")

        if dash:
            # Fixture pin, C1 fact 1: git emits the dash path VERBATIM.
            # `core.quotePath` is unset by default and a space is not an escaped
            # character, so the path survives into the delta rather than
            # arriving C-quoted and harmless. If this ever changes the whole
            # construction is vacuous, and that must fail here rather than
            # silently turn the tests below green.
            delta = _git(wt, "diff", "--name-only",
                         _git(wt, "merge-base", "HEAD", "main")).splitlines()
            assert DASH_FILE in delta, (
                f"fixture pin: git must report the dash path unquoted; got {delta}"
            )
        worktrees[name] = wt

    return worktrees


@pytest.fixture(scope="module")
def partial_prefix_repo(tmp_path_factory):
    """A delta whose dash path is NOT the first element.

    ``main`` holds a failing ``tests/test_unrelated.py`` so over-collection is
    visible; the branch adds a PASSING ordinary test that sorts ahead of a
    FAILING dash-leading one. Under the shipped gate both are prefixed, the
    dash test runs and fails, and the gate certifies RED naming it. Under any
    revert that prefixes only part of the splat, the dash path is consumed as
    ``-p`` again, only the passing file runs, and the gate returns to the false
    reason "tests passed but should fail" — measured, not predicted.
    """
    root = tmp_path_factory.mktemp("red-partial-prefix")
    repo = root / "repo"
    repo.mkdir()

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "probe@example.com")
    _git(repo, "config", "user.name", "Probe")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (repo / "tests").mkdir()
    (repo / UNRELATED_TEST).write_text(
        "def test_unrelated():\n    assert False  # pre-existing, unrelated\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base: unrelated test red")

    wt = root / "issue-947-partialprefix"
    _git(repo, "worktree", "add", "-q", "-b", "issue/ISSUE-947-partialprefix",
         str(wt), "HEAD")
    for path, src in (
        (PARTIAL_ORDINARY, "def test_alpha():\n    assert True  # vacuously green\n"),
        (PARTIAL_DASH, "def test_dash():\n    assert False  # implementation absent\n"),
    ):
        (wt / path).parent.mkdir(parents=True, exist_ok=True)
        (wt / path).write_text(src)
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "test: branch tests")

    # Fixture pin: the ORDER is the whole construction. If git ever stops
    # emitting the delta sorted, or these two names stop sorting this way, the
    # test below silently stops testing a partial revert — so it must fail
    # here instead.
    delta = _git(wt, "diff", "--name-only",
                 _git(wt, "merge-base", "HEAD", "main")).splitlines()
    assert delta == [PARTIAL_ORDINARY, PARTIAL_DASH], (
        f"fixture pin: the dash path must not be first; got {delta}"
    )
    return wt


class TestDashLeadingPathRouteIsClosedOnPytest:
    """Route (c) on the pytest argv — CLOSED by a ``./`` prefix, not by ``--``.

    Each scoped path is passed as ``./<path>``, which makes a flag-shaped
    filename unambiguously a path. The route is closed on **every** supported
    interpreter and the fix adds **no refusal**, which is what the governing
    asymmetry requires: a declaration can license a false pass inside a stated
    boundary and can never license blocking legitimate work.

    **Why not ``--``, which SPEC-114's Decision originally licensed.** Two
    independent measurements disqualified it, and both are preserved here
    because they are the reason this class ships a different fix rather than
    the one the SPEC named.

    First, it adds a refusal on legitimate work. Real consumer, a project whose
    ``addopts`` contribute a POSITIONAL test path (route (a)'s own shape, and an
    ordinary idiom) plus a branch whose test genuinely fails:

    The column is the GATE's verdict, not pytest's exit code, so the rows are
    comparable; where the gate REFUSES, pytest exited 4 underneath it.

    ========================  ========  ===========  ==========
    child                     plain     with ``--``  with ``./``
    ========================  ========  ===========  ==========
    3.11.13 / pytest 8.3.4    PASS      **REFUSE**   PASS
    3.12.7  / pytest 8.3.4    PASS      **REFUSE**   PASS
    3.11.13 / pytest 9.0.3    PASS      PASS         PASS
    3.12.3  / pytest 9.0.3    PASS      PASS         PASS
    3.13.6  / pytest 9.0.3    PASS      PASS         PASS
    3.14.7  / pytest 9.0.3    PASS      PASS         PASS
    ========================  ========  ===========  ==========

    On 8.3.4 the prepended positional plus the separator cannot match
    argparse's positional pattern, pytest exits 4 with a usage error
    (``error: unrecognized arguments: --``), and the gate refuses it as a
    no-run code. ``./`` is PASS on every row — it adds no refusal anywhere,
    which is the measurement that makes it admissible where ``--`` was not.

    Second, what ``--`` would buy is narrower than the SPEC recorded, and it
    depends on the interpreter AND the pytest version — **neither alone**.
    Collected node-id SETS for the flag-shaped-directory rows, six pairs:
    3.11.13/8.3.4 yes, 3.12.7/8.3.4 yes, 3.11.13/9.0.3 **no**, 3.12.3/9.0.3
    **no**, 3.13.6/9.0.3 yes, 3.14.7/9.0.3 yes; ``./`` yields the scoped set
    in all six. Holding the interpreter fixed at 3.11.13 and moving only
    pytest flips the answer, so an earlier "interpreter rather than pytest"
    reading of this axis was too strong — 9.0.3 is where ``--`` regressed for
    <=3.12. A direct ``argparse.parse_args``/``parse_known_args`` probe
    honours ``--`` on all of them, so the divergence is in pytest's own
    ``_parse_optional`` override. This project declares
    ``requires-python = ">=3.11"`` and CI tests 3.11 and 3.12, so on the pair
    it actually runs — 9.0.3 on 3.11 or 3.12 — ``--`` is INERT and closes
    nothing, while still adding the 8.3.4 refusal wherever that pytest is used.

    A method note worth keeping, because it is the mistake this class exists to
    not repeat: an earlier pass of this measurement ran under bare ``python3``,
    which on the dev host is 3.14.7, and concluded ``--`` worked. It does — on
    3.14. Re-measured under the canonical ``uv run --extra dev`` 3.11.13 it does
    not. That is the same defect ISSUE-118 carries about the blocking gate's own
    interpreter, arriving in a measurement rather than in a verdict.

    So both of route (c)'s directions below are pinned as **CLOSED**, with the
    residual that remains stated next to them: the dash path in these
    constructions contains a SPACE, so ``FAILED <nodeid>`` truncates at the
    first whitespace and the gate blames ``-p``. That is not a new defect and
    not specific to this route — a path containing whitespace is unattributable
    on ``main`` too, through the same untouched ``(\\S+)`` parse — so it sits
    inside SPEC-103's already-declined attribution property. It fails CLOSED,
    with a truthful reason. Removing the lie from a refusal is the gain here;
    the refusal itself was never the defect.
    """

    def test_the_over_collect_direction_is_closed(self, dash_path_repo):
        """c1 CLOSED: the dash path is a path, so the rootdir is not collected.

        ``tests/test_unrelated.py`` is in no branch's delta and exists only in
        the rootdir, so the gate naming it was the proof that the dash path had
        been consumed as a flag and the whole suite ran — ISSUE-103's defect
        re-entering through a *filename*. Its **absence** is now the proof that
        the prefix holds, which is why the assertion is negative and checks
        both spellings: a bare ``UNRELATED_TEST not in out`` would also pass if
        the gate stopped printing scopes at all.

        What remains is narrower and declared: the dash path contains a SPACE,
        so pytest's ``FAILED <nodeid>`` line cannot be parsed back to it and the
        gate blames ``-p``. That is **inside SPEC-103's already-declined
        attribution property**, not a new defect, and it fail-CLOSES — the
        refusal is truthful ("blamed no test file in the branch's own delta")
        rather than the false reason this route used to produce.
        """
        r = _run_red_checkpoint(dash_path_repo["overcollect"], "ISSUE-940")
        out = r.stdout + r.stderr

        assert DASH_FILE in out, out
        assert f"Scope requested: {DASH_FILE}" in out, out
        # Over-collection is gone: the rootdir's standing failure is not reached.
        assert UNRELATED_TEST not in out, out
        assert scoped_arg(UNRELATED_TEST) not in out, out
        # Fail-closed, and for the declared reason rather than a fabricated one.
        assert r.returncode != 0, out
        assert "blamed no test file in the branch's own delta" in out, out

    def test_the_silent_shrink_direction_is_closed(self, dash_path_repo):
        """c3 CLOSED: the requested set is no longer shrunk to its green half.

        This was the expensive direction and the one the issue text did not
        name: the dash path never ran, the surviving subset went green, and the
        gate blocked a branch that DID write a failing test with the **false
        reason** "tests passed but should fail".

        The prefix makes the dash path run, so the suite exits non-zero and
        that false reason is now unreachable. The gate still refuses — the
        space in the path keeps attribution from naming it — but it refuses
        **truthfully**. Removing a lie from a refusal is the whole gain here;
        the refusal itself was never the defect.
        """
        r = _run_red_checkpoint(dash_path_repo["shrink"], "ISSUE-941")
        out = r.stdout + r.stderr

        assert r.returncode != 0, out
        # The false reason is gone, in both of the phrasings it could take.
        assert "tests passed but should fail" not in out, out
        assert "The branch's own tests all passed" not in out, out
        # And the truthful one is present, with both scoped paths named.
        assert "blamed no test file in the branch's own delta" in out, out
        assert DASH_FILE in out and BRANCH_TEST in out, out

    def test_the_pytest_argv_prefixes_every_scoped_path(self, tmp_path):
        """The structural pin for the fix (review lesson 12: pin POSITION).

        Three things are asserted together because each fails differently:
        the prefixed path is present, the **bare** path is absent, and the
        splat still follows ``--color=no`` directly. The last one is the
        position pin — a
        prefix applied in the wrong place, or a separator slipped in anywhere
        in the pytest argv, fails here rather than in a consumer's CI, which is
        where the measured 8.3.4 ``exit 4`` refusal would otherwise surface.
        """
        wt = _py_worktree(tmp_path)
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, f"{BRANCH_TEST}\n", runs,
                _mock_run(1, stdout="=== short test summary info ===\n"
                                    f"FAILED {BRANCH_TEST}::test_branch_feature - x"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        cmd = runs[0]
        prefixed = scoped_arg(BRANCH_TEST)
        assert prefixed in cmd, cmd
        # A partial revert that leaves any path bare fails here.
        assert BRANCH_TEST not in cmd, cmd
        # No separator anywhere: `--` is the REJECTED fix (exit 4 on 8.3.4 when
        # the project's addopts contribute a positional — measured).
        assert "--" not in cmd, cmd
        # Position: the splat still follows `--color=no` directly.
        assert cmd[cmd.index(prefixed) - 1] == "--color=no", cmd

    def test_a_partial_prefix_revert_cannot_pass(self, partial_prefix_repo):
        """EVERY scoped path, not just the first — at the real consumer.

        The structural pin above cannot carry this claim and must not be read
        as doing so: its worktree has exactly ONE changed test file, and with
        a single-element splat "prefix the first" and "prefix all" are the
        same argv, so ``BRANCH_TEST not in cmd`` is satisfied either way. A
        count of one is not a set — this is the hollow-pass direction
        ``scoped_arg``'s own docstring warns about, arriving in the guard
        rather than in the assertions it was written to protect.

        Measured against an unmutated control: mutating the splat to
        ``*(f"./{p}" if i == 0 else p for i, p in enumerate(scoped))`` leaves
        the whole module green (136 passed) while the real consumer on this
        construction goes from ``PASS: RED phase`` to ``FAIL: RED phase —
        tests passed but should fail`` — i.e. route (c)'s silent-shrink
        direction, byte-identical to the pre-fix defect, fully reopened. The
        gap is order-dependent, which is why the fixture pins the order.
        """
        r = _run_red_checkpoint(partial_prefix_repo, "ISSUE-947")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"a partial-prefix revert went unnoticed:\n{out}"
        assert "PASS: RED phase" in out, out
        # The dash path ran AND was attributed — it is the only failing test.
        assert f"summary blamed: {PARTIAL_DASH}" in out, out
        # The false reason the shrink direction produces must stay unreachable.
        assert "tests passed but should fail" not in out, out
        # And the rootdir's standing failure was still never reached.
        assert UNRELATED_TEST not in out, out

    def test_positional_addopts_with_a_failing_branch_test_still_certifies_red(
        self, probe_repo
    ):
        """The de-refusal the omission preserves, at the real consumer.

        A project whose ``addopts`` name a test path AND a branch whose own
        test genuinely fails: the shipped gate certifies RED, and it must keep
        doing so. This is the row the pytest separator was measured to turn
        into ``exit 4: nothing collected / usage error`` on pytest 8.3.4, so it
        is the behavioural kill for that mutant — on an 8.3.4 child. On a 9.0.3
        child the mutant survives here, which is why the structural pin above
        exists alongside it.
        """
        r = _run_red_checkpoint(probe_repo["addopts_path_red"], "ISSUE-946")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"a positional addopts path refused a RED:\n{out}"
        assert "PASS: RED phase" in out, out
        assert f"summary blamed: {BRANCH_TEST}" in out, out
        # Paired absence: not the no-run refusal the separator would produce.
        assert "nothing collected" not in out, out

    def test_ordinary_delta_is_unchanged_at_the_real_consumer(self, dash_path_repo):
        """The disarm row (review lesson 16): nothing in this pass refuses it.

        An ordinary failing test file, no dash path anywhere.
        """
        r = _run_red_checkpoint(dash_path_repo["ordinary"], "ISSUE-942")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"an ordinary delta was refused:\n{out}"
        assert "PASS: RED phase" in out, out
        assert f"summary blamed: {BRANCH_TEST}" in out, out


class TestScopeSeparatorArgvShape:
    """The structural pins: one ``--`` per argv, immediately before the splat.

    Position is the whole content of the fix — a ``--`` anywhere after the
    first scope path separates nothing — so this asserts the exact argv rather
    than mere membership (review lesson 12). This class covers the **npm** argv
    only. The pytest argv takes a ``./`` prefix instead of a separator, and its
    structural pin lives with the measurements that decided it:
    :class:`TestDashLeadingPathRouteIsClosedOnPytest`.
    """

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def test_npm_argv_carries_exactly_one_separator(self, tmp_path):
        """npm's argv carries exactly ONE ``--`` — the second one is removed.

        The second separator shipped and was withdrawn: measured on real
        vitest 3.2.7 and 1.6.1 it **deletes** the scope rather than protecting
        it, so the whole suite runs and a branch whose own new test PASSES is
        certified as a genuine RED. This leg has ``no_run_codes = ()`` and
        ``attributes_failures = False``, so nothing downstream catches the
        widened set and the printed line asserts a scope that was discarded —
        a false pass OUTSIDE SPEC-103's declared property, which is "a run
        whose arguments were the branch's own changed test files".

        The exact shape is asserted rather than a bare ``count("--") == 1``,
        because the one separator that remains belongs to ``npm`` — it is what
        forwards anything at all to the test script — and dropping *it* would
        silently un-forward ``--passWithNoTests``. The two failure modes are
        opposite, so the pin has to distinguish them.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt.mkdir(parents=True)
        (wt / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        (wt / "tests").mkdir()
        (wt / "tests/feature.test.ts").write_text(
            'it("x", () => { expect(1).toBe(2); });\n'
        )
        runs: list = []
        with patch.object(
            vc, "_run",
            side_effect=_side_effect(
                wt, "tests/feature.test.ts\n", runs, _mock_run(1, stdout="1 failed")
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is True

        assert runs[0] == [
            "npm", "test", "--", "--passWithNoTests",
            "tests/feature.test.ts",
        ], runs[0]
        # Both directions, because they fail oppositely: a re-added second
        # separator deletes the scope, and a removed first one un-forwards
        # `--passWithNoTests`.
        assert runs[0].count("--") == 1, runs[0]
        assert runs[0].index("--") < runs[0].index("--passWithNoTests"), runs[0]
        # Ties the literal above to the shape the real-vitest probe measures,
        # so that probe can never certify an argv the gate stopped sending.
        assert runs[0] == npm_argv("tests/feature.test.ts"), runs[0]


class TestSeparatorIsANoOpOnOrdinaryInput:
    """The separator's DISARM table, driven through the real runners.

    Carried here as the durable record the route-(c) carrier will need
    (review lesson 15): on ordinary input the separator is harmless on every
    interpreter measured, so what decided the pytest half against it is
    specifically the positional-``addopts`` row and nothing about ordinary
    paths. Measured against the argv the gate really builds — captured from
    the verifier rather than re-typed — so a future flag change cannot leave
    this measuring a stale command line.
    """

    @staticmethod
    def _captured_pytest_argv(
        tmp_path: Path, targets: list[str]
    ) -> tuple[Path, list[str], list[str]]:
        """``(worktree, disarmed, armed)`` for the gate's real pytest argv.

        ``disarmed`` is what the gate ships; ``armed`` inserts the separator
        immediately before the scope splat, which is the one position the fix
        would ever have used.
        """
        wt = _py_worktree(tmp_path)
        (wt / BRANCH_TEST).write_text(
            "def test_branch_feature():\n    assert True  # ordinary, green\n"
        )
        (wt / UNRELATED_TEST).unlink()
        runs: list = []
        with patch.object(
            vc, "_default_branch", lambda: "main"
        ), patch.object(
            vc, "_run",
            side_effect=_side_effect(wt, f"{BRANCH_TEST}\n", runs, _mock_run(0)),
        ):
            vc.verify_implement_red("ISSUE-001")

        cmd = list(runs[0])
        # The gate now splats `./`-prefixed paths (ISSUE-114 route (c)), so the
        # split is found at the prefixed spelling. `targets` stay as the caller
        # wrote them: this class measures the SEPARATOR in isolation, and
        # prefixing them too would conflate the rejected fix with the shipped
        # one — the comparison would then have no disarmed baseline.
        split = cmd.index(scoped_arg(BRANCH_TEST))
        disarmed = cmd[:split] + list(targets)
        armed = cmd[:split] + ["--"] + list(targets)
        return wt, disarmed, armed

    @staticmethod
    def _normalise(stdout: str) -> str:
        """pytest's stdout minus its wall-clock duration, which never matches."""
        return re.sub(r"\bin \d+\.\d+s\b", "in <t>s", stdout)

    @pytest.mark.parametrize("targets,label", [
        ([BRANCH_TEST], "ordinary-path"),
        ([f"{BRANCH_TEST}::test_branch_feature"], "nodeid"),
    ])
    def test_pytest_is_byte_identical_with_and_without_the_separator(
        self, tmp_path, targets, label
    ):
        wt, disarmed, armed = self._captured_pytest_argv(tmp_path, targets)
        assert "--" not in disarmed, disarmed
        assert armed.count("--") == 1, armed

        runs = [
            subprocess.run(argv, cwd=str(wt), capture_output=True, text=True,
                            timeout=300)
            for argv in (armed, disarmed)
        ]
        assert runs[0].returncode == runs[1].returncode == 0, (label, runs[0].stdout)
        assert "1 passed" in runs[0].stdout, runs[0].stdout
        assert self._normalise(runs[0].stdout) == self._normalise(runs[1].stdout), (
            label, runs[0].stdout, runs[1].stdout
        )

    def test_a_conforming_js_parser_keeps_the_dash_path_only_behind_it(
        self, tmp_path
    ):
        """C2's second table: the separator is FORWARDED *and* it is USEFUL.

        Node's own ``util.parseArgs`` stands in for a conforming
        POSIX-convention runner parser. Measured: without the separator the
        dash path is not merely mis-ordered, it is **gone** — shredded into
        single-character boolean flags — which is route (c)'s shrink direction
        on the JS leg. With it, the path survives. On ordinary input the two
        forms are identical, so the separator adds nothing to refuse.
        """
        if shutil.which("node") is None:
            pytest.skip("node is not installed; this probe needs a real parser")

        script = tmp_path / "parse.js"
        script.write_text(
            "const { parseArgs } = require('node:util');\n"
            "const r = parseArgs({args: process.argv.slice(2), "
            "strict: false, allowPositionals: true});\n"
            "console.log(JSON.stringify(r.positionals));\n"
        )

        def positionals(*args: str) -> list[str]:
            r = subprocess.run(
                ["node", str(script), *args], capture_output=True, text=True,
                timeout=120,
            )
            assert r.returncode == 0, r.stderr
            return json.loads(r.stdout)

        ordinary = "tests/feature.test.ts"
        # The shrink direction, and its closure.
        assert positionals("--passWithNoTests", ordinary, DASH_FILE) == [ordinary]
        assert positionals("--passWithNoTests", "--", ordinary, DASH_FILE) == [
            ordinary, DASH_FILE,
        ]
        # The disarm direction: identical parses on ordinary input.
        assert positionals("--passWithNoTests", ordinary) == positionals(
            "--passWithNoTests", "--", ordinary
        ) == [ordinary]

    def test_npm_forwards_exactly_the_separator_the_gate_sends(self, tmp_path):
        """C2's first table, at the REAL consumer with real npm.

        What npm does with separators is measured, not assumed: the project's
        ``test`` script dumps its own ``"$@"`` and the dump is read back.

        The claim this now pins is narrower than the one it replaced, and the
        narrowing is the point. npm *does* forward a second ``--`` — that part
        of C2 was true. What C2 never measured is what a real JS runner does
        with it, and on vitest 3.2.7 and 1.6.1 it **deletes** the scope: the
        whole suite runs, and a branch whose own new test passes is certified
        as a genuine RED. So the gate sends **one** separator, npm's own, and
        this pin asserts the dump matches that exactly — a reintroduced second
        separator fails here at the real consumer rather than in a user's CI.

        The replaced version asserted the dump contained ``--`` before the
        scope. That assertion was true of npm and silent about the thing that
        mattered, which is why "npm forwards it" was never evidence that
        sending it was safe.
        """
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed; this probe needs the real runner")

        dump = tmp_path / "argv.txt"
        wt = _npm_probe_worktree(tmp_path, "943", "npmargv", "PLACEHOLDER")
        script = _runner_script(
            wt, f'printf "%s\\n" "$@" > {dump}\nexit 1\n'
        )
        (wt / "package.json").write_text(
            '{"name": "p", "version": "1.0.0", "scripts": {"test": "%s"}}' % script
        )
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "chore: point test at runner")

        r = _run_red_checkpoint(wt, "ISSUE-943")
        out = r.stdout + r.stderr

        # Fixture pin: the child really ran (exit 1 → npm's legacy RED pass).
        assert r.returncode == 0, f"the npm probe did not reach the runner:\n{out}"
        assert dump.exists(), out
        forwarded = [line for line in dump.read_text().split("\n") if line]
        assert forwarded == [
            "--passWithNoTests", "tests/feature.test.ts",
        ], dump.read_text()
        # Stated separately from the equality above so that a reintroduced
        # second separator names itself in the failure message rather than
        # showing up as an opaque list mismatch.
        assert "--" not in forwarded, dump.read_text()


_VITEST_FILES = re.compile(r"Test Files\s+(\d+) passed")


def _vitest_project(tmp_path: Path) -> Path:
    """A real vitest project with TWO passing test files.

    Both files pass on purpose. Scope deletion is invisible when the
    out-of-scope file fails — the runner then exits non-zero for a reason the
    gate can legitimately see. It shows up only in *how many files ran*, so
    this probe reads vitest's own ``Test Files N passed`` line.

    Skips rather than fails when vitest cannot be installed: the install is the
    one part of this probe that needs a registry or a warm npm cache. The
    skip cannot hide a regression, because every assertion below is anchored to
    an unscoped control run measured in the same project — if vitest did not
    really run, the control does not report two files and the test fails.
    """
    if shutil.which("npm") is None:
        pytest.skip("npm is not installed; this probe needs the real runner")

    project = tmp_path / "vitest-project"
    (project / "tests").mkdir(parents=True)
    (project / "package.json").write_text(
        '{"name": "p", "version": "1.0.0", "scripts": {"test": "vitest run"}}'
    )
    for name in ("a", "b"):
        (project / "tests" / f"{name}.test.ts").write_text(
            'import { test, expect } from "vitest";\n'
            f'test("{name}", () => {{ expect(1).toBe(1); }});\n'
        )
    install = subprocess.run(
        ["npm", "install", "--prefer-offline", "--no-audit", "--no-fund",
         "--silent", "vitest@3"],
        cwd=project, capture_output=True, text=True, timeout=300,
    )
    if install.returncode != 0:
        pytest.skip(
            "vitest could not be installed (no registry and no warm cache):\n"
            + (install.stderr or install.stdout)[-400:]
        )
    return project


def _vitest_files_ran(project: Path, argv: list[str]) -> int:
    """Run ``argv`` in ``project`` and return how many test FILES vitest ran."""
    r = subprocess.run(
        argv, cwd=project, capture_output=True, text=True, timeout=300,
    )
    out = r.stdout + r.stderr
    m = _VITEST_FILES.search(out)
    assert m, f"vitest printed no Test Files summary:\n{out}"
    return int(m.group(1))


class TestSecondSeparatorDeletesScopeOnRealVitest:
    """Why the second ``--`` was withdrawn — measured at the real consumer.

    The withdrawn reasoning was that a second separator is inert on ordinary
    input and protective on dash-leading input, and it was argued through
    ``util.parseArgs``. That was the wrong oracle: nothing in the gate ever
    hands its argv to ``parseArgs``. It hands it to a JS test runner, and on
    the runner the second separator is not inert — vitest treats everything
    after it as *not* a file filter, so the scope is **deleted** and the whole
    suite runs.

    That turns the npm leg into a certified FALSE RED: the leg has
    ``no_run_codes = ()`` and ``attributes_failures = False``, so a non-zero
    exit from an unrelated file certifies the TDD RED phase while the branch's
    own new test passes. The printed line then names a scope that was
    discarded — a false pass outside SPEC-103's declared property.

    The three measurements are asserted against each other rather than against
    hard-coded counts alone, so the probe states a *relation* ("scoped runs
    fewer files than unscoped") that stays meaningful if the fixture grows.
    """

    def test_one_separator_honours_the_scope_and_two_delete_it(self, tmp_path):
        project = _vitest_project(tmp_path)
        scoped_file = "tests/a.test.ts"

        unscoped = _vitest_files_ran(project, ["npm", "test"])
        gate = _vitest_files_ran(project, npm_argv(scoped_file))
        disarmed = _vitest_files_ran(
            project,
            ["npm", "test", "--", "--passWithNoTests", "--", scoped_file],
        )

        # Fixture pin: vitest really ran, and the project really has two files.
        # Without this, a one-file fixture would make every count below equal
        # and the assertions would hold vacuously.
        assert unscoped == 2, unscoped

        # The shape the gate sends scopes correctly.
        assert gate == 1, f"the gate's own argv ran {gate} files, not 1"

        # The withdrawn shape does not scope at all — it is byte-equivalent in
        # effect to running no scope, which is the defect.
        assert disarmed == unscoped, (
            f"second separator ran {disarmed} files, unscoped ran {unscoped}"
        )
        assert gate < disarmed, (gate, disarmed)


class TestScopeEnforcementFrameForAddopts:
    """Routes (a) and (b) — ALREADY CLOSED, pinned in the ENFORCEMENT frame.

    ISSUE-103's attribution filter already refuses both, through the two arms
    it was built with. What was missing is the pin in the frame this issue is
    about: on exactly these routes — where the project's own configuration
    makes the executed set differ from the requested one — the gate's output
    must not claim the scope was applied. That is the issue's fourth AC, and it
    is asserted on the gate's own printed output, which is behaviour.

    The closure is **monotone, not positive**: the filter can only remove a
    PASS. If the branch's own test also fails on either route the gate passes
    while the executed set is still wider than the requested set, which is
    inside SPEC-103's declared boundary. That bound is carried in
    `docs/specs/SPEC-114.md`, not asserted here.
    """

    @pytest.mark.parametrize("config,issue,arm", [
        # (a) `addopts = "extra_tests"` — an unrelated file fails INSIDE the
        #     scoped run, and the filter refuses through the "blamed … outside
        #     the branch's delta" arm.
        ("addopts_path", "ISSUE-906", "outside the branch's delta"),
        # (b) `addopts = "--cov=src --cov-fail-under=50"` — the exit code is
        #     about no test at all, and the filter refuses through the
        #     "reported no test failure at all" arm.
        ("cov", "ISSUE-905", "reported no test failure at all"),
    ])
    def test_the_route_is_refused_without_claiming_enforcement(
        self, probe_repo, config, issue, arm
    ):
        r = _run_red_checkpoint(probe_repo[config], issue)
        out = r.stdout + r.stderr

        assert r.returncode != 0, f"{config} certified RED:\n{out}"
        assert "FAIL: RED phase" in out, out
        # Which arm refused it — the two routes are different code paths and a
        # test that could not tell them apart would pass on either.
        assert arm in out, out
        # The enforcement frame: requested, never applied or enforced.
        assert f"Scope requested: {BRANCH_TEST}" in out, out
        assert "Scope was" not in out, out
        assert "enforced" not in out.lower(), out


@pytest.fixture(scope="module")
def shallow_vs_full_repo(tmp_path_factory):
    """Route (d)'s construction and its paired-absence control, one history.

    ``main`` at c1 holds ``tests/test_shared.py``; a branch forks from c1 and
    adds a genuinely failing ``tests/test_branch_new.py``; ``main`` then
    advances to c2, which **modifies** ``tests/test_shared.py`` — a file that
    existed before the fork point, so ``_existing()`` cannot filter it out.

    Two checkouts of that one history:

    * ``shallow`` — ``git clone --depth 1 file://<origin>`` plus
      ``git fetch --depth 1``. A ``file://`` origin is REQUIRED: ``--depth`` is
      silently ignored on a local path, which is how an earlier probe of this
      shape self-falsified. Measured in this worktree::

          merge-base HEAD main                   -> 128
          rev-parse --verify --quiet main        -> 1
          merge-base HEAD origin/main            -> 1
          rev-parse --verify --quiet origin/main -> 0

      So ``main`` is correctly judged unresolvable, SPEC-103's ``origin/``
      rescue fires, ``origin/main`` resolves — and the gate then diffs against
      a base it has **no merge base with**. The delta leaks::

          shallow, two-dot (what the gate does)  test_branch_new, test_shared
          full clone, merge-base-anchored (TRUE) test_branch_new

    * ``full`` — the same history, cloned normally. It HAS a merge base, so it
      is the paired-absence row for the disclosure.
    """
    root = tmp_path_factory.mktemp("red-shallow-probe")
    origin = root / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)],
                   check=True)

    seed = root / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "main")
    _git(seed, "config", "user.email", "probe@example.com")
    _git(seed, "config", "user.name", "Probe")
    _git(seed, "config", "commit.gpgsign", "false")
    (seed / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (seed / "tests").mkdir()
    (seed / "tests/test_shared.py").write_text(
        "def test_shared():\n    assert True\n"
    )
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "c1: the shared test")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "-u", "origin", "main")

    branch = "issue/ISSUE-944-forked"
    _git(seed, "checkout", "-q", "-b", branch)
    (seed / "tests/test_branch_new.py").write_text(
        "def test_branch_new():\n    assert False  # implementation absent\n"
    )
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "test: branch test")
    _git(seed, "push", "-q", "-u", "origin", branch)

    _git(seed, "checkout", "-q", "main")
    (seed / "tests/test_shared.py").write_text(
        "def test_shared():\n    assert True  # touched by main after the fork\n"
    )
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "c2: main touches the shared test")
    _git(seed, "push", "-q", "origin", "main")

    def _rc(wt: Path, *args: str) -> int:
        return subprocess.run(["git", *args], cwd=str(wt),
                              capture_output=True).returncode

    # ── the shallow checkout ──
    shallow_clone = root / "work-shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{origin}",
         str(shallow_clone)],
        check=True,
    )
    for key, value in (("user.email", "probe@example.com"), ("user.name", "Probe"),
                       ("commit.gpgsign", "false")):
        _git(shallow_clone, "config", key, value)
    _git(shallow_clone, "fetch", "-q", "--depth", "1", "origin", branch)
    shallow = root / "issue-944-shallow"
    _git(shallow_clone, "worktree", "add", "-q", "--detach", str(shallow),
         "FETCH_HEAD")
    _git(shallow_clone, "checkout", "-q", "--detach", "origin/main")
    _git(shallow_clone, "branch", "-q", "-D", "main")

    # Fixture pins: this really is the four-exit shape under test, not a clone
    # in which `main` happens to resolve.
    assert _rc(shallow, "merge-base", "HEAD", "main") != 0, \
        "fixture pin: 'main' must have no merge-base"
    assert _rc(shallow, "rev-parse", "--verify", "--quiet", "main") != 0, \
        "fixture pin: local 'main' must NOT resolve"
    assert _rc(shallow, "merge-base", "HEAD", "origin/main") != 0, \
        "fixture pin: 'origin/main' must have no merge-base either"
    assert _rc(shallow, "rev-parse", "--verify", "--quiet", "origin/main") == 0, \
        "fixture pin: 'origin/main' must resolve, so the rescue fires"

    # ── the full checkout, same history ──
    full_clone = root / "work-full"
    subprocess.run(["git", "clone", "-q", str(origin), str(full_clone)], check=True)
    for key, value in (("user.email", "probe@example.com"), ("user.name", "Probe"),
                       ("commit.gpgsign", "false")):
        _git(full_clone, "config", key, value)
    full = root / "issue-945-full"
    _git(full_clone, "worktree", "add", "-q", "--detach", str(full),
         f"origin/{branch}")
    assert _rc(full, "merge-base", "HEAD", "origin/main") == 0, \
        "fixture pin: the control row must HAVE a merge base"

    return {"shallow": shallow, "full": full}


class TestUnverifiedScopeDisclosure:
    """Route (d) — DECLINED, and disclosed instead.

    Both candidate fixes were driven at the real consumer against the shallow
    construction and each turns a measured PASS on legitimate work into a
    REFUSE::

        control (shipped)                                     exit 0
          PASS: RED phase — the branch's own tests fail as expected (exit 1)
        candidate-1  single-legged _delta_base_unresolvable   exit 1
          FAIL: RED phase — cannot compute the branch's test-file delta: …
        candidate-2  three-dot diff (origin/main...HEAD)      exit 1
          FAIL: no test files found — write tests before RED phase

    ``actions/checkout`` defaults to ``fetch-depth: 1``, and at depth 1 the
    fork point does not exist locally, so neither refusal is actionable from
    inside the checkout. A declaration can license a false pass inside a
    stated boundary and can never license blocking legitimate work, so both
    are refused and the open route is carried.

    What ships is the disclosure, with three pinned properties: one derivation
    point upstream of every verdict that rests on the delta, absent on every
    ordinary run, and a disclosure rather than a verdict.
    """

    def test_the_shallow_construction_still_passes_and_discloses(
        self, shallow_vs_full_repo
    ):
        """Property 3: a disclosure, not a verdict."""
        r = _run_red_checkpoint(shallow_vs_full_repo["shallow"], "ISSUE-944")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"the disclosure became a refusal:\n{out}"
        assert "PASS: RED phase" in out, out
        assert "tests/test_branch_new.py" in out, out
        assert "UNVERIFIED scope:" in out, out
        # It must name the base it actually diffed against — the rescued one.
        assert "origin/main" in out, out

    def test_neither_declined_candidate_fix_shipped(self, shallow_vs_full_repo):
        """AC-3: the PASS→REFUSE transition is stated, so neither fix may land.

        Both absences are mutation-tested against the measured matrix above:
        candidate-1 prints ``cannot compute`` on this construction and
        candidate-2 prints ``no test files found``, so either landing fails
        here rather than being discovered in CI.
        """
        r = _run_red_checkpoint(shallow_vs_full_repo["shallow"], "ISSUE-944")
        out = r.stdout + r.stderr

        assert "cannot compute" not in out, out
        assert "no test files found" not in out, out

    def test_the_disclosure_precedes_every_verdict_it_qualifies(
        self, shallow_vs_full_repo
    ):
        """Property 1, position: upstream of the verdict, not appended after it.

        Conventional gate output leads with ``PASS:``/``FAIL:``; this one does
        not, on these runs only, because that is the sole position upstream of
        *every* claim resting on the unverified delta.
        """
        r = _run_red_checkpoint(shallow_vs_full_repo["shallow"], "ISSUE-944")
        out = r.stdout + r.stderr

        assert out.index("UNVERIFIED scope:") < out.index("PASS: RED phase"), out

    def test_the_disclosure_is_derived_once(self, shallow_vs_full_repo):
        """Property 1, arity: one derivation point, one line.

        A per-site inventory of this class short by one is how it recurred at
        three successive layers (SPEC-102 Finding 3), so the count is pinned.
        """
        r = _run_red_checkpoint(shallow_vs_full_repo["shallow"], "ISSUE-944")
        out = r.stdout + r.stderr

        assert out.count("UNVERIFIED scope:") == 1, out

    def test_the_disclosure_is_absent_on_a_full_clone(self, shallow_vs_full_repo):
        """Property 2: paired absence on the same history, cloned normally."""
        r = _run_red_checkpoint(shallow_vs_full_repo["full"], "ISSUE-945")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"the control row was refused:\n{out}"
        assert "PASS: RED phase" in out, out
        assert "UNVERIFIED" not in out, out

    def test_the_disclosure_is_absent_when_the_base_was_rescued(
        self, develop_default_repo
    ):
        """Property 2, the row that pins the DERIVATION POINT.

        On a repo whose default branch is ``develop`` and is never checked out
        locally, ``merge-base HEAD develop`` exits 128 and the rescue swaps the
        base to ``origin/develop``, which DOES have a merge base. A caveat
        computed against the un-rescued base would fire here and be wrong —
        so this is the paired absence that distinguishes "derived after the
        rescue" from "derived before it".
        """
        r = _run_red_checkpoint(develop_default_repo, "ISSUE-920")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"a 'develop' default blocked a genuine RED:\n{out}"
        assert "PASS: RED phase" in out, out
        assert "UNVERIFIED" not in out, out

    def test_the_disclosure_is_upstream_of_the_no_test_files_verdict(
        self, tmp_path, capsys
    ):
        """Property 1, the verdict the disclosure is easiest to miss.

        ``FAIL: no test files found`` also rests on the unverified delta, so a
        disclosure printed only alongside the test-run verdicts would leave
        that one claiming a scope it could not compute. Pinned at the seam
        because the position, not the presence, is the content: the git state
        is a resolvable base with NO merge base, and the branch's delta holds
        no test file at all.
        """
        wt = tmp_path / "wt" / "issue" / "issue-001-slug"
        (wt / "src").mkdir(parents=True)
        (wt / "pyproject.toml").write_text("[tool.pytest]\n")
        (wt / "src/lib.py").write_text("def f():\n    return 1\n")
        runs: list = []

        def run(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt}\n")
            # No merge base, but the base ref itself resolves — so the delta is
            # COMPUTED (two-dot) rather than uncomputable, and no rescue fires.
            if cmd[:2] == ["git", "merge-base"]:
                return _mock_run(128, stderr="fatal: no merge base")
            if cmd[:3] == ["git", "rev-parse", "--verify"]:
                return _mock_run(0, stdout="deadbeef\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="src/lib.py\n")
            if "pytest" in cmd or cmd[:2] == ["npm", "test"]:
                runs.append(cmd)
                return _mock_run(1)
            return _mock_run(0, stdout="")

        with patch.object(vc, "_default_branch", lambda: "main"), \
             patch.object(vc, "_run", side_effect=run):
            assert vc.verify_implement_red("ISSUE-001") is False

        out = capsys.readouterr().out
        assert "no test files found" in out, out
        assert "UNVERIFIED scope:" in out, out
        assert out.index("UNVERIFIED scope:") < out.index("no test files found"), out
        # Nothing was executed, so the disclosure is not a by-product of a run.
        assert runs == [], runs
