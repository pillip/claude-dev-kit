# Code Review (degraded) — ISSUE-040 / PR #65

Scope: `git diff main...HEAD` @ cced139 — `README.md` (+37/−14), `tests/test_readme_consistency.py` (new, 120 lines). Reviewed dimension: code (+ minimality folded in). Security reviewed separately (`security-review.md`).

Verification performed: 6/6 new tests pass in the worktree (0.01s, hermetic). All four README agent-count statements (3 prose + 1 structure-comment) are captured by `COUNT_PATTERNS`. Table walker parses exactly 32 rows and terminates correctly on the blank line after the table. AC greps re-run independently: `v0.1` → 0, `opus (21` → 0, `.claude-kit/` → only the deliberately-live line 714, `33` → only the legal `ISSUE-033` reference. Agents/*.md = 32 = `test_agent_effort.py` pin. New auditor rows' role blurbs match agent frontmatter descriptions. AC 1–3 all satisfied.

---

### [Medium] Tests badge "1167 passing" was generated from a venv missing dev extras — silently undercounts the canonical suite by 7

**File:** `README.md:5` (changed in this diff: 1116 → 1167)

**Evidence:** In this worktree's venv PyYAML is absent (`uv run python -c "import yaml"` → ModuleNotFoundError). Consequence: `tests/test_plugin_manifest.py`'s 6 tests are silently dropped at collection (module-level `pytest.importorskip("yaml")`, line 16 — `pytest --collect-only tests/test_plugin_manifest.py` → "no tests collected") and `test_strict_yaml_parse_when_pyyaml_present` skips at runtime. Full-repo collection here = 1168, so a run yields exactly **1167 passed, 1 skipped** — the badge number's provenance. But PyYAML is a declared optional dependency (`pyproject.toml:16`, `pyyaml>=6.0`) and `CONTRIBUTING.md:70` explicitly instructs installing dev extras so these tests run. In the env CONTRIBUTING itself prescribes, collection is 1174, not 1167.

**Impact:** The one README line this PR freshly updated for accuracy is already wrong in the project's own canonical dev environment — the exact staleness class ISSUE-040 exists to sweep. It will also silently drift again on the next test addition (no guard exists, and none can reasonably exist — see fix).

**Suggested fix:** Regenerate the number from a dev-extras-synced env (`uv sync --extra dev` per CONTRIBUTING, expect 1174), or drop the hardcoded count entirely (e.g. "Tests passing") since it is unguardable. Per recalled review lessons (ISSUE-046/047): do **not** add a consistency test that shells out to pytest to verify the badge — recursive pytest spawn is the known anti-pattern; unguarded is acceptable, wrong is not.

---

### [Low] `"v0.1" not in readme` is a substring check that will spuriously fail on future legitimate `v0.10`+ mentions

**File:** `tests/test_readme_consistency.py:88`

**Evidence:** `"v0.1" in "since v0.10"` → `True` (verified). When the kit reaches v0.10/v0.11 and any README sentence legitimately references it, this test fails with the misleading message "stale v0.1 version pin still in README".

**Suggested fix:** `assert not re.search(r"v0\.1(?!\d)", readme)` — still catches `v0.1` and `v0.1.0` (both genuinely stale), permits `v0.10`+.

---

### [Low] `"33 agents" not in readme` guards a string that never existed; the historical stale string "old 33 per-agent pins" has no regression guard

**File:** `tests/test_readme_consistency.py:89`

**Evidence:** Verified: `"33 agents" in "33 engineering agents"` → False; `"33 agents" in "old 33 per-agent pins"` → False. The two 33-strings actually removed by this diff contain neither. "33 engineering agents" regressing IS caught (by both count tests, which fail on any count ≠ roster), but "the old 33 per-agent pins" (removed at README:515) regressing is caught by nothing. AC-literal is still satisfied (the AC's grep is the same substring), so this is hardening, not an AC gap.

**Suggested fix:** Replace with `assert not re.search(r"\b33\b[^\n]*\bagent", readme)` (or add `assert "33 per-agent" not in readme`).

---

### [Low] `.claude-kit/` retirement guard is phrasing-dependent — a rephrased submodule mention slips through

**File:** `tests/test_readme_consistency.py:97-107`

**Evidence:** The prose check requires the exact substring `` `.claude-kit/` submodule `` and the diagram check requires `".claude-kit/"` **and** `"# submodule"` on the same line. A regression written as `├── .claude-kit/  # git submodule` or "vendored `.claude-kit/` checkout" passes both. AC-1 defines legality as "zero matches or explicitly-live only", which suggests pinning occurrences rather than pattern-matching retirement phrasings.

**Suggested fix:** Invert the check — whitelist instead of blacklist: `offenders = [l for l in readme.splitlines() if ".claude-kit/" in l and "runtime state" not in l]; assert not offenders`. That makes ANY new `.claude-kit/` mention outside the one live line-714 context a failure.

---

### [Low] `test_readme_count_matches_effort_test_roster` passes vacuously if the README stops stating any count

**File:** `tests/test_readme_consistency.py:52-60`

**Evidence:** The `for count in _stated_counts(...)` loop has no `assert counts` guard (its sibling `test_stated_agent_counts_match_roster:44` has one). If a future rewrite drops all "N engineering agents" phrasings, this test passes with zero assertions executed. Suite-level signal survives via the sibling's guard, so this is single-test vacuity, not a suite blind spot.

**Suggested fix:** Add the same `assert counts, "README states no agent count"` guard (or derive `counts` once at module/fixture level for both tests).

---

### [Low] `/spec` Usage test: two theoretical brittleness/power nits

**File:** `tests/test_readme_consistency.py:110-120`

**Evidence:** (1) The section extractor `r"^## Usage\n(.*?)(?=^## )"` requires a subsequent `## ` heading; if "Usage" ever becomes the last h2, the test fails spuriously with "README has no ## Usage section". (2) `r"^### Spec\b"` matches a hypothetical `### Spec-Required gate` heading (verified: `\b` matches before `-`), so the assertion could pass without a real `/spec` entry — though the companion `^/spec\b` code-block assertion mostly closes that hole.

**Suggested fix:** (1) `(?=^## |\Z)`. (2) `r"^### Spec( |$|\s*—)"` or `r"^### Spec\b(?!-)"`.

---

### [Medium — PRE-EXISTING, record-only, not introduced by this branch] Three untouched agents-table Tools cells drift from frontmatter

**File:** `README.md` agents table (rows untouched by this diff)

**Evidence (per tech-lead verification, rows confirmed outside this diff):** `a11y-auditor` and `ui-reviewer` Tools cells omit `Bash`; `design-auditor` cell lists "Edit, Write" while frontmatter is only "Read, Glob, Grep". The new `test_agents_table_has_row_per_agent_file` checks row *names* only, so this column-level drift is invisible to the new tests.

**Disposition:** Explicitly out of scope per issue AC ("fixing PRE-EXISTING drift in untouched table rows"). Recorded for a follow-up issue: either fix the three cells or extend the lint test to compare Effort/Tools cells against frontmatter (which would have caught this class permanently).

---

## Minimality axis (over-engineering)

Scanned the full diff for delete/stdlib/native/yagni/shrink candidates. The test file is 120 lines for 6 AC-mandated tests, each with a distinct failure mode and helpful messages; helpers are minimal (`_readme`, `_stated_counts`, `_agent_table_names` each have ≥2 call sites or isolate one parsing concern). `test_readme_count_matches_effort_test_roster` is transitively redundant with the sibling count test (agents/ count == pin is already asserted by `test_agent_effort.py`), but the cross-check is explicitly required by AC-2 ("totals match tests/test_agent_effort.py roster pin") — explicitly-requested work is never a cut. README changes are targeted deletions/corrections, no added structure.

Lean already. Ship.

---

## Self-Review

1. **Severity re-assessment:** Badge finding held at Medium — it is a factual error in a line this PR changed, in the project's canonical env, on the exact axis (README accuracy) the issue targets; no code-correctness impact keeps it below High. All regex findings held at Low: none fails today, all are future-brittleness or regression-power hardening.
2. **False-positive check:** Badge — actively tried to refute by checking whether 1167 is correct for a lockfile-only env: it is (1168 collected − 1 runtime skip), but `pyproject.toml:16` + `CONTRIBUTING.md:70` establish dev-extras as the prescribed env, where the count is 1174; the refutation failed, finding stands (with the nuance stated). v0.10 collision, `\b`-before-hyphen, and vacuous-loop behaviors were all executed, not assumed.
3. **Blind-spot scan (code dimension):** Re-checked error-message quality (all asserts carry actionable messages — good), duplication (none), edge cases of the table walker (multi-table README, missing separator row, EOF table: all fail loudly, none silently), hermeticity (no network/subprocess/env/writes; pure repo-relative file reads — consistent with recalled lesson that these must stay pure-file lint tests), and factual accuracy of every changed README line (counts, tiers, auditor blurbs, /spec claims, pattern-(b) prose — all check out except the badge).
4. **AC verification:** AC-1 greps re-run clean (line-714 `.claude-kit/` exemption correctly implemented in the test); AC-2 table = 32 rows = 32 files = pin, enforced by tests; AC-3 `/spec` Usage entry present and format-consistent with sibling entries. All satisfied.
5. **Confidence: High** — every finding is backed by an executed probe or file read in this worktree, and the 6 new tests were run in isolation as permitted.
