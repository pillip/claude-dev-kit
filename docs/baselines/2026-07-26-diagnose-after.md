# After baseline — /diagnose benchmark (post 0.2.0 harness changes)

> ISSUE-001's before/after loop, closed. Same recipe as
> `2026-07-23-diagnose-baseline.md` (the **before**), re-run on the 0.2.0
> plugin after ISSUE-030/031/032 landed. Verified live 2026-07-26.

## Metrics — before vs after

| Metric | Before (2026-07-23) | After (2026-07-26, 0.2.0) | Δ |
|---|---|---|---|
| Wall-clock (API `duration_ms`) | 74.4 s | 61.4 s | −17% |
| API turns | 10 | 9 | −1 |
| Input tokens (fresh) | 6,822 | 8,027 | +18% |
| Cache creation tokens | 23,091 | 23,517 | ~flat |
| **Cache read tokens** | **262,480** | **188,763** | **−28%** |
| Output tokens | 4,424 | 3,943 | −11% |
| Cost | $1.014 | $0.937 | −8% |
| Checkpoints exercised | 0 | 0 | — |
| Subagents spawned | 0 | 0 | — |

## Reading

- **The 28% cache-read drop is the headline** — that's the ISSUE-032 preamble
  diet (1385→618 duplicated lines) plus ISSUE-031's lighter checkpoint text
  showing up as less harness context carried through every API turn. On a run
  that touches 9 turns, ~73k fewer cache-read tokens per run is the measurable
  payoff the telemetry (ISSUE-001) was built to capture.
- Cost and wall-clock both fell (−8% / −17%) consistent with the smaller
  per-turn context.
- **What this run does NOT measure**: the benchmark still spawns 0 subagents
  and runs 0 checkpoints (the /diagnose skill works inline), so it isolates the
  context/preamble reduction — NOT the ISSUE-030 model-inherit effect (needs a
  subagent-spawning run) nor the ISSUE-029 delegation quality (needs /review).
  Those were verified functionally live on 2026-07-26 (see the session log:
  /code-review fired, the eval judge round-tripped, native-memory recall
  worked) but their token/quality deltas want a /review-based benchmark.

## Recipe

Identical to the before-baseline: a git fixture with a qty-default `TypeError`
bug in `cart.py`, kit installed as a plugin, then

```bash
claude -p "/claude-dev-kit:diagnose <bug description> — reproduce, diagnose, apply the fix" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Task" --output-format json
```

collecting the JSON `usage`/`duration_ms`/`num_turns` + `trace_query.py summary`.
