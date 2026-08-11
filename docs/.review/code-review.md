# Code Review (degraded) — ISSUE-037 / PR #58

Scope: `git diff origin/main...HEAD` (b0d8bb3...7b552e0). Files: `project/.claude/hooks/session_start.py` (+29/-13), `tests/test_lifecycle_hooks.py` (+58). All 9 tests in `tests/test_lifecycle_hooks.py` pass (`uv run pytest -q`, 0.31s). RED validity of TC-037a verified empirically: the pre-fix hook (origin/main) fails all three key assertions (pinned regex leak, pinned-root substring leak, missing "Kit Script Root").

Fix approach matches spec candidate (a): under plugin install the hook emits a `<kit-root>` placeholder that defers resolution to the Kit Script Root preamble section, which is verifiably present in every generated skill (`tests/test_plugin_root_resolution.py` enforces it) and is substituted at load time with the currently installed version's path. Standalone keeps the concrete absolute path. Never-fail contract preserved (no new exception paths; `run_quiet` still swallows; plugin wiring wraps with `|| true`). No new `timeout=` literals or env-var knobs introduced (recalled lessons 1–2: clean).

### [Medium] TC-037b standalone regression guard can hollow-pass via silent real-repo fallback

**Evidence:** `tests/test_lifecycle_hooks.py:206-209`:

```python
match = re.search(r"python3 (\S*contributor_report\.py)", out)
assert match, ...
assert Path(match.group(1)).is_file(), ...
```

Nothing pins the matched path to the fixture root. If the fixture ever stops resolving (candidate-order change in `find_kit_root`, `HOOK_ROOT` plumbing regression, fixture path drift), the hook silently falls back to `Path(__file__).resolve().parents[3]` — the real kit repo. Empirically replayed on this machine (real `kit_config.py get contributor_mode` → `true`, the typical kit-contributor config): with the fixture scripts absent, the hook still prints `CONTRIBUTOR MODE: ON` with the real repo's `contributor_report.py`, which exists → every assertion in TC-037b passes while testing the wrong root. This is the exact tmp-fixture/real-repo-fallback pattern from the ISSUE-047 review lesson. (TC-037a is NOT affected: in both fallback outcomes its asserts fail loudly — verified.)

**Fix:** Replace the `is_file()` assert with an equality pin that subsumes it:
`assert match.group(1) == str(root / "scripts" / "contributor_report.py")`.

### [Low] Own-location fallback mis-flags a plugin cache dir as non-pinned

**Evidence:** `project/.claude/hooks/session_start.py:33`:

```python
candidates.append((Path(__file__).resolve().parents[3], False))
```

Under a plugin install the hook file itself lives inside the version-pinned cache dir, so `parents[3]` IS the pinned root — but it is hardcoded `from_plugin=False`. If this candidate ever wins while the file runs from the cache (env stripped, or manual/non-standard hook wiring pointing at the cache copy), the pinned absolute path gets printed again — resurrecting the exact ISSUE-037 bug through the back door. No exploit path via the shipped wiring: `hooks/hooks.json` invokes the hook as `python3 "$CLAUDE_PLUGIN_ROOT/..."`, so the env var must be set for the command to resolve at all and is inherited by the subprocess — hence Low, defense-in-depth only.

**Fix:** Backstop by path shape rather than trusting only the source: e.g. `from_plugin = from_plugin or bool(re.search(r"[\\/]cache[\\/].+[\\/]\d+\.\d+\.\d+$", str(c)))` inside the resolution loop (or flag the `parents[3]` candidate pinned when it matches that pattern).

### [Low] Standalone instruction prints an unquoted absolute path — breaks on paths with spaces

**Evidence:** `project/.claude/hooks/session_start.py:77` + `:83`: `report = str(kit / "scripts" / "contributor_report.py")` interpolated as `python3 {report} --skill ...`. A standalone checkout under a directory with spaces (e.g. `~/My Projects/`) yields a non-executable instructed command. Pre-existing behavior, but this diff rewrites the line. (Related: TC-037b's `\S*` capture group has the same whitespace assumption — the equality-pin fix above at least turns it into a loud failure.)

**Fix:** Quote the path in the printed instruction: `f'python3 "{report}" --skill ...'` (and relax the TC-037b regex to accept the quotes).

## AC Verification

- **AC1** (no `/cache/…/<semver>/` segment in contributor-mode output under pinned `CLAUDE_PLUGIN_ROOT`): **PASS** — plugin branch emits only the `<kit-root>` placeholder; TC-037a asserts both the regex and the direct pinned-root substring (the substring assert also covers semver formats the regex misses, e.g. `0.2.0-rc1`).
- **AC2** (instruction resolves current version after update/GC): **PASS by construction** — resolution is deferred to the Kit Script Root shown in the invoking skill's preamble, substituted at load time with the currently installed root; the report is only ever filed mid-kit-skill-workflow, when such a preamble is guaranteed in context. Not end-to-end executable in a unit test; TC-037a's `"Kit Script Root" in out` assert is the proxy, consistent with the tests the spec promised.
- **AC3** (standalone contributor mode still yields a working invocation): **PASS** — non-plugin branch behavior unchanged (concrete absolute path); TC-037b asserts the printed path exists on disk (with the hollow-fallback caveat in the Medium finding above).

## Over-Engineering (minimality axis)

Lean already. Ship.
