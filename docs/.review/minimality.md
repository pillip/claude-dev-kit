# Minimality Review — ISSUE-041 (over-engineering axis)

This is a dedup/net-removal refactor. Weighting per task guidance: net removal
should approve; flag only over-abstraction beyond the existing `{{PREAMBLE}}`
precedent.

## Assessment against the recalled over-engineering concerns

- **12-chunk `AGENT_DESIGN_FRAGMENTS` decomposition — JUSTIFIED, not gratuitous.**
  Verified by reading all 3 agent files: the shared boilerplate is *interleaved*
  with platform-specific text that differs per agent — step 3 `Constraints`
  (web: "performance, accessibility" vs mobile/desktop: "platform conventions..."),
  the Mobile-/Desktop-Specific Design Lens sections, the WebSearch domain phrase
  (`[product domain] UI/mobile app/desktop app design trends`), the reference-research
  step 3, and the token-location tail (`CSS custom properties?` vs `` `src/theme/`? ``).
  A single contiguous blob cannot be substring-guarded across these gaps, so the
  chunks correspond exactly to the maximal shared-contiguous runs. Minimal, not padded.

- **Resolver signature — consistent with precedent, no new machinery.** Both new
  tokens register as `Callable[[str], str]` in the same `RESOLVERS` dict as
  `PREAMBLE`. They are registered directly (no `_resolve_*` wrapper), which is
  marginally *less* indirection than `PREAMBLE` — acceptable.

- **`find_out_of_sync_fragments(..., fragments=None)` seam — legitimate, not yagni.**
  The injectable `fragments` param exists to let the mutation self-test doctor a
  chunk without monkeypatching a module global. Two real callers (default + test).

## Findings

`Lean already. Ship.`

Net removable lines: **~0**. Do NOT cut the drift-guard machinery or the chunk
decomposition — both are the minimum needed to enforce agent alignment for static
(non-generated) files, and the skill side genuinely collapses 3 inline copies → 1
canonical source via the established token mechanism. (Optional trivial shrink:
`_RESPONSE_STEP` could be a ternary instead of a 3-entry dict, ~3 lines — but the
data-driven dict is clearer and mirrors the per-skill style; not worth changing.)
