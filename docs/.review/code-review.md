# Code Review (degraded) — ISSUE-036 / PR #57

Reviewed: `git diff origin/main...HEAD` @ 9e2334f (skills/brainstorm/SKILL.md(+tmpl), skills/review/SKILL.md(+tmpl), tests/test_brainstorm_research_path_guard.py (new), tests/test_review_delegation_guard.py (+45)).

Verification performed (read-only):
- `python3 scripts/gen_skills.py --dry-run` → "All 20 SKILL.md files are fresh." (tmpl↔generated freshness holds).
- `uv run pytest -q tests/test_review_delegation_guard.py tests/test_brainstorm_research_path_guard.py` → 19 passed.
- Mutation check: applied the new `STEP_HEADER_RE` monotonicity logic to `origin/main:skills/review/SKILL.md` — pre-fix header order `[1, 2, 5, 6, 7, 8, 9, 10, 8, 9, 10, 11, 12]` yields violation `3.10 -> 3.8`. The guard genuinely rejects the duplicated cluster it was written for (adjacent-pair `cur <= prev` comparison is sound and complete for strict monotonicity — any non-monotonic sequence has an adjacent inversion, and duplicates are caught by `<=`).
- Repo-wide grep for stale step references: external mentions of "Figma 3.5–3.10" (docs/specs/SPEC-019.md, agents/review-merge-auditor.md, scripts/synthesize_review_notes.py docstring) remain accurate because the Figma cluster kept its numbers. No external reference to the old 3.11/3.12 (synthesize/merge-audit) numbering survives — except one, inside the new test itself (finding below).
- Checkpoint phase names (`figma-compliance`, `computed-styles`, `structural-match`, `layout`, `visual-diff`, `ui-review`, `synthesis-audit`) untouched — scope-out respected.
- Recalled review lessons (subprocess timeouts / env-var knobs / mock seams): not applicable — the diff contains no `subprocess`, no `timeout=`, no env vars, no mocks.

## AC Verification

- **AC1 — strictly increasing `3.N)` sequence in generated SKILL.md**: PASS. Extracted document-order headers: 3.1, 3.2, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15. No duplicates. (Gaps 3.3/3.4 are pre-existing and permitted by the AC's "strictly increasing" wording; the test correctly tolerates them — it could not do otherwise.)
- **AC2 — synthesis cross-references exact**: PASS. Step 3.14 reads "(Figma 3.5–3.10, UI review 3.11, design audit 3.12, a11y audit 3.13)"; the Figma cluster is exactly 3.5 (compliance) through 3.10 (visual diff debug images). The italic aside was updated to "checks 3.5–3.13 … see steps 3.14 and 3.15", the minimality-axis note now says "(step 3.14)", and step 5 says "produced by step 3.14". All in-file references consistent in both tmpl and generated output.
- **AC3 — brainstorm degraded path names canonical dir**: PASS. The research-auditor invocation line (skills/brainstorm/SKILL.md:40) reads `inputs = (draft, \`docs/references/research/\`)`; "snapshot directory" occurs 0 times in both SKILL.md and SKILL.md.tmpl.
- **Tests promised**: PASS. Monotonicity guard added (both tmpl and generated file, mutation-verified above); brainstorm canonical-dir assertion added and deliberately scoped to the `subagent_type: research-auditor` line to avoid a vacuous whole-file substring pass (the canonical dir already appears elsewhere in the file) — good non-hollow design, explicitly documented in the module docstring.

## Findings

### [Low] Stale docstring in TestReviewStepHeadersAreMonotonic describes the pre-fix state and cites retired step numbers

**Evidence**: tests/test_review_delegation_guard.py:118-121

```
"""ISSUE-036 — step numbers 3.8/3.9/3.10 are currently reused twice
(Figma cluster AND ui/design/a11y cluster). Step headers must be
strictly increasing in document order so cross-references like
"steps 3.11 and 3.12" are unambiguous. ...
```

Two problems once this PR lands: (a) "are currently reused twice" is present-tense RED-phase wording that becomes false the moment the fix merges — a future reader will think the bug is live; (b) the example cross-reference "steps 3.11 and 3.12" refers to the OLD numbers of synthesize/merge-audit, which this very PR renumbers to 3.14/3.15 — post-fix, 3.11/3.12 denote ui-review/design-audit, so the example points at the wrong steps and no longer matches any cross-reference in the skill (the module-level comment at lines 24-26 already uses the correct "steps 3.14 and 3.15" example, making the class docstring internally inconsistent with it).

**Fix**: Reword to past tense with current numbers, e.g.: `"""ISSUE-036 — step numbers 3.8/3.9/3.10 were once reused twice (Figma cluster AND ui/design/a11y cluster). Step headers must be strictly increasing in document order so cross-references like "steps 3.14 and 3.15" are unambiguous. ..."""`

## Over-Engineering (minimality axis)

tests/test_brainstorm_research_path_guard.py:41: shrink 2×2 copy-pasted assertion bodies (identical message blocks repeated for generated vs tmpl in both classes) → parametrize over the two paths (`@pytest.mark.parametrize("path", [SKILL, TMPL], ids=["generated", "template"])`) or extract the assertion loop into a shared helper alongside `_auditor_lines`; ~79 lines becomes ~55 with identical coverage and failure messages.

Net removable lines: ~24.
