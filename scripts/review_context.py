#!/usr/bin/env python3
"""Review execution-context decision + telemetry seam (ISSUE-066 / SPEC-066).

Decides the SPEC-019 review path ONCE per review run for both dimensions
(``code`` -> runtime ``/code-review``, ``security`` -> ``/security-review``),
combining two inputs:

- the **capability half**: the in-process ``has_skill.find_skill`` probe per
  dimension (exit 1 = definitive filesystem miss; 0/2 = installed/unknown),
- the **context half**: a model-reported ``--invocation-tools
  {present,absent}`` flag — the model checks its own tool list once for the
  runtime skill-invocation tool (a script cannot observe the model's
  toolset). The flag is validated closed-vocabulary data, not a directive
  (review lesson 10): both misreport directions converge on a review that
  still runs — degraded, or inline-fail-then-degraded.

  In a sub-task the token is ``Skill`` (``SlashCommand`` was absent from
  every probed sub-task context; the main-session path was not probed, so a
  ``SlashCommand`` tool still counts where one exists). The *sub-agent's*
  ``tools:`` wins over the invoked skill's ``allowed-tools``, so the grant
  that makes ``present`` reachable lives in ``agents/team-lead.md`` — the
  one agent that executes step 3.1. Full measurement, including that a
  grant does not imply provisioning (re-probe: ISSUE-082): the sub-agent
  skill-invocation row of ``docs/cc_feature_matrix.md``.

Decision table per dimension (``decide_review_context``):
    probe exit 1                      -> degraded, reason ``capability-absent``
    probe exit 0/2, tools ``absent``  -> degraded, reason ``context-unreachable``
    probe exit 0/2, tools ``present`` -> delegated (prose invokes the skill)

The reason vocabulary is exactly ``capability-absent`` /
``context-unreachable`` / ``inline-attempt-failed`` (hyphenated — the
ISSUE-066 ACs quote these strings). Decide-time reasons are emitted by the
``decide`` subcommand only; ``inline-attempt-failed`` is the single reason
the prose-side ``emit`` subcommand accepts for ``review_degraded_path_used``
(a ``delegated`` dimension whose inline invocation failed anyway —
probe-exit-2 ambiguity).

**Single emit call site**: ``_emit_event`` is the ONE function through which
every review delegation event is appended (``decide`` for decide-time
degradations, ``emit`` for the prose-side events) — do not add a second
emission call site. It carries the ISSUE-058 writer hardening — run-id
whitelist, runs-dir realpath containment, ``O_NOFOLLOW`` append, 4096-byte
event cap with long-string truncation, never raises — and **silently skips
when unconfigured**. Note the divergence: docs/telemetry_schema.md's "Append
behavior" section describes the *shared* emitter, which instead ANNOUNCES an
unresolvable run id and writes the event under ``unattributed``. This module
predates that change by one merge and keeps the older silent-skip semantics
until ISSUE-075; the Emit-site inventory in that doc records the difference.

Migration status (ship-time decision, 2026-10-11): the kit's shared emit SEAM
is now ``scripts/kit_telemetry.py::emit_event`` (ISSUE-067, landed just before
this module). This body was NOT swapped onto it, and the migration is tracked
as **ISSUE-075**. Rationale for deferring rather than doing it here: (1)
``emit_event``'s containment check and its documented "NEVER raises" contract
were both being rewritten by ISSUE-070 — the latter was *false* then
(reproducible by closing stdout), whereas this function's blanket
``except Exception`` makes the guarantee hold today, so adopting at that
point would have traded a working promise for a known-broken one inside the
review gate. **ISSUE-070 has since landed (PR #141)**: the never-raises
contract is now true and pinned by tests, so this reason is spent and
ISSUE-075 migrates against a tested promise;
(2) ISSUE-067
deliberately replaced silent-skip with announce-and-write-unattributed
semantics, so two tests here pin the opposite contract
(``test_unset_run_id_is_silent_noop_exit_0``, ``test_invalid_run_id_refused``)
and would have to be rewritten to assert the inverse in the same commit that
resolves a merge — not a change to make unreviewed. When ISSUE-075 runs, the
API is ``emit_event(event_type, payload=None, *, script_name, project_path,
issue_id)``: ``script_name`` is required keyword-only, ``issue_id`` is a
TOP-LEVEL event field (this module's ``--issue``), ``reason`` stays inside
``payload``, ``project_path`` must be passed explicitly (it defaults to
``Path.cwd()``), only ``payload["detail"]`` is truncated there — so preserve
this module's stronger all-string-value truncation at the call site — and
``False`` is a skip, not an error. One ISSUE-070 change the migration must
respect: ``project_path`` is NOT its own containment root there. That root
is derived from the process CWD's main git work tree, else
``CLAUDE_PROJECT_DIR``, else the CWD, and a ``project_path`` resolving
outside it is refused with an announcement and nothing written.

Subject binding (ISSUE-096) — what a ``delegated`` dimension may review
-----------------------------------------------------------------------

``decide`` only answers WHETHER to delegate. Four times across three sprints
(PRs #139, #141, #145 + one more) the runtime skill was then reached on the
``delegated`` path and **auto-collected its own subject by running git against
the MAIN checkout**, arriving with the literal ``DIFF CONTENT: (Bash completed
with no output)`` and ``GIT STATUS: On branch main``. Uncorrected, every one
of those passes would have returned a clean bill having reviewed nothing — a
silent fail-open on a blocking gate, whose defeated output is byte-identical
to its healthy one.

Three subcommands close that, and the division of labour is the decision this
issue made (`option (c)`: the script owns everything checkable, the step-3.1
prose consumes it — prose alone is precisely what was skipped four times):

- ``collect`` establishes the subject and REFUSES rather than yielding an
  empty one. The range is anchored on ``gh pr view --json headRefOid`` (head)
  and on ``refs/remotes/origin/<baseRefName>`` (base) — never on a bare
  ``main``, which DWIMs to the LOCAL ref; that is
  ``verify_checkpoint.py::_default_branch()``'s defect (ISSUE-089 owns it and
  it is deliberately not reproduced here). The base side is the **cached**
  remote-tracking ref: no fetch runs, so a ref stale against the live remote
  stays stale — named in the payload rather than hidden.
- ``delegate`` is the ECHO GATE: it re-establishes the subject and records a
  delegation only when the consumer echoes back the byte count and sha256 it
  measured. A producer-printed digest is an *attestation* — it proves only
  that the producer computed something; a consumer-echoed digest is a
  *verification*. The 2026-10-31 amendment measured why this matters: a
  materialised diff FILE was reported "not present" from the code reviewer's
  own context, and only the required byte-count echo caught it.
  **Disclosed residual (a claim, not a measurement):** the echo is checked for
  equality, not for provenance — an orchestrator holding ``collect``'s output
  could paste it without the reviewer having read anything (review lesson 6:
  an attestation that can satisfy a gate is forgeable). What the gate does
  remove is the SILENT arm: a reviewer handed nothing measures
  ``0``/``sha256(b"")`` and cannot produce a match, so the fail-open becomes
  an explicit fabrication instead of an invisible default. The pre-ISSUE-096
  ``emit --event review_delegated_to_*`` call path is retained ungated for the
  ISSUE-066 acceptance tests, so it remains a bypass for a caller that ignores
  step 3.1.
- ``record-subject`` puts the counter-evidence (byte count + head oid) into
  ``docs/review_notes/<ISSUE>.md`` and verifies it, so "reviewed nothing" can
  no longer render identically to "reviewed and found nothing". It must be
  invoked DOWNSTREAM of the synthesizer (step 3.14), which rewrites that file.

Refusal vocabulary (``SUBJECT_REASONS``) is closed and deliberately DISJOINT
from the three-value ``review_degraded_path_used`` vocabulary below: this
issue adds no fourth token there. An echo-gate rejection degrades through the
existing ``inline-attempt-failed`` token. A refusal prints ``reason=<token>``
on stderr and NOTHING on stdout, so ``SUBJ="$(… collect …)"`` cannot carry a
usable payload out of a failure (the ``wt_setup.sh``/ISSUE-083 precedent).

Env knobs (``KIT_RUN_ID`` is pre-documented in README and
docs/telemetry_schema.md):
    KIT_RUN_ID — run id for best-effort telemetry appends to
        ``<cwd>/.claude/runs/<run-id>.jsonl``. Unset or no runs dir =>
        emission is a silent no-op.
    KIT_REVIEW_GH_TIMEOUT — seconds to wait for the one ``gh pr view``
        consultation in ``collect`` (default 30; invalid or non-positive
        values fall back to the default). ``gh`` talks to the network and can
        STALL rather than fail, which would hang the review gate instead of
        failing it; a timeout is reported as ``reason=gh-timeout`` and the
        message names this knob. Also documented in README's environment
        table, next to ``KIT_WORKTREE_FETCH_TIMEOUT``.

Usage (from the project root — ``skills/review/SKILL.md`` step 3.1):
    python3 scripts/review_context.py decide --invocation-tools absent --issue ISSUE-066
    python3 scripts/review_context.py collect --pr 139 --issue ISSUE-096
    python3 scripts/review_context.py delegate --dimension code --pr 139 \\
        --issue ISSUE-096 --echoed-bytes 77801 --echoed-sha256 <hex>
    python3 scripts/review_context.py record-subject --pr 139 --issue ISSUE-096
    python3 scripts/review_context.py emit --event review_delegated_to_code_review --issue ISSUE-066 [--pr 123]
    python3 scripts/review_context.py emit --event review_degraded_path_used \\
        --dimension code --reason inline-attempt-failed --issue ISSUE-066

Exit codes: 0 = decision computed / event handled (telemetry no-op included)
/ subject established / gate passed;
1 = subject REFUSED because it was computed and is EMPTY (a no-op PR, or a
change that cancels itself out) — nothing to review, so nothing is delegated;
2 = bad input (closed-vocabulary violation, bad issue id format
ISSUE-<digits>), or the subject COULD NOT BE COMPUTED, or the consumer's echo
did not match. The 1/2 split is load-bearing: a gate whose subject is computed
must distinguish "computed and empty" from "could not compute".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import has_skill

_SCRIPT_NAME = "review_context"

# Dimension -> runtime skill name (the SPEC-019 review vocabulary).
DIMENSION_SKILLS: dict[str, str] = {
    "code": "code-review",
    "security": "security-review",
}

# Allowlisted prose-side events (docs/telemetry_schema.md, ISSUE-019 table).
DEGRADED_EVENT = "review_degraded_path_used"
ALLOWED_EMIT_EVENTS: tuple[str, ...] = (
    "review_delegated_to_code_review",
    "review_delegated_to_security_review",
    DEGRADED_EVENT,
)

# The only reason the prose-side emit seam accepts; decide-time reasons
# (capability-absent / context-unreachable) are emitted by `decide` only.
INLINE_ATTEMPT_FAILED = "inline-attempt-failed"

INVOCATION_TOOLS_VALUES: tuple[str, ...] = ("present", "absent")

_ISSUE_ID_RE = re.compile(r"ISSUE-\d+")

# Script-side run-id source for telemetry (docs/telemetry_schema.md).
RUN_ID_ENV = "KIT_RUN_ID"

# Hardened-append constants. These duplicate the shared emitter's
# (scripts/kit_telemetry.py, ISSUE-067) by value; ISSUE-075 deletes them when
# this module adopts that seam. synthesize_gate_results._emit_telemetry, the
# shape these originally mirrored, already delegates there.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_MAX_EVENT_BYTES = 4096
_MAX_DETAIL_CHARS = 512

# ── review-subject binding constants (ISSUE-096) ─────────────────────

#: Closed refusal vocabulary for the subject-collection step. DISJOINT from
#: the ``review_degraded_path_used`` reasons on purpose — a subject refusal is
#: not a degradation reason, and this issue adds no fourth token there.
SUBJECT_REASONS: tuple[str, ...] = (
    # computed, and empty (exit 1)
    "empty-diff-head-is-merge-base",
    "empty-diff-unexplained",
    # could not compute (exit 2)
    "gh-unavailable",
    "gh-failed",
    "gh-timeout",
    "gh-bad-output",
    "not-a-git-repo",
    "base-ref-unresolvable",
    "head-oid-unreachable",
    "merge-base-unresolvable",
    "git-diff-failed",
    # the consumer did not read what was collected (exit 2)
    "echo-mismatch",
    # counter-evidence in the review record (exit 2)
    "review-notes-missing",
    "review-notes-outside-project",
    "subject-incomplete",
    "subject-mismatch",
)

#: Heading of the counter-evidence block appended to the review notes.
SUBJECT_HEADING = "## Review Subject"

GH_TIMEOUT_ENV = "KIT_REVIEW_GH_TIMEOUT"
_GH_TIMEOUT_DEFAULT = 30

#: ``gh`` output crosses a trust boundary into a git argv. An oid must be
#: hex and a ref name must not be option-shaped.
_OID_RE = re.compile(r"[0-9a-f]{7,64}")
_REF_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+-]{0,199}")
_PR_RE = re.compile(r"[0-9]{1,12}")
_DIFF_HEADER_PREFIX = b"diff --git "


# ── pure decision table ──────────────────────────────────────────────


def decide_review_context(
    invocation_tools: str, probe=has_skill.find_skill
) -> dict[str, dict[str, str]]:
    """Decide the review path per dimension — ONCE for both dimensions.

    ``invocation_tools`` is the model-reported context half (``present`` /
    ``absent``); ``probe`` is the capability half (injectable for tests,
    defaults to :func:`has_skill.find_skill` returning ``(exit_code,
    evidence)``). Returns ``{"code": {"path": ..., "reason": ...},
    "security": {...}}`` with path ``delegated`` (reason ``""``) or
    ``degraded`` (reason ``capability-absent`` / ``context-unreachable``).

    Raises :class:`ValueError` on a closed-vocabulary violation — validated
    data, not a directive (review lesson 10).
    """
    if invocation_tools not in INVOCATION_TOOLS_VALUES:
        raise ValueError(
            f"invocation_tools must be one of {INVOCATION_TOOLS_VALUES}, "
            f"got {invocation_tools!r}"
        )
    decisions: dict[str, dict[str, str]] = {}
    for dimension, skill in DIMENSION_SKILLS.items():
        code, _evidence = probe(skill)
        if code == 1:
            decisions[dimension] = {"path": "degraded", "reason": "capability-absent"}
        elif invocation_tools == "absent":
            decisions[dimension] = {
                "path": "degraded",
                "reason": "context-unreachable",
            }
        else:
            decisions[dimension] = {"path": "delegated", "reason": ""}
    return decisions


# ── telemetry (best-effort, silent no-op, never raises) ──────────────


def _emit_event(
    project_path: Path,
    event_type: str,
    payload: dict,
    issue_id: str | None = None,
) -> None:
    """Append one schema-conformant event line; silent no-op when unconfigured.

    THE single emit call site for all review delegation events; the kit's
    shared emit SEAM is ``scripts/kit_telemetry.py::emit_event``, which this
    body is scheduled to adopt under ISSUE-075 (see the module docstring's
    "Migration status" for why that was deferred rather than done at
    ISSUE-066's ship). Hardened as an untrusted-path write: run-id is
    whitelist-validated, the runs dir realpath must stay inside the project,
    the event file is opened ``O_NOFOLLOW`` so a pre-planted symlink cannot
    redirect the append, long string values are truncated, and events over
    the 4096-byte POSIX-atomicity cap are dropped.
    """
    try:
        run_id = os.environ.get(RUN_ID_ENV, "").strip()
        if not _RUN_ID_RE.fullmatch(run_id):
            return
        runs_dir = Path(project_path) / ".claude" / "runs"
        if not runs_dir.is_dir():
            return
        if not runs_dir.resolve().is_relative_to(Path(project_path).resolve()):
            return
        trimmed: dict = {}
        for key, value in payload.items():
            if isinstance(value, str) and len(value) > _MAX_DETAIL_CHARS:
                value = value[:_MAX_DETAIL_CHARS] + "…[truncated]"
            trimmed[key] = value
        event: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "skill_or_script": _SCRIPT_NAME,
        }
        if issue_id is not None:
            event["issue_id"] = issue_id
        event["payload"] = trimmed
        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > _MAX_EVENT_BYTES:
            return
        fd = os.open(
            runs_dir / f"{run_id}.jsonl",
            os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:
        # Never fail the parent review run on a telemetry write error.
        return


# ── review subject: collection, echo gate, counter-evidence ──────────


class SubjectRefused(Exception):
    """A review subject could not be established, or is empty.

    ``exit_code`` is 1 when the subject was COMPUTED and is empty and 2 when
    it could not be computed at all — the distinction the four observed
    fail-opens erased.
    """

    def __init__(self, reason: str, detail: str, exit_code: int):
        assert reason in SUBJECT_REASONS, f"unknown refusal reason {reason!r}"
        super().__init__(f"reason={reason} {detail}")
        self.reason = reason
        self.detail = detail
        self.exit_code = exit_code


def _refuse(reason: str, detail: str, exit_code: int = 2) -> SubjectRefused:
    return SubjectRefused(reason, detail, exit_code)


def _reason_token(text: str) -> str | None:
    """Extract the ``reason=<token>`` a refusal rendered (tests + callers)."""
    match = re.search(r"reason=([a-z0-9-]+)", text)
    return match.group(1) if match else None


def _gh_timeout() -> int:
    """Seconds for the one ``gh`` consultation. Invalid values => default."""
    raw = os.environ.get(GH_TIMEOUT_ENV, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return _GH_TIMEOUT_DEFAULT
    return value if value > 0 else _GH_TIMEOUT_DEFAULT


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a LOCAL git command, capturing bytes (diffs are not text).

    No timeout: every call here is a local object-database read that
    terminates immediately. The network consultation is ``gh``, which IS
    bounded (``KIT_REVIEW_GH_TIMEOUT``).
    """
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)


def _git_text(cwd: Path, *args: str) -> tuple[int, str]:
    done = _git(cwd, *args)
    return done.returncode, done.stdout.decode("utf-8", "replace").strip()


def _pr_refs(pr: str, cwd: Path) -> dict[str, str]:
    """Ask ``gh`` for the PR's head oid and the two ref names.

    The head oid comes from ``gh pr view --json headRefOid`` — the PR's own
    record of what it is, not from whatever this checkout happens to have
    checked out.
    """
    if shutil.which("gh") is None:
        raise _refuse(
            "gh-unavailable",
            "`gh` is not on PATH, so the PR's head oid cannot be read. "
            "This is a missing tool, NOT an empty diff — install gh / run "
            "`gh auth login`.",
        )
    try:
        done = subprocess.run(
            ["gh", "pr", "view", pr, "--json", "baseRefName,headRefName,headRefOid"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_gh_timeout(),
        )
    except subprocess.TimeoutExpired:
        raise _refuse(
            "gh-timeout",
            f"`gh pr view {pr}` did not answer within {_gh_timeout()}s "
            f"(raise {GH_TIMEOUT_ENV} if the remote is merely slow). A stall "
            "is not an empty diff.",
        ) from None
    if done.returncode != 0:
        raise _refuse(
            "gh-failed",
            f"`gh pr view {pr}` exited {done.returncode}: "
            f"{done.stderr.strip()[:200]}",
        )
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        raise _refuse(
            "gh-bad-output",
            f"`gh pr view {pr}` did not return JSON: {done.stdout.strip()[:200]!r}",
        ) from None
    if not isinstance(payload, dict):
        raise _refuse("gh-bad-output", "`gh pr view` returned a non-object")

    refs = {key: str(payload.get(key, "")).strip() for key in
            ("headRefOid", "headRefName", "baseRefName")}
    if not _OID_RE.fullmatch(refs["headRefOid"]):
        raise _refuse(
            "gh-bad-output",
            f"headRefOid is not a hex oid: {refs['headRefOid']!r} — refusing "
            "to put it in a git argv",
        )
    for key in ("headRefName", "baseRefName"):
        if not _REF_NAME_RE.fullmatch(refs[key]):
            raise _refuse(
                "gh-bad-output", f"{key} is not a plain ref name: {refs[key]!r}"
            )
    return refs


def _resolve_worktree(branch: str, cwd: Path) -> tuple[Path, str]:
    """Find the checkout that holds ``branch``; else the main work tree.

    This is the half the measured failure got wrong: the collection ran where
    the CWD happened to be (the main checkout, on ``main``) instead of where
    the PR branch lives (``.worktrees/<slug>``). The returned path is where
    the diff is actually taken, so it is load-bearing rather than decorative.
    """
    code, out = _git_text(cwd, "worktree", "list", "--porcelain")
    if code != 0:
        raise _refuse(
            "not-a-git-repo",
            f"`git worktree list` failed in {cwd} — no checkout to collect from",
        )
    main_path: Path | None = None
    current: Path | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree "):])
            if main_path is None:
                main_path = current
        elif line.startswith("branch ") and current is not None:
            if line[len("branch "):] == f"refs/heads/{branch}":
                return current.resolve(), "branch-worktree"
    if main_path is None:
        raise _refuse("not-a-git-repo", f"no git work tree found at {cwd}")
    return main_path.resolve(), "main-checkout"


def collect_subject(pr: str, cwd: Path) -> dict:
    """Establish the reviewable subject, or raise :class:`SubjectRefused`.

    Which ref each endpoint comes from is part of the payload, not folklore:
    ``head`` is ``gh pr view --json headRefOid``, ``base`` is
    ``refs/remotes/origin/<baseRefName>`` (the cached remote-tracking ref — no
    fetch runs). A bare ``main`` is NOT used: it resolves to the local ref,
    which ISSUE-089 measured as a wrong diff subject.
    """
    if not _PR_RE.fullmatch(pr):
        raise _refuse("gh-bad-output", f"--pr must be a PR number, got {pr!r}")

    refs = _pr_refs(pr, cwd)
    head_oid = refs["headRefOid"]
    base_ref = f"refs/remotes/origin/{refs['baseRefName']}"

    code, base_oid = _git_text(cwd, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    if code != 0:
        raise _refuse(
            "base-ref-unresolvable",
            f"{base_ref} does not resolve in {cwd}. Refusing to fall back to "
            f"the local `{refs['baseRefName']}` ref: a bare trunk name DWIMs "
            "to the local branch and reviews the wrong subject (ISSUE-089). "
            "Fetch the base branch and retry.",
        )

    # Resolve AND canonicalise in one step: `git merge-base` always answers
    # with a full oid, so an abbreviated headRefOid compared verbatim could
    # never match it and would misreport a no-op PR as unexplained.
    code, head_oid = _git_text(cwd, "rev-parse", "--verify", f"{head_oid}^{{commit}}")
    if code != 0:
        raise _refuse(
            "head-oid-unreachable",
            f"the PR's head oid {refs['headRefOid']} is not in this checkout's "
            f"object database ({cwd}), so the diff COULD NOT BE COMPUTED — this "
            "is not an empty diff. Fetch the PR branch "
            f"(`git fetch origin {refs['headRefName']}`) and retry.",
        )

    code, merge_base = _git_text(cwd, "merge-base", base_oid, head_oid)
    if code != 0:
        raise _refuse(
            "merge-base-unresolvable",
            f"no merge base between {base_ref} ({base_oid[:12]}) and "
            f"{head_oid[:12]} — unrelated histories?",
        )

    worktree_path, worktree_source = _resolve_worktree(refs["headRefName"], cwd)
    diff_range = f"{base_oid}...{head_oid}"
    done = _git(worktree_path, "diff", "--no-ext-diff", diff_range)
    if done.returncode != 0:
        raise _refuse(
            "git-diff-failed",
            f"`git diff {diff_range}` exited {done.returncode} in "
            f"{worktree_path}: {done.stderr.decode('utf-8', 'replace').strip()[:200]}",
        )

    raw = done.stdout
    subject = {
        "issue_id": None,  # filled by the caller that knows it
        "pr_number": pr,
        "range": diff_range,
        "base_ref": base_ref,
        "base_oid": base_oid,
        "head_ref": f"gh:pr/{pr}#headRefOid",
        "head_oid": head_oid,
        "merge_base": merge_base,
        "worktree_path": str(worktree_path),
        "worktree_source": worktree_source,
        "diff_bytes": len(raw),
        "diff_headers": sum(
            1 for line in raw.split(b"\n") if line.startswith(_DIFF_HEADER_PREFIX)
        ),
        "diff_sha256": hashlib.sha256(raw).hexdigest(),
    }
    if subject["diff_bytes"] == 0:
        if merge_base == head_oid:
            raise _refuse(
                "empty-diff-head-is-merge-base",
                f"the PR head {head_oid[:12]} IS the merge base with "
                f"{base_ref}: nothing changed, so there is nothing to review. "
                "This is a genuine no-op PR, not a failed collection.",
                exit_code=1,
            )
        raise _refuse(
            "empty-diff-unexplained",
            f"the range {merge_base[:12]}...{head_oid[:12]} spans commits yet "
            "produced 0 bytes (a change and its revert?). Computed and empty "
            "— nothing is delegated, but this is NOT the no-op-PR case.",
            exit_code=1,
        )
    return subject


def _print_refusal(exc: SubjectRefused) -> int:
    """Refusals go to stderr ONLY: stdout must never carry a usable payload."""
    print(
        f"ERROR: review subject refused — reason={exc.reason} — {exc.detail}",
        file=sys.stderr,
    )
    return exc.exit_code


def _contained(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def _parse_recorded_subject(text: str) -> dict[str, list[str]]:
    """Read the counter-evidence block back out of the review notes.

    Workspace state read by a gate is untrusted input. Three fail-closed
    choices follow from that:

    - only the block's own ``- key: value`` lines are parsed, stopping at the
      next ``## `` heading;
    - **every** occurrence of a key is collected, not the first — a true line
      followed by a false one must not read as agreement (the duplicate-key
      collect-all lesson, ISSUE-042);
    - a key that is absent is absent, never a default that agrees.

    Returns ``{}`` when no block exists, and ``{"__duplicate_blocks__": [...]}``
    when more than one block claims to be the record.
    """
    if text.count(SUBJECT_HEADING) > 1:
        return {"__duplicate_blocks__": [str(text.count(SUBJECT_HEADING))]}
    start = text.find(SUBJECT_HEADING)
    if start < 0:
        return {}
    body = text[start + len(SUBJECT_HEADING):]
    end = body.find("\n## ")
    if end >= 0:
        body = body[:end]
    found: dict[str, list[str]] = {}
    for line in body.splitlines():
        match = re.fullmatch(r"-\s*([a-z0-9_]+):\s*(\S+)\s*", line)
        if match:
            found.setdefault(match.group(1), []).append(match.group(2))
    return found


def _agrees(recorded: dict[str, list[str]], key: str, expected: str) -> bool:
    """True only when EVERY recorded occurrence of ``key`` equals ``expected``."""
    values = recorded.get(key, [])
    return bool(values) and all(value == expected for value in values)


def _render_subject_block(subject: dict) -> str:
    return (
        f"\n{SUBJECT_HEADING}\n"
        "_Counter-evidence for what this review actually read "
        "(ISSUE-096). Produced by `review_context.py record-subject`._\n\n"
        f"- diff_bytes: {subject['diff_bytes']}\n"
        f"- diff_headers: {subject['diff_headers']}\n"
        f"- diff_sha256: {subject['diff_sha256']}\n"
        f"- head_oid: {subject['head_oid']}\n"
        f"- base_ref: {subject['base_ref']}\n"
        f"- range: {subject['range']}\n"
        f"- worktree_path: {subject['worktree_path']}\n"
        f"- worktree_source: {subject['worktree_source']}\n"
    )


# ── CLI handlers ─────────────────────────────────────────────────────


def cmd_decide(args: argparse.Namespace) -> int:
    """Handler for `decide` — compute the per-dimension path decisions once,
    emit one reason-tagged ``review_degraded_path_used`` event per degraded
    dimension (none for delegated), and print the decision JSON."""
    # Call-time attribute lookup keeps the delegation seam monkeypatchable
    # (tests patch has_skill.find_skill).
    decisions = decide_review_context(
        args.invocation_tools, probe=has_skill.find_skill
    )
    project = Path.cwd()
    for dimension, decision in decisions.items():
        if decision["path"] == "degraded":
            _emit_event(
                project,
                DEGRADED_EVENT,
                {"dimension": dimension, "reason": decision["reason"]},
                issue_id=args.issue,
            )
    print(
        json.dumps(
            {
                "issue_id": args.issue,
                "invocation_tools": args.invocation_tools,
                "dimensions": decisions,
            }
        )
    )
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    """Handler for `collect` — establish the subject, or refuse.

    On success the payload goes to stdout as one JSON object; on refusal
    stdout stays EMPTY so a shell capture cannot carry a half-subject forward.
    """
    try:
        subject = collect_subject(args.pr, Path.cwd())
    except SubjectRefused as exc:
        return _print_refusal(exc)
    subject["issue_id"] = args.issue
    print(json.dumps(subject))
    return 0


def cmd_delegate(args: argparse.Namespace) -> int:
    """Handler for `delegate` — the ECHO GATE.

    Re-establishes the subject (no handoff artifact to trust or poison) and
    records the delegation only when the consumer's echoed byte count AND
    sha256 both match. A reviewer that received nothing measures
    ``0``/``sha256(b"")`` and cannot pass. Any refusal is propagated with its
    own exit code and reason, and NO ``review_delegated_to_*`` event is
    emitted on any failing path.
    """
    try:
        subject = collect_subject(args.pr, Path.cwd())
    except SubjectRefused as exc:
        return _print_refusal(exc)

    echoed_sha = args.echoed_sha256.strip().lower()
    if args.echoed_bytes != subject["diff_bytes"] or echoed_sha != subject["diff_sha256"]:
        return _print_refusal(
            _refuse(
                "echo-mismatch",
                f"the {args.dimension} reviewer echoed "
                f"{args.echoed_bytes} bytes / sha256 {echoed_sha[:12]}… but the "
                f"subject is {subject['diff_bytes']} bytes / sha256 "
                f"{subject['diff_sha256'][:12]}… — it did not read the diff "
                "that was collected for it, so its verdict is about something "
                "else. Discard the verdict; do not record a delegation.",
            )
        )

    event = f"review_delegated_to_{DIMENSION_SKILLS[args.dimension].replace('-', '_')}"
    _emit_event(
        Path.cwd(),
        event,
        {
            "pr_number": args.pr,
            "diff_bytes": subject["diff_bytes"],
            "diff_sha256": subject["diff_sha256"],
            "head_oid": subject["head_oid"],
        },
        issue_id=args.issue,
    )
    print(
        f"echo verified: {args.dimension} reviewed {subject['diff_bytes']} bytes "
        f"at head {subject['head_oid']} (range {subject['range']})"
    )
    return 0


def cmd_record_subject(args: argparse.Namespace) -> int:
    """Handler for `record-subject` — counter-evidence in the review record.

    MUST run downstream of the synthesizer (step 3.14), which rewrites
    ``docs/review_notes/<ISSUE>.md``. Appends the block when absent, verifies
    it when present, and refuses when it is partial or disagrees with the
    recomputed subject — so a verdict can no longer be recorded without
    saying what it was a verdict ON.
    """
    try:
        subject = collect_subject(args.pr, Path.cwd())
    except SubjectRefused as exc:
        return _print_refusal(exc)

    root = Path.cwd()
    notes = Path(args.notes) if args.notes else (
        root / "docs" / "review_notes" / f"{args.issue}.md"
    )
    if not _contained(notes, root):
        return _print_refusal(
            _refuse(
                "review-notes-outside-project",
                f"{notes} resolves outside the project root {root} — refusing "
                "to read or write it",
            )
        )
    if not notes.is_file():
        return _print_refusal(
            _refuse(
                "review-notes-missing",
                f"{notes} does not exist, so the review record cannot carry "
                "the byte count and head oid the review was taken at. Run the "
                "synthesizer (step 3.14) first.",
            )
        )

    text = notes.read_text(encoding="utf-8", errors="replace")
    recorded = _parse_recorded_subject(text)
    if "__duplicate_blocks__" in recorded:
        return _print_refusal(
            _refuse(
                "subject-incomplete",
                f"{notes} carries {recorded['__duplicate_blocks__'][0]} "
                f"{SUBJECT_HEADING!r} blocks — two records cannot both be THE "
                "record, and only the first would ever be checked",
            )
        )
    if recorded:
        missing = [k for k in ("diff_bytes", "head_oid") if k not in recorded]
        if missing:
            return _print_refusal(
                _refuse(
                    "subject-incomplete",
                    f"{notes} has a {SUBJECT_HEADING!r} block that is missing "
                    f"{', '.join(missing)} — a verdict without both is exactly "
                    "the record this issue exists to prevent",
                )
            )
        if not _agrees(recorded, "diff_bytes", str(subject["diff_bytes"])) or not (
            _agrees(recorded, "head_oid", subject["head_oid"])
        ):
            return _print_refusal(
                _refuse(
                    "subject-mismatch",
                    f"{notes} records diff_bytes={recorded['diff_bytes']} at "
                    f"head {recorded['head_oid']}, but the subject is "
                    f"diff_bytes={subject['diff_bytes']} at head "
                    f"{subject['head_oid'][:12]}… — the notes describe a "
                    "different review than the one that can be reproduced",
                )
            )
        print(f"counter-evidence already present and matching: {notes}")
        return 0

    with notes.open("a", encoding="utf-8") as handle:
        handle.write(_render_subject_block(subject))
    # Verify what landed rather than what was intended.
    reread = _parse_recorded_subject(
        notes.read_text(encoding="utf-8", errors="replace")
    )
    if not _agrees(reread, "diff_bytes", str(subject["diff_bytes"])) or not _agrees(
        reread, "head_oid", subject["head_oid"]
    ):
        return _print_refusal(
            _refuse(
                "subject-incomplete",
                f"wrote the counter-evidence block to {notes} but could not "
                "read both values back",
            )
        )
    print(
        f"counter-evidence recorded in {notes}: "
        f"diff_bytes={subject['diff_bytes']} head_oid={subject['head_oid']}"
    )
    return 0


def cmd_emit(args: argparse.Namespace) -> int:
    """Handler for `emit` — the prose-side call site of the single emit seam.

    Cross-field closed vocabulary: ``review_degraded_path_used`` requires
    ``--dimension`` + ``--reason inline-attempt-failed`` (and no ``--pr``);
    the delegated events take an optional ``--pr`` only.
    """
    if args.event == DEGRADED_EVENT:
        if args.dimension is None or args.reason is None:
            print(
                f"Error: --event {DEGRADED_EVENT} requires --dimension "
                f"{{code,security}} and --reason {INLINE_ATTEMPT_FAILED}",
                file=sys.stderr,
            )
            return 2
        if args.pr is not None:
            print(
                f"Error: --pr is not accepted with --event {DEGRADED_EVENT}",
                file=sys.stderr,
            )
            return 2
        payload: dict = {"dimension": args.dimension, "reason": args.reason}
    else:
        if args.dimension is not None or args.reason is not None:
            print(
                "Error: --dimension/--reason are only valid with "
                f"--event {DEGRADED_EVENT}",
                file=sys.stderr,
            )
            return 2
        payload = {}
        if args.pr is not None:
            payload["pr_number"] = args.pr
    _emit_event(Path.cwd(), args.event, payload, issue_id=args.issue)
    return 0


# ── CLI entry point ──────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit 0 on a computed decision / handled event
    (telemetry no-op included); exit 2 on bad input."""
    parser = argparse.ArgumentParser(
        description=(
            "Decide the /review execution context once (SPEC-066) and emit "
            "review delegation telemetry through the single seam."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    de = subparsers.add_parser(
        "decide",
        help="Compute the per-dimension delegated/degraded decision ONCE",
    )
    de.add_argument(
        "--invocation-tools",
        required=True,
        choices=INVOCATION_TOOLS_VALUES,
        help=(
            "Model-reported context half: is a runtime skill-invocation "
            "tool in the current tool list? Look for `Skill` first (what a "
            "Task sub-agent actually receives, when its `tools:` grants it); "
            "a `SlashCommand` tool also counts where one exists, since only "
            "sub-task contexts were probed on CC 2.1.224 and the "
            "main-session path was not — see ISSUE-072 and the sub-agent "
            "skill-invocation row in docs/cc_feature_matrix.md"
        ),
    )
    de.add_argument(
        "--issue",
        required=True,
        help="Issue id, format ISSUE-<number> (e.g. ISSUE-066)",
    )

    co = subparsers.add_parser(
        "collect",
        help="Establish the reviewable subject for a PR, or refuse (ISSUE-096)",
    )
    co.add_argument(
        "--pr",
        required=True,
        help="PR number; its head oid is read from `gh pr view --json headRefOid`",
    )
    co.add_argument(
        "--issue", required=True, help="Issue id, format ISSUE-<number>"
    )

    dg = subparsers.add_parser(
        "delegate",
        help=(
            "Echo gate: record review_delegated_to_code_review / "
            "review_delegated_to_security_review ONLY when the runtime "
            "reviewer echoes back the digest of the diff it was given"
        ),
    )
    dg.add_argument("--dimension", required=True, choices=sorted(DIMENSION_SKILLS))
    dg.add_argument("--pr", required=True, help="PR number (same as `collect`)")
    dg.add_argument(
        "--issue", required=True, help="Issue id, format ISSUE-<number>"
    )
    dg.add_argument(
        "--echoed-bytes",
        required=True,
        type=int,
        help="Byte count the runtime reviewer reported measuring",
    )
    dg.add_argument(
        "--echoed-sha256",
        required=True,
        help="sha256 the runtime reviewer reported measuring",
    )

    rs = subparsers.add_parser(
        "record-subject",
        help=(
            "Append + verify the counter-evidence (byte count, head oid) in "
            "docs/review_notes/<ISSUE>.md — run AFTER the synthesizer"
        ),
    )
    rs.add_argument("--pr", required=True, help="PR number (same as `collect`)")
    rs.add_argument(
        "--issue", required=True, help="Issue id, format ISSUE-<number>"
    )
    rs.add_argument(
        "--notes",
        default=None,
        help="Notes path (default docs/review_notes/<ISSUE>.md, project-relative)",
    )

    em = subparsers.add_parser(
        "emit",
        help="Prose-side emit seam for allowlisted review delegation events",
    )
    em.add_argument(
        "--event",
        required=True,
        choices=ALLOWED_EMIT_EVENTS,
        help="Allowlisted event type (docs/telemetry_schema.md, ISSUE-019 table)",
    )
    em.add_argument(
        "--issue",
        required=True,
        help="Issue id, format ISSUE-<number> (e.g. ISSUE-066)",
    )
    em.add_argument(
        "--pr",
        default=None,
        help="PR ref for the delegated events (optional)",
    )
    em.add_argument(
        "--dimension",
        choices=sorted(DIMENSION_SKILLS),
        default=None,
        help=f"Required with --event {DEGRADED_EVENT}",
    )
    em.add_argument(
        "--reason",
        choices=(INLINE_ATTEMPT_FAILED,),
        default=None,
        help=(
            f"Required with --event {DEGRADED_EVENT}; the only reason the "
            "prose seam accepts (decide-time reasons are emitted by `decide`)"
        ),
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if not args.command:
        parser.print_help()
        return 2

    if not _ISSUE_ID_RE.fullmatch(args.issue):
        print(
            f"Error: --issue must match ISSUE-<number> (e.g. ISSUE-066), "
            f"got {args.issue!r}",
            file=sys.stderr,
        )
        return 2

    if args.command == "decide":
        return cmd_decide(args)
    if args.command == "collect":
        return cmd_collect(args)
    if args.command == "delegate":
        return cmd_delegate(args)
    if args.command == "record-subject":
        return cmd_record_subject(args)
    return cmd_emit(args)


if __name__ == "__main__":
    raise SystemExit(main())
