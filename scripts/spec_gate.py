#!/usr/bin/env python3
"""Spec gate logic invoked by /implement.

Reads the target issue from issues.md and decides one of three outcomes:
- proceed         : implementation can begin immediately (no spec needed)
- auto_spec       : sprint mode + Spec-Required=true + no SPEC → /spec must run first
- hold            : non-sprint mode + missing SPEC OR signal-detected → user must choose
- bypassed        : --skip-spec-gate was passed → proceed + emit telemetry

The user-facing 3-way HOLD prompt itself lives in the /implement skill (uses
AskUserQuestion). This script's job is to produce the structured decision +
diagnostics that drive that prompt.

Usage:
    python3 scripts/spec_gate.py ISSUE-007 [--skip-spec-gate] [--issues-md=issues.md]
        → prints JSON: {decision, reasons, signals, spec_path}

Exit code:
    0 = decision computed successfully
    2 = bad input (issue not found, etc.)

SPEC resolution is MULTI-CHECKOUT (ISSUE-102)
---------------------------------------------
The two artifacts this gate must see together are, by the kit's own two rules,
guaranteed never to co-locate until merge:

* the Shared-Registry rule commits the issue's ``Spec:`` field to **main's**
  ``issues.md`` and forbids committing registry files to a feature branch, so a
  branch's copy stays frozen at its base commit reading ``Spec: none``;
* ``/spec``'s Output Contract writes the SPEC file on the **branch**.

Resolving the ``Spec:`` value against the single directory of the ``issues.md``
that was read therefore made the sprint-mode ``auto_spec`` gate unsatisfiable —
it refused from main (field known, file on the branch) and refused from the
worktree (file present, field stale). So BOTH halves are resolved across every
checkout of the repository, and the relaxation is scoped to exactly the caller
class that needs it:

1. the lookup runs only when ``Spec-Required=true`` — the ``hold``-by-signal,
   ``bypassed`` and signal-detection paths never reach it;
2. only the ``Spec:`` FIELD is read from another checkout, and only when the
   registry copy actually read declares no SPEC. Everything else about the
   issue (body, status, estimate, and therefore every signal) stays bound to
   the registry copy the caller pointed at;
3. when the SPEC is found under the read registry's own root with that
   registry's own field — the legacy co-located configuration — the reason
   string is byte-for-byte the pre-ISSUE-102 one. A cross-checkout ``proceed``
   names which checkout supplied the field and which held the file, so the
   relaxation is never invisible in the output.

**What this establishes, and what it does not** (review lesson 6): it
establishes that *some* checkout of this repository holds a regular file at the
declared path. It does NOT establish provenance — that *this issue's branch*
produced that SPEC. A leftover worktree carrying an old SPEC at the same path,
or an empty file created by hand, satisfies the gate. File existence is a weak
attestation; closing that would need a git-level check
(``git cat-file -e <branch>:<path>``) and is not in this gate's scope.

The ``Spec:`` value is untrusted input (review lesson 5), and widening the roots
widens what a traversal in it can reach, so every candidate is contained to the
root it is resolved against: an absolute value, a ``..`` escape, a symlink
leaving the checkout, and anything that is not a regular file are all REFUSED,
and the refusal is named in ``reasons`` so it cannot be read as "simply absent".

"The SPEC is absent from every checkout I consulted" and "I could not determine
the checkouts to consult" are DIFFERENT outcomes. A directory that is not in a
repository has exactly one checkout and is a COMPLETE enumeration. Only a git
consultation that genuinely could not be made (no ``git`` executable, a
timeout, an unexpected non-zero exit) is INCOMPLETE, and it is reported as its
own reason line instead of collapsing into "absent".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

SPRINT_ENV = "KIT_SPRINT_MODE"

#: Wall-clock bound for each local ``git`` consultation, in seconds. No env
#: knob: both calls are local-only (``worktree list`` / ``rev-parse``, no
#: network) and terminate immediately, so there is nothing for an operator to
#: tune — unlike ``worktree.sh``'s remote fetch, which has
#: ``KIT_WORKTREE_FETCH_TIMEOUT`` precisely because it can stall offline. A
#: timeout here is reported as an INCOMPLETE enumeration rather than raised.
GIT_QUERY_TIMEOUT = 10

#: Marker word that separates "could not compute" from "computed and empty" in
#: the emitted reasons. The /implement skill's step 0c reads it.
INCOMPLETE_MARKER = "checkout enumeration INCOMPLETE"

# Keyword signals that recommend (never auto-trigger) a spec.
SIGNAL_KEYWORDS: list[tuple[str, str]] = [
    (r"\bAPI\b", "API surface"),
    (r"\bschema\b", "schema"),
    (r"\bmigration\b", "migration"),
    (r"\bbreaking\b", "breaking change"),
    (r"\bprotocol\b", "protocol"),
    (r"데이터모델", "data model (ko)"),
    (r"\bnew\s+package\b", "new package"),
    (r"\bnew\s+dependency\b", "new dependency"),
    (r"\badd\s+(?:a\s+)?dependency\b", "add dependency"),
]


def parse_issue(issues_md: Path, issue_id: str) -> dict | None:
    """Return a dict with the target issue's fields, or None if not found."""
    text = issues_md.read_text(encoding="utf-8")
    pattern = (
        rf"^### {re.escape(issue_id)}:.*?(?=^### ISSUE-\d+:|\Z)"
    )
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    block = m.group(0)
    return {
        "id": issue_id,
        "estimate": _field(block, "Estimate"),
        "status": _field(block, "Status").lower(),
        "spec_required": _field(block, "Spec-Required").lower(),
        "spec_path": _field(block, "Spec"),
        "body": block,
    }


def _field(block: str, name: str) -> str:
    m = re.search(rf"^- {re.escape(name)}:[ \t]*(.*)$", block, re.MULTILINE)
    return m.group(1).strip() if m else ""


def scan_signals(issue_body: str) -> list[dict]:
    """Return a list of {signal, evidence} dicts for recommendation logging."""
    found: list[dict] = []
    for pattern, label in SIGNAL_KEYWORDS:
        m = re.search(pattern, issue_body, re.IGNORECASE)
        if m:
            # Capture a small context window for evidence.
            start = max(0, m.start() - 30)
            end = min(len(issue_body), m.end() + 30)
            evidence = issue_body[start:end].replace("\n", " ")
            found.append({"signal": label, "evidence": evidence.strip()})
    # Estimate at cap = a signal.
    if re.search(r"^- Estimate:\s*1\.5d\s*$", issue_body, re.MULTILINE):
        found.append({"signal": "estimate at 1.5d cap", "evidence": "Estimate: 1.5d"})
    return found


def _git(start: Path, *args: str) -> subprocess.CompletedProcess | None:
    """Run a local git query in ``start``. ``None`` means it could not be made."""
    try:
        return subprocess.run(
            ["git", "-C", str(start), *args],
            capture_output=True,
            text=True,
            timeout=GIT_QUERY_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def checkout_roots(start: Path) -> tuple[list[Path], str | None]:
    """Every checkout of the repository containing ``start``, ``start`` first.

    Returns ``(roots, incomplete_reason)``. ``roots[0]`` is always ``start``
    itself, so a directory outside any repository keeps the pre-ISSUE-102
    single-root behaviour exactly. ``incomplete_reason`` is ``None`` when the
    enumeration is COMPLETE — including the case where ``start`` is simply not
    in a repository, which is one checkout and not a failure to count them.

    ``git worktree list --porcelain`` is the oracle rather than a hand-rolled
    walk of ``.git``/``worktrees/*/gitdir`` (review lesson 4: re-typing an
    oracle is the recurring class). Its answer is still validated as untrusted
    input (review lesson 5): a listed path is accepted only when it names a
    real directory, and duplicates collapse. No branch or trunk name is ever
    resolved here — ISSUE-089's stale-``main`` binding has no foothold.
    """
    roots = [start]
    listed = _git(start, "worktree", "list", "--porcelain")
    if listed is None:
        return roots, f"git could not be run (missing executable or >{GIT_QUERY_TIMEOUT}s)"
    if listed.returncode != 0:
        inside = _git(start, "rev-parse", "--is-inside-work-tree")
        if inside is not None and inside.returncode != 0:
            # git's own answer to "am I in a repository": no. One checkout.
            return roots, None
        return roots, f"git worktree list exited {listed.returncode}"

    seen = {start.resolve()}
    for line in listed.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        candidate = Path(line[len("worktree "):].strip())
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        roots.append(candidate)
    return roots, None


def _declares_spec(value: str) -> bool:
    """True when a ``Spec:`` field names something rather than nothing."""
    return bool(value) and value.strip().lower() != "none"


def _contain(root: Path, spec_path: str) -> Path | None:
    """Resolve ``spec_path`` under ``root``, or ``None`` if it escapes it.

    The ``Spec:`` value comes from a markdown registry and is untrusted;
    widening the roots widens what a ``..`` escape or a symlink can reach, so
    containment is checked per root instead of being inherited from the
    single-root version's bare ``.resolve().exists()``.
    """
    candidate = Path(spec_path)
    if candidate.is_absolute():
        return None
    try:
        resolved = (root / candidate).resolve()
        root_resolved = root.resolve()
    except (OSError, ValueError):
        # ValueError: an embedded NUL in the registry value.
        return None
    if root_resolved not in resolved.parents:
        return None
    return resolved


def _spec_field_from_other_checkout(
    issue_id: str, roots: list[Path], read_from: Path, registry_name: str
) -> tuple[str, Path | None]:
    """Find the issue's ``Spec:`` field in another checkout's registry copy.

    Only the ``Spec:`` field is taken — never the body, status or estimate — so
    signal detection stays bound to the registry copy the caller pointed at.
    The candidate registry is untrusted input: it must be a regular file, and
    an unreadable or undecodable one is skipped rather than raised.
    """
    read_resolved = read_from.resolve()
    for root in roots:
        if root.resolve() == read_resolved:
            continue
        candidate = root / registry_name
        if not candidate.is_file():
            continue
        try:
            other = parse_issue(candidate, issue_id)
        except (OSError, UnicodeDecodeError):
            continue
        if other and _declares_spec(other["spec_path"]):
            return other["spec_path"], root
    return "", None


def spec_lookup(
    issue_id: str,
    spec_path: str,
    issues_md_dir: Path,
    registry_name: str = "issues.md",
) -> dict:
    """Resolve the issue's SPEC across every checkout of this repository.

    Returns ``{declared, field_root, found_at, roots, incomplete, contained}``.
    ``found_at`` is the checkout root whose tree holds the file, or ``None``.
    """
    roots, incomplete = checkout_roots(issues_md_dir)

    declared, field_root = spec_path, issues_md_dir
    if not _declares_spec(declared):
        declared, field_root = _spec_field_from_other_checkout(
            issue_id, roots, issues_md_dir, registry_name
        )

    found_at: Path | None = None
    refused: list[Path] = []
    if _declares_spec(declared):
        for root in roots:
            resolved = _contain(root, declared)
            if resolved is None:
                refused.append(root)
                continue
            if resolved.is_file():
                found_at = root
                break

    return {
        "declared": declared,
        "field_root": field_root,
        "found_at": found_at,
        "roots": roots,
        "incomplete": incomplete,
        "refused": refused,
    }


def _spec_present_reason(spec_path: str, lookup: dict, issues_md_dir: Path) -> str:
    read_root = issues_md_dir.resolve()
    legacy = (
        lookup["field_root"] is not None
        and lookup["field_root"].resolve() == read_root
        and lookup["found_at"].resolve() == read_root
    )
    if legacy:
        # Byte-for-byte the pre-ISSUE-102 string for the co-located caller class.
        return f"Spec-Required=true and SPEC exists at {spec_path}"
    return (
        f"Spec-Required=true and SPEC exists at {lookup['declared']} "
        f"(Spec: field read from {lookup['field_root']}; file found in "
        f"{lookup['found_at']}; {len(lookup['roots'])} checkout(s) consulted)"
    )


def _spec_missing_reasons(lookup: dict, sprint_mode: bool) -> list[str]:
    tail = (
        "sprint mode → auto-run /spec"
        if sprint_mode
        else "non-sprint mode → HOLD for user choice"
    )
    count = len(lookup["roots"])
    refused = lookup["refused"]
    roots = ", ".join(str(r) for r in lookup["roots"])
    if not _declares_spec(lookup["declared"]):
        # No checkout declares a SPEC: the pre-ISSUE-102 string, unchanged.
        reasons = [f"Spec-Required=true, SPEC missing, {tail}"]
    elif len(refused) == count:
        reasons = [
            f"Spec-Required=true, Spec: value {lookup['declared']!r} REFUSED by "
            f"containment in all {count} checkout(s) consulted ({roots}) — absolute "
            f"path, '..' escape, or symlink leaving the checkout, {tail}"
        ]
    else:
        reasons = [
            f"Spec-Required=true, SPEC declared at {lookup['declared']} but absent "
            f"from all {count} checkout(s) consulted ({roots}), {tail}"
        ]
        if refused:
            # A refused traversal must never read as "simply absent".
            reasons.append(
                f"Spec: value {lookup['declared']!r} was REFUSED by containment in "
                f"{len(refused)} of {count} checkout(s) "
                f"({', '.join(str(r) for r in refused)}) — it escaped that checkout"
            )
    if lookup["incomplete"]:
        reasons.append(
            f"{INCOMPLETE_MARKER} ({lookup['incomplete']}) — 'absent' above means "
            "absent from the checkouts that COULD be consulted, which is not the "
            "same as absent from the repository"
        )
    return reasons


def decide(
    issue: dict,
    issues_md_dir: Path,
    sprint_mode: bool,
    skip_gate: bool,
    registry_name: str = "issues.md",
) -> dict:
    """Apply the decision table.

    Returns a dict:
      {
        "decision": "proceed" | "auto_spec" | "hold" | "bypassed",
        "reasons": [str, ...],
        "signals": [{signal, evidence}, ...],
        "spec_path": str,
        "sprint_mode": bool,
      }
    """
    reasons: list[str] = []
    signals = scan_signals(issue["body"])
    spec_required = issue["spec_required"] == "true"

    if skip_gate:
        reasons.append("--skip-spec-gate was passed; bypassing gate")
        return _result("bypassed", reasons, signals, issue, sprint_mode)

    # The multi-checkout lookup runs ONLY for the caller class that needs it
    # (ISSUE-102). The signal-detection and bypass paths below never reach it,
    # so they are unchanged and consult no git.
    if spec_required:
        lookup = spec_lookup(
            issue["id"], issue["spec_path"], issues_md_dir, registry_name
        )
        if lookup["found_at"] is not None:
            reasons.append(
                _spec_present_reason(issue["spec_path"], lookup, issues_md_dir)
            )
            return _result("proceed", reasons, signals, issue, sprint_mode)

        reasons.extend(_spec_missing_reasons(lookup, sprint_mode))
        decision = "auto_spec" if sprint_mode else "hold"
        return _result(decision, reasons, signals, issue, sprint_mode)

    # Spec NOT required, but signals fired.
    if signals:
        labels = [s["signal"] for s in signals]
        if sprint_mode:
            reasons.append(
                f"Spec-Required=false; signals detected ({', '.join(labels)}); "
                "sprint mode → log recommendation, proceed"
            )
            return _result("proceed", reasons, signals, issue, sprint_mode)
        else:
            reasons.append(
                f"Spec-Required=false; signals detected ({', '.join(labels)}); "
                "non-sprint mode → HOLD for user choice"
            )
            return _result("hold", reasons, signals, issue, sprint_mode)

    # Nothing to gate on.
    reasons.append("Spec-Required=false and no signals; proceeding silently")
    return _result("proceed", reasons, signals, issue, sprint_mode)


def _result(
    decision: str,
    reasons: list[str],
    signals: list[dict],
    issue: dict,
    sprint_mode: bool,
) -> dict:
    return {
        "decision": decision,
        "reasons": reasons,
        "signals": signals,
        "spec_path": issue["spec_path"],
        "sprint_mode": sprint_mode,
        "issue_id": issue["id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spec gate for /implement")
    parser.add_argument("issue_id", help="Target issue (e.g., ISSUE-007)")
    parser.add_argument(
        "--issues-md",
        default="issues.md",
        help="Path to issues.md (default: ./issues.md)",
    )
    parser.add_argument(
        "--skip-spec-gate",
        action="store_true",
        help="Bypass the gate; emit a 'bypassed' telemetry event",
    )
    parser.add_argument(
        "--force-sprint-mode",
        action="store_true",
        help="Override KIT_SPRINT_MODE env (for testing)",
    )
    args = parser.parse_args(argv)

    issues_md = Path(args.issues_md)
    if not issues_md.exists():
        print(json.dumps({"error": f"issues.md not found at {issues_md}"}))
        return 2

    if not re.match(r"^ISSUE-\d+$", args.issue_id):
        print(json.dumps({"error": f"invalid issue id: {args.issue_id}"}))
        return 2

    issue = parse_issue(issues_md, args.issue_id)
    if issue is None:
        print(json.dumps({"error": f"{args.issue_id} not found in {issues_md}"}))
        return 2

    sprint_mode = args.force_sprint_mode or os.environ.get(SPRINT_ENV) == "1"
    result = decide(
        issue,
        issues_md.resolve().parent,
        sprint_mode,
        args.skip_spec_gate,
        # Other checkouts are consulted for the SAME registry filename the
        # caller pointed at, derived rather than hard-coded as "issues.md".
        registry_name=issues_md.name,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
