"""ISSUE-096 — bind the delegated review to the PR's own diff.

**Five times across four sprints** the runtime review skill was reached on the
SPEC-019 ``delegated`` path and then **collected its own subject instead of
the one it was handed** — four as zero-byte collections against the MAIN
checkout, the fifth as a NON-empty collection of the wrong subject. The dated
measurements are the review-target row of ``docs/cc_feature_matrix.md`` and
are not restated here. What they dictate: the digest, not the byte count, is
the load-bearing check, because a non-empty check passes the fifth shape.

What these pin, per acceptance criterion: AC-1 the range + path + a positive
byte count + the exact ``diff_command``, with the digest **echoed back by the
consumer** rather than merely printed by the producer; AC-2 a zero-byte
collection cannot be delegated; AC-3 "computed and empty" stays distinguishable
from "could not compute" by exit code AND token, including the failure modes
that previously escaped as a traceback at exit 1; AC-4 the measured failure
shape (branch in ``.worktrees/<slug>``, collection driven from MAIN); AC-5 the
record carries counter-evidence it did not produce itself; AC-7 the
pre-existing decision surface is untouched.

Disarm discipline (review lesson 16): every gate here is also driven with its
premise violated, through the real CLI — wrong echo, forged empty-diff echo,
forged notes block, absent receipt, another dimension's receipt, moved head,
prunable worktree — and through a real ``subprocess`` boundary, not only
in-process.

Everything is offline: ``git init --bare`` + clone fixtures and a stub ``gh``
on ``PATH``. No fixture PR is ever taken against the live repo (the ISSUE-083
review's two stray worktrees on main are the precedent).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = KIT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import review_context as rc  # noqa: E402
import sprint_queue  # noqa: E402

RUN_ID = "testrun096"
PR_NUMBER = "7"
PR_BRANCH = "issue/ISSUE-999-x"
WT_SLUG = "issue-ISSUE-999-x"


def _reason(text: str) -> str | None:
    """The ``reason=<token>`` a refusal rendered. Local on purpose: the
    module."""
    match = re.search(r"reason=([a-z0-9-]+)", text)
    return match.group(1) if match else None


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
    """A stub ``gh pr view``: both the ``--json a,b,c`` object shape and
    the."""
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
        return _git_bytes(
            cwd or self.worktree, "diff", "--no-ext-diff", "--no-textconv", rng
        )

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

    def env(self, run_id: str | None = RUN_ID) -> dict:
        """Subprocess env with the stub on PATH (and optionally a run id)."""
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}{os.pathsep}{env['PATH']}"
        env.pop("KIT_RUN_ID", None)
        if run_id is not None:
            env["KIT_RUN_ID"] = run_id
        return env


@pytest.fixture()
def pr_fixture(tmp_path) -> PrFixture:
    """The measured shape: PR branch in ``.worktrees/<slug>``, CWD at main.

    ``git init --bare`` + clone, mirroring ``tests/test_worktree.py``: no
    network, and the live repo is never a fixture (ISSUE-083's precedent).
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


def _events(root: Path, run_id: str = RUN_ID) -> list[dict]:
    path = root / ".claude" / "runs" / f"{run_id}.jsonl"
    assert path.is_file(), f"expected telemetry file at {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _no_events(root: Path, run_id: str = RUN_ID) -> bool:
    return not (root / ".claude" / "runs" / f"{run_id}.jsonl").exists()


def _runs_dir(root: Path) -> Path:
    path = root / ".claude" / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _collect_json(capsys) -> dict:
    code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
    out = capsys.readouterr()
    assert code == 0, f"collect refused: {out.err}"
    return json.loads(out.out)


def _delegate_args(subject: dict, dimension: str = "code", **over) -> list[str]:
    return [
        "delegate",
        "--dimension",
        dimension,
        "--pr",
        PR_NUMBER,
        "--issue",
        "ISSUE-096",
        "--head-oid",
        str(subject["head_oid"]),
        "--echoed-bytes",
        str(over.get("bytes", subject["diff_bytes"])),
        "--echoed-sha256",
        str(over.get("sha", subject["diff_sha256"])),
    ]


RECORD_ARGS = ["record-subject", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]

#: A wrong subject that is LARGER than the real one, in the shape of the
#: 2026-10-31 reproduction (main's dirty registry churn, ~51KB).
_WRONG_BUT_BIGGER = b"diff --git a/docs/sprint_state.md b/docs/sprint_state.md\n" * 900


# ── AC-1: the payload carries the range, the path and a positive count ──


class TestCollectPayload:
    def test_collect_prints_range_bytes_and_worktree_path(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-1 (print side). ``diff_bytes > 0`` would also hold for the."""
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
        """Counter-evidence, not narration: which ref supplied each endpoint."""
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        assert subject["base_ref"] == "refs/remotes/origin/main"
        assert subject["range"].endswith(f"...{subject['head_oid']}")
        assert subject["worktree_source"] == "branch-worktree"

    def test_the_payload_carries_no_field_nothing_reads(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Every emitted field has a consumer: prose, receipt or notes block."""
        pr_fixture.activate(monkeypatch)
        keys = set(_collect_json(capsys))
        assert keys == {
            "issue_id",
            "pr_number",
            "range",
            "base_ref",
            "head_oid",
            "worktree_path",
            "worktree_source",
            "diff_command",
            "diff_bytes",
            "diff_headers",
            "diff_sha256",
        }
        # Named as FORBIDDEN, not merely absent from the permitted set: this
        # guard passed with `head_ref` present, which is the finding. Each of
        # these was written and read by nothing — `merge_base`, a constant
        # template restating `pr_number`, and the left half of `range`.
        assert keys.isdisjoint({"merge_base", "head_ref", "base_oid"})

    def test_collect_does_not_follow_a_stale_local_trunk(
        self, pr_fixture, monkeypatch, capsys
    ):
        """ISSUE-089's bug must not be re-introduced by the range
        computation:"""
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
        assert after["range"] == before["range"]
        assert after["range"].startswith(f"{pr_fixture.data['baseOid']}...")
        assert after["diff_bytes"] == before["diff_bytes"]

    def test_collect_through_a_real_subprocess_boundary(self, pr_fixture):
        """Through the real consumer shape, not only ``main()`` in-process."""
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
            env=pr_fixture.env(run_id=None),
        )
        assert result.returncode == 0, result.stderr
        subject = json.loads(result.stdout)
        assert subject["diff_bytes"] == len(pr_fixture.oracle_diff())


class TestTheCommandHandedOverIsTheCommandMeasured:
    """The prose must hand the reviewer the EXACT argv the gate measures: a."""

    def test_diff_command_reproduces_the_digest_byte_for_byte(
        self, pr_fixture, monkeypatch, capsys
    ):
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)
        out = subprocess.run(shlex.split(subject["diff_command"]), capture_output=True)
        assert out.returncode == 0, out.stderr
        assert len(out.stdout) == subject["diff_bytes"]
        assert hashlib.sha256(out.stdout).hexdigest() == subject["diff_sha256"]

    def test_a_local_diff_external_cannot_change_the_subject(
        self, pr_fixture, monkeypatch, capsys
    ):
        """``diff.external`` is a per-repo config a developer may well have."""
        ext = pr_fixture.clone / "ext.sh"
        ext.write_text("#!/bin/sh\necho EXTERNAL-DIFF-JUNK\n", encoding="utf-8")
        ext.chmod(0o755)
        _git(pr_fixture.worktree, "config", "diff.external", str(ext))
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)

        # Premise, measured rather than assumed: the config IS observable.
        unguarded = _git_bytes(
            pr_fixture.worktree, "diff", subject["range"]
        )
        assert unguarded != pr_fixture.oracle_diff(), (
            "fixture failed to make diff.external observable"
        )
        assert subject["diff_bytes"] == len(pr_fixture.oracle_diff())
        assert hashlib.sha256(
            subprocess.run(
                shlex.split(subject["diff_command"]), capture_output=True
            ).stdout
        ).hexdigest() == subject["diff_sha256"]

    def test_a_local_textconv_cannot_empty_the_subject(
        self, pr_fixture, monkeypatch, capsys
    ):
        """``--no-ext-diff`` does NOT disable textconv — measured: with a."""
        tc = pr_fixture.clone / "tc.sh"
        tc.write_text("#!/bin/sh\necho TEXTCONV-CONSTANT\n", encoding="utf-8")
        tc.chmod(0o755)
        common = Path(
            _git(pr_fixture.worktree, "rev-parse", "--path-format=absolute",
                 "--git-common-dir")
        )
        (common / "info").mkdir(parents=True, exist_ok=True)
        (common / "info" / "attributes").write_text("*.py diff=py\n", encoding="utf-8")
        _git(pr_fixture.worktree, "config", "diff.py.textconv", str(tc))

        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)

        rng = f"{pr_fixture.data['baseOid']}...{pr_fixture.data['headRefOid']}"
        textconv_only = _git_bytes(
            pr_fixture.worktree, "diff", "--no-ext-diff", rng
        )
        assert len(textconv_only) < len(pr_fixture.oracle_diff()), (
            "fixture failed to make textconv observable"
        )
        assert subject["diff_bytes"] == len(pr_fixture.oracle_diff()) > 0
        assert "--no-textconv" in subject["diff_command"]


# ── AC-4: regression pin of the measured failure shape ───────────────


class TestMeasuredFailureShapeIsPinned:
    def test_main_checkout_cwd_resolves_the_branch_worktree_and_real_bytes(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-4 — the exact shape observed on PR #139 / #141 / #145.

        The pre-fix behaviour is measured in the same test rather than
        recalled: the bare ``git diff`` the runtime skill ran yields zero bytes
        on this exact input.
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
        """No worktree holds the branch → named fallback, still real bytes."""
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
    def test_the_two_zero_byte_outcomes_do_not_collapse(
        self, pr_fixture, tmp_path, monkeypatch, capsys
    ):
        """AC-3's core: a single shared "empty diff" outcome fails this AC.

        Arm A is a head oid equal to its merge base (a genuine no-op PR); arm B
        is a single-branch clone that never fetched the PR branch — the
        "collection ran against the wrong checkout" shape, made non-recoverable.
        Both the exit codes and the exact tokens are pinned.
        """
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

        assert (empty_code, failed_code) == (1, 2)
        assert _reason(empty_err) == "empty-diff-head-is-merge-base"
        assert _reason(failed_err) == "head-oid-unreachable"

    def test_an_abbreviated_head_oid_still_classifies_as_the_no_op_case(
        self, pr_fixture, monkeypatch, capsys
    ):
        """The two endpoints must be compared in the SAME form."""
        full = _git(pr_fixture.clone, "rev-parse", "refs/remotes/origin/main")
        pr_fixture.set_gh(headRefOid=full[:10], headRefName="issue/ISSUE-998-noop")
        pr_fixture.activate(monkeypatch)

        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        err = capsys.readouterr().err
        assert code == 1
        assert _reason(err) == "empty-diff-head-is-merge-base"

    def test_a_reverted_change_is_empty_but_not_a_no_op_pr(
        self, pr_fixture, monkeypatch, capsys
    ):
        """Computed, empty, and NOT explained by head == merge-base: a
        commit."""
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


class TestNoCollectionFailureEscapesAsExitOne:
    """The fail-open the ISSUE-096 review found INSIDE this guard.

    An uncaught exception in the collection path exits **1** — this module's
    code for "computed and EMPTY" — with no ``reason=`` token at all, so the
    two AC-3 outcomes differ by neither. Each test below drives a routine
    real-world input through that path.
    """

    def test_a_prunable_worktree_registration_is_a_named_refusal(self, pr_fixture):
        """Routine after ``wt_cleanup.sh`` without ``git worktree prune``."""
        shutil.rmtree(pr_fixture.worktree)
        assert "prunable" in _git(
            pr_fixture.clone, "worktree", "list", "--porcelain"
        ), "fixture failed to reproduce the prunable registration"

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "review_context.py"), "collect",
             "--pr", PR_NUMBER, "--issue", "ISSUE-096"],
            cwd=str(pr_fixture.clone),
            capture_output=True,
            text=True,
            env=pr_fixture.env(run_id=None),
        )
        assert result.returncode == 2, result.stderr
        assert result.stdout == ""
        assert "Traceback" not in result.stderr
        assert _reason(result.stderr) == "worktree-path-missing"
        assert "git worktree prune" in result.stderr

    def test_git_missing_from_path_is_its_own_reason(
        self, pr_fixture, monkeypatch, capsys
    ):
        """``_git`` lacked the ``shutil.which`` guard its ``gh`` sibling has."""
        monkeypatch.setenv("PATH", str(pr_fixture.bindir))
        monkeypatch.chdir(pr_fixture.clone)
        assert shutil.which("git") is None, "fixture failed to hide git"
        code = rc.main(["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert out.out == ""
        assert _reason(out.err) == "git-unavailable"

    @pytest.mark.parametrize("command", ["collect", "delegate", "record-subject"])
    def test_every_subject_subcommand_is_covered_by_the_mapping(
        self, pr_fixture, monkeypatch, capsys, command
    ):
        """All three share the dispatcher, so all three are pinned — driven
        at."""
        def boom(*_a, **_kw):
            raise OSError("unmodelled failure")

        pr_fixture.activate(monkeypatch)
        monkeypatch.setattr(rc, "_pr_refs", boom)
        argv = {
            "collect": ["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"],
            "delegate": _delegate_args(
                {"head_oid": "a" * 40, "diff_bytes": 1, "diff_sha256": "b" * 64}
            ),
            "record-subject": RECORD_ARGS,
        }[command]
        assert rc.main(argv) == 2
        out = capsys.readouterr()
        assert out.out == ""
        assert _reason(out.err) == "collection-error"
        assert "OSError" in out.err


class TestCollectionBoundaryFailuresAreNamed:
    """"Before concluding a capability is absent, check whether your own."""

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
        """A STALLING network consultation must be a named refusal, and the."""
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
        """The PR ref reaches argv — validate it, and name what was wrong."""
        pr_fixture.activate(monkeypatch)
        code = rc.main(["collect", "--pr", "7; rm -rf /", "--issue", "ISSUE-096"])
        out = capsys.readouterr()
        assert code == 2
        assert out.out == ""
        assert "--pr" in out.err
        # Positive control: the same fixture with a well-formed number works.
        assert _collect_json(capsys)["diff_bytes"] > 0

    def test_every_refusal_token_is_in_the_closed_vocabulary(self):
        """The new vocabulary is closed, and DISJOINT from the ISSUE-066."""
        assert len(set(rc.SUBJECT_REASONS)) == len(rc.SUBJECT_REASONS)
        assert set(rc.SUBJECT_REASONS).isdisjoint(
            {"capability-absent", "context-unreachable", rc.INLINE_ATTEMPT_FAILED}
        )
        for token in rc.SUBJECT_REASONS:
            assert token == token.lower()
            assert " " not in token

    def test_only_a_computed_empty_subject_may_exit_1(self):
        """"**Nothing else exits 1**" was documented, true, and unenforced.

        ``exit_code`` was a free parameter, so a future
        ``_refuse("git-diff-failed", …, exit_code=1)`` would silently reinstate
        the conflation AC-3 exists to prevent. One table, both ways.
        """
        for token in rc.SUBJECT_REASONS:
            expected = 1 if token.startswith("empty-diff-") else 2
            assert rc.SubjectRefused(token, "d", expected).exit_code == expected
            with pytest.raises(ValueError):
                rc.SubjectRefused(token, "d", 3 - expected)

    def test_the_closed_vocabulary_is_enforced_under_dash_O(self):
        """A bare ``assert`` is stripped by ``python -O``, and the refusal."""
        probe = (
            "import sys; sys.path.insert(0, %r); import review_context as rc\n"
            "try:\n"
            "    rc.SubjectRefused('not-a-real-token', 'detail', 2)\n"
            "except ValueError as exc:\n"
            "    print('rejected:', exc); sys.exit(0)\n"
            "sys.exit('accepted an unknown refusal token')\n"
        ) % str(SCRIPTS_DIR)
        for flags in ([], ["-O"]):
            done = subprocess.run(
                [sys.executable, *flags, "-c", probe], capture_output=True, text=True
            )
            assert done.returncode == 0, f"{flags}: {done.stdout}{done.stderr}"
            assert "rejected:" in done.stdout, flags


# ── AC-1 (echo) + AC-2: the consumer must echo the digest back ───────


class TestEchoGate:
    def test_matching_echo_records_the_delegation_with_its_subject(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-1 (echo side): the verdict is accepted only against a real
        read,."""
        _runs_dir(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)

        assert rc.main(_delegate_args(subject)) == 0, capsys.readouterr().err
        events = _events(pr_fixture.worktree)
        assert _no_events(pr_fixture.clone)
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
        _runs_dir(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)
        assert rc.main(_delegate_args(subject, dimension="security")) == 0
        assert _events(pr_fixture.worktree)[0]["event_type"] == (
            "review_delegated_to_security_review"
        )

    @pytest.mark.parametrize(
        "echo,why",
        [
            (lambda s: {"bytes": s["diff_bytes"] + 1}, "a byte count off by one"),
            (lambda s: {"sha": "0" * 64}, "the digest of something else"),
            (
                lambda s: {"bytes": 0, "sha": hashlib.sha256(b"").hexdigest()},
                "the first four reproductions: a reviewer handed nothing "
                "measures 0 / sha256(b'')",
            ),
            (
                lambda s: {
                    "bytes": len(_WRONG_BUT_BIGGER),
                    "sha": hashlib.sha256(_WRONG_BUT_BIGGER).hexdigest(),
                },
                "the FIFTH reproduction (2026-10-31): the wrong subject was NOT "
                "empty — 48.5KB of main's dirty registry churn. A `bytes > 0` "
                "check passes this; only the digest rejects it",
            ),
        ],
        ids=["bytes", "sha", "received-nothing", "wrong-but-bigger"],
    )
    def test_wrong_echo_is_refused_and_records_nothing(
        self, pr_fixture, monkeypatch, capsys, echo, why
    ):
        """DISARM direction: the reviewer did not read what we collected."""
        _runs_dir(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)

        over = echo(subject)
        assert (over.get("bytes"), over.get("sha")) != (
            subject["diff_bytes"],
            subject["diff_sha256"],
        ), f"premise: the echo under test must be wrong — {why}"
        code = rc.main(_delegate_args(subject, **over))
        err = capsys.readouterr().err
        assert code == 2, why
        assert _reason(err) == "echo-mismatch", why
        assert _no_events(pr_fixture.worktree), why

        # Positive control, same fixture: the correct echo DOES record.
        assert rc.main(_delegate_args(subject)) == 0
        assert len(_events(pr_fixture.worktree)) == 1

    def test_zero_byte_collection_cannot_be_delegated_even_with_a_true_echo(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-2: a zero-byte subject is refused BEFORE the echo is
        considered."""
        _runs_dir(pr_fixture.worktree)
        noop = _git(pr_fixture.clone, "rev-parse", "refs/remotes/origin/main")
        pr_fixture.set_gh(headRefOid=noop)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)

        code = rc.main(
            _delegate_args(
                {
                    "head_oid": noop,
                    "diff_bytes": 0,
                    "diff_sha256": hashlib.sha256(b"").hexdigest(),
                }
            )
        )
        err = capsys.readouterr().err
        assert code == 1
        assert "reason=empty-diff-head-is-merge-base" in err
        assert _no_events(pr_fixture.worktree)

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
            _delegate_args(
                {"head_oid": "a" * 40, "diff_bytes": 1, "diff_sha256": "a" * 64}
            )
        )
        assert code == 2
        assert "reason=head-oid-unreachable" in capsys.readouterr().err
        assert _no_events(narrow)

    def test_echo_flags_are_required(self, pr_fixture, monkeypatch, capsys):
        """An omitted echo must not be read as a passing echo — pinned to
        the."""
        _runs_dir(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        code = rc.main(
            ["delegate", "--dimension", "code", "--pr", PR_NUMBER, "--issue", "ISSUE-096"]
        )
        out = capsys.readouterr()
        assert code == 2
        assert "--echoed-sha256" in out.err
        assert _no_events(pr_fixture.worktree)
        # Positive control: with the echo supplied, the same call records.
        subject = _collect_json(capsys)
        assert rc.main(_delegate_args(subject)) == 0
        assert len(_events(pr_fixture.worktree)) == 1

    def test_a_head_that_moved_mid_review_is_its_own_reason(
        self, pr_fixture, monkeypatch, capsys
    ):
        """A valid verdict must not be discarded under misleading text."""
        _runs_dir(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)

        (pr_fixture.worktree / "src" / "more.py").write_text("X = 1\n", encoding="utf-8")
        _git(pr_fixture.worktree, "add", "src/more.py")
        _git(pr_fixture.worktree, "commit", "-m", "head moves mid-review")
        moved = _git(pr_fixture.worktree, "rev-parse", "HEAD")
        pr_fixture.set_gh(headRefOid=moved)

        code = rc.main(_delegate_args(subject))
        err = capsys.readouterr().err
        assert code == 2
        assert _reason(err) == "head-moved"
        assert subject["head_oid"][:12] in err and moved[:12] in err
        assert _no_events(pr_fixture.worktree)

    def test_delegate_refuses_when_its_verification_cannot_be_recorded(
        self, pr_fixture, monkeypatch, capsys
    ):
        """A passing echo whose receipt has nowhere to go must fail HERE,."""
        pr_fixture.activate(monkeypatch)
        subject = _collect_json(capsys)  # no KIT_RUN_ID, no runs dir
        code = rc.main(_delegate_args(subject))
        err = capsys.readouterr().err
        assert code == 2
        assert _reason(err) == "verification-unconfigured"
        assert rc.RUN_ID_ENV in err
        assert ".claude/runs" in err

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root ignores the 0444 mode that makes the receipt append fail",
    )
    def test_delegate_refuses_when_only_another_dimension_was_recorded(
        self, pr_fixture
    ):
        """The read-back must be bound to the dimension AT HAND.

        Reproduced three times in review: with the run file readable but
        un-appendable (ENOSPC, a read-only mount, a ``chmod`` sweep)
        ``_emit_event`` swallows the write by contract, so "did ANY dimension
        verify?" is satisfied by the OTHER dimension's line and every
        dimension after the first passes with no receipt of its own. Driven
        through the real CLI and asserted PER DIMENSION — a whole-file
        assertion is the shape that let this through the first disarm matrix.
        """
        runs = _runs_dir(pr_fixture.worktree)
        env = pr_fixture.env()
        base = [sys.executable, str(SCRIPTS_DIR / "review_context.py")]
        collected = subprocess.run(
            base + ["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"],
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert collected.returncode == 0, collected.stderr
        subject = json.loads(collected.stdout)

        first = subprocess.run(
            base + _delegate_args(subject, dimension="code"),
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert first.returncode == 0, first.stderr

        run_file = runs / f"{RUN_ID}.jsonl"
        run_file.chmod(0o444)
        second = subprocess.run(
            base + _delegate_args(subject, dimension="security"),
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        run_file.chmod(0o644)

        assert [e["event_type"] for e in _events(pr_fixture.worktree)] == [
            "review_delegated_to_code_review"
        ], "premise: the security receipt must not have landed"
        assert second.returncode == 2, second.stdout
        assert _reason(second.stderr) == "verification-missing"
        assert "security" in second.stderr
        assert ".claude/runs" in second.stderr

    def test_delegate_through_a_real_subprocess_boundary(self, pr_fixture):
        """Lesson 16: exercise the defence through its real consumer."""
        _runs_dir(pr_fixture.worktree)
        env = pr_fixture.env()
        base = [sys.executable, str(SCRIPTS_DIR / "review_context.py")]
        collected = subprocess.run(
            base + ["collect", "--pr", PR_NUMBER, "--issue", "ISSUE-096"],
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert collected.returncode == 0, collected.stderr
        subject = json.loads(collected.stdout)

        bad = subprocess.run(
            base + _delegate_args(
                subject, dimension="security", bytes=0,
                sha=hashlib.sha256(b"").hexdigest(),
            ),
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert bad.returncode == 2
        assert _reason(bad.stderr) == "echo-mismatch"
        assert _no_events(pr_fixture.worktree)

        good = subprocess.run(
            base + _delegate_args(subject, dimension="security"),
            cwd=str(pr_fixture.clone), capture_output=True, text=True, env=env,
        )
        assert good.returncode == 0, good.stderr
        assert len(_events(pr_fixture.worktree)) == 1


# ── AC-5: counter-evidence the record did not produce itself ─────────


NOTES_BODY = (
    "# Review Notes — PR #7\n\n## Code Review\n_Source: code-review_\n\n"
    "_No findings._\n\n## Security Findings\n_Source: security-review_\n\n"
    "_No findings._\n\n## Over-Engineering\n\n_No findings._\n"
)


def _write_notes(root: Path, body: str = NOTES_BODY) -> Path:
    path = root / "docs" / "review_notes" / "ISSUE-096.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture()
def verified(pr_fixture, monkeypatch, capsys):
    """A subject whose echo gate PASSED — i.e. a receipt exists to consume."""
    _runs_dir(pr_fixture.worktree)
    pr_fixture.activate(monkeypatch)
    monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
    subject = _collect_json(capsys)
    assert rc.main(_delegate_args(subject)) == 0, capsys.readouterr().err
    capsys.readouterr()
    return subject


class TestCounterEvidenceConsumesAPassingDelegation:
    """AC-5 — the block is written only against a receipt from the echo gate."""

    def test_record_subject_writes_the_verified_subject(
        self, pr_fixture, verified, capsys
    ):
        notes = _write_notes(pr_fixture.worktree)
        assert rc.main(RECORD_ARGS) == 0
        out = capsys.readouterr()
        text = notes.read_text(encoding="utf-8")
        assert rc.SUBJECT_HEADING in text
        assert f"- diff_bytes: {verified['diff_bytes']}" in text
        assert f"- head_oid: {verified['head_oid']}" in text
        assert f"- diff_sha256: {verified['diff_sha256']}" in text
        assert "- verified_dimensions: code" in text
        assert "- worktree_source: branch-worktree" in text
        # The verdict the notes already carried is preserved, not rewritten.
        assert "## Code Review" in text
        assert text.startswith("# Review Notes — PR #7")
        # The committed file is pushed to a public remote: no absolute local
        # path goes into it. ``worktree_source`` carries the semantic content,
        # and the operator still sees WHERE the block went, on stdout.
        assert verified["worktree_path"] not in text
        assert "- worktree_path:" not in text
        assert verified["worktree_path"] in out.out
        assert "worktree_source=branch-worktree" in out.out

    def test_no_delegation_receipt_means_no_counter_evidence(
        self, pr_fixture, monkeypatch, capsys
    ):
        """AC-5's purpose, as a test: a run where nothing delegated. This
        used."""
        _runs_dir(pr_fixture.worktree)
        notes = _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        code = rc.main(RECORD_ARGS)
        err = capsys.readouterr().err
        assert code == 2
        assert _reason(err) == "verification-missing"
        assert notes.read_text(encoding="utf-8") == NOTES_BODY

    def test_a_rejected_echo_leaves_nothing_for_the_record_to_consume(
        self, pr_fixture, monkeypatch, capsys
    ):
        """"Invoked and REJECTED" must not render like "invoked and passed"."""
        _runs_dir(pr_fixture.worktree)
        notes = _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)
        assert rc.main(_delegate_args(subject, bytes=0,
                                     sha=hashlib.sha256(b"").hexdigest())) == 2
        capsys.readouterr()

        assert rc.main(RECORD_ARGS) == 2
        assert _reason(capsys.readouterr().err) == "verification-missing"
        assert notes.read_text(encoding="utf-8") == NOTES_BODY

    def test_an_unconfigured_run_id_is_a_named_refusal_not_a_pass(
        self, pr_fixture, monkeypatch, capsys
    ):
        """No run id => no run file => no receipt. Never a silent pass."""
        notes = _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        code = rc.main(RECORD_ARGS)
        err = capsys.readouterr().err
        assert code == 2
        assert _reason(err) == "verification-unconfigured"
        assert rc.RUN_ID_ENV in err
        assert notes.read_text(encoding="utf-8") == NOTES_BODY

    @pytest.mark.parametrize(
        "mutate,why",
        [
            ({"head_oid": "f" * 40}, "a receipt for a different head"),
            ({"diff_sha256": "f" * 64}, "a receipt for different content"),
            ({"diff_bytes": 1}, "a receipt for a different byte count"),
        ],
        ids=["head", "sha", "bytes"],
    )
    def test_a_receipt_for_a_different_subject_does_not_count(
        self, pr_fixture, monkeypatch, capsys, mutate, why
    ):
        """Workspace-persisted state consumed by a gate is untrusted input."""
        runs = _runs_dir(pr_fixture.worktree)
        notes = _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)
        payload = {
            "pr_number": PR_NUMBER,
            "diff_bytes": subject["diff_bytes"],
            "diff_sha256": subject["diff_sha256"],
            "head_oid": subject["head_oid"],
        }
        payload.update(mutate)
        (runs / f"{RUN_ID}.jsonl").write_text(
            json.dumps(
                {
                    "ts": "2026-10-31T00:00:00+00:00",
                    "event_type": "review_delegated_to_code_review",
                    "skill_or_script": "review_context",
                    "issue_id": "ISSUE-096",
                    "payload": payload,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert rc.main(RECORD_ARGS) == 2, why
        assert _reason(capsys.readouterr().err) == "verification-missing"
        assert notes.read_text(encoding="utf-8") == NOTES_BODY

    def test_a_receipt_for_a_different_issue_does_not_count(
        self, pr_fixture, monkeypatch, capsys
    ):
        runs = _runs_dir(pr_fixture.worktree)
        _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        subject = _collect_json(capsys)
        (runs / f"{RUN_ID}.jsonl").write_text(
            json.dumps(
                {
                    "event_type": "review_delegated_to_code_review",
                    "issue_id": "ISSUE-777",
                    "payload": {
                        "diff_bytes": subject["diff_bytes"],
                        "diff_sha256": subject["diff_sha256"],
                        "head_oid": subject["head_oid"],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert rc.main(RECORD_ARGS) == 2
        assert _reason(capsys.readouterr().err) == "verification-missing"

    def test_a_malformed_run_file_does_not_hide_a_real_receipt(
        self, pr_fixture, verified, capsys
    ):
        """Untrusted input: skip the junk lines, keep reading."""
        runs = _runs_dir(pr_fixture.worktree)
        path = runs / f"{RUN_ID}.jsonl"
        good = path.read_text(encoding="utf-8")
        path.write_text(
            "not json at all\n[]\n{}\n" + '{"event_type": 7}\n' + good,
            encoding="utf-8",
        )
        _write_notes(pr_fixture.worktree)
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err

    def test_a_non_regular_run_file_is_a_named_refusal(
        self, pr_fixture, monkeypatch, capsys
    ):
        """A planted FIFO must not hang the gate (ISSUE-070's lesson)."""
        runs = _runs_dir(pr_fixture.worktree)
        os.mkfifo(runs / f"{RUN_ID}.jsonl")
        _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        code = rc.main(RECORD_ARGS)
        assert code == 2
        assert _reason(capsys.readouterr().err) == "verification-unreadable"

    def test_a_symlinked_run_file_is_not_followed(
        self, pr_fixture, monkeypatch, capsys
    ):
        runs = _runs_dir(pr_fixture.worktree)
        decoy = pr_fixture.worktree / "decoy.jsonl"
        decoy.write_text("{}\n", encoding="utf-8")
        (runs / f"{RUN_ID}.jsonl").symlink_to(decoy)
        _write_notes(pr_fixture.worktree)
        pr_fixture.activate(monkeypatch)
        monkeypatch.setenv("KIT_RUN_ID", RUN_ID)
        assert rc.main(RECORD_ARGS) == 2
        assert _reason(capsys.readouterr().err) == "verification-unreadable"


class TestCounterEvidenceSurvivesASecondReviewCycle:
    """The gate's own output must not invalidate the gate: step 6 commits
    and."""

    def test_a_committed_block_does_not_wedge_the_next_cycle(
        self, pr_fixture, verified, monkeypatch, capsys
    ):
        notes = _write_notes(pr_fixture.worktree)
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err
        capsys.readouterr()
        first = notes.read_text(encoding="utf-8")

        # Exactly what step 6 does: commit the notes. The head moves.
        _git(pr_fixture.worktree, "add", "docs/review_notes/ISSUE-096.md")
        _git(pr_fixture.worktree, "commit", "-m", "docs: review notes")
        moved = _git(pr_fixture.worktree, "rev-parse", "HEAD")
        assert moved != verified["head_oid"], "fixture failed to move the head"
        pr_fixture.set_gh(headRefOid=moved)

        # Cycle 2: a fresh collection, a fresh passing echo, a fresh record.
        second_subject = _collect_json(capsys)
        assert second_subject["head_oid"] == moved
        assert rc.main(_delegate_args(second_subject)) == 0, capsys.readouterr().err
        capsys.readouterr()
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err

        text = notes.read_text(encoding="utf-8")
        assert text.count(rc.SUBJECT_HEADING) == 1, "the block was appended twice"
        assert f"- head_oid: {moved}" in text
        assert verified["head_oid"] not in text
        assert text != first
        assert text.startswith("# Review Notes — PR #7")
        assert "## Code Review" in text

    def test_record_subject_is_idempotent_at_an_unchanged_head(
        self, pr_fixture, verified, capsys
    ):
        notes = _write_notes(pr_fixture.worktree)
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err
        first = notes.read_text(encoding="utf-8")
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err
        assert notes.read_text(encoding="utf-8") == first
        assert first.count(rc.SUBJECT_HEADING) == 1

    @pytest.mark.parametrize(
        "pre,why",
        [
            (
                f"- diff_bytes: 999999\n- head_oid: {'0' * 40}\n",
                "a hand-written block cannot make the record disagree with "
                "reality",
            ),
            (
                f"- head_oid: {'0' * 40}\n",
                "AC-5's disarm: the record may not end up carrying one value",
            ),
        ],
        ids=["forged", "incomplete"],
    )
    def test_a_pre_existing_block_is_replaced_by_the_verified_one(
        self, pr_fixture, verified, capsys, pre, why
    ):
        notes = _write_notes(
            pr_fixture.worktree, NOTES_BODY + f"\n{rc.SUBJECT_HEADING}\n" + pre
        )
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err
        text = notes.read_text(encoding="utf-8")
        assert f"- diff_bytes: {verified['diff_bytes']}" in text, why
        assert f"- head_oid: {verified['head_oid']}" in text, why
        assert "999999" not in text
        assert "0" * 40 not in text
        assert text.count(rc.SUBJECT_HEADING) == 1


class TestARefusalLeavesTheNotesUntouched:
    """Review lesson 12 on the WRITE side: the gate ran downstream of the
    mutation it gates.

    The read-back ran AFTER the write, so one unpaired code fence — which
    ``synthesize_review_notes.py`` produces whenever a finding's multi-line
    ``evidence`` puts a ``` at column 0 — made the append branch run, write,
    and only then fail: measured over three invocations as exit 2 with the
    literal heading count going 1 → 2 → 3, i.e. permanent wedging plus
    unbounded growth. The candidate is validated BEFORE it is written.
    """

    #: A synthesized finding whose evidence opens a fence and never closes it.
    FENCED = (
        "# Review Notes — PR #7\n\n## Code Review\n_Source: code-review_\n\n"
        "- **[Low] a finding whose evidence quotes a snippet**\n"
        "  Evidence: scripts/x.py:1 — the synthesizer indents only the FIRST\n"
        "  line of `evidence`, so the fence below sits at column 0:\n"
        "```python\n"
        "def unterminated():\n"
        "    return 1\n"
        "\n## Security Findings\n_Source: security-review_\n\n_No findings._\n\n"
        "## Over-Engineering\n\n_No findings._\n"
    )

    def test_an_unterminated_fence_refuses_without_writing(
        self, pr_fixture, verified, capsys
    ):
        notes = _write_notes(pr_fixture.worktree, self.FENCED)
        assert rc._subject_blocks(self.FENCED) == [], "premise: the fence is open"
        code = rc.main(RECORD_ARGS)
        err = capsys.readouterr().err
        assert code == 2
        assert _reason(err) == "subject-incomplete"
        assert "fence" in err, (
            "the refusal must NAME the cause; 'could not read both values back' "
            "sends the operator to debug the wrong half"
        )
        assert notes.read_text(encoding="utf-8") == self.FENCED

    def test_three_retries_do_not_accumulate_blocks(
        self, pr_fixture, verified, capsys
    ):
        """1 → 2 → 3 headings was the measured growth. It must stay at 0."""
        notes = _write_notes(pr_fixture.worktree, self.FENCED)
        for attempt in range(3):
            assert rc.main(RECORD_ARGS) == 2, attempt
            capsys.readouterr()
        text = notes.read_text(encoding="utf-8")
        assert text == self.FENCED
        assert text.count(rc.SUBJECT_HEADING) == 0


class TestNotesFileBoundaryFailuresAreNamed:
    def test_present_but_unparseable_block_is_not_read_as_absent(
        self, pr_fixture, verified, capsys
    ):
        """Otherwise the append branch runs, the file ends with TWO blocks,."""
        notes = _write_notes(
            pr_fixture.worktree,
            NOTES_BODY + f"\n{rc.SUBJECT_HEADING}\n\nnothing parseable here\n",
        )
        code = rc.main(RECORD_ARGS)
        err = capsys.readouterr().err
        assert code == 2
        assert _reason(err) == "subject-unparseable"
        assert notes.read_text(encoding="utf-8").count(rc.SUBJECT_HEADING) == 1

    def test_duplicate_blocks_are_their_own_named_refusal(
        self, pr_fixture, verified, capsys
    ):
        """Two blocks = two claims; only one could ever be checked."""
        block = f"\n{rc.SUBJECT_HEADING}\n- diff_bytes: 1\n- head_oid: {'0' * 40}\n"
        notes = _write_notes(pr_fixture.worktree, NOTES_BODY + block + block)
        code = rc.main(RECORD_ARGS)
        assert code == 2
        assert _reason(capsys.readouterr().err) == "subject-duplicate-block"
        # Positive control: one block in the same fixture is accepted.
        notes.write_text(NOTES_BODY + block, encoding="utf-8")
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err

    def test_missing_notes_file_is_a_named_refusal(
        self, pr_fixture, verified, capsys
    ):
        assert rc.main(RECORD_ARGS) == 2
        assert _reason(capsys.readouterr().err) == "review-notes-missing"

    def test_a_symlinked_notes_file_is_not_followed(
        self, pr_fixture, verified, capsys
    ):
        """``open("a")`` followed an in-project symlink: measured in review,
        a."""
        victim = pr_fixture.worktree / "src" / "app.py"
        before = victim.read_text(encoding="utf-8")
        notes = pr_fixture.worktree / "docs" / "review_notes" / "ISSUE-096.md"
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.symlink_to(victim)

        code = rc.main(RECORD_ARGS)
        assert code == 2
        assert _reason(capsys.readouterr().err) == "review-notes-not-a-file"
        assert victim.read_text(encoding="utf-8") == before

    def test_the_write_half_refuses_a_symlink_on_its_own(self, tmp_path):
        """Defence-in-depth, pinned at its own boundary: through the CLI
        the."""
        victim = tmp_path / "victim.mk"
        victim.write_text("all:\n\techo real\n", encoding="utf-8")
        link = tmp_path / "notes.md"
        link.symlink_to(victim)
        with pytest.raises(rc.SubjectRefused) as excinfo:
            rc._write_notes(link, "counter-evidence\n")
        assert excinfo.value.reason == "review-notes-not-a-file"
        assert excinfo.value.exit_code == 2
        assert victim.read_text(encoding="utf-8") == "all:\n\techo real\n"

    def test_the_write_half_never_creates_a_missing_file(self, tmp_path):
        """No ``O_CREAT``: the notes are the synthesizer's artifact, and."""
        missing = tmp_path / "absent.md"
        with pytest.raises(rc.SubjectRefused) as excinfo:
            rc._write_notes(missing, "counter-evidence\n")
        assert excinfo.value.reason == "review-notes-not-a-file"
        assert not missing.exists()

    def test_notes_resolving_outside_the_project_are_refused(
        self, pr_fixture, verified, tmp_path, capsys
    ):
        """A symlinked notes DIRECTORY is the remaining escape route."""
        outside = tmp_path / "outside"
        (outside / "review_notes").mkdir(parents=True)
        victim = outside / "review_notes" / "ISSUE-096.md"
        victim.write_text(NOTES_BODY, encoding="utf-8")
        docs = pr_fixture.worktree / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "review_notes").symlink_to(outside / "review_notes")

        code = rc.main(RECORD_ARGS)
        assert code == 2
        assert _reason(capsys.readouterr().err) == "review-notes-outside-project"
        assert victim.read_text(encoding="utf-8") == NOTES_BODY

    def test_refused_collection_writes_no_counter_evidence(
        self, pr_fixture, verified, capsys
    ):
        """A subject that could not be established must not bless the notes."""
        notes = _write_notes(pr_fixture.worktree)
        pr_fixture.set_gh(__fail__="gh: no such PR\n")
        assert rc.main(RECORD_ARGS) == 2
        assert _reason(capsys.readouterr().err) == "gh-failed"
        assert notes.read_text(encoding="utf-8") == NOTES_BODY

    def test_undecodable_notes_do_not_crash_the_gate(
        self, pr_fixture, verified, capsys
    ):
        notes = _write_notes(pr_fixture.worktree)
        notes.write_bytes(b"# notes \xff\xfe not utf-8\n")
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err
        assert rc.SUBJECT_HEADING in notes.read_text(
            encoding="utf-8", errors="replace"
        )


class TestTheRecordLandsInTheBranchWorktree:
    def test_notes_are_written_where_the_branch_lives_not_where_cwd_is(
        self, pr_fixture, verified, capsys
    ):
        """CWD is the MAIN checkout; the notes belong to the PR's worktree."""
        _write_notes(pr_fixture.worktree)
        main_notes = pr_fixture.clone / "docs" / "review_notes" / "ISSUE-096.md"
        main_notes.parent.mkdir(parents=True, exist_ok=True)
        main_notes.write_text(NOTES_BODY, encoding="utf-8")

        assert Path.cwd() == pr_fixture.clone
        assert rc.main(RECORD_ARGS) == 0, capsys.readouterr().err

        assert rc.SUBJECT_HEADING in (
            pr_fixture.worktree / "docs" / "review_notes" / "ISSUE-096.md"
        ).read_text(encoding="utf-8")
        assert main_notes.read_text(encoding="utf-8") == NOTES_BODY


# ── the heading detector: a line-anchored, fence-aware match ─────────


class TestSubjectBlockDetection:
    """A bare ``text.count("## Review Subject")`` matched four decoys — all."""

    REAL = f"intro\n\n{rc.SUBJECT_HEADING}\n- diff_bytes: 1\n"

    @pytest.mark.parametrize(
        "text,why",
        [
            (f"### Review Subject\n- diff_bytes: 1\n", "an h3, not the block"),
            ("## Review Subject (archived)\n- diff_bytes: 1\n", "a different heading"),
            (
                "```\n## Review Subject\n- diff_bytes: 1\n```\n",
                "inside a fenced code block",
            ),
            (
                "~~~md\n## Review Subject\n- diff_bytes: 1\n~~~\n",
                "inside a tilde fence",
            ),
            (
                "The gate appends a `## Review Subject` block to the notes.\n",
                "prose quoting the heading — this PR's own review notes do it",
            ),
            ("  ## Review Subject\n", "indented, so not an ATX heading"),
        ],
        ids=["h3", "suffixed", "backtick-fence", "tilde-fence", "prose", "indented"],
    )
    def test_decoys_are_not_blocks(self, text, why):
        assert rc._subject_blocks(text) == [], why

    def test_the_real_heading_is_found(self):
        assert len(rc._subject_blocks(self.REAL)) == 1

    def test_duplicates_are_both_found(self):
        assert len(rc._subject_blocks(self.REAL + "\n" + self.REAL)) == 2

    def test_a_block_terminates_at_a_later_h1(self):
        text = (
            f"{rc.SUBJECT_HEADING}\n- diff_bytes: 1\n"
            "\n# Appendix\n- diff_bytes: 2\n"
        )
        recorded = rc._parse_recorded_subject(text)
        assert recorded["diff_bytes"] == ["1"], (
            "the block ran past a later h1 and swallowed its lines"
        )

    def test_a_block_terminates_at_the_next_h2(self):
        text = (
            f"{rc.SUBJECT_HEADING}\n- diff_bytes: 1\n"
            "\n## Next Section\n- diff_bytes: 2\n"
        )
        assert rc._parse_recorded_subject(text)["diff_bytes"] == ["1"]

    def test_every_occurrence_of_a_key_is_collected(self):
        """First-occurrence-wins lets a true line be followed by a false
        one."""
        text = f"{rc.SUBJECT_HEADING}\n- diff_bytes: 1\n- diff_bytes: 2\n"
        assert rc._parse_recorded_subject(text)["diff_bytes"] == ["1", "2"]

    def test_the_fence_pattern_matches_the_suites_oracle(self):
        """A hand-rolled parser must not drift from the oracle it mirrors:"""
        assert rc._FENCE_RE.pattern == sprint_queue._FENCE_RE.pattern


# ── AC-7: the pre-existing decision surface is untouched ─────────────


class TestDecisionSurfaceUnchanged:
    """AC-7's ``decide`` command is discharged by
    ``tests/test_review_context.py``."""

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


def _skill_texts() -> list[tuple[str, str]]:
    return [
        (name, (KIT_ROOT / "skills" / "review" / name).read_text(encoding="utf-8"))
        for name in ("SKILL.md.tmpl", "SKILL.md")
    ]


def _step_3_1(text: str) -> str:
    start = text.index("\n3.1)")
    return text[start : text.index("\n3.2)", start)]


#: Occurrence WHITELIST for step 3.1 — (regex, why). Not a phrasing blacklist:
#: a rewording that keeps the obligation passes, and a rewording that drops it
#: fails. Each entry is mutation-tested below by deleting it from the REAL text.
# The dated 48.5KB / "accepts no review target" anecdote is deliberately NOT
# pinned here: MATRIX_ROW_REQUIREMENTS below already pins those strings,
# mutation-tested, in the file that owns the measurement. This whitelist pins
# step 3.1's OBLIGATIONS instead.
STEP_31_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    (r"review_context\.py collect", "name the executable collection step"),
    (r"review_context\.py delegate", "name the executable echo gate"),
    (r"--echoed-bytes", "the byte count must be echoed by the consumer"),
    (r"--echoed-sha256", "the digest must be echoed by the consumer"),
    (r"--head-oid", "pin the subject, so a moved head is not a mismatch"),
    (r"diff_command", "the reviewer gets the exact argv the gate measures"),
    (
        r"[Dd]o not let it auto-collect",
        "the prohibition itself: the harness auto-collecting its own subject "
        "IS the defect, and an anecdote about it is not a prohibition",
    ),
    (
        r"[Dd]o not fabricate",
        "an echo the orchestrator invents is the one remaining fail-open",
    ),
    (r"KIT_RUN_ID", "the receipt has no home without a run id"),
    (
        r"KIT_RUN_ID=review-\$ARGUMENTS python3 scripts/review_context\.py emit",
        "`cmd_emit` treats an unset run id as a silent no-op at exit 0, so "
        "without the knob the one record of WHY a dimension degraded is lost",
    ),
)


class TestSkillTemplateBindsTheSubject:
    """The decision: the checkable half lives in the script, and step 3.1."""

    @pytest.mark.parametrize(
        "pattern,why", STEP_31_REQUIREMENTS, ids=lambda v: str(v)[:38]
    )
    def test_step_3_1_carries_each_required_occurrence(self, pattern, why):
        for name, text in _skill_texts():
            assert re.search(pattern, _step_3_1(text)), f"{name}: {why}"

    @pytest.mark.parametrize(
        "pattern,why", STEP_31_REQUIREMENTS, ids=lambda v: str(v)[:38]
    )
    def test_removing_any_required_occurrence_fails_the_guard(self, pattern, why):
        """Mutation-tested against the REAL text, per requirement: an."""
        block = _step_3_1((KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl").read_text(
            encoding="utf-8"
        ))
        assert re.search(pattern, block), f"premise: /{pattern}/ is in the real text"
        assert not re.search(pattern, re.sub(pattern, "", block)), why

    def test_counter_evidence_step_runs_after_every_synthesizer_call(self):
        """Review lesson 12: pin POSITION, not just presence."""
        for name, text in _skill_texts():
            last_synth = text.rindex("synthesize_review_notes.py")
            record = text.index("review_context.py record-subject")
            assert record > last_synth, (
                f"{name}: the record-subject call must stay DOWNSTREAM of EVERY "
                "synthesizer call that rewrites the notes it checks"
            )

    def test_the_record_step_supplies_the_run_id_the_receipt_lives_under(self):
        for name, text in _skill_texts():
            line_start = text.index("review_context.py record-subject")
            line = text[text.rindex("\n", 0, line_start) : line_start]
            assert "KIT_RUN_ID" in line, (
                f"{name}: record-subject consumes the delegation receipt, so the "
                "run id must be on its own command line"
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
        """Review lesson: a new env knob needs a line in the owning
        module's."""
        module = (SCRIPTS_DIR / "review_context.py").read_text(encoding="utf-8")
        docstring = module.split('"""', 2)[1]
        assert rc.GH_TIMEOUT_ENV in docstring
        assert rc.GH_TIMEOUT_ENV in (KIT_ROOT / "README.md").read_text(encoding="utf-8")

    def test_the_docstring_does_not_claim_one_collection_per_run(self):
        """A false docstring claim is a defect in a PR about
        counter-evidence: the collection runs FOUR times per run."""
        module = (SCRIPTS_DIR / "review_context.py").read_text(encoding="utf-8")
        docstring = module.split('"""', 2)[1]
        assert "ONCE per review run" in docstring, (
            "the `decide` contract genuinely is once per run — this test is "
            "about the COLLECTION claim, so the decide wording must survive"
        )
        collect_claim = docstring[docstring.index("Subject binding (ISSUE-096)"):]
        assert "ONCE per review run" not in collect_claim
        assert "four times per review run" in collect_claim


MATRIX = KIT_ROOT / "docs" / "cc_feature_matrix.md"

#: The 2026-10-31 measurement, as an occurrence whitelist on the matrix row.
MATRIX_ROW_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    (r"2026-10-31", "dated, like every other local-probe row"),
    (r"48\.5KB", "the literal byte figure the harness reported receiving"),
    (r"On branch main", "the literal git status — the wrong CHECKOUT, verbatim"),
    (r"discard", "the pinned arguments were DISCARDED, not merely ignored"),
    (
        r"Bash completed with no output",
        "the other arm: from the worktree it collects NOTHING, so neither "
        "CWD works",
    ),
    (r"ISSUE-096", "the consumer of this row"),
)


class TestTheMatrixCarriesTheReviewTargetMeasurement:
    """AC-6's sibling measurement: can a caller pin what the runtime
    reviews?"""

    @staticmethod
    def _row() -> str:
        for line in MATRIX.read_text(encoding="utf-8").splitlines():
            if "accepts no review target" in line:
                return line
        raise AssertionError(
            "docs/cc_feature_matrix.md carries no row for the runtime "
            "review-target measurement (2026-10-31)"
        )

    @pytest.mark.parametrize(
        "pattern,why", MATRIX_ROW_REQUIREMENTS, ids=lambda v: str(v)[:38]
    )
    def test_each_observation_is_present(self, pattern, why):
        assert re.search(pattern, self._row()), why

    @pytest.mark.parametrize(
        "pattern,why", MATRIX_ROW_REQUIREMENTS, ids=lambda v: str(v)[:38]
    )
    def test_removing_any_observation_fails_the_guard(self, pattern, why):
        row = self._row()
        assert not re.search(pattern, re.sub(pattern, "", row)), why

    def test_the_row_is_a_well_formed_six_cell_matrix_row(self):
        cells = [c.strip() for c in self._row().strip().strip("|").split("|")]
        assert len(cells) == 6, (
            f"the matrix tables are 6-cell rows; this one has {len(cells)} — an "
            "unescaped `|` would also silently drop it from every other guard "
            "that parses this file"
        )

    def test_the_new_row_does_not_collide_with_the_issue_082_row_guard(self):
        """``tests/test_subagent_skill_grant.py`` selects rows whose
        FEATURE."""
        feature = [c.strip() for c in self._row().strip().strip("|").split("|")][1]
        assert not (
            re.search(r"sub-agent context", feature, re.IGNORECASE)
            and re.search(r"\bSkill\b", feature)
        ), feature
