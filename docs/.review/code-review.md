# Code Review — ISSUE-041 (degraded-path, code dimension)

Scope: dedup/net-removal refactor of UI/UX design-philosophy boilerplate into a
canonical fragment (`scripts/fragments.py`) consumed by 3 skill tmpls via tokens
and mirrored by 3 static agents behind a drift guard. No runtime behavior change
(prompt/instruction text + a build-time codegen module).

Empirical verification performed (worktree):
- `python3 -m pytest tests/test_design_fragments.py tests/test_reference_anchor_tuning.py` → **40 passed**.
- `python3 scripts/gen_skills.py --dry-run` → **All 20 SKILL.md files are fresh**.
- Resolver output for all 3 skills inspected and matches the blocks removed from
  each tmpl (see AC-2 below).
- `git diff --name-only af832cb..HEAD -- 'skills/*/SKILL.md'` → **only `skills/uiux/SKILL.md`**
  changed among generated files. Mobile/desktop generated SKILL.md are byte-identical
  to pre-extraction — the resolver reproduces the previous inline content exactly.
- Freshness gate exists and asserts: `tests/test_gen_skills.py::test_dry_run_passes_when_fresh`
  (returncode 0) + `test_dry_run_detects_stale`. The "forgot to regenerate" direction is covered.

## Findings

### Low — Drift guard is a presence-of-new whitelist, not an absence-of-old check
`scripts/fragments.py:210` (`find_out_of_sync_fragments`)
The guard asserts each canonical chunk is *contained* in the agent text. It does
NOT assert that superseded/old wording is *absent*. If a future edit left stale
boilerplate in an agent file *alongside* the new canonical chunk, the guard would
still pass. This is the known trade-off called out in the task (LESSON A(d)).
Impact in THIS diff: none — the 4 wording unifications cleanly replaced old with
new (verified: all 3 agents report `[]` from the guard; no duplicated sentinels).
Severity is Low because triggering a real regression requires an agent to carry
duplicate/contradictory copies, which is not the normal editing pattern, and the
skill-side `test_fragment_appears_exactly_once` provides a partial backstop.
Recommended action: accept as documented trade-off. Optionally, if cheap, add a
per-agent "no orphaned old sentinel" assertion for any wording that was
intentionally unified (e.g. assert `"Spot-check 3 random components"` and
`"re-check prototype setup"` no longer appear in any agent). Not blocking.

### Info — Platform-specific tails on prefix chunks are intentionally unguarded
`scripts/fragments.py:170` (`interview_skip`), `:191` (`self_review_token_rule`)
These chunks end mid-sentence (e.g. `...from competitor analysis`,
`...outside of`) so each agent's platform tail (`, Desktop Identity...`,
`` `src/theme/`? ``) stays inline and is NOT covered by the guard. This is correct
and documented, but means deletion/corruption of a platform tail would not be
detected by the drift guard. Verified the prefix-containment still holds for all
3 agents (desktop's appended `, Desktop Identity from product type.` does not
break containment). No action required.

### Info — Web SKILL.md gains a cosmetic 5→3 space continuation-indent change
`skills/uiux/SKILL.md` (diff lines 432-438)
Because the canonical `_INTERVIEW_TEMPLATE` uses 3-space continuation indent while
the old inline web block used 5-space, regeneration reflows 3 lines of the web
skill. Whitespace-only, does not affect how Claude reads the prompt (these files
are prompt text, not strictly-rendered markdown). Benign; noted for completeness.

## Notes on quality (no findings)
- Correctness: `.format()` fill logic for the desktop question/derive inserts and
  the response-step number is correct; blank-line handling reproduces the original
  layout exactly (proven by mobile/desktop generated files being byte-unchanged).
- Error handling: unknown `skill_name` raises `ValueError` via `_require_uiux_skill`
  (tested with `implement`, `figma2proto`, `""`).
- Test coverage: comprehensive — resolvers, per-skill deltas, no-inline (AC-1),
  exactly-once (TC-041d), drift guard in BOTH directions (canonical-edit mutation
  self-test + agent-edit containment), whitespace-insensitivity, unknown-skill.
  The `fragments=` parameter on the guard is a legitimate test-injection seam, not
  dead config.
