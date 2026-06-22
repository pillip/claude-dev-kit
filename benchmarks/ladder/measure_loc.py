#!/usr/bin/env python3
"""Measure logical lines of code (SLOC) per implementation, per arm.

SLOC = physical lines containing at least one token that is not a comment,
string/docstring, or layout token. This fairly excludes docstrings and
comments so verbose documentation does not inflate one arm over another.

Usage:
    python3 measure_loc.py        # scan ./results/{baseline,treatment}/task*.py
"""

from __future__ import annotations

import token
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Names may not all exist across Python versions (FSTRING_* added in 3.12).
_SKIP_NAMES = ["COMMENT", "STRING", "NL", "NEWLINE", "INDENT", "DEDENT",
               "ENCODING", "ENDMARKER", "FSTRING_START", "FSTRING_MIDDLE",
               "FSTRING_END"]
SKIP = {getattr(token, n) for n in _SKIP_NAMES if hasattr(token, n)}


def sloc(path: Path) -> int:
    code_lines: set[int] = set()
    with path.open("rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type not in SKIP and tok.string.strip():
                code_lines.add(tok.start[0])
    return len(code_lines)


def nonblank(path: Path) -> int:
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def main() -> int:
    arms = ["baseline", "treatment"]
    tasks = sorted({p.name for arm in arms for p in (HERE / "results" / arm).glob("task*.py")})

    print(f"{'task':<8} {'baseline_sloc':>14} {'treatment_sloc':>15} {'delta':>8} {'reduction':>10}")
    print("-" * 60)
    tot_b = tot_t = 0
    for t in tasks:
        b = sloc(HERE / "results" / "baseline" / t)
        tr = sloc(HERE / "results" / "treatment" / t)
        tot_b += b
        tot_t += tr
        red = f"{(b - tr) / b:.0%}" if b else "—"
        print(f"{t:<8} {b:>14} {tr:>15} {b - tr:>8} {red:>10}")
    print("-" * 60)
    red = f"{(tot_b - tot_t) / tot_b:.0%}" if tot_b else "—"
    print(f"{'TOTAL':<8} {tot_b:>14} {tot_t:>15} {tot_b - tot_t:>8} {red:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
