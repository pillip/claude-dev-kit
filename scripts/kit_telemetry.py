#!/usr/bin/env python3
"""Shared kit telemetry emitter (ISSUE-067) — the single home of the
ISSUE-058 writer hardening, with every skip/fallback path ANNOUNCED.

Every kit telemetry emit either runs or announces its skip/fallback with a
named reason on stdout — "no signal" can no longer be confused with "all
clear". This module replaces the per-script hand-rolled appenders (the
first migration is ``synthesize_gate_results._emit_telemetry``) and backs
the skill-prompt call sites via the CLI below.

Python API (this docstring is the API contract — ISSUE-066 adopts it at
its ship-time rebase)::

    def emit_event(
        event_type: str,
        payload: dict | None = None,
        *,
        script_name: str,            # becomes the event's skill_or_script field
        project_path: str | Path | None = None,  # default Path.cwd();
                                     # events land in <project>/.claude/runs/
        issue_id: str | None = None, # optional schema field
    ) -> bool:                       # True = a line was written, False = skipped

Behavior (see docs/telemetry_schema.md for the event catalog):

- Run-id resolution happens INSIDE the helper from the env knob
  ``KIT_RUN_ID``:
    - set and matching ``[A-Za-z0-9_-]{1,64}`` (fullmatch) → clean path:
      append to ``<project>/.claude/runs/<run_id>.jsonl``, print NOTHING.
    - unset/blank → FALLBACK: append to ``.claude/runs/unattributed.jsonl``;
      the event gains a top-level ``"run_id_fallback": "KIT_RUN_ID unset"``
      field and ONE stdout line announces the fallback, naming the knob.
    - set but failing the whitelist → the same ``unattributed`` fallback
      with ``run_id_fallback`` noting the invalid value's rejection; the
      raw invalid value is NEVER used in a filename.
- Containment (ISSUE-070): ``project_path`` is NOT its own containment
  root. The root is derived independently of the caller by
  :func:`_containment_root` — main git work-tree root of the process CWD,
  else ``CLAUDE_PROJECT_DIR``, else the CWD — and a ``project_path`` that
  resolves outside it is refused with a named reason, NOTHING written.
  Before ISSUE-070 both sides of this comparison came from the caller's own
  argument, which made the check unfalsifiable for any non-symlinked root:
  any existing writable directory could be given ``.claude/runs`` and an
  appended event. A linked worktree resolves to the MAIN repo root, so
  ``<main-root>/.worktrees/<slug>`` and the main root admit each other.
- ``<project>/.claude/runs/`` is auto-created (mkdir parents, exist_ok)
  INSIDE that root — dir absence is no longer a silent-skip path; mere
  creation is not announced. The project ROOT itself is never created: a
  contained ``project_path`` that is not an existing directory is refused
  with an announcement (review fix, PR #123 security finding F1 — the
  emitter must not be a directory-creation primitive). Every
  ``exists()``/``stat`` probe of the caller's path runs strictly AFTER
  containment, so a refusal never discloses whether an out-of-root path
  exists.
- The resolved runs dir must additionally stay inside the resolved project
  root, so a symlinked ``.claude/`` cannot even gain subdirectories; on
  violation the rejection is announced and NOTHING is written anywhere.
- ISSUE-058 hardening preserved byte-for-byte: ``payload["detail"]`` longer
  than 512 chars is truncated with ``…[truncated]``; a serialized event
  over 4096 bytes is skipped (now ANNOUNCED, naming the cap — previously a
  silent drop); the event file is opened O_NOFOLLOW so a pre-planted
  symlink cannot redirect the append (refusal announced as a write
  failure).
- Planted-node hardening (ISSUE-070): the event path is predictable, so the
  open also carries ``O_NONBLOCK`` and is followed by an ``fstat``. The
  ``O_NONBLOCK`` leg is the anti-HANG guard — a planted FIFO otherwise
  blocks ``os.open`` forever, and ``verify_checkpoint.py``'s wrapper
  catches exceptions, not stalls, so a hang STALLS a gate instead of
  failing it. The ``fstat`` leg is the anti-WRITE guard and closes the
  TOCTOU window FOR THE NODE AT THE EVENT PATH, because it interrogates the
  descriptor actually opened: anything that is not a single-linked regular
  file (FIFO, socket, device node, directory, hardlink) is refused with a
  named reason. It does NOT re-validate LOCATION — ``fstat`` answers "what
  kind of file is this", not "where is it" — and ``O_NOFOLLOW`` binds only
  the FINAL path component. A ``.claude/`` swapped for a directory symlink
  between the containment check and the open therefore still redirects the
  append outside the root (demonstrated in review, PR #141; carried, not
  closed here — closing it needs an ``openat``/``dir_fd`` walk).
- ``emit_event`` NEVER raises — telemetry is a non-blocking instrument and
  the parent must never fail because of it. This is the contract ISSUE-075
  adopts, so it is pinned by tests rather than merely advertised: the catch
  set is deliberately ``Exception`` (which covers ``RecursionError``, a
  ``RuntimeError`` and not a ``ValueError``) and :func:`_announce` itself
  cannot raise, so a caller that has closed stdout gets a dropped
  announcement rather than a propagated ``ValueError``. Every skip
  announces (best-effort) and returns False.
- Event schema: ``ts`` (ISO-8601 UTC), ``event_type``, ``skill_or_script``,
  optional ``issue_id``, ``payload``, plus the optional ``run_id_fallback``.
- All announcements are single stdout lines prefixed ``[kit-telemetry]``.

CLI (for skill-prompt call sites — one-line adoption)::

    python3 scripts/kit_telemetry.py --script <name> --event <event_type> \\
        [--payload '<json-object>'] [--issue-id ISSUE-NNN] [--project-path <dir>]

The CLI always exits 0 (non-blocking), even on skip paths — the stdout
announcement is the signal. An invalid ``--payload`` announces and writes
nothing.

Env knobs (documented here and in README's environment-variable list):
    KIT_RUN_ID — run id for telemetry appends to
        ``<project>/.claude/runs/<run-id>.jsonl``. Unset or invalid =>
        the event is written under the ``unattributed`` run id with a
        ``run_id_fallback`` field and a stdout announcement naming the knob.
    CLAUDE_PROJECT_DIR — consulted as the containment root ONLY when the
        process CWD is not inside a git work tree (set by the Claude Code
        runtime; the kit never sets it). It is a fallback, not an override:
        the git work-tree root wins, because from inside a linked worktree
        only the git answer is the main root. When neither is available the
        root is the process CWD.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

# Env knob naming the run id (docs/telemetry_schema.md).
RUN_ID_ENV = "KIT_RUN_ID"

# Env knob naming the project root, consulted only as a fallback when the
# process is not inside a git work tree (ISSUE-070 containment root).
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"

# Explicit fallback run id when KIT_RUN_ID is unset or invalid — the event
# survives, visibly unattributed, instead of being silently dropped.
FALLBACK_RUN_ID = "unattributed"

# Whitelist for the attacker-influenced run-id filename component.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")

# Attacker-derived text (e.g. error messages quoting unknown keys) is
# truncated rather than allowed to pad the event past the 4 KiB cap —
# padding would silently drop the forensic record.
_MAX_DETAIL_CHARS = 512

# Event payload ceiling per docs/telemetry_schema.md (POSIX O_APPEND
# atomicity for small writes).
_MAX_EVENT_BYTES = 4096

_ANNOUNCE_PREFIX = "[kit-telemetry]"


def _announce(message: str) -> None:
    """One stdout line per skip/fallback — the no-silent-no-op contract.

    Best-effort on purpose (ISSUE-070): ``emit_event`` promises never to
    raise, and announcing is the LAST thing that may break that promise.
    A caller that has closed stdout makes ``print`` raise ``ValueError``;
    before this guard that exception escaped even the outer handler, because
    the handler's own announcement raised again. A lost line is strictly
    better than a telemetry instrument failing its parent.
    """
    try:
        print(f"{_ANNOUNCE_PREFIX} {message}")
    except Exception:  # noqa: BLE001 — see the docstring: never escalate
        pass


def _quote(value: object) -> str:
    """Render attacker-influenced text as a single escaped token.

    Announcements are one stdout line by contract. ``repr`` escapes
    newlines, so a crafted ``--project-path`` or ``--event`` cannot forge a
    second ``[kit-telemetry]`` line that reads like an all-clear.

    Review fix (PR #141): this must wrap EVERY caller-supplied value that
    reaches an announcement, not just the path. Shipped applied to the
    path only, it left the 4 KiB-cap, ``KIT_RUN_ID``-fallback, outer-handler
    and ``--payload`` announcements forging a second line through
    ``event_type`` — a defence tested in the arm direction at one call site
    and absent at the others (review lesson 16).
    """
    return repr(str(value))


def _main_repo_root(start: Path) -> Path | None:
    """The main git work-tree root containing ``start``, or None.

    Mirrors ``bash scripts/worktree.sh root`` (``git rev-parse
    --show-toplevel`` plus the linked-worktree ``commondir`` hop) in-process.
    A subprocess is deliberately avoided here: this module exists partly to
    stop a telemetry emit from stalling a gate, and shelling out to git on
    every emit would add a second way for it to stall. The mirror is pinned
    against that oracle — including the linked-worktree case — in
    ``tests/test_kit_telemetry.py::TestContainmentRootDerivation``.

    Two deliberate divergences from that oracle, both in the narrowing
    (safe) direction: ``GIT_DIR``/``GIT_WORK_TREE`` are not consulted
    because no subprocess runs, and a ``commondir`` hop that leaves the
    work tree is rejected rather than followed (see below).
    """
    for candidate in (start, *start.parents):
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            return candidate
        if not dot_git.is_file():
            continue
        # Linked worktree or submodule: ``.git`` is a file holding
        # ``gitdir: <path>``. A linked worktree's git dir carries a
        # ``commondir`` pointing at the MAIN repo's ``.git`` — that hop is
        # what makes ``<main-root>/.worktrees/<slug>`` resolve to
        # ``<main-root>``, which is the property a worktree-rooted caller
        # (ISSUE-075) depends on. A submodule has no ``commondir``; its own
        # work tree is then the boundary, which is the conservative answer.
        #
        # Review fix (PR #141): everything read below — the ``.git`` file
        # and the ``commondir`` it names — is WORKSPACE CONTENT, i.e.
        # untrusted input on read (review lesson 5), and this function
        # derives a SECURITY boundary from it. A linked worktree's ``.git``
        # is an ordinary writable file inside the tree, so an attacker with
        # the write access AC-2 already assumes could otherwise name any
        # ``commondir`` and move the root anywhere (``/x`` made containment
        # vacuous). Hence: ONE try — any malformed byte falls through to the
        # conservative answer rather than escaping this function — plus the
        # anchor below.
        try:
            spec = dot_git.read_text(encoding="utf-8", errors="replace")
            gitdir = ""
            for line in spec.splitlines():
                if line.startswith("gitdir:"):
                    gitdir = line.split(":", 1)[1].strip()
                    break
            if not gitdir:
                return candidate
            git_path = Path(gitdir)
            if not git_path.is_absolute():
                git_path = candidate / git_path
            commondir = git_path / "commondir"
            if not commondir.is_file():
                return candidate
            common = Path(
                commondir.read_text(encoding="utf-8", errors="replace").strip()
            )
            if not common.is_absolute():
                common = git_path / common
            common_dir = common.resolve()
            hop = common_dir.parent
            # The anchor. "Is the hop an ancestor of this work tree" is NOT
            # enough — every ancestor is one, including ``/`` and ``$HOME``,
            # which is precisely the direction an attacker wants (found in
            # review by both runtime reviewers after a first fix checked only
            # the sideways direction). What cannot be forged without write
            # access at the destination is the destination's own git dir:
            # require ``hop`` to be a real work tree whose ``.git`` IS the
            # common dir we just followed. A bare-repo-backed worktree
            # (``commondir`` = ``/srv/proj.git``) fails this too, so the root
            # never widens to the directory holding sibling projects.
            if not common_dir.is_dir():
                return candidate
            if (hop / ".git").resolve() != common_dir:
                return candidate
            # Belt and braces, and the reason an out-of-tree
            # ``git worktree add`` target (which `worktree.sh create` never
            # produces) contains itself rather than resolving to the main
            # root — a deliberate narrowing.
            if not candidate.resolve().is_relative_to(hop):
                return candidate
            return hop
        except (OSError, ValueError):
            # ValueError covers an embedded NUL in a planted ``gitdir:``.
            # Failing closed here keeps one corrupt byte in workspace state
            # from taking down every emit in the tree.
            return candidate
    return None


def _containment_root() -> Path:
    """The one directory tree this emitter may write under.

    Derived WITHOUT consulting the caller's ``project_path`` — that is the
    whole point of ISSUE-070: a check whose two sides both come from the
    caller cannot fail. Resolution order:

    1. the main git work-tree root of the process CWD (a linked worktree
       resolves to the MAIN root, so ``<main-root>/.worktrees/<slug>`` and
       the main root admit each other);
    2. ``CLAUDE_PROJECT_DIR``, when it names an existing directory;
    3. the process CWD.

    Under a plugin install this is the USER's project — the git root of the
    CWD the runtime launched the command in — never the kit's install
    directory, so events keep landing exactly where ISSUE-067 put them.
    The scope is honest about its limit: containment is relative to the
    project the process runs in, so it does not defend a project root that
    is itself ``$HOME``.
    """
    cwd = Path.cwd().resolve()
    root = _main_repo_root(cwd)
    if root is not None:
        return root.resolve()
    raw = os.environ.get(PROJECT_DIR_ENV, "").strip()
    if raw:
        candidate = Path(raw)
        if candidate.is_dir():
            return candidate.resolve()
    return cwd


def _resolve_run_id() -> tuple[str, str | None]:
    """Resolve (run_id, fallback_reason) from the KIT_RUN_ID env knob.

    fallback_reason is None on the clean path; otherwise it names the knob
    and the condition, and run_id is the explicit ``unattributed`` id.
    """
    raw = os.environ.get(RUN_ID_ENV, "").strip()
    if not raw:
        return FALLBACK_RUN_ID, f"{RUN_ID_ENV} unset"
    if not _RUN_ID_RE.fullmatch(raw):
        # NEVER use the raw invalid value in a filename.
        return FALLBACK_RUN_ID, (
            f"{RUN_ID_ENV} invalid (must match {_RUN_ID_RE.pattern})"
        )
    return raw, None


def emit_event(
    event_type: str,
    payload: dict | None = None,
    *,
    script_name: str,
    project_path: str | Path | None = None,
    issue_id: str | None = None,
) -> bool:
    """Append one schema-conformant event line; announce every skip/fallback.

    Returns True when a line was written, False when the emit was skipped
    (the skip is always announced). Never raises.
    """
    try:
        project = Path(project_path) if project_path is not None else Path.cwd()
        run_id, fallback_reason = _resolve_run_id()

        # Containment against a root the CALLER DID NOT SUPPLY (ISSUE-070).
        # This is the check that was structurally unfalsifiable before:
        # `runs_dir.resolve().is_relative_to(project.resolve())` compared two
        # values both derived from ``project_path``, so for any non-symlinked
        # root it always passed and the emitter would create
        # ``<arbitrary-dir>/.claude/runs`` and append there. Resolving the
        # caller's path first also means a symlink inside the root that
        # points out of it cannot launder the destination.
        root = _containment_root()
        resolved_project = project.resolve()
        if not resolved_project.is_relative_to(root):
            _announce(
                f"skipped: containment violation — project path "
                f"{_quote(project)} resolves outside the kit project root "
                f"{_quote(root)}; event {_quote(event_type)} NOT written"
            )
            return False

        # Every exists()/stat probe of the caller-derived path runs AFTER
        # containment (forgeable-attestation review lesson, point 6): a
        # pre-containment probe whose refusal reason diverges on existence
        # would turn this instrument into a filesystem-existence oracle for
        # paths the caller is not even allowed to write to.
        #
        # The project root must already exist (review fix, PR #123 security
        # finding F1). `.claude/runs/` is still auto-created inside a real
        # project — dir absence there is not a skip path — but the emitter
        # never materializes the root itself.
        if not project.is_dir():
            _announce(
                f"skipped: project root {_quote(project)} is not an existing "
                f"directory; event {_quote(event_type)} NOT written"
            )
            return False

        # Second containment leg, still before any mkdir: a symlinked
        # .claude/ or runs/ must not even gain subdirectories outside the
        # project root. Kept as its own check because the root above is the
        # project's, not this subtree's (ISSUE-058 / lesson 12 — the control's
        # POSITION before the mkdir is what the test pins).
        runs_dir = project / ".claude" / "runs"
        if not runs_dir.resolve().is_relative_to(resolved_project):
            _announce(
                "skipped: containment violation — resolved .claude/runs "
                f"escapes the project root; event {_quote(event_type)} NOT written"
            )
            return False
        runs_dir.mkdir(parents=True, exist_ok=True)

        body = dict(payload) if payload else {}
        detail = body.get("detail")
        if isinstance(detail, str) and len(detail) > _MAX_DETAIL_CHARS:
            body["detail"] = detail[:_MAX_DETAIL_CHARS] + "…[truncated]"

        event: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "skill_or_script": script_name,
        }
        if issue_id is not None:
            event["issue_id"] = issue_id
        event["payload"] = body
        if fallback_reason is not None:
            event["run_id_fallback"] = fallback_reason

        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > _MAX_EVENT_BYTES:
            _announce(
                f"skipped: serialized event exceeds the {_MAX_EVENT_BYTES}-byte "
                f"cap — event {_quote(event_type)} NOT written"
            )
            return False

        # Hardened open. The event path is predictable, so everything that
        # can be planted there is handled at the open itself:
        #   O_NOFOLLOW — a pre-planted symlink must not redirect the append
        #     outside the project (ISSUE-058 hardening, unchanged).
        #   O_NONBLOCK — the anti-HANG leg (ISSUE-070). Without it a planted
        #     FIFO blocks os.open FOREVER, and verify_checkpoint.py's wrapper
        #     catches exceptions, not stalls, so the emit would STALL a gate
        #     instead of failing it. A no-op for regular files.
        #   fstat after the open — the anti-WRITE leg. It is immune to the
        #     TOCTOU window for the NODE, because it interrogates the
        #     descriptor actually opened rather than a path that may have
        #     been swapped since. Refuses FIFOs, sockets, device nodes,
        #     directories and hardlinks. It does NOT re-check location; see
        #     the module docstring for the directory-symlink gap that
        #     remains open.
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(runs_dir / f"{run_id}.jsonl", flags, 0o644)
        except OSError as exc:
            _announce(
                f"skipped: write failed ({exc}) — event {_quote(event_type)} "
                "NOT written"
            )
            return False
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                _announce(
                    "skipped: refusing to write through a non-regular file at "
                    f"the event path (st_mode type {stat.S_IFMT(info.st_mode):#o}) "
                    f"— event {_quote(event_type)} NOT written"
                )
                return False
            if info.st_nlink != 1:
                _announce(
                    "skipped: refusing to write through a multiply-linked file "
                    f"({info.st_nlink} links) at the event path — event "
                    f"{_quote(event_type)} NOT written"
                )
                return False
            os.write(fd, data)
        except OSError as exc:
            _announce(
                f"skipped: write failed ({exc}) — event {_quote(event_type)} "
                "NOT written"
            )
            return False
        finally:
            os.close(fd)

        if fallback_reason is not None:
            _announce(
                f"fallback: {fallback_reason} — event {_quote(event_type)} "
                f"written under run id '{FALLBACK_RUN_ID}'"
            )
        return True
    except Exception as exc:  # non-blocking instrument: never fail the parent
        _announce(
            f"skipped: emit failed ({exc}) — event {_quote(event_type)} NOT written"
        )
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit one kit telemetry event (non-blocking; always exits 0)."
    )
    parser.add_argument("--script", required=True, help="skill_or_script field")
    parser.add_argument("--event", required=True, help="event_type field")
    parser.add_argument("--payload", help="event payload as a JSON object")
    parser.add_argument("--issue-id", help="optional issue_id field")
    parser.add_argument(
        "--project-path", help="project root (default: current directory)"
    )
    args = parser.parse_args(argv)

    payload: dict | None = None
    if args.payload is not None:
        try:
            payload = json.loads(args.payload)
        except ValueError:
            _announce(
                f"skipped: --payload is not valid JSON — event "
                f"{_quote(args.event)} NOT written"
            )
            return 0
        if not isinstance(payload, dict):
            _announce(
                f"skipped: --payload is not a JSON object — event "
                f"{_quote(args.event)} NOT written"
            )
            return 0

    emit_event(
        args.event,
        payload,
        script_name=args.script,
        project_path=args.project_path,
        issue_id=args.issue_id,
    )
    return 0  # the announcement is the signal; telemetry never blocks


if __name__ == "__main__":
    sys.exit(main())
