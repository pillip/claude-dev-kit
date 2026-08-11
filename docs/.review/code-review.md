# Code Review (degraded) — ISSUE-038 / PR #59

Scope: `git diff origin/main...HEAD` @ 1401f58 — `project/.claude/hooks/autotest.py` (+256/−81), `tests/test_autotest.py` (+206). Suite run in worktree: **31 passed in 2.69s** (no spawn-leak signal). Reviewed dimension: code (+ minimality folded in). Security reviewed separately.

### [Medium] Non-atomic, lock-free cache writes: a stale "pass" can overwrite a fresh "fail" debounce entry under concurrent hook processes

**Evidence:** `project/.claude/hooks/autotest.py:273-281` — `_save_cache` truncate-writes the whole file (`open(path, "w")` + `json.dump`), no temp-file/`os.replace`, no locking. `project/.claude/hooks/autotest.py:585-592` — the outcome is recorded with `"last_run": time.time()` taken *after* the runs complete (runs can take minutes: up to 5×30s unit + 2×60s E2E).

**Impact:** Most race outcomes are fail-safe: a torn/interleaved write produces invalid JSON, which `_load_cache` rebuilds (re-run, never skip); a lost index entry just re-walks. But one interleaving is not: process A starts on source state S0 (tests pass), process B starts after an edit introduces a bug and records `"fail"`, then slow A finishes and overwrites the entry with `"pass"` and a fresh `last_run`. The next edit within 30s with unchanged test files is skipped — a failure debounced into silence, the exact AC-4 hazard. Requires two concurrent hook processes on the same file in the same project root (PostToolUse hooks serialize per agent, and kit worktrees have separate cache files, so this is narrow — hence Medium, not High).

**Fix:** (1) Write atomically: dump to `path + ".tmp"` then `os.replace` (also eliminates the torn-write/rebuild churn). (2) Record `last_run` as the run *start* time, so the skip window is measured from when the tested state was captured. (3) When writing a `"pass"`, don't clobber an existing entry whose `last_run` is newer and whose result is `"fail"`.

### [Medium] Index caches absolute test paths but the fingerprint is relpath-based — `mv`/clone of the project keeps a "valid" fingerprint pointing at the old tree

**Evidence:** `project/.claude/hooks/autotest.py:304` — fingerprint entries use `os.path.relpath(entry.path, scan_root)`; `project/.claude/hooks/autotest.py:356-364` and `397-405` — the module index stores absolute `test_path` values; `project/.claude/hooks/autotest.py:575-576` — selected files are executed with no existence check.

**Impact:** `mv project/ project2/` (or an APFS clonefile / `cp -c` / ns-preserving rsync copy) preserves mtimes exactly. The relocated cache's relpath fingerprint still matches, so the warm path returns the *old* absolute paths. If the old tree is gone: pytest runs a nonexistent path → nonzero exit → false `"Test failed"` block on every edit until a test file's mtime changes. If the old tree still exists (copy case): the hook silently runs the *original* tree's tests against stale code — a wrong-tree pass/fail with no signal. Workaround exists (delete `.claude/run/autotest_cache.json`), so Medium.

**Fix:** Store module index entries as paths relative to `project_root` and join on read; or on a warm hit, verify each cached path with `os.path.isfile` and fall through to a rebuild if any is missing.

### [Low] Fingerprint and discovery use mismatched predicates: hidden-dir JS tests and symlinked test files are discoverable but never invalidate the index

**Evidence:** `project/.claude/hooks/autotest.py:234-238` — `_skip_js_scan_dir` excludes `node_modules` *and all hidden dirs* from the JS fingerprint; `project/.claude/hooks/autotest.py:389-393` — the discovery `os.walk` skips only `node_modules` (and doesn't prune `dirs`, so it still descends the node_modules tree — pre-existing). Also `project/.claude/hooks/autotest.py:301` — `entry.is_file(follow_symlinks=False)` excludes symlinked test files from the fingerprint, while `os.walk` + `open()` includes them in discovery (both Python and JS paths).

**Impact:** A test file added/changed in a hidden dir (JS) or reached via symlink is invisible to the fingerprint: adding one never refreshes the index (AC-2 corner), and removing one leaves it cached. Rare layouts; degraded discovery only, debounce is unaffected (`_test_set_hash` stats the selected files directly). Low.

**Fix:** Use the same predicate on both sides: prune the discovery walk with `_skip_js_scan_dir` (via `dirs[:] = [...]`, which also stops descending node_modules) and either include symlinked files in the fingerprint or exclude them from discovery.

### [Low] Warm-path cache entries not validated to string paths — valid-JSON garbage can crash the hook, denting the fail-soft contract

**Evidence:** `project/.claude/hooks/autotest.py:347-349` / `384-386` — `if isinstance(cached, list): return list(cached)` trusts element types. `_load_cache` (`:258-269`) validates the outer shape only. A hand-edited cache like `{"modules": {"user": [1]}}` passes validation; the int then reaches `subprocess.run([pytest_cmd, 1, ...])` → uncaught `TypeError` → traceback, exit 1.

**Impact:** The stated contract is "corrupt cache → rebuild, never crash". Exit 1 is non-blocking in Claude Code (stderr noise, edit proceeds), and the trigger requires a hand-corrupted-but-valid-JSON cache, so no real exploit path — Low.

**Fix:** Treat a cached value as a hit only if `all(isinstance(x, str) for x in cached)` (adding an `os.path.isfile` check here also mitigates the stale-abs-path finding above); otherwise fall through to rebuild.

### [Low] `DEBOUNCE_SECONDS` is a new hard-coded time knob: no env override, no doc line

**Evidence:** `project/.claude/hooks/autotest.py:20` — `DEBOUNCE_SECONDS = 30.0`. No mention in the module docstring, README, or `docs/troubleshooting.md` (grep confirms zero user-facing doc hits).

**Impact:** Kit lesson (ISSUE-046/047): hard-coded timing constants introduced without env-configurability + docs recur as breakage. This one cannot break gates (it is not a subprocess timeout, and mis-sizing only delays or repeats *passing* runs — failures are exempt), so Low. Note: the diff introduces **no new subprocess `timeout=` literals**; the pre-existing 30s/60s caps remain the known logged planner candidate, out of this issue's scope.

**Fix:** `DEBOUNCE_SECONDS = float(os.environ.get("AUTOTEST_DEBOUNCE_SECONDS", "30"))`, one line in the module docstring, one line in `docs/troubleshooting.md` (0 = disable).

### [Low] Debounce map grows without pruning; full cache is rewritten on every event

**Evidence:** `project/.claude/hooks/autotest.py:587-592` — `cache["debounce"][key] = {...}` keyed by absolute source path; entries for deleted/renamed files persist forever, and every event round-trips the entire JSON (both indexes + all debounce entries).

**Impact:** Bounded by source-file count, so perf/bloat only. Low.

**Fix:** On save, drop debounce entries with `last_run` older than a few windows (one-line dict comprehension).

### [Low] Coverage gap: debounce window *expiry* is untested

**Evidence:** `tests/test_autotest.py:571-595` asserts the within-window skip; no test asserts that an identical passing pair re-runs once `DEBOUNCE_SECONDS` elapses.

**Impact:** A regression to an unbounded window (flipped comparison, wrong `last_run` type) would make the hook silently stop re-testing a passing module on later source edits — and no current test would fail. The main safety property (failures re-run) *is* tested, so Low.

**Fix:** Monkeypatch `autotest.time.time` (or set `autotest.DEBOUNCE_SECONDS = 0.0`) and assert the second `handle_event` re-runs.

### [Low] Corrupt-cache test cannot detect a late hook crash — `run_hook` discards returncode/stderr

**Evidence:** `tests/test_autotest.py:11-21` — `run_hook` returns parsed stdout or `None`; `tests/test_autotest.py:542-547` (`test_corrupt_cache_rebuilds_and_exits_clean`) asserts `out is None` and that the cache file is valid JSON. A crash *after* `find_related_python_tests` saves the rebuilt cache (e.g. in the debounce block) produces empty stdout + traceback on stderr + exit 1 — and the test still passes. The "exits clean" claim in the name is not asserted.

**Impact:** Hollow-assertion risk for exactly the fail-soft contract this test exists to pin. Low (the crash-on-load case *is* caught via the still-corrupt cache file).

**Fix:** Have `run_hook` (or this test locally) surface `result.returncode`/`stderr` and assert `returncode == 0` and no traceback.

## Over-Engineering (minimality axis)

- tests/test_autotest.py:545-560: shrink — `_load` and `_make_python_project` duplicated verbatim between `TestIndexCache` and `TestDebounce` → hoist both to module-level helpers (or a fixture) shared by the two classes (~22 lines).
- tests/test_autotest.py:449-452: delete — per-call `sys.path.insert` + `importlib.reload`; the module holds no mutable global state the tests reset, and repeated inserts accumulate in `sys.path` → single module-level import (folds into the shared helper above) (~4 lines).
- Considered, rejected: the hand-rolled recursive `os.scandir` in `_stat_fingerprint` looks like an `os.walk` reinvention, but AC-1's letter (zero `os.walk` calls on the warm path, asserted by monkeypatch) mandates it — not a cut. `CACHE_VERSION` is cheap forward-compat for an on-disk format — not yagni.

Net removable lines: ~25 (all test-side).

## AC verification

- **AC-1 (warm index, no walk): PASS.** Warm hit is `_load_cache` + stat-only scandir fingerprint + cached list; zero `os.walk` calls asserted for both Python and JS paths (TC-038a). Stat scan on the hot path is explicitly allowed by the spec's "tests-dir mtime scan" note.
- **AC-2 (invalidation): PASS** (with the hidden-dir/symlink corner, Low). Any add/modify/delete of a fingerprint-visible test file changes `(relpath, mtime_ns, size)` → immediate reindex; TC-038b asserts discovery and on-disk persistence.
- **AC-3 (debounce skip): PASS.** Same `(lang:abspath, test-set hash)` with `result == "pass"` inside 30s skips; TC-038c mocks the module-global runner seam with a call-count guard (correct seam per kit lesson).
- **AC-4 (failure never debounced): PASS.** The skip path requires `result == "pass"`; TC-038d asserts a second block and an increased run count. Residual: the narrow cross-process pass-over-fail overwrite (Medium finding above).

Behavior knobs preserved: `MAX_RELATED_TESTS = 5` (autotest.py:197,555), `TIMEOUT = 30` / `E2E_TIMEOUT = 60` untouched, block-dict shape and unit-then-E2E ordering unchanged; caps are applied *before* the debounce hash so the debounce covers exactly what runs.

Confidence: **High** — full diff + full file read, suite run green (2.69s), mock seams and tmp_path containment verified against recalled lessons, each finding actively falsification-checked (e.g. `mv` preserves mtime_ns, making the stale-abs-path fingerprint match real; all other write races degrade to safe re-runs).
