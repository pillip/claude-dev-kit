"""Tests for scripts/worktree.sh — git worktree lifecycle manager."""

import collections
import os
import shutil
import subprocess
import pytest

_HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(_HERE, "..", "scripts", "worktree.sh")
SETUP_SCRIPT = os.path.join(_HERE, "..", "scripts", "wt_setup.sh")
README = os.path.join(_HERE, "..", "README.md")

#: ``timeout``/``gtimeout`` is GNU coreutils and is absent on a stock macOS.
#: ``worktree.sh`` degrades to an unbounded remote consultation there, so the
#: wall-clock test is skipped rather than asserted on such a runner.
_TIMEOUT_BIN = shutil.which("timeout") or shutil.which("gtimeout")


def _env() -> dict:
    """Hermetic subprocess env for the worktree scripts.

    Both knobs are cleared at the subprocess boundary — the one seam through
    which they can reach the script under test — rather than via an autouse
    ``conftest.py`` fixture, so no other test file can reintroduce them:

    * ``CLAUDE_PLUGIN_ROOT`` — ``wt_setup.sh`` resolves its sibling scripts
      through it, so a developer who exports it (dogfooding an installed
      plugin) would otherwise exercise a *different* ``worktree.sh`` than the
      one under test.
    * ``KIT_WORKTREE_FETCH_TIMEOUT`` — a small value exported in a shell would
      turn a healthy remote resolution into a timeout refusal. Tests that need
      it pass it explicitly through ``**envvars``.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("KIT_WORKTREE_FETCH_TIMEOUT", None)
    return env


def _run(args: list[str], cwd: str, **envvars: str) -> subprocess.CompletedProcess:
    env = _env()
    env.update(envvars)
    return subprocess.run(
        ["bash", SCRIPT, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def _run_setup(branch: str, cwd: str, **envvars: str) -> subprocess.CompletedProcess:
    """Drive the REAL consumer shape: ``WT="$(bash scripts/wt_setup.sh <branch>)"``."""
    env = _env()
    env.update(envvars)
    return subprocess.run(
        ["bash", SETUP_SCRIPT, branch],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def _git(repo: str, *args: str) -> str:
    """Run git in ``repo`` and return stripped stdout; raises on failure."""
    return subprocess.run(
        ["git", "-C", repo, *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_rc(repo: str, *args: str) -> int:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    ).returncode


def _has_local_branch(repo: str, branch: str) -> bool:
    return _git_rc(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}") == 0


@pytest.fixture()
def git_repo(tmp_path):
    """Create a minimal git repo with an initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", repo], check=True, capture_output=True)
    # Configure a local identity so the fixture works on CI runners with no
    # global git identity (matches the pattern in test_hook_runner.py).
    subprocess.run(
        ["git", "-C", repo, "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo, "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo, "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return repo


#: What ``remote_repo`` hands a test. ``repo`` is the working clone the script
#: is invoked in; ``origin`` is the bare repo it was cloned from.
RemoteRepo = collections.namedtuple(
    "RemoteRepo", "repo origin branch remote_sha main_sha"
)

REMOTE_ONLY_BRANCH = "issue/ISSUE-999-x"


@pytest.fixture()
def remote_repo(tmp_path):
    """A bare ``origin`` plus a clone, with one branch that exists ONLY on the remote.

    Reproduces the exact state ``cmd_remove``'s unconditional ``git branch -D``
    leaves behind after a review-phase cleanup: ``refs/remotes/origin/<branch>``
    is present and carries the reviewed commits, ``refs/heads/<branch>`` is gone.
    That is the precondition for ISSUE-083's silent re-root.

    Entirely local (``git init --bare`` + ``git clone`` of a filesystem path) —
    nothing here touches the network and the live repo is never used as a
    fixture. Mirrors ``git_repo``'s local-identity config for CI runners with
    no global git identity.
    """
    origin = str(tmp_path / "origin.git")
    # Deliberately NOT tmp_path/"repo" — `git_repo` owns that name, and one test
    # requests both fixtures.
    repo = str(tmp_path / "clone")

    subprocess.run(["git", "init", "--bare", origin], check=True, capture_output=True)
    # Pin the bare repo's default branch without relying on `git init -b`
    # (git >= 2.28) or on the runner's init.defaultBranch.
    _git(origin, "symbolic-ref", "HEAD", "refs/heads/main")

    subprocess.run(["git", "clone", origin, repo], check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    _git(repo, "commit", "--allow-empty", "-m", "init")
    _git(repo, "push", "-u", "origin", "main")
    main_sha = _git(repo, "rev-parse", "main")

    _git(repo, "checkout", "-b", REMOTE_ONLY_BRANCH)
    _git(repo, "commit", "--allow-empty", "-m", "reviewed work")
    _git(repo, "push", "-u", "origin", REMOTE_ONLY_BRANCH)
    remote_sha = _git(repo, "rev-parse", REMOTE_ONLY_BRANCH)

    _git(repo, "checkout", "main")
    # The defect's precondition, created exactly the way cmd_remove creates it.
    _git(repo, "branch", "-D", REMOTE_ONLY_BRANCH)

    assert not _has_local_branch(repo, REMOTE_ONLY_BRANCH)
    assert (
        _git_rc(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{REMOTE_ONLY_BRANCH}")
        == 0
    )
    assert remote_sha != main_sha

    return RemoteRepo(
        repo=repo,
        origin=origin,
        branch=REMOTE_ONLY_BRANCH,
        remote_sha=remote_sha,
        main_sha=main_sha,
    )


class TestRoot:
    def test_returns_repo_root(self, git_repo):
        result = _run(["root"], git_repo)
        assert result.returncode == 0
        assert result.stdout.strip() == os.path.realpath(git_repo)


class TestCreate:
    def test_creates_worktree_and_returns_path(self, git_repo):
        result = _run(["create", "feature/foo-bar"], git_repo)
        assert result.returncode == 0
        wt_path = result.stdout.strip()
        assert wt_path.endswith(".worktrees/feature-foo-bar")
        assert os.path.isdir(wt_path)

    def test_idempotent_create(self, git_repo):
        r1 = _run(["create", "feature/foo"], git_repo)
        r2 = _run(["create", "feature/foo"], git_repo)
        assert r1.stdout.strip() == r2.stdout.strip()

    def test_slug_conversion(self, git_repo):
        result = _run(["create", "issue/ISSUE-001-login"], git_repo)
        assert result.returncode == 0
        assert "issue-ISSUE-001-login" in result.stdout

    # ---------------------------------------------------------------- ISSUE-083
    # Branch resolution: refs/heads -> refs/remotes/origin -> base.
    # The harm these pin is a *silent* re-root of a reviewed branch onto the
    # caller's current HEAD, so the refusal tests below are the load-bearing
    # half — a change that only pins the happy path reproduces the fail-open
    # pattern verbatim.

    def test_remote_only_branch_head_equals_remote_tip(self, remote_repo):
        """TC-083a (AC-1): resolved by SHA EQUALITY against the remote tip.

        Also kills mutant (ii) — an upstream set while HEAD stays at the
        default base passes an upstream-only assertion and fails this one.
        """
        result = _run(["create", remote_repo.branch], remote_repo.repo)
        assert result.returncode == 0, result.stderr
        wt_path = result.stdout.strip()
        head = _git(wt_path, "rev-parse", "HEAD")
        assert head == remote_repo.remote_sha
        assert head != remote_repo.main_sha

    def test_remote_only_branch_tracks_origin(self, remote_repo):
        """TC-083a (AC-1): upstream is origin/<branch>. Kills mutant (iii)."""
        result = _run(["create", remote_repo.branch], remote_repo.repo)
        assert result.returncode == 0, result.stderr
        wt_path = result.stdout.strip()
        upstream = _git(wt_path, "rev-parse", "--abbrev-ref", "HEAD@{upstream}")
        assert upstream == f"origin/{remote_repo.branch}"

    def test_wt_setup_composite_pin_on_remote_only_branch(self, remote_repo):
        """TC-083b (AC-1): the real consumer shape ``WT="$(bash wt_setup.sh …)"``.

        ``wt_setup.sh`` is a thin delegate, so the fix must reach it unaided;
        the ISSUE-078 helper/consumer disagreement is the precedent for pinning
        the consumer rather than only the helper.
        """
        result = _run_setup(remote_repo.branch, remote_repo.repo)
        assert result.returncode == 0, result.stderr
        wt = result.stdout.strip()
        assert wt.endswith(".worktrees/issue-ISSUE-999-x")
        assert os.path.isdir(wt)
        assert _git(wt, "rev-parse", "HEAD") == remote_repo.remote_sha
        assert (
            _git(wt, "rev-parse", "--abbrev-ref", "HEAD@{upstream}")
            == f"origin/{remote_repo.branch}"
        )
        marker = os.path.join(wt, ".claude-kit", "freeze-dir.txt")
        assert open(marker, encoding="utf-8").read().strip() == wt

    @pytest.mark.parametrize(
        "breakage,reason",
        [
            ("remove-origin-dir", "reason=remote-unreachable"),
            ("rename-origin-dir", "reason=remote-unreachable"),
            ("deconfigure-origin", "reason=no-remote-configured"),
            ("delete-remote-branch", "reason=no-such-remote-ref"),
        ],
    )
    def test_unreachable_remote_refuses_instead_of_rerooting(
        self, remote_repo, breakage, reason
    ):
        """TC-083c (AC-2): the DISARM direction — refuse, do not fall through.

        Each breakage leaves ``refs/remotes/origin/<branch>`` in place (git keeps
        remote-tracking refs when the remote's path or config disappears — pinned
        by the ``show-ref`` assertion below), so the script still knows the branch
        is remote-only but can no longer establish its tip.
        """
        repo = remote_repo.repo
        if breakage == "remove-origin-dir":
            shutil.rmtree(remote_repo.origin)
        elif breakage == "rename-origin-dir":
            os.rename(remote_repo.origin, remote_repo.origin + ".moved")
        elif breakage == "deconfigure-origin":
            _git(repo, "config", "--remove-section", "remote.origin")
        elif breakage == "delete-remote-branch":
            _git(remote_repo.origin, "branch", "-D", remote_repo.branch)

        # The remote-only SIGNAL must survive the breakage, otherwise this
        # scenario would collapse into AC-4's genuinely-new-branch case.
        assert (
            _git_rc(
                repo,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/remotes/origin/{remote_repo.branch}",
            )
            == 0
        )

        result = _run(["create", remote_repo.branch], repo)

        assert result.returncode != 0
        assert result.stdout.strip() == ""
        assert remote_repo.branch in result.stderr
        assert reason in result.stderr
        assert not _has_local_branch(repo, remote_repo.branch)
        assert not os.path.isdir(
            os.path.join(os.path.realpath(repo), ".worktrees", "issue-ISSUE-999-x")
        )

    def test_wt_setup_refusal_yields_no_path_and_no_tree(self, remote_repo):
        """TC-083d (AC-2) through the REAL consumer. Kills mutant (iv).

        A refusal downgraded to a warning that still prints a path would let
        ``WT="$(bash scripts/wt_setup.sh …)"`` proceed into a silently
        re-rooted tree — exactly the ISSUE-078 near-miss.
        """
        shutil.rmtree(remote_repo.origin)
        result = _run_setup(remote_repo.branch, remote_repo.repo)

        assert result.returncode != 0
        assert result.stdout.strip() == ""
        assert "reason=remote-unreachable" in result.stderr
        assert not _has_local_branch(remote_repo.repo, remote_repo.branch)
        assert not os.path.isdir(
            os.path.join(
                os.path.realpath(remote_repo.repo), ".worktrees", "issue-ISSUE-999-x"
            )
        )

    @pytest.mark.skipif(
        _TIMEOUT_BIN is None,
        reason="no timeout/gtimeout binary — worktree.sh degrades to an unbounded consult",
    )
    def test_remote_consultation_timeout_is_a_distinct_outcome(self, remote_repo):
        """TC-083e (AC-2): a HANGING remote is a named refusal, not a hang.

        ``offline`` is one of the refusal cases the issue names, and an offline
        remote does not fail fast — it stalls. Exit 124 is therefore classified
        separately from an unreachable remote, and the message names the knob
        that remediates it (review lesson: print the knob in the failure it fixes).
        The ``ext::`` transport gives a deterministic, fully offline stall.
        """
        repo = remote_repo.repo
        _git(repo, "config", "protocol.ext.allow", "always")
        _git(repo, "remote", "set-url", "origin", "ext::sleep 5")

        result = _run(
            ["create", remote_repo.branch], repo, KIT_WORKTREE_FETCH_TIMEOUT="1"
        )

        assert result.returncode != 0
        assert result.stdout.strip() == ""
        assert "reason=remote-fetch-timeout" in result.stderr
        assert "KIT_WORKTREE_FETCH_TIMEOUT" in result.stderr
        assert not _has_local_branch(repo, remote_repo.branch)

    def test_divergence_fast_forwardable_is_named_and_resolves_to_local(
        self, remote_repo
    ):
        """TC-083f (AC-3): L is an ancestor of R — named, and local still wins."""
        repo = remote_repo.repo
        _git(repo, "branch", remote_repo.branch, "main")
        local_sha = _git(repo, "rev-parse", remote_repo.branch)
        assert local_sha == remote_repo.main_sha
        short_l = _git(repo, "rev-parse", "--short", f"refs/heads/{remote_repo.branch}")
        short_r = _git(
            repo, "rev-parse", "--short", f"refs/remotes/origin/{remote_repo.branch}"
        )

        result = _run(["create", remote_repo.branch], repo)

        assert result.returncode == 0, result.stderr
        assert "divergence" in result.stderr
        assert short_l in result.stderr
        assert short_r in result.stderr
        assert "ahead" in result.stderr
        # Resolution choice (documented in the script header): LOCAL wins.
        assert _git(result.stdout.strip(), "rev-parse", "HEAD") == local_sha

    def test_divergence_non_ancestor_is_named_and_resolves_to_local(self, remote_repo):
        """TC-083g (AC-3): genuinely diverged — named, and local still wins.

        Also kills mutant (v): over-applying the remote preference would reset
        an existing local branch to the remote tip and discard unpushed work.
        """
        repo = remote_repo.repo
        _git(repo, "checkout", "-b", remote_repo.branch, "main")
        _git(repo, "commit", "--allow-empty", "-m", "unpushed local work")
        local_sha = _git(repo, "rev-parse", remote_repo.branch)
        _git(repo, "checkout", "main")
        assert local_sha != remote_repo.remote_sha
        short_l = _git(repo, "rev-parse", "--short", f"refs/heads/{remote_repo.branch}")
        short_r = _git(
            repo, "rev-parse", "--short", f"refs/remotes/origin/{remote_repo.branch}"
        )

        result = _run(["create", remote_repo.branch], repo)

        assert result.returncode == 0, result.stderr
        assert "divergence" in result.stderr
        assert short_l in result.stderr
        assert short_r in result.stderr
        assert "diverged" in result.stderr
        assert _git(result.stdout.strip(), "rev-parse", "HEAD") == local_sha

    def test_new_branch_base_is_unchanged_pinned_by_sha(self, git_repo):
        """TC-083h (AC-4): today's base, by sha, in a repo with no remote at all.

        The variable named ``default_branch`` is really
        ``git symbolic-ref --short HEAD``. This issue must not change that, so
        the base is pinned by equality rather than by name.
        """
        base = _git(git_repo, "symbolic-ref", "--short", "HEAD")
        base_sha = _git(git_repo, "rev-parse", base)

        result = _run(["create", "feature/brand-new"], git_repo)

        assert result.returncode == 0, result.stderr
        wt_path = result.stdout.strip()
        assert wt_path.endswith(".worktrees/feature-brand-new")
        assert _git(wt_path, "rev-parse", "HEAD") == base_sha
        assert "ERROR" not in result.stderr
        assert "divergence" not in result.stderr

    def test_new_branch_is_not_refused_when_a_remote_exists(self, remote_repo):
        """TC-083i (AC-4): no local ref AND no remote ref -> base, never a refusal.

        Guards the over-reach direction of the fail-closed rule: a configured
        ``origin`` must not turn every new branch into a remote lookup.
        """
        repo = remote_repo.repo
        base_sha = _git(repo, "rev-parse", "main")

        result = _run_setup("feature/fresh", repo)

        assert result.returncode == 0, result.stderr
        wt = result.stdout.strip()
        assert _git(wt, "rev-parse", "HEAD") == base_sha
        assert "ERROR" not in result.stderr
        assert "divergence" not in result.stderr
        assert (
            open(
                os.path.join(wt, ".claude-kit", "freeze-dir.txt"), encoding="utf-8"
            ).read().strip()
            == wt
        )

    def test_local_only_branch_with_no_remote_still_succeeds(self, git_repo):
        """TC-083j (AC-4): a local branch in a repo with no ``origin`` at all."""
        _git(git_repo, "branch", "feature/local-only")
        local_sha = _git(git_repo, "rev-parse", "feature/local-only")

        result = _run(["create", "feature/local-only"], git_repo)

        assert result.returncode == 0, result.stderr
        assert _git(result.stdout.strip(), "rev-parse", "HEAD") == local_sha
        assert "ERROR" not in result.stderr

    def test_announces_which_source_supplied_the_branch(self, remote_repo, git_repo):
        """TC-083k: counter-evidence on stderr for all three resolution sources.

        The defeated output and the healthy output were byte-identical before
        this change, which is what let the defect live undetected; an absence of
        warnings is not evidence, so each path names its source.
        """
        remote = _run(["create", remote_repo.branch], remote_repo.repo)
        assert remote.returncode == 0, remote.stderr
        assert "source=remote-tip" in remote.stderr

        new = _run(["create", "feature/announce-new"], git_repo)
        assert new.returncode == 0, new.stderr
        assert "source=new-from-base" in new.stderr

        _git(git_repo, "branch", "feature/announce-local")
        local = _run(["create", "feature/announce-local"], git_repo)
        assert local.returncode == 0, local.stderr
        assert "source=local-ref" in local.stderr

    def test_fetch_timeout_knob_is_documented(self):
        """TC-083l: the new env knob is documented where its siblings live.

        Recurring review lesson (ISSUE-046/047/049/052/069): a new env knob needs
        a line in the owning script's header AND in a user-facing doc, in the
        same PR as the knob.
        """
        script_text = open(SCRIPT, encoding="utf-8").read()
        header = script_text.split("set -euo pipefail", 1)[0]
        assert "KIT_WORKTREE_FETCH_TIMEOUT" in header
        assert "KIT_WORKTREE_FETCH_TIMEOUT" in open(README, encoding="utf-8").read()


class TestPath:
    def test_existing_worktree(self, git_repo):
        _run(["create", "feature/x"], git_repo)
        result = _run(["path", "feature/x"], git_repo)
        assert result.returncode == 0
        assert result.stdout.strip().endswith(".worktrees/feature-x")

    def test_missing_worktree(self, git_repo):
        result = _run(["path", "feature/nonexistent"], git_repo)
        assert result.returncode == 1
        assert "error" in result.stderr.lower()


class TestRemove:
    def test_removes_worktree_and_branch(self, git_repo):
        _run(["create", "feature/rm-me"], git_repo)
        result = _run(["remove", "feature/rm-me"], git_repo)
        assert result.returncode == 0

        # worktree dir should be gone
        path_result = _run(["path", "feature/rm-me"], git_repo)
        assert path_result.returncode == 1

        # branch should be gone
        branch_check = subprocess.run(
            ["git", "-C", git_repo, "branch", "--list", "feature/rm-me"],
            capture_output=True,
            text=True,
        )
        assert branch_check.stdout.strip() == ""

    def test_remove_from_inside_worktree(self, git_repo):
        """Remove should succeed even when CWD is inside the worktree."""
        create_result = _run(["create", "feature/cwd-test"], git_repo)
        wt_path = create_result.stdout.strip()

        # Run remove with CWD inside the worktree
        result = _run(["remove", "feature/cwd-test"], wt_path)
        assert result.returncode == 0

        # Output should be the repo root
        assert result.stdout.strip() == os.path.realpath(git_repo)

        # Worktree should be gone
        assert not os.path.isdir(wt_path)

    def test_remove_nonexistent_is_noop(self, git_repo):
        result = _run(["remove", "feature/ghost"], git_repo)
        assert result.returncode == 0


class TestUsage:
    def test_no_args(self, git_repo):
        result = _run([], git_repo)
        assert result.returncode == 1

    def test_create_no_branch(self, git_repo):
        result = _run(["create"], git_repo)
        assert result.returncode == 1
