#!/usr/bin/env python3
"""LLM-as-judge eval for review_notes quality (ISSUE-002).

Runs a fresh `claude -p` (headless) judge over a `review_notes.md` + the PR diff,
scoring how well the review covered what the diff warranted (rubric:
templates/review_eval_rubric.md). Emits `docs/review_eval_<pr>.md`. Wired into
/ship as a NON-BLOCKING advisory — it never changes the ship exit code.

No separate billing: the judge runs on the user's existing Claude Code auth via
the `claude` CLI, NOT the Anthropic API. If the CLI is unavailable the eval is
skipped with a one-line warning and exit 0 (degraded mode).

Usage:
    python3 scripts/eval_review.py --pr 42 --notes docs/review_notes/ISSUE-1.md
    python3 scripts/eval_review.py --pr 42 --notes <path> --runs 2   # determinism
    python3 scripts/eval_review.py --pr 42 --notes <path> --model sonnet
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "templates" / "review_eval_rubric.md"
REQUIRED_DIMENSIONS = ("coverage", "false_positive_rate", "actionability", "traceability")
HIGH_SEVERITIES = ("Critical", "High")


# ── Pure helpers (unit-tested without the CLI) ───────────────────────

def load_rubric(path: Path = RUBRIC_PATH) -> str:
    """Return the rubric text. Tolerates extra prose; requires the 4 dimension
    headers to be present so a truncated/edited rubric fails loudly."""
    text = path.read_text(encoding="utf-8")
    missing = [d for d in REQUIRED_DIMENSIONS if f"### {d}" not in text]
    if missing:
        raise ValueError(f"rubric {path} missing dimension headers: {missing}")
    return text


def build_prompt(diff: str, notes: str, rubric: str) -> str:
    return (
        "You are an independent judge auditing a code review — NOT re-reviewing "
        "the code for the user. Read the PR diff and the reviewer's notes, then "
        "score how well the notes covered what the diff actually warranted.\n\n"
        "Return ONE JSON object per the rubric's output contract and nothing "
        "else — no markdown fences, no prose.\n\n"
        f"=== RUBRIC ===\n{rubric}\n\n"
        f"=== PR DIFF ===\n{diff}\n\n"
        f"=== REVIEW NOTES ===\n{notes}\n"
    )


def parse_verdict(raw: str) -> dict:
    """Extract the JSON verdict from a judge response (tolerates stray text /
    ```json fences around the object)."""
    s = raw.strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in judge output")
    obj = json.loads(s[start : end + 1])
    scores = obj.get("scores") or {}
    for d in REQUIRED_DIMENSIONS:
        if not isinstance(scores.get(d), (int, float)):
            raise ValueError(f"verdict missing numeric score for {d!r}")
    obj.setdefault("missed_findings", [])
    obj.setdefault("concerns", [])
    # Normalize verdict per the rubric rule even if the judge omitted/contradicted it.
    obj["verdict"] = _derive_verdict(obj)
    return obj


def _derive_verdict(obj: dict) -> str:
    missed_high = any(
        f.get("severity") in HIGH_SEVERITIES for f in obj.get("missed_findings", [])
    )
    low_score = any(
        float(obj["scores"].get(d, 5)) <= 2 for d in REQUIRED_DIMENSIONS
    )
    return "concerns" if (missed_high or low_score) else "pass"


def high_finding_keys(verdict: dict) -> set[str]:
    """Stable identity for Critical/High missed findings (for determinism overlap)."""
    keys = set()
    for f in verdict.get("missed_findings", []):
        if f.get("severity") in HIGH_SEVERITIES:
            keys.add(f"{f.get('severity')}::{(f.get('diff_ref') or '').strip()}")
    return keys


def overlap_ratio(a: set[str], b: set[str]) -> float:
    """Jaccard overlap of two high-finding key sets. Two empty sets = 1.0
    (both agree there is nothing critical missed)."""
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def render_report(pr: str, verdict: dict, *, determinism: float | None) -> str:
    s = verdict["scores"]
    lines = [
        f"# Review Eval — PR #{pr}",
        "",
        f"**Verdict:** {verdict['verdict']}",
        "",
        "| Dimension | Score (0-5) |",
        "|---|---|",
    ]
    for d in REQUIRED_DIMENSIONS:
        lines.append(f"| {d} | {s.get(d)} |")
    if determinism is not None:
        lines += ["", f"**Determinism** (Critical/High overlap across runs): {determinism:.0%}"]

    lines += ["", "## Missed findings"]
    missed = verdict.get("missed_findings", [])
    if not missed:
        lines.append("_None._")
    for f in missed:
        lines.append(
            f"- **[{f.get('severity')}] {f.get('title','').strip()}** "
            f"(`{f.get('diff_ref','?')}`, {f.get('rubric','?')})"
        )
        if f.get("evidence"):
            lines.append(f"  Evidence: {f['evidence'].strip()}")

    lines += ["", "## Concerns"]
    concerns = verdict.get("concerns", [])
    if not concerns:
        lines.append("_None._")
    for c in concerns:
        lines.append(f"- ({c.get('rubric','?')}, `{c.get('diff_ref','?')}`) {c.get('note','').strip()}")

    return "\n".join(lines).rstrip() + "\n"


# ── I/O (thin wrappers over the CLI/git) ─────────────────────────────

def cli_available() -> bool:
    return shutil.which("claude") is not None


def get_pr_diff(pr: str) -> str:
    proc = subprocess.run(
        ["gh", "pr", "diff", str(pr)], capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh pr diff {pr} failed: {proc.stderr.strip()}")
    return proc.stdout


def run_judge(prompt: str, model: str | None) -> str:
    cmd = ["claude", "-p", prompt, "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {proc.stderr.strip()}")
    return proc.stdout


def evaluate(pr: str, notes_path: Path, *, model: str | None, runs: int) -> dict:
    diff = get_pr_diff(pr)
    notes = notes_path.read_text(encoding="utf-8")
    prompt = build_prompt(diff, notes, load_rubric())

    verdicts = [parse_verdict(run_judge(prompt, model)) for _ in range(max(1, runs))]
    primary = verdicts[0]
    determinism = None
    if len(verdicts) > 1:
        keys = [high_finding_keys(v) for v in verdicts]
        pairs = [
            overlap_ratio(keys[i], keys[j])
            for i in range(len(keys))
            for j in range(i + 1, len(keys))
        ]
        determinism = sum(pairs) / len(pairs) if pairs else 1.0
    primary["_determinism"] = determinism
    return primary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM-as-judge eval of review notes (advisory).")
    parser.add_argument("--pr", required=True)
    parser.add_argument("--notes", required=True, type=Path)
    parser.add_argument("--model", default=None, help="judge model alias (default: session model)")
    parser.add_argument("--runs", type=int, default=1, help="re-runs for a determinism check")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    # Degraded mode: never block the ship gate on a missing dependency.
    if not cli_available():
        print("eval skipped: claude CLI not available", file=sys.stderr)
        return 0
    if not args.notes.exists():
        print(f"eval skipped: review notes not found ({args.notes})", file=sys.stderr)
        return 0

    try:
        verdict = evaluate(args.pr, args.notes, model=args.model, runs=args.runs)
    except Exception as exc:  # advisory tool — surface, never crash the gate
        print(f"eval skipped: {exc}", file=sys.stderr)
        return 0

    out = args.out or (ROOT / "docs" / f"review_eval_{args.pr}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    report = render_report(args.pr, verdict, determinism=verdict.get("_determinism"))
    out.write_text(report, encoding="utf-8")
    print(f"eval: {verdict['verdict']} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
