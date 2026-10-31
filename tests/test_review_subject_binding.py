"""ISSUE-096 — bind the delegated review to the PR's own diff.

Four times across three sprints (PRs #139, #141, #145 and one more) the
runtime review skill was reached on the SPEC-019 ``delegated`` path and then
**auto-collected its own subject by running git against the MAIN checkout**:
the harness arrived with the literal ``DIFF CONTENT: (Bash completed with no
output)`` and ``GIT STATUS: On branch main``. Uncorrected it would have
returned a clean bill having reviewed nothing — a silent fail-open on a
blocking gate, whose defeated output is byte-identical to its healthy one.

What these pin, per acceptance criterion:

- AC-1  ``collect`` prints ``<base-oid>...<head-oid>`` (head oid byte-equal to
        ``gh pr view <n> --json headRefOid -q .headRefOid``), a byte count > 0
        and the worktree path, exit 0 — **and the digest is verified by being
        echoed back by the consumer**, not merely printed by the producer. A
        printed-but-unread number is the same fail-open this issue is about
        (2026-10-31 amendment: on PR #145 the file-path hand-off was measured
        unreliable across contexts and only the required echo caught it).
- AC-2  a zero-byte collection cannot be delegated: non-zero exit, named
        ``reason=``, and NO ``review_delegated_to_*`` event in the run.
- AC-3  "computed and empty" stays distinguishable from "could not compute" —
        different exit code AND different ``reason=`` token, both pinned as
        exact strings with the other token asserted absent.
- AC-4  the measured failure shape as a regression pin: branch in
        ``.worktrees/<slug>``, collection driven from the MAIN checkout.
        The same test measures the pre-fix behaviour (bare ``git diff`` at the
        main checkout → 0 bytes) so the contrast is recorded, not asserted
        from memory.
- AC-5  the review record carries counter-evidence (byte count + head oid),
        and a notes file missing either FAILS.
- AC-7  the pre-existing decision surface is untouched.

Disarm discipline (review lesson 16 — a newly added defence must be tested in
the DISARM direction and through its real consumer): every gate here has a
test that drives it with the guard's premise violated (wrong echo, forged
empty-diff echo, tampered notes), and the CLI is additionally exercised
through a real ``subprocess`` boundary, not only in-process.

Everything is offline: ``git init --bare`` + clone fixtures and a stub ``gh``
on ``PATH``. No fixture PR is ever taken against the live repo (the ISSUE-083
review's two stray worktrees on main are the precedent).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = KIT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import review_context as rc  # noqa: E402

RUN_ID = "testrun096"
PR_NUMBER = "7"
PR_BRANCH = "issue/ISSUE-999-x"
WT_SLUG = "issue-ISSUE-999-x"


# ── git / gh fixture helpers ─────────────────────────────────────────


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout


def _identity(repo: Path) -> None:
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")


def _write_gh_stub(bindir: Path, data: dict) -> Path:
    """A stub ``gh`` answering ``pr view``, with the fixture's refs baked in.

    Supports the two invocation shapes this issue cares about:
    ``gh pr view <n> --json a,b,c`` (JSON object) and
    ``gh pr view <n> --json headRefOid -q .headRefOid`` (bare value) — so the
    test can obtain the AC-1 oracle through the same binary the script uses.
    """
    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / "gh_data.json").write_text(json.dumps(data), encoding="utf-8")
    stub = bindir / "gh"
    stub.write_text(
        f"""#!{sys.executable}
import json, pathlib, sys, time

DATA = json.loads(pathlib.Path(__file__).with_name("gh_data.json").read_text())
if DATA.get("__sleep__"):
    time.sleep(DATA["__sleep__"])
if "__fail__" in DATA:
    sys.stderr.write(DATA["__fail__"])
    sys.exit(1)
argv = sys.argv[1:]
if argv[:2] != ["pr", "view"]:
    sys.stderr.write("gh-stub: unsupported invocation %r\\n" % (argv,))
    sys.exit(1)
fields, query = [], None
i = 2
while i < len(argv):
    if argv[i] == "--json":
        fields = argv[i + 1].split(",")
        i += 2
    elif argv[i] in ("-q", "--jq"):
        query = argv[i + 1]
        i += 2
    else:
        i += 1
if DATA.get("__raw__") is not None:
    sys.stdout.write(DATA["__raw__"])
    sys.exit(0)
payload = {{f: DATA[f] for f in fields if f in DATA}}
if query:
    sys.stdout.write(payload.get(query.lstrip("."), "") + "\\n")
else:
    sys.stdout.write(json.dumps(payload) + "\\n")
""",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


class PrFixture:
    """A bare origin + clone whose PR branch is checked out in ``.worktrees/``."""

    def __init__(self, origin: Path, clone: Path, bindir: Path, data: dict):
        self.origin = origin
        self.clone = clone
        self.bindir = bindir
        self.data = data

    @property
    def worktree(self) -> Path:
        return self.clone / ".worktrees" / WT_SLUG

    def oracle_diff(self, cwd: Path | None = None) -> bytes:
        rng = f"{self.data['baseOid']}...{self.data['headRefOid']}"
        return _git_bytes(cwd or self.worktree, "diff", "--no-ext-diff", rng)

    def gh_headrefoid(self) -> str:
        """The literal AC-1 oracle: ``gh pr view <n> --json headRefOid -q …``."""
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}{os.pathsep}{env['PATH']}"
        out = subprocess.run(
            ["gh", "pr", "view", PR_NUMBER, "--json", "headRefOid", "-q", ".headRefOid"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        return out.stdout.strip()

    def activate(self, monkeypatch, cwd: Path | None = None) -> None:
        monkeypatch.setenv("PATH", f"{self.bindir}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.chdir(cwd or self.clone)

    def set_gh(self, **overrides) -> None:
        self.data.update(overrides)
        (self.bindir / "gh_data.json").write_text(
            json.dumps(self.data), encoding="utf-8"
        )


@pytest.fixture()
def pr_fixture(tmp_path) -> PrFixture:
    """The measured shape: PR branch in ``.worktrees/<slug>``, CWD at main.

    Entirely local — ``git init --bare`` plus a clone of a filesystem path,
    mirroring ``tests/test_worktree.py``'s ``remote_repo``. Nothing here
    touches the network and the live repo is never used as a fixture.
    """
    origin = tmp_path / "origin.git"
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "init", "--bare", str(origin)], check=True, capture_output=True
    )
    _git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    subprocess.run(
        ["git", "clone", str(origin), str(clone)], check=True, capture_output=True
    )
    _identity(clone)

    (clone / "README.md").write_text("base line\n", encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-m", "init")
    _git(clone, "push", "-u", "origin", "main")
    base_oid = _git(clone, "rev-parse", "refs/remotes/origin/main")

    _git(clone, "checkout", "-b", PR_BRANCH)
    (clone / "src").mkdir()
    (clone / "src" / "app.py").write_text(
        "\n".join(f"LINE_{i} = {i}" for i in range(40)) + "\n", encoding="utf-8"
    )
    (clone / "README.md").write_text("base line\nchanged by the PR\n", encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-m", "pr work")
    _git(clone, "push", "-u", "origin", PR_BRANCH)
    head_oid = _git(clone, "rev-parse", "HEAD")

    # The measured shape: main checkout back on main, branch living in a
    # linked worktree under .worktrees/<slug>.
    _git(clone, "checkout", "main")
    _git(clone, "worktree", "add", str(clone / ".worktrees" / WT_SLUG), PR_BRANCH)

    data = {
        "headRefOid": head_oid,
        "headRefName": PR_BRANCH,
        "baseRefName": "main",
        "baseOid": base_oid,
    }
    bindir = tmp_path / "bin"
    _write_gh_stub(bindir, data)
    return PrFixture(origin=origin, clone=clone, bindir=bindir, data=data)


def _events(project: Path, run_id: str = RUN_ID) -> list[dict]:
    path = project / ".claude" / "runs" / f"{run_id}.jsonl"
    assert path.is_file(), f"expected telemetry file at {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _no_events(project: Path, run_id: str = RUN_ID) -> bool:
    return not (project / ".claude" / "runs" / f"{run_id}.jsonl").exists()


def _runs_dir(project: Path) -> None:
    (project / ".claude" / "runs").mkdir(parents=True, exist_ok=True)


def _collect_json(capsys, *extra: str) -> dict:
    code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096", *extra])
    out = capsys.readouterr()
    assert code == 0, f"collect refused: {out.err}"
    return json.loads(out.out)


# ── AC-1: the payload carries the range, the path and a positive count ──


class TestCollectPayload:
    def test_collect_prints_range_bytes_and_worktree_path(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-1 (print side). Head oid byte-equal to the gh oracle."""
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)

        gh_oid = pr_fixture.gh_headrefoid()
        assert subject["head_oid"] == gh_oid
        assert subject["range"] == f"{pr_fixture.data['baseOid']}...{gh_oid}"
        assert isinstance(subject["diff_bytes"], int)
        assert subject["diff_bytes"] > 0
        assert subject["worktree_path"] == str(pr_fixture.worktree.resolve())
        assert subject["diff_headers"] == 2  # README.md + src/app.py
        assert subject["diff_sha256"] == hashlib.sha256(
            pr_fixture.oracle_diff()
        ).hexdigest()

    def test_collect_names_the_ref_each_side_came_from(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Counter-evidence, not narration: which ref supplied each endpoint.

        The base side must be the REMOTE-tracking ref. A bare ``main`` DWIMs to
        the LOCAL ref, which ISSUE-089 measured as a wrong diff subject —
        ``verify_checkpoint.py::_default_branch()``'s defect, deliberately not
        reproduced here.
        """
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        assert subject["base_ref"] == "refs/remotes/origin/main"
        assert subject["head_ref"] == f"gh:pr/{PR_NUMBER}#headRefOid"
        assert subject["worktree_source"] == "branch-worktree"

    def test_collect_does_not_follow_a_stale_local_trunk(
        self, pr_fixture, monkeypatch, capsys
    ):
        """ISSUE-089's bug must not be re-introduced by the range computation.

        A local ``main`` moved ahead of ``origin/main`` must not change the
        subject: the base endpoint is pinned to the remote-tracking ref.
        """
        pr_fixture.activate(monkeypatch)
        before = _collect_json(capsys)

        (pr_fixture.clone / "LOCAL_ONLY.md").write_text("drift\n", encoding="utf-8")
        # Explicit path, never ``add -A``: the fixture has a nested worktree
        # under .worktrees/, which ``-A`` would stage as a gitlink and silently
        # change the subject under test.
        _git(pr_fixture.clone, "add", "LOCAL_ONLY.md")
        _git(pr_fixture.clone, "commit", "-m", "local main moves ahead")
        assert _git(pr_fixture.clone, "rev-parse", "main") != pr_fixture.data["baseOid"]

        after = _collect_json(capsys)
        assert after["base_oid"] == before["base_oid"] == pr_fixture.data["baseOid"]
        assert after["diff_bytes"] == before["diff_bytes"]

    def test_collect_through_a_real_subprocess_boundary(self, pr_fixture):
        """Through the real consumer shape, not only ``main()`` in-process."""
        env = dict(os.environ)
        env["PATH"] = f"{pr_fixture.bindir}{os.pathsep}{env['PATH']}"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_context.py"),
                "collect",
                "--pr",
                PR_NUMBER,
                "--issue",
                "ISSUE-096",
            ],
            cwd=str(pr_fixture.clone),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        subject = json.loads(result.stdout)
        assert subject["diff_bytes"] == len(pr_fixture.oracle_diff())


# ── AC-4: regression pin of the measured failure shape ───────────────


class TestMeasuredFailureShapeIsPinned:
    def test_main_checkout_cwd_resolves_the_branch_worktree_and_real_bytes(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-4 — the exact shape observed on PR #139 / #141 / #145.

        CWD is the MAIN checkout (on ``main``, clean) while the PR branch lives
        in ``.worktrees/<slug>``. The pre-fix behaviour is measured in the same
        test rather than recalled: the bare ``git diff`` the runtime skill ran
        yields zero bytes on this exact input.
        """
        pre_fix_bytes = len(_git_bytes(pr_fixture.clone, "diff"))
        assert pre_fix_bytes == 0, "fixture failed to reproduce the measured shape"
        assert _git(pr_fixture.clone, "rev-parse", "--abbrev-ref", "HEAD") == "main"

        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)

        assert subject["worktree_path"] == str(pr_fixture.worktree.resolve())
        assert subject["worktree_path"] != str(pr_fixture.clone.resolve())
        assert subject["diff_bytes"] == len(pr_fixture.oracle_diff())
        assert subject["diff_bytes"] > pre_fix_bytes

    def test_falls_back_to_the_main_checkout_and_says_so(
        self, pr_fixture, monkeypatch, capsys
    ):
        """No worktree holds the branch → named fallback, still real bytes.

        The over-reach direction of AC-4: resolving the worktree must not turn
        a perfectly reviewable PR into a refusal when no linked worktree exists.
        """
        _git(pr_fixture.clone, "worktree", "remove", str(pr_fixture.worktree))
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        assert subject["worktree_source"] == "main-checkout"
        assert subject["worktree_path"] == str(pr_fixture.clone.resolve())
        assert subject["diff_bytes"] == len(
            pr_fixture.oracle_diff(cwd=pr_fixture.clone)
        )


# ── AC-3: computed-and-empty vs could-not-compute ────────────────────


class TestEmptyIsDistinguishableFromFailed:
    def test_genuinely_empty_pr_refuses_with_its_own_reason(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-3 arm A: head oid == merge-base. Exit 1, exact token pinned."""
        noop = _git(pr_fixture.clone, "rev-parse", "refs/remotes/origin/main")
        pr_fixture.set_gh(headRefOid=noop, headRefName="issue/ISSUE-998-noop")
        pr_fixture.activate(monkeypatch)

        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()

        assert code == 1
        assert out.out == "", "a refusal must not print a usable payload"
        assert "reason=empty-diff-head-is-merge-base" in out.err
        assert "reason=head-oid-unreachable" not in out.err
        assert "reason=empty-diff-unexplained" not in out.err

    def test_unreachable_head_oid_refuses_with_a_different_code_and_reason(
        self, pr_fixture, tmp_path, monkeypatch, capsys
    ):
        """AC-3 arm B: the subject's objects are absent from this checkout.

        A single-branch clone that never fetched the PR branch — the "collection
        ran against the wrong checkout" shape, made non-recoverable. This must
        NOT render as an empty diff.
        """
        narrow = tmp_path / "narrow"
        subprocess.run(
            [
                "git",
                "clone",
                "--no-local",
                "--single-branch",
                "--branch",
                "main",
                str(pr_fixture.origin),
                str(narrow),
            ],
            check=True,
            capture_output=True,
        )
        _identity(narrow)
        assert (
            subprocess.run(
                ["git", "-C", str(narrow), "cat-file", "-e",
                 pr_fixture.data["headRefOid"] + "^{commit}"],
                capture_output=True,
            ).returncode
            != 0
        ), "fixture failed to make the head oid unreachable"

        pr_fixture.activate(monkeypatch, cwd=narrow)
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()

        assert code == 2
        assert out.out == ""
        assert "reason=head-oid-unreachable" in out.err
        assert "reason=empty-diff-head-is-merge-base" not in out.err

    def test_the_two_zero_byte_outcomes_do_not_collapse(
        self, pr_fixture, tmp_path, monkeypatch, capsys
    ):
        """AC-3's core: a single shared "empty diff" outcome fails this AC."""
        # Captured BEFORE the override: ``set_gh`` mutates the fixture's own
        # record, so reading it back after the override would hand the second
        # arm the no-op oid and collapse the two inputs into one.
        real_head = pr_fixture.data["headRefOid"]
        noop = _git(pr_fixture.clone, "rev-parse", "refs/remotes/origin/main")
        pr_fixture.set_gh(headRefOid=noop)
        pr_fixture.activate(monkeypatch)
        empty_code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        empty_err = capsys.readouterr().err

        narrow = tmp_path / "narrow2"
        subprocess.run(
            ["git", "clone", "--no-local", "--single-branch", "--branch", "main",
             str(pr_fixture.origin), str(narrow)],
            check=True,
            capture_output=True,
        )
        _identity(narrow)
        pr_fixture.set_gh(headRefOid=real_head)
        pr_fixture.activate(monkeypatch, cwd=narrow)
        failed_code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        failed_err = capsys.readouterr().err

        assert empty_code != failed_code
        assert rc._reason_token(empty_err) == "empty-diff-head-is-merge-base"
        assert rc._reason_token(failed_err) == "head-oid-unreachable"

    def test_an_abbreviated_head_oid_still_classifies_as_the_no_op_case(
        self, pr_fixture, monkeypatch, capsys
    ):
        """The two endpoints must be compared in the SAME form.

        ``git merge-base`` always answers with a full oid. If the head oid is
        taken verbatim from ``gh`` without canonicalisation, an abbreviated
        value can never equal it — and a genuine no-op PR would be reported as
        ``empty-diff-unexplained``: the right refusal with the wrong diagnosis,
        which is how a reviewer gets sent to debug a non-existent collection.
        """
        full = _git(pr_fixture.clone, "rev-parse", "refs/remotes/origin/main")
        pr_fixture.set_gh(headRefOid=full[:10], headRefName="issue/ISSUE-998-noop")
        pr_fixture.activate(monkeypatch)

        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        err = capsys.readouterr().err
        assert code == 1
        assert rc._reason_token(err) == "empty-diff-head-is-merge-base"

    def test_a_reverted_change_is_empty_but_not_a_no_op_pr(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Computed, empty, and NOT explained by head == merge-base.

        A commit plus its revert: the head moved, so "nothing changed" would be
        a lie, and "could not compute" would be a different lie. Its own token.
        """
        _git(pr_fixture.clone, "checkout", "-b", "issue/ISSUE-997-revert", "main")
        (pr_fixture.clone / "temp.txt").write_text("x\n", encoding="utf-8")
        _git(pr_fixture.clone, "add", "temp.txt")
        _git(pr_fixture.clone, "commit", "-m", "add temp")
        _git(pr_fixture.clone, "rm", "-q", "temp.txt")
        _git(pr_fixture.clone, "commit", "-m", "remove temp")
        head = _git(pr_fixture.clone, "rev-parse", "HEAD")
        _git(pr_fixture.clone, "checkout", "main")
        pr_fixture.set_gh(headRefOid=head, headRefName="issue/ISSUE-997-revert")
        pr_fixture.activate(monkeypatch)

        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()

        assert code == 1
        assert out.out == ""
        assert "reason=empty-diff-unexplained" in out.err
        assert "reason=empty-diff-head-is-merge-base" not in out.err


class TestCollectionBoundaryFailuresAreNamed:
    """"Before concluding a capability is absent, check whether your own
    configuration caused the absence" — each boundary failure keeps its own
    token instead of degrading into "the diff was empty"."""

    def test_gh_missing_from_path_is_its_own_reason(
        self, pr_fixture, tmp_path, monkeypatch, capsys
    ):
        empty_bin = tmp_path / "emptybin"
        empty_bin.mkdir()
        monkeypatch.setenv("PATH", str(empty_bin))
        monkeypatch.chdir(pr_fixture.clone)
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert "reason=gh-unavailable" in out.err

    def test_gh_failure_is_distinct_from_gh_absence(
        self, pr_fixture, monkeypatch, capsys
    ):
        pr_fixture.set_gh(__fail__="no pull requests found for branch\n")
        pr_fixture.activate(monkeypatch)
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert "reason=gh-failed" in out.err
        assert "reason=gh-unavailable" not in out.err

    def test_gh_bad_output_is_its_own_reason(self, pr_fixture, monkeypatch, capsys):
        pr_fixture.set_gh(__raw__="not json at all\n")
        pr_fixture.activate(monkeypatch)
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert "reason=gh-bad-output" in out.err

    def test_option_shaped_head_oid_is_refused_before_reaching_git(
        self, pr_fixture, monkeypatch, capsys
    ):
        """``gh`` output crosses a trust boundary into argv — validate on read."""
        pr_fixture.set_gh(headRefOid="--upload-pack=touch /tmp/pwned")
        pr_fixture.activate(monkeypatch)
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert "reason=gh-bad-output" in out.err

    def test_hanging_gh_times_out_and_names_the_knob(
        self, pr_fixture, monkeypatch, capsys
    ):
        """A network consultation that STALLS must be a named refusal.

        Review lesson: print the knob's name in the failure message it
        remediates (the ISSUE-083 ``KIT_WORKTREE_FETCH_TIMEOUT`` precedent).
        """
        pr_fixture.set_gh(__sleep__=10)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv(rc.GH_TIMEOUT_ENV, "1")
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert "reason=gh-timeout" in out.err
        assert rc.GH_TIMEOUT_ENV in out.err

    def test_missing_remote_tracking_base_refuses_rather_than_using_local(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Fail closed instead of silently reviewing against the local trunk."""
        _git(pr_fixture.clone, "update-ref", "-d", "refs/remotes/origin/main")
        pr_fixture.activate(monkeypatch)
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert "reason=base-ref-unresolvable" in out.err

    def test_bad_pr_number_is_rejected_at_the_boundary(
        self, pr_fixture, monkeypatch, capsys
    ):
        """The PR ref reaches argv — validate it, and name what was wrong.

        Pinned to the ``--pr`` diagnostic, not merely to exit 2: before this
        issue landed, ANY exit-2 assertion here passed vacuously because the
        subcommand itself did not exist (the ISSUE-037 hollow-pass shape).
        """
        pr_fixture.activate(monkeypatch)
        code = rc.main(["collect", "--pr", "7; rm -rf /", "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert out.out == ""
        assert "--pr" in out.err
        # Positive control: the same fixture with a well-formed number works.
        assert _collect_json(capsys)["diff_bytes"] > 0

    def test_every_refusal_token_is_in_the_closed_vocabulary(self):
        """The new vocabulary is closed, and DISJOINT from the ISSUE-066 one.

        The three-value ``review_degraded_path_used`` vocabulary
        (capability-absent / context-unreachable / inline-attempt-failed) is
        pinned elsewhere; a subject-refusal token must never be mistaken for
        one of those.
        """
        assert len(set(rc.SUBJECT_REASONS)) == len(rc.SUBJECT_REASONS)
        assert set(rc.SUBJECT_REASONS).isdisjoint(
            {"capability-absent", "context-unreachable", rc.INLINE_ATTEMPT_FAILED}
        )
        for token in rc.SUBJECT_REASONS:
            assert token == token.lower()
            assert " " not in token


# ── AC-1 (echo) + AC-2: the consumer must echo the digest back ───────


class TestEchoGate:
    def _echo_args(self, subject: dict, **over) -> list[str]:
        args = [
            "delegate",
            "--dimension",
            "code",
            "--pr",
            PR_NUMBER,
            "--issue",
            "ISSUE-096",
            "--echoed-bytes",
            str(over.get("bytes", subject["diff_bytes"])),
            "--echoed-sha256",
            str(over.get("sha", subject["diff_sha256"])),
        ]
        return args

    def test_matching_echo_records_the_delegation_with_its_subject(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-1 (echo side): the verdict is accepted only against a real read."""
        _runs_dir(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)

        assert rc.main(self._echo_args(subject)) == 0
        events = _events(pr_fixture.clone)
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "review_delegated_to_code_review"
        assert event["issue_id"] == "ISSUE-096"
        assert event["payload"]["pr_number"] == PR_NUMBER
        assert event["payload"]["diff_bytes"] == subject["diff_bytes"]
        assert event["payload"]["diff_sha256"] == subject["diff_sha256"]
        assert event["payload"]["head_oid"] == subject["head_oid"]

    def test_security_dimension_records_its_own_event(
        self, pr_fixture, monkeypatch, capsys
    ):
        _runs_dir(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)
        args = self._echo_args(subject)
        args[args.index("--dimension") + 1] = "security"
        assert rc.main(args) == 0
        assert _events(pr_fixture.clone)[0]["event_type"] == (
            "review_delegated_to_security_review"
        )

    @pytest.mark.parametrize("field", ["bytes", "sha"])
    def test_wrong_echo_is_refused_and_records_nothing(
        self, pr_fixture, monkeypatch, capsys, field
    ):
        """DISARM direction: the reviewer did not read what we collected."""
        _runs_dir(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)

        over = {"bytes": subject["diff_bytes"] + 1} if field == "bytes" else {
            "sha": "0" * 64
        }
        code = rc.main(self._echo_args(subject, **over))
        err = capsys.readouterr().err
        assert code == 2
        assert "reason=echo-mismatch" in err
        assert _no_events(pr_fixture.clone)

        # Positive control, same fixture: the correct echo DOES record.
        assert rc.main(self._echo_args(subject)) == 0
        assert len(_events(pr_fixture.clone)) == 1

    def test_the_empty_collection_digest_cannot_satisfy_the_gate(
        self, pr_fixture, monkeypatch, capsys
    ):
        """The measured forgery: a reviewer that received no diff at all.

        ``(Bash completed with no output)`` means the reviewer measured zero
        bytes and ``sha256(b"")``. That echo must not be accepted for a PR
        whose real subject is non-empty — this is the whole defect, in one
        assertion.
        """
        _runs_dir(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)

        code = rc.main(
            self._echo_args(
                subject, bytes=0, sha=hashlib.sha256(b"").hexdigest()
            )
        )
        assert code == 2
        assert "reason=echo-mismatch" in capsys.readouterr().err
        assert _no_events(pr_fixture.clone)

    def test_zero_byte_collection_cannot_be_delegated_even_with_a_true_echo(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-2: a zero-byte subject is refused BEFORE the echo is considered.

        The echo here is honest — the reviewer really did see zero bytes — and
        it still must not produce a delegation event.
        """
        _runs_dir(pr_fixture.clone)
        noop = _git(pr_fixture.clone, "rev-parse", "refs/remotes/origin/main")
        pr_fixture.set_gh(headRefOid=noop)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)

        code = rc.main(
            [
                "delegate",
                "--dimension",
                "code",
                "--pr",
                PR_NUMBER,
                "--issue",
                "ISSUE-096",
                "--echoed-bytes",
                "0",
                "--echoed-sha256",
                hashlib.sha256(b"").hexdigest(),
            ]
        )
        err = capsys.readouterr().err
        assert code == 1
        assert "reason=empty-diff-head-is-merge-base" in err
        assert _no_events(pr_fixture.clone)

    def test_no_delegated_event_for_an_unreachable_subject(
        self, pr_fixture, tmp_path, monkeypatch, capsys
    ):
        """AC-2, "could not compute" arm — still no delegation."""
        narrow = tmp_path / "narrow3"
        subprocess.run(
            ["git", "clone", "--no-local", "--single-branch", "--branch", "main",
             str(pr_fixture.origin), str(narrow)],
            check=True,
            capture_output=True,
        )
        _identity(narrow)
        _runs_dir(narrow)
        pr_fixture.activate(monkeypatch, cwd=narrow)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)

        code = rc.main(
            [
                "delegate",
                "--dimension",
                "code",
                "--pr",
                PR_NUMBER,
                "--issue",
                "ISSUE-096",
                "--echoed-bytes",
                "1",
                "--echoed-sha256",
                "a" * 64,
            ]
        )
        assert code == 2
        assert "reason=head-oid-unreachable" in capsys.readouterr().err
        assert _no_events(narrow)

    def test_echo_flags_are_required(self, pr_fixture, monkeypatch, capsys):
        """An omitted echo must not be read as a passing echo.

        Pinned to the named flag in the diagnostic and paired with a positive
        control, so this cannot pass merely because the subcommand is absent.
        """
        _runs_dir(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        code = rc.main(
            ["delegate", "--dimension", "code", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]
        )
        out = capsys.readouterr()
        assert code == 2
        assert "--echoed-sha256" in out.err
        assert _no_events(pr_fixture.clone)
        # Positive control: with the echo supplied, the same call records.
        subject = _collect_json(capsys)
        assert rc.main(self._echo_args(subject)) == 0
        assert len(_events(pr_fixture.clone)) == 1

    def test_delegate_through_a_real_subprocess_boundary(self, pr_fixture):
        """Lesson 16: exercise the defence through its real consumer."""
        _runs_dir(pr_fixture.clone)
        env = dict(os.environ)
        env["PATH"] = f"{pr_fixture.bindir}{os.pathsep}{env['PATH']}"
        env["KIT_RUN_ID"] = RUN_ID
        base = [sys.executable, str(SCRIPTS_DIR / "review_context.py")]
        collected = subprocess.run(
            base + ["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"],
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert collected.returncode == 0, collected.stderr
        subject = json.loads(collected.stdout)

        bad = subprocess.run(
            base + ["delegate", "--dimension", "security", "--pr", PR_NUMBER,
                    "--issue", "ISSUE-096", "--echoed-bytes", "0",
                    "--echoed-sha256", hashlib.sha256(b"").hexdigest()],
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert bad.returncode == 2
        assert "reason=echo-mismatch" in bad.stderr
        assert _no_events(pr_fixture.clone)

        good = subprocess.run(
            base + ["delegate", "--dimension", "security", "--pr", PR_NUMBER,
                    "--issue", "ISSUE-096",
                    "--echoed-bytes", str(subject["diff_bytes"]),
                    "--echoed-sha256", subject["diff_sha256"]],
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert good.returncode == 0, good.stderr
        assert len(_events(pr_fixture.clone)) == 1


# ── AC-5: counter-evidence in the review record ──────────────────────


class TestReviewNotesCounterEvidence:
    NOTES_BODY = (
        "# Review Notes — PR #7\n\n## Code Review\n_Source: code-review_\n\n"
        "_No findings._\n\n## Security Findings\n_Source: security-review_\n\n"
        "_No findings._\n\n## Over-Engineering\n\n_No findings._\n"
    )

    def _notes(self, root: Path) -> Path:
        path = root / "docs" / "review_notes" / "ISSUE-096.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.NOTES_BODY, encoding="utf-8")
        return path

    def test_record_subject_appends_byte_count_and_head_oid(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-5: "reviewed nothing" can no longer render as "found nothing"."""
        notes = self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)

        assert rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]) == 0
        text = notes.read_text(encoding="utf-8")
        assert rc.SUBJECT_HEADING in text
        assert str(subject["diff_bytes"]) in text
        assert subject["head_oid"] in text
        # The verdict the notes already carried is preserved, not rewritten.
        assert "## Code Review" in text
        assert text.startswith("# Review Notes — PR #7")

    def test_record_subject_is_idempotent(self, pr_fixture, monkeypatch, capsys):
        self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        assert rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]) == 0
        first = (
            pr_fixture.clone / "docs" / "review_notes" / "ISSUE-096.md"
        ).read_text(encoding="utf-8")
        assert rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]) == 0
        second = (
            pr_fixture.clone / "docs" / "review_notes" / "ISSUE-096.md"
        ).read_text(encoding="utf-8")
        assert first == second
        assert first.count(rc.SUBJECT_HEADING) == 1

    def test_notes_missing_the_byte_count_fail(self, pr_fixture, monkeypatch, capsys):
        """AC-5 DISARM: a verdict without counter-evidence must FAIL."""
        notes = self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        notes.write_text(
            self.NOTES_BODY
            + f"\n{rc.SUBJECT_HEADING}\n- head_oid: {subject['head_oid']}\n",
            encoding="utf-8",
        )
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 2
        assert "reason=subject-incomplete" in capsys.readouterr().err

    def test_notes_missing_the_head_oid_fail(self, pr_fixture, monkeypatch, capsys):
        notes = self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        notes.write_text(
            self.NOTES_BODY
            + f"\n{rc.SUBJECT_HEADING}\n- diff_bytes: {subject['diff_bytes']}\n",
            encoding="utf-8",
        )
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 2
        assert "reason=subject-incomplete" in capsys.readouterr().err

    def test_tampered_counter_evidence_is_refused(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Workspace state read by a gate is untrusted input: validate on read."""
        notes = self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        notes.write_text(
            self.NOTES_BODY
            + f"\n{rc.SUBJECT_HEADING}\n- diff_bytes: 999999\n"
            f"- head_oid: {subject['head_oid']}\n",
            encoding="utf-8",
        )
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        err = capsys.readouterr().err
        assert code == 2
        assert "reason=subject-mismatch" in err
        # Positive control: restoring the true value in the same fixture passes.
        notes.write_text(self.NOTES_BODY, encoding="utf-8")
        assert rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]) == 0

    def test_a_contradicting_duplicate_value_is_refused(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Collect ALL occurrences, not the first (the ISSUE-042 lesson).

        First-occurrence-wins lets a true line be followed by a false one and
        still pass, so the record would disagree with itself while the gate
        reported agreement.
        """
        notes = self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        notes.write_text(
            self.NOTES_BODY
            + f"\n{rc.SUBJECT_HEADING}\n"
            f"- diff_bytes: {subject['diff_bytes']}\n"
            f"- head_oid: {subject['head_oid']}\n"
            "- diff_bytes: 1\n",
            encoding="utf-8",
        )
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 2
        assert "reason=subject-mismatch" in capsys.readouterr().err

    def test_duplicate_subject_blocks_are_refused(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Two blocks = two claims; only the first would ever be checked."""
        notes = self._notes(pr_fixture.clone)
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        true_block = (
            f"\n{rc.SUBJECT_HEADING}\n- diff_bytes: {subject['diff_bytes']}\n"
            f"- head_oid: {subject['head_oid']}\n"
        )
        notes.write_text(
            self.NOTES_BODY
            + true_block
            + f"\n{rc.SUBJECT_HEADING}\n- diff_bytes: 1\n- head_oid: {'0' * 40}\n",
            encoding="utf-8",
        )
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 2
        assert "reason=subject-incomplete" in capsys.readouterr().err
        # Positive control: exactly one true block in the same fixture passes.
        notes.write_text(self.NOTES_BODY + true_block, encoding="utf-8")
        assert rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]) == 0

    def test_missing_notes_file_is_a_named_refusal(
        self, pr_fixture, monkeypatch, capsys
    ):
        pr_fixture.activate(monkeypatch)
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 2
        assert "reason=review-notes-missing" in capsys.readouterr().err

    def test_notes_outside_the_project_are_refused(
        self, pr_fixture, tmp_path, monkeypatch, capsys
    ):
        outside = tmp_path / "outside.md"
        outside.write_text(self.NOTES_BODY, encoding="utf-8")
        pr_fixture.activate(monkeypatch)
        code = rc.main(
            ["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096",
             "--notes", str(outside)]
        )
        assert code == 2
        assert "reason=review-notes-outside-project" in capsys.readouterr().err
        assert outside.read_text(encoding="utf-8") == self.NOTES_BODY

    def test_refused_collection_writes_no_counter_evidence(
        self, pr_fixture, monkeypatch, capsys
    ):
        """A subject that could not be established must not bless the notes."""
        notes = self._notes(pr_fixture.clone)
        pr_fixture.set_gh(__fail__="gh: no such PR\n")
        pr_fixture.activate(monkeypatch)
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 2
        assert "reason=gh-failed" in capsys.readouterr().err
        assert notes.read_text(encoding="utf-8") == self.NOTES_BODY

    def test_undecodable_notes_do_not_crash_the_gate(
        self, pr_fixture, monkeypatch, capsys
    ):
        notes = self._notes(pr_fixture.clone)
        notes.write_bytes(b"# notes \xff\xfe not utf-8\n")
        pr_fixture.activate(monkeypatch)
        code = rc.main(["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        assert code == 0
        assert rc.SUBJECT_HEADING in notes.read_text(
            encoding="utf-8", errors="replace"
        )


# ── AC-7: the pre-existing decision surface is untouched ─────────────


class TestDecisionSurfaceUnchanged:
    def test_decide_still_prints_its_json_and_exits_0(
        self, tmp_path, monkeypatch, capsys
    ):
        """AC-7, the literal command from the acceptance criterion."""
        proj = tmp_path / "proj"
        (proj / ".claude" / "runs").mkdir(parents=True)
        monkeypatch.chdir(proj)
        monkeypatch.setattr(
            rc.has_skill, "find_skill", lambda name: (1, "stub")
        )
        assert (
            rc.main(["decide", "--invocation-tools", "absent", "--issue", "ISSUE-999"])
            == 0
        )
        data = json.loads(capsys.readouterr().out)
        assert set(data) == {"issue_id", "invocation_tools", "dimensions"}
        assert set(data["dimensions"]) == {"code", "security"}

    def test_the_prose_emit_seam_still_accepts_only_its_one_reason(
        self, tmp_path, monkeypatch
    ):
        """The closed three-value vocabulary did NOT gain a fourth token."""
        proj = tmp_path / "proj"
        (proj / ".claude" / "runs").mkdir(parents=True)
        monkeypatch.chdir(proj)
        assert rc.main(
            ["emit", "--event", "review_degraded_path_used", "--dimension", "code",
             "--reason", "echo-mismatch", "--issue", "ISSUE-096"]
        ) == 2


# ── the contract in the skill text (option "both") ───────────────────


class TestSkillTemplateBindsTheSubject:
    """The decision: the checkable half lives in the script, and step 3.1
    consumes it. Prose alone is what was skipped four times, so these pin that
    the prose names the EXECUTABLE steps rather than describing the discipline.
    """

    @staticmethod
    def _texts() -> list[tuple[str, str]]:
        return [
            (name, (KIT_ROOT / "skills" / "review" / name).read_text(encoding="utf-8"))
            for name in ("SKILL.md.tmpl", "SKILL.md")
        ]

    def test_step_3_1_names_the_collection_and_the_echo_gate(self):
        for name, text in self._texts():
            assert "review_context.py collect" in text, name
            assert "review_context.py delegate" in text, name
            assert "--echoed-sha256" in text, name
            assert "--echoed-bytes" in text, name

    def test_step_3_1_forbids_the_runtime_skill_auto_collecting(self):
        for name, text in self._texts():
            assert "(Bash completed with no output)" in text, name

    def test_counter_evidence_step_runs_after_the_synthesizer(self):
        """Review lesson 12: pin POSITION, not just presence.

        ``record-subject`` verifies ``docs/review_notes/<ISSUE>.md``, which the
        synthesizer at step 3.14 OVERWRITES. Placed upstream of it the check
        would gate a surface that is mutated afterwards — and pass anyway.
        """
        for name, text in self._texts():
            synth = text.index("synthesize_review_notes.py")
            record = text.index("review_context.py record-subject")
            assert record > synth, (
                f"{name}: the record-subject call must stay DOWNSTREAM of the "
                "synthesizer that rewrites the notes it checks"
            )

    def test_generated_skill_is_in_sync_with_its_template(self):
        tmpl = (KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(
            encoding="utf-8"
        )
        generated = (KIT_ROOT / "skills" / "review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        body = tmpl.split("{{PREAMBLE}}", 1)[1]
        assert body.strip() in generated


class TestDocsCarryTheContract:
    def test_telemetry_schema_documents_the_subject_payload_fields(self):
        text = (KIT_ROOT / "docs" / "telemetry_schema.md").read_text(encoding="utf-8")
        for field in ("diff_bytes", "diff_sha256", "head_oid"):
            assert field in text, (
                f"docs/telemetry_schema.md must document the {field!r} payload "
                "field added to the review delegation events (ISSUE-096)"
            )

    def test_the_new_timeout_knob_is_documented_where_its_siblings_live(self):
        """Review lesson: a new env knob needs a line in the owning module's
        docstring AND in a user-facing doc, in the same PR."""
        module = (SCRIPTS_DIR / "review_context.py").read_text(encoding="utf-8")
        docstring = module.split('"""', 2)[1]
        assert rc.GH_TIMEOUT_ENV in docstring
        assert rc.GH_TIMEOUT_ENV in (KIT_ROOT / "README.md").read_text(encoding="utf-8")
