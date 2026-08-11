# Security Review (degraded) — ISSUE-036 / PR #57

**Scope:** `git diff origin/main...HEAD` @ 9e2334f — skills/brainstorm/SKILL.md(+tmpl), skills/review/SKILL.md(+tmpl), tests/test_brainstorm_research_path_guard.py (new), tests/test_review_delegation_guard.py.

**No security findings.** The diff is a text/docs-precision change (step renumbering + naming a canonical directory) plus read-only structural guard tests. No security-relevant surface is introduced or weakened.

## Surfaces checked

- **Instruction-injection surface (skill markdown executed as agent instructions):** Changes are limited to step-number renumbering (3.8–3.10 → 3.11–3.13, 3.11/3.12 → 3.14/3.15) and replacing the vague phrase "snapshot directory" with the literal `docs/references/research/`. No new instructions, subagent invocations, or command examples added. The renumbering *removes* ambiguity in the block-save gate cross-references (synthesis 3.14 / merge-audit 3.15), which is a hardening of gate sequencing, not a weakening.
- **References resolving to attacker-controlled paths:** The newly named `docs/references/research/` is a fixed repo-relative path that matches `scripts/capture_source.py`'s `DEFAULT_DIR = Path("docs/references/research")` (line 45). It replaces a vaguer phrase, narrowing where the research-auditor looks. The fact that this directory holds untrusted captured web content pre-exists this diff (capture_source.py already wrote there; the auditor already consumed it) — not introduced by this PR.
- **Command examples / secret exfiltration:** No new commands in the diff; no secrets, keys, or credentials in any hunk.
- **allowed-tools frontmatter:** Verified unchanged in both `skills/review/SKILL.md` and `skills/brainstorm/SKILL.md` (and templates) — no tool-permission widening.
- **Test code executing untrusted input:** Both test files use only `Path.read_text` on repo-internal files plus substring/regex assertions. No subprocess, no network, no deserialization, no mocks. The `STEP_HEADER_RE` regex (`^3\.(\d+)\)`, MULTILINE) is linear — no ReDoS.
- **Dependencies:** No dependency or lockfile changes (diff stat: 4 skill markdown files + 2 test files only).
- **Recalled-lesson classes:** No subprocess/timeout seams touched (ISSUE-046/047 class n/a); no env-var knobs added; no mock seams in the new tests.

## Findings

None.

**Confidence: High** — small diff read in full; every checklist category checked against concrete evidence in the worktree.
