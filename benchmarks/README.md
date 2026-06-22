# Ponytail-axis benchmarks

Measures the effect of the ponytail-benchmarked changes (ISSUE-018/019/020) on
the kit's agents. Two experiments, both A/B with the **model held constant**
(`sonnet`) across arms so the measured delta isolates the prompt change, not the
model.

> **Read the caveats.** N is small, fixtures are hand-authored, runs are
> single-shot (no variance estimate), and the over-engineering ground truth is
> author-labelled. These are **directional** signals, not statistics. They were
> run on 2026-06-22.

## Experiment 1 — Over-engineering review axis (ISSUE-018)

`ponytail_axis/` — 6 fixtures (4 with planted over-engineering, 2 lean controls).
Each reviewed by two reviewer prompts: **baseline** (Code-Quality + Security
checklist) vs **treatment** (+ the over-engineering axis with `delete/stdlib/
native/yagni/shrink` tags). Findings scored against `expected.json`
(`score.py`): a finding hits a planted item if its line is within ±3 lines.

Reproduce: `python3 ponytail_axis/score.py`

| arm | recall | hits | tag-match | lean false-pos |
|-----|--------|------|-----------|----------------|
| baseline  | 100% | 8/8 | 0%  | 0/2 |
| treatment | 100% | 8/8 | 88% | 0/2 |

**Finding — recall saturated; the value is classification and direction, not detection.**
The planted over-engineering was blatant enough that the baseline's existing
"complexity and duplication" check caught the same lines (100% both arms). The
axis changed two things the recall number hides:

1. **Classification: 0% → 88% correct tags.** Baseline flags the line but does
   not label it as a *cut*; treatment labels it `delete`/`stdlib`/`yagni`, which
   is what makes a finding actionable and gradeable.
2. **Direction flip (the real signal).** On fixture `03` the **baseline
   recommended *adding* a `Notifier` ABC/Protocol**, and on `01` "add a second
   source to justify the ABC" — i.e. baseline pushed *toward more abstraction*
   on the exact lines the treatment said to delete. Without the minimality axis,
   a reviewer's default instinct is to add structure, not remove it.

Neither arm produced false positives on the lean controls — the axis did not
manufacture findings on already-clean code (it emitted "Lean already. Ship.").

**Limitation:** the fixtures were too easy to separate the arms on recall. A
harder fixture set (subtle over-engineering a quality review would miss) is
needed to measure a detection delta. Logged here rather than hidden.

## Experiment 2 — Decision-ladder LOC (ISSUE-019)

`ladder/` — 3 over-engineering-tempting tasks. Each implemented by two developer
prompts: **baseline** (senior-dev framing) vs **treatment** (+ the six-rung
decision ladder). Logical code lines counted by `measure_loc.py` (tokenize-based;
excludes blanks, comments, and docstrings so verbose docs don't skew it).

Reproduce: `python3 ladder/measure_loc.py`

| task | baseline SLOC | treatment SLOC | reduction |
|------|---------------|----------------|-----------|
| A — read JSON config value | 53 | 10 | 81% |
| B — N most-recent items     | 12 | 10 | 17% |
| C — feature-flag check      | 37 | 5  | 86% |
| **TOTAL** | **102** | **25** | **75%** |

**Finding — 75% fewer logical LOC, concentrated where baseline over-built.**
Baseline C built a 37-line immutable `FeatureFlags` class (`__contains__`, `get`,
`_validate_key`, `__repr__`, defensive copy) for "is this flag enabled?";
treatment wrote a 5-line function. Baseline A added a `_MISSING` sentinel,
`KeyError` path, and a `__main__` smoke-test block; treatment used
`dict.get(key, default)`. Where baseline was already near-minimal (task B), the
ladder forced almost no change (17%) — it does not cut for cutting's sake. This
matches ponytail's own pattern: large reductions on over-engineered tasks,
little on lean ones.

**Safety preserved.** Every treatment implementation kept input validation
(`isinstance` guards, JSON-object checks) — consistent with the rule that the
ladder never overrides validation/error-handling/security.

## Experiment 3 — Debt harvester (ISSUE-020)

Not a performance benchmark — the harvester's value is *correctness*, covered by
`tests/test_debt_harvest.py` (9/9: valid markers parsed, `no-trigger` flagged,
clean tree message, malformed handled, vendor dirs and binaries skipped).
