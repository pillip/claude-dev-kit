# Security Review (degraded) — ISSUE-037 / PR #58

Scope: `project/.claude/hooks/session_start.py` (+29/-13), `tests/test_lifecycle_hooks.py` (+58), diff `origin/main...HEAD` @ 7b552e0. The hook's stdout is injected into the model's session context, so it was reviewed as an instruction-injection surface.

Positive note (context for severity): the new plugin-branch instruction (session_start.py:73-87) is a **constant string** — no env var, file content, or path segment is interpolated into the injected text on the plugin path. This is a strict reduction of attacker-influenceable data in the injection surface versus the old pinned absolute path.

---

### [Medium] `<kit-root>` deferred resolution can degrade into executing an attacker-planted relative `scripts/contributor_report.py` without a permission prompt

**Evidence**: `project/.claude/hooks/session_start.py:73-75` — the injected instruction defers path resolution to the model: `report = "<kit-root>/scripts/contributor_report.py"` with `<kit-root> = "the Kit Script Root absolute path shown in the preamble of any active kit skill"`. Two weaknesses in that binding:

1. "**any** active kit skill" — the model must judge which in-context skills are kit skills; a project-local skill (`.claude/skills/` in an untrusted repo) can impersonate a kit preamble and present a fake `### Kit Script Root` pointing at an attacker directory.
2. No failure-mode guidance: if the model cannot resolve an absolute root, the natural fallback (also suggested by the genuine preamble's standalone-layout branch, `scripts/preambles.py:44` "run commands as written") is the relative form `python3 scripts/contributor_report.py`. Kit skills pre-allowlist exactly that shape — `skills/ship/SKILL.md:5` frontmatter includes `Bash(python3 scripts/*)` — so in an untrusted project cwd that planted `scripts/contributor_report.py`, the command executes attacker code **with no permission prompt**.

Preconditions (why Medium, not High): contributor mode ON (kit-developer setting, small population), plugin install, untrusted repo with a planted file, and the model taking the impersonated/relative resolution path instead of the genuine preamble's absolute path. Uncertainty flag: exploit probability is model-behavior-dependent; the channel itself is verified.

**Fix**: Tighten the injected instruction: (a) bind resolution to "the Kit Script Root shown in the preamble of the kit skill **you are currently executing** (the one whose step you are rating)", not "any active kit skill"; (b) add an explicit safe failure mode: "if you cannot resolve an absolute Kit Script Root, skip filing the report — never invoke `scripts/contributor_report.py` via a relative path." Alternative structural fix: have the hook print the stable, non-pinned cache **parent** dir (strip the trailing version segment from `CLAUDE_PLUGIN_ROOT`) plus "use the highest installed version directory" — keeps resolution deterministic and out of free-text preamble scanning entirely.

---

### [Medium] (pre-existing in touched code) Plugin-wired hook falls back to executing project-directory scripts when the plugin-root probe fails

**Evidence**: `project/.claude/hooks/session_start.py:29-36` — candidate order is `CLAUDE_PLUGIN_ROOT` → `HOOK_ROOT`/`CLAUDE_PROJECT_DIR` → `parents[3]`, and `hooks/hooks.json` (SessionStart) invokes the hook with `HOOK_ROOT="$CLAUDE_PROJECT_DIR"`. If the plugin cache root exists (the `[ -f … ]` guard passed, so the hook file is present) but `scripts/kit_update_check.py` is missing there (partial cache GC — the exact degradation class ISSUE-037 documents — or a future repackaging), the hook resolves the kit root to the **untrusted project directory** and then, at `session_start.py:60-66`, executes `<project>/scripts/kit_update_check.py` and `<project>/scripts/kit_config.py` with the user's Python at SessionStart — hooks run with no permission gate — and injects the first script's stdout **verbatim** into session context (line 61-62), an unfiltered instruction-injection channel on top of the direct code execution.

This PR did not introduce the fallback order (it only threaded `from_plugin` through), but the changed hunk contains it and the PR's own premise (cache dirs get GC'd) makes the trigger state credible. Medium because the required partial state (hook file survives, scripts/ gone) is an edge case; the consequence when it fires is arbitrary code execution.

**Fix**: In `find_kit_root`, when `CLAUDE_PLUGIN_ROOT` is set (i.e., running as the plugin's hook), do not fall through to the project-dir candidate — return `None` if the plugin root fails the probe. The `HOOK_ROOT` candidate remains correct for the snippet wiring (copied install), where the project genuinely is the trust root. Cheap change, no functionality loss: healthy plugin installs always pass the plugin-root probe.

---

### [Low] Script path unquoted in the injected command template

**Evidence**: `project/.claude/hooks/session_start.py:83` — `f"workflow): python3 {report} --skill <name> …"` prints the path unquoted in both branches; the plugin-branch template likewise shows `python3 <kit-root>/scripts/contributor_report.py` unquoted, and the substituted marketplace-cache path can contain spaces (e.g., a home directory with a space). A model executing the instruction verbatim produces a mis-tokenized command. No practical attacker control over the path (the kit-root path is chosen by the user/installer, not by repo content), hence Low — hardening only.

**Fix**: Quote the path in the template: `python3 "<kit-root>/scripts/contributor_report.py"` / `python3 "{report}"`.

---

## Surfaces checked, no findings

- **Secrets leakage into session context**: none; the plugin branch prints only constant text and the diff removes the cache path (which encodes username) from plugin-mode output. Standalone branch prints a local absolute path into the local session only — not exfiltration.
- **Injected env/file content (plugin branch)**: constant string; nothing interpolated.
- **Subprocess safety**: list argv, no `shell=True`, `capture_output`, `timeout=20` — unchanged by diff; no new invocation added.
- **stdin handling**: `json.load(sys.stdin)` drained and unused; exceptions swallowed by design; payload cannot influence output.
- **Never-fail contract**: the diff adds no new exception masking; `run_quiet`'s swallow-all is pre-existing and intentional (never block session start). The Medium fallback finding above is the only place the contract intersects a security-relevant state, and it is reported there.
- **New test code**: executes only literal stub scripts written by the tests themselves into `tempfile.TemporaryDirectory()`; `_run_session_start` pops `CLAUDE_PLUGIN_ROOT` and pins `HOOK_ROOT` to the temp root, so the subprocess cannot resolve the developer's real environment as the kit root in the paths under test. No untrusted input executed; assertions (`VERSION_PINNED_CACHE_RE`, `str(pinned_root) not in out`, on-disk existence check in TC-037b) genuinely enforce the AC.
- **Dependencies**: none added.

## Confidence

**Medium.** Evidence for each finding is verified in the wiring configs and source (not inferred), but both Medium findings depend on conditions I cannot measure from the diff alone: F1 on probabilistic model resolution behavior, F2 on a partial cache-GC state whose real-world frequency is unknown. Those uncertainties are flagged inline; severities already discount for them.
