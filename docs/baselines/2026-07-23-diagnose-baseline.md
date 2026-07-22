# Baseline run — /diagnose benchmark (pre ISSUE-030..033)

> ISSUE-001 (minimal re-scope). This is the **before** measurement for the
> harness changes ISSUE-030 (model pins → inherit), 031 (checkpoint diet),
> 032 (SessionStart hook + preamble slim), 033 (native-memory learning loop).
> Re-run the identical recipe after each change lands and compare.

## Environment

- Claude Code **2.1.193**, session model `claude-fable-5` (headless default).
- Kit installed as a **plugin** (`--scope local`) from a local-dir marketplace
  pointing at the kit repo, branch `issue/ISSUE-001-telemetry-minimal`
  (post-ISSUE-035/027 tree: Kit Script Root preamble, plugin-first install).
- Telemetry: shape-only `events.jsonl` (agent_state.py) + `claude -p
  --output-format json` usage block.

## Recipe (repeat verbatim for the after-run)

1. Fixture project (git repo, no remote) with two files:
   - `cart.py` — `total_price()` multiplies `item["price"] * item.get("qty")`;
     items without `qty` produce `TypeError` (None). `checkout()` wraps it.
   - `test_cart.py` — `test_checkout_defaults_qty_to_one` (fails),
     `test_checkout_with_discount` (passes).
2. `claude plugin marketplace add <kit-repo>` +
   `claude plugin install claude-dev-kit@claude-dev-kit --scope local`.
3. Run:

   ```bash
   claude -p "/claude-dev-kit:diagnose test_checkout_defaults_qty_to_one fails with TypeError: unsupported operand type(s) for *: 'float' and 'NoneType' — reproduce with 'python3 -m pytest test_cart.py -q', diagnose, and apply the targeted fix" \
     --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Task" --output-format json
   ```

4. Collect: the JSON `usage`/`total_cost_usd`/`num_turns`/`duration_ms` +
   `python3 scripts/trace_query.py summary .claude/run/events.jsonl*`.

## Metrics — 2026-07-23 (BEFORE)

| Metric | Value |
|---|---|
| Outcome | Bug fixed + committed locally; tests green (GH branch/PR skipped — fixture has no remote) |
| Wall-clock (API `duration_ms`) | 74.4 s |
| API turns (`num_turns`) | 10 |
| Input tokens (fresh) | 6,822 |
| Cache creation tokens | 23,091 |
| Cache read tokens | 262,480 |
| Output tokens | 4,424 |
| Cost | $1.014 (fable-5 $1.0137 + haiku $0.0007) |
| Telemetry: user turns | 1 |
| Telemetry: tool calls | 9 (Bash×6, Read×2, Edit×1; 0 failures) |
| Telemetry: subagent spawns | 0 |
| Telemetry: checkpoint runs | 0 |
| Permission denials | 0 |

## Observations (relevant to the after-comparison)

- **The skill's own harness was largely bypassed**: /diagnose declares 4
  checkpoint gates and a diagnostician subagent, but the headless run spawned
  **no subagent and ran no checkpoint** — the model read, fixed, tested, and
  committed directly. The ~262k cache-read tokens are dominated by the skill
  body + preamble being carried through 10 API turns.
  - For ISSUE-031/032 this IS the signal: gates and preamble cost context
    without shaping this run's behavior.
  - For ISSUE-030 note the subagent-pin effect is NOT exercised by this
    benchmark (0 spawns) — judge 030 by reviewer/auditor quality on a /review
    or /implement run instead, or accept this as a cost-only comparison.
- Kit Script Root worked implicitly (no path errors); the run also filed a
  contributor-mode field report about the no-remote edge case.
- events.jsonl is rotated to `events.jsonl.1` by the Stop-hook cleanup at
  session end — query with the glob `events.jsonl*`.
