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

Coverage layers:

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
import os
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
# A failing test outside `tests/`, so a project whose addopts inject this path
# adds a failure the branch never touched. Kept DISJOINT from the scoped argv on
# purpose: measured, pytest 8.3.4 deduplicates an addopts path that CONTAINS the
# scoped file (collecting only the file, exit 0) where 9.0.3 collects both, so an
# overlapping path would make the construction version-dependent.
EXTRA_TEST = "extra_tests/test_extra.py"


def _mock_run(returncode: int, stdout: str = "", stderr: str = ""):
    """Mirror of tests/test_verify_checkpoint.py's _mock_run helper."""
    result = subprocess.CompletedProcess([], returncode)
    result.stdout = stdout
    result.stderr = stderr
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
    #  pyproject override or None)
    configs = (
        ("arm", "901", green_base, fails, None),
        ("disarm", "902", red_base, passes, None),
        ("both", "903", red_base, fails, None),
        # A project whose own addopts suppress pytest's short summary. Measured:
        # `addopts = "-rN"` prints no `FAILED <nodeid>` line at all, so per-file
        # attribution only survives because the verifier requests `-rfE` itself.
        ("quiet", "904", green_base, fails,
         '[tool.pytest.ini_options]\naddopts = "-rN"\n'),
        # F1-c: exit 1 from a COVERAGE threshold, with zero test failures. The
        # branch's own test passes and covers nothing, so the scoped run prints
        # `1 passed` and `FAIL Required test coverage of 50% not reached` and
        # exits 1. Measured pre-fix: certified as RED.
        ("cov", "905", green_base, passes,
         '[tool.pytest.ini_options]\naddopts = "--cov=src --cov-fail-under=50"\n'),
        # F1-b: the project's own addopts inject an extra test PATH, so the
        # scoped run collects `extra_tests/` too. The branch's own test passes
        # and the pre-existing unrelated one there fails — AC-1's defect,
        # reached through a route scoping the argv alone does not close.
        # Measured pre-fix: certified as RED with "per-file attribution
        # unavailable".
        ("addopts_path", "906", green_base, passes,
         '[tool.pytest.ini_options]\naddopts = "extra_tests"\n'),
        # Item 3: the exit-5 route that actually reproduces. The project's own
        # addopts DESELECT the branch's test, so the scoped run collects it and
        # evaluates nothing: `1 deselected`, exit 5.
        ("deselect", "907", green_base,
         "import pytest\n\n\n@pytest.mark.slow\n"
         "def test_branch_feature():\n    assert False  # implementation absent\n",
         "[tool.pytest.ini_options]\n"
         "addopts = \"-m 'not slow'\"\nmarkers = [\"slow: marked slow\"]\n"),
    )
    for name, num, base, test_src, pyproject in configs:
        wt = root / f"issue-{num}-{name}"
        _git(repo, "worktree", "add", "-q", "-b", f"issue/ISSUE-{num}-{name}",
             str(wt), base)
        (wt / BRANCH_TEST).write_text(test_src)
        if pyproject:
            (wt / "pyproject.toml").write_text(pyproject)
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "test: branch test")
        worktrees[name] = wt

    return worktrees


def _run_red_checkpoint(wt: Path, issue_id: str):
    """Invoke the real consumer from inside ``wt``.

    ``CLAUDE_PLUGIN_ROOT`` is cleared so ``checkpoint.sh`` resolves its kit root
    from its own location — i.e. the tree this test ships in, not an installed
    plugin copy.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env["KIT_CHECKPOINT_TEST_TIMEOUT"] = "120"
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
        """AC-2: branch tests genuinely fail → exit 0, naming the branch file."""
        r = _run_red_checkpoint(probe_repo["arm"], "ISSUE-901")
        out = r.stdout + r.stderr

        assert r.returncode == 0, f"expected RED pass, got {r.returncode}:\n{out}"
        assert "PASS: RED phase" in out, out
        assert BRANCH_TEST in out, out
        # Fixture pin: a missing-pytest or empty-run child would exit non-zero
        # too, so assert the attribution actually came from a test failure.
        assert "failing: " in out, out

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
        assert f"failing: {BRANCH_TEST}" in out, out


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
        assert BRANCH_TEST in runs[0], runs[0]
        assert UNRELATED_TEST not in runs[0], runs[0]

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
        wt = _py_worktree(tmp_path)
        assert self._red(wt, f"{BRANCH_TEST}\n", _mock_run(124)) is False
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

    def test_hazard_note_states_the_npm_residual(self):
        """F1-d's residual must be written down, not just accepted in code.

        "A disclosed residual is a CLAIM" — the note previously claimed the
        "evaluated nothing" route was closed for every runner while npm's
        `no_run_codes` was empty and npm had no attribution requirement.
        """
        note = _hazard_note()
        assert "npm" in note, note
        # The specific mechanism, not just the word "npm": `no_run_codes` is
        # empty for npm, so npm's no-run exits are refused by nothing. Asserting
        # the token keeps this reading the residual paragraph rather than any
        # comment in the function that happens to mention npm (the superset
        # weakness M10 was strengthened for, one level smaller).
        assert "no_run_codes" in note, note


class TestRunnerNotExecutableIsRefused:
    """F1-d, the half that was closable: exit 127 must never certify RED.

    The rework scoped the attribution requirement to pytest and disclosed npm's
    empty ``no_run_codes`` as a residual. Team-lead measured that disclosure
    rather than accepting it ("a disclosed residual is a CLAIM") and it is only
    *partly* forced:

    ===========================================  ====  ===================
    measured route                               exit  safely refusable?
    ===========================================  ====  ===================
    npm, no ``test`` script ("nothing ran")         1  NO — collides
    npm, ``test`` script's binary absent          127  yes
    runner binary absent (``_run`` synthesises)   127  yes
    npm, a genuine JS test failure (GENUINE RED)    1  (must stay RED)
    ===========================================  ====  ===================

    npm uses exit 1 for BOTH ``Missing script: "test"`` and a real test
    failure, so refusing exit 1 would refuse every JS RED — that route is a
    genuine design limit. Exit **127** collides with nothing, so leaving it
    unrefused meant "the runner was never executed" certified the TDD RED
    phase. It is now refused for BOTH runners.
    """

    def test_npm_exit_127_real_consumer(self, tmp_path):
        """The disarm direction at the REAL consumer, with REAL npm (lesson 16).

        The project's ``test`` script names a binary that does not exist, which
        is a measured 127 from npm itself — not a synthesised one. Pre-fix this
        certified RED having executed no test whatsoever.
        """
        if shutil.which("npm") is None:
            pytest.skip("npm is not installed; this probe needs the real runner")

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "probe@example.com")
        _git(repo, "config", "user.name", "Probe")
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / "package.json").write_text(
            '{"name": "p", "version": "1.0.0", '
            '"scripts": {"test": "definitely-not-a-real-binary-xyz"}}'
        )
        (repo / "tests").mkdir()
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")

        wt = tmp_path / "issue-930-npm127"
        _git(repo, "worktree", "add", "-q", "-b", "issue/ISSUE-930-npm127",
             str(wt), "HEAD")
        # git does not track empty directories, so `tests/` is absent from the
        # checkout even though it exists in the source repo.
        (wt / "tests").mkdir(exist_ok=True)
        (wt / "tests" / "feature.test.ts").write_text(
            'it("branch feature", () => { expect(1).toBe(2); });\n'
        )
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "test: branch test")

        r = _run_red_checkpoint(wt, "ISSUE-930")
        out = r.stdout + r.stderr

        assert r.returncode != 0, f"exit 127 certified RED:\n{out}"
        assert "FAIL: RED phase" in out, out
        assert "could not be executed" in out, out
        assert "inconclusive" in out, out
        # Fixture pin: this really is the 127 route and not some other refusal.
        assert "127" in out, out
        assert "tests/feature.test.ts" in out, out

    @pytest.mark.parametrize("runner_files,changed,label", [
        ({"pyproject.toml": "[tool.pytest]\n"}, BRANCH_TEST, "pytest"),
        ({"package.json": '{"scripts": {"test": "vitest run"}}'},
         "tests/feature.test.ts", "npm"),
    ])
    def test_exit_127_is_refused_for_both_runners(
        self, tmp_path, capsys, runner_files, changed, label
    ):
        """127 is refused for pytest AND npm — the tightening is not runner-local.

        Unit-level because making a real binary disappear is not constructible
        at the real consumer for pytest; the npm half is additionally covered
        through the real consumer above.
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
                wt, f"{changed}\n", runs,
                # Exactly what `_run` synthesises for a missing binary.
                _mock_run(127, stdout="", stderr="x: command not found"),
            ),
        ):
            assert vc.verify_implement_red("ISSUE-001") is False, label

        out = capsys.readouterr().out
        assert "could not be executed" in out, out
        assert "inconclusive" in out, out
        assert changed in out, out

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
        """
        note = _hazard_note()
        assert "no_run_codes" in note, note
        assert "127" in note, note
        # The collision is the reason exit 1 is NOT refused; it must be stated.
        assert "exits 1 for BOTH" in note or "exit 1 would" in note, note


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
