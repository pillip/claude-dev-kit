# Review Notes — PR #72

## Code Review
_Source: reviewer-degraded_

- **[Low] Drift guard is a presence-of-new whitelist, not an absence-of-old check**
  Evidence: scripts/fragments.py:210 find_out_of_sync_fragments asserts each canonical chunk is CONTAINED in the agent text; it does not assert that superseded/old wording is ABSENT. A future edit that left stale boilerplate alongside the new canonical chunk would still pass the guard. Impact in THIS diff: none — all 3 agents report [] and the 4 wording unifications cleanly replaced old with new. Known trade-off (LESSON A(d)).
  Fix: Accept as documented trade-off (non-blocking). Optionally add a cheap per-agent 'no orphaned old sentinel' assertion for the intentionally-unified wordings (e.g. assert 'Spot-check 3 random components' and 're-check prototype setup' no longer appear in any agent).

- **[Low] [info] Platform-specific tails on prefix chunks are intentionally unguarded**
  Evidence: scripts/fragments.py:170 (interview_skip) and :191 (self_review_token_rule) end mid-sentence so each agent's platform tail (', Desktop Identity...', '`src/theme/`?') stays inline and is not covered by the drift guard. This is correct and documented; deletion/corruption of a platform tail would not be caught by the guard. Originally Info-level, no action required — recorded for completeness.
  Fix: No action required — intentional design; the platform deltas are out of the drift-guard's scope by design.

- **[Low] [info] Web SKILL.md gains a cosmetic 5->3 space continuation-indent change**
  Evidence: skills/uiux/SKILL.md — the canonical _INTERVIEW_TEMPLATE uses a 3-space continuation indent while the old inline web block used 5-space, so regeneration reflows 3 lines. Whitespace-only; does not affect how the prompt reads. This is documented wording-unification #1 in the PR body. Originally Info-level, benign.
  Fix: No action required — benign whitespace unification, documented in the PR.

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

_No findings._
