#!/usr/bin/env python3
"""Score over-engineering detection runs against ground truth.

Reads expected.json and per-arm run outputs under results/<arm>/<fixture>.json,
each shaped {"lean_verdict": bool, "findings": [{"line": int, "tag": str, "what": str}]}.

A finding HITS a planted item if its line falls within [line_lo-PROX, line_hi+PROX].
Hit detection is tag-agnostic (reviewers phrase the same cut differently); tag
agreement is reported separately as a bonus signal.

Metrics per arm:
  - recall      = planted items hit / total planted (over-engineered fixtures)
  - tag_match   = hits where the finding's tag equals the planted tag / hits
  - lean_fp     = lean fixtures that got >=1 cut finding (false positives)

Usage:
    python3 score.py                 # scan ./results/*
    python3 score.py --results DIR
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROX = 3
HERE = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def score_arm(arm_dir: Path, expected: dict) -> dict:
    planted_total = hits = tag_match = lean_fp = lean_total = 0
    per_fixture: list[dict] = []

    for fname, spec in expected["fixtures"].items():
        run_path = arm_dir / f"{fname}.json"
        run = _load(run_path) if run_path.exists() else {"lean_verdict": True, "findings": []}
        findings = run.get("findings", []) or []

        if spec["lean"]:
            lean_total += 1
            fp = len(findings) > 0
            lean_fp += 1 if fp else 0
            per_fixture.append({"fixture": fname, "lean": True, "false_positive": fp,
                                "n_findings": len(findings)})
            continue

        f_hits = 0
        for item in spec["planted"]:
            planted_total += 1
            lo, hi = item["line_lo"] - PROX, item["line_hi"] + PROX
            matched = [f for f in findings if isinstance(f.get("line"), int) and lo <= f["line"] <= hi]
            if matched:
                hits += 1
                f_hits += 1
                if any(f.get("tag") == item["tag"] for f in matched):
                    tag_match += 1
        per_fixture.append({"fixture": fname, "lean": False,
                            "planted": len(spec["planted"]), "hits": f_hits})

    return {
        "arm": arm_dir.name,
        "planted_total": planted_total,
        "hits": hits,
        "recall": round(hits / planted_total, 3) if planted_total else None,
        "tag_match_rate": round(tag_match / hits, 3) if hits else None,
        "lean_total": lean_total,
        "lean_false_positives": lean_fp,
        "per_fixture": per_fixture,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score over-engineering detection runs.")
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--expected", default=str(HERE / "expected.json"))
    args = ap.parse_args(argv)

    expected = _load(Path(args.expected))
    results_dir = Path(args.results)
    arms = sorted(p for p in results_dir.iterdir() if p.is_dir()) if results_dir.is_dir() else []
    if not arms:
        print(f"No arm directories under {results_dir}")
        return 2

    scored = [score_arm(a, expected) for a in arms]

    print(f"{'arm':<12} {'recall':>8} {'hits':>10} {'tag_match':>10} {'lean_FP':>9}")
    print("-" * 52)
    for s in scored:
        recall = f"{s['recall']:.0%}" if s["recall"] is not None else "—"
        tagm = f"{s['tag_match_rate']:.0%}" if s["tag_match_rate"] is not None else "—"
        print(f"{s['arm']:<12} {recall:>8} {str(s['hits'])+'/'+str(s['planted_total']):>10} "
              f"{tagm:>10} {str(s['lean_false_positives'])+'/'+str(s['lean_total']):>9}")

    print()
    print(json.dumps(scored, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
