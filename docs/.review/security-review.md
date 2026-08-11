# Security Review (degraded) — ISSUE-038 / PR #59

Runtime `/security-review` is not exposed; this is the degraded-path security pass.
Scope: the security checklist only (injection, authn/z, secrets, input validation,
deserialization, dependencies, XSS, misconfiguration). Code-quality and the
minimality axis are covered by separate invocations.

Files reviewed:
- `project/.claude/hooks/autotest.py` (+256/-81) — the PostToolUse hook now
  persists a module→test-file index and a debounce state under
  `.claude/run/autotest_cache.json`.
- `tests/test_autotest.py` (+206).

Threat-model baseline (from the task): the hook *already* discovers and executes
test files from the workspace by design, and can BLOCK the model's action on
failure. Findings below are scoped to NEW attack surface introduced by the cache.

## Surfaces explicitly checked and cleared

- **Deserialization (pickle vs json).** Cache is read with `json.load` only
  (`_load_cache`, line 255). No `pickle`/`eval`/`exec`/`yaml.load` anywhere in
  the diff. `_load_cache` is strictly typed/validated and fail-soft
  (`{{{ not json` → empty cache; test `test_corrupt_cache_rebuilds_and_exits_clean`).
  Not a finding.
- **Shell / command injection into argv.** All `subprocess.run` calls use list
  form; no `shell=True`. Test file paths become discrete argv elements, so a
  malicious *filename* cannot break out into a shell. (The one residual argv
  concern — leading-dash option injection via a *poisoned* cache entry — is
  folded into Finding 1.)
- **Secrets / file contents.** The cache stores only file *paths*, `mtime_ns`,
  `size`, and SHA-1 fingerprints. No file contents, tokens, or env values are
  persisted. (Absolute-path/username leakage is Finding 4.)
- **New env-var knobs / new subprocess-timeout instances.** None added.
  `DEBOUNCE_SECONDS`/`CACHE_VERSION` are module constants, not env knobs; no new
  `subprocess.run(timeout=...)` seam was introduced (the pre-existing 30s
  `TIMEOUT` is out of scope per the task).
- **Test code isolation.** Debounce tests monkeypatch at the correct seam
  (`autotest.run_python_test`), so no recursive real-pytest spawn; other tests
  run only trivial tempdir fixtures with test-controlled content. No unsafe
  execution of untrusted input in the tests.

---

### [Medium] Cache-derived related-test paths are executed unvalidated on warm hits (cache poisoning → out-of-tree file execution + pytest/vitest option injection)

**Evidence.** On a warm index hit, `find_related_python_tests` /
`find_related_js_tests` return `list(cached)` verbatim with no re-validation
(autotest.py:347-349, 384-386). `_run_source_branch` then appends every cached
`rf` to `selected` **without** the `os.path.isfile` guard that `primary` gets:

```python
if primary and os.path.isfile(primary):     # primary IS checked
    test_files.append(primary)
for rf in related:                            # rf (from cache) is NOT checked
    if rf not in test_files:
        test_files.append(rf)
...
for tf in selected:
    blocked = run_python_test(tf) if lang == "py" else run_js_test(tf)
```
`run_python_test` passes `tf` straight into `subprocess.run([pytest, tf, "-x", ...])`
(autotest.py:147-152). Pytest *imports* the file it is pointed at, so an arbitrary
path executes module-level code.

The warm-hit path is fully attacker-steerable because the stored `fingerprint`
is itself in the attacker-writable cache: the fingerprint is a SHA-1 of
`(relpath, mtime_ns, size)` (`_stat_fingerprint`), all computable, so a poisoned
cache can set `index["fingerprint"]` to match the *current* tree and thereby
skip the scan entirely while returning arbitrary `modules` entries. Those entries
can (a) point **outside** `tests/` and outside the project root (path traversal
past what the scan would ever select), (b) skip the `test_`/`.test.` name
predicate, and (c) begin with `-` (e.g. `"-pattacker_plugin"`, `"-c/tmp/evil.ini"`,
`"--pdb"`), which pytest/vitest interpret as **options/plugins**, not paths.

Precondition is local write to `.claude/run/autotest_cache.json`, which is
roughly baseline-equivalent to dropping a `tests/test_x.py` — hence **Medium**,
not High. The genuine escalation over baseline is: reaching files *outside* the
workspace, bypassing the name filter, and injecting collector options/plugins.

**Fix.** Treat cached paths as untrusted on read. In `_run_source_branch` (and/or
at the point `list(cached)` is returned), drop any entry that is not an existing
regular file, not under `project_root` (py: under `project_root/tests`), does not
match the test-name predicate (`_is_python_test_file` / `_is_js_test_file`), or
starts with `-`. Apply the same `os.path.isfile` guard to `rf` that `primary`
already gets. This keeps warm-hit performance while making a poisoned cache no
more powerful than the baseline scan.

### [Low] Debounce trusts an attacker-writable "pass" entry to suppress the block-on-failure safety signal

**Evidence.** `_run_source_branch` returns `None` (no block, tests skipped) when a
cached debounce entry has `result == "pass"`, a matching `test_set`, and
`last_run` within `DEBOUNCE_SECONDS` (autotest.py:562-571). The cache is
fail-soft and writable anywhere in the workspace, so a pre-seeded `"pass"` entry
— keyed on `lang:abspath(source)` with a forged matching `test_set` (again just
`(path, mtime_ns, size)` SHA-1 over the unchanged test files) and a recent
`last_run` — silences a genuine failing run for up to 30s after a source edit
that breaks tests but doesn't touch the test files. Impact is bounded: this is
the advisory autotest convenience hook, not an authoritative gate
(`verify_gates.py`/CI are elsewhere), the window is 30s, and it needs local
cache write.

**Fix.** Acceptable within the stated threat model, but treat the debounce record
as advisory-only: document that the autotest hook is not a security control, and
consider not letting a *stored* `pass` suppress a run across separate hook
invocations (e.g. keep debounce in memory for a single event, or namespace/sign
the cache) so on-disk tampering cannot mute a real failure.

### [Low] Non-atomic, symlink-following cache write can clobber a pre-planted symlink target

**Evidence.** `_save_cache` does `os.makedirs(dirname, exist_ok=True)` then
`open(path, "w")` with no `O_NOFOLLOW` and no atomic temp-then-rename
(autotest.py:277-279). If `.claude/run/autotest_cache.json` (or `.claude/run/`)
is a symlink an attacker planted in the workspace, the hook overwrites the link
target with cache JSON. Content is attacker-uncontrolled JSON, so this is
destructive (file clobber) rather than an injection vector, and requires the
attacker to plant the link first. The non-atomic write can also corrupt the
cache under concurrent hook invocations, though `_load_cache` fails soft on that.

**Fix.** Write to a temp file in the same directory and `os.replace()` into place
(atomic), and refuse to follow a symlink at the final path (e.g. `os.open` with
`O_NOFOLLOW`, or reject if `os.path.islink(path)`).

### [Low] Cache persists absolute paths (OS username / project layout) and is not covered by .gitignore

**Evidence.** `python_index`/`js_index` module lists and every `debounce` key
store `os.path.abspath(...)` values such as `/Users/<user>/...`
(autotest.py:561, 356, 397). `git check-ignore .claude/run/autotest_cache.json`
returns "not ignored" (exit 1), and the repo `.gitignore` has no `.claude/run/`
entry — even though `docs/telemetry_schema.md` asserts `.claude/run/` is
gitignored. If a consumer commits the cache it leaks local usernames and internal
test structure. No secrets or file contents are exposed, so severity is Low.

**Fix.** Add `.claude/run/` to the kit's shipped/template `.gitignore` (and this
repo's), and/or store project-relative paths in the cache instead of absolute
ones.

---

## Self-Review

1. **Severity re-assessment.** Finding 1 yields code execution but its precondition
   (local write to the cache) is ~equivalent to the hook's existing baseline
   capability, so it is capped at Medium; the delta over baseline (out-of-tree
   files, name-filter bypass, option injection, scan bypass via forged fingerprint)
   is real and justifies Medium over Low. Findings 2–4 are bounded, local-precondition,
   non-injection issues → Low.
2. **False-positive check.** Finding 1: code-traced — `rf` is appended without the
   `os.path.isfile` guard `primary` gets, and reaches `subprocess` argv (confirmed
   autotest.py:549-551, 575-576, 147-152). Finding 4: confirmed via `git check-ignore`
   exit 1. Finding 3: confirmed `open(path,"w")` with no atomic/no-follow. Finding 2:
   confirmed `result == "pass"` gate. No FPs identified.
3. **Blind-spot scan.** Injection (argv list-form — safe; option-injection folded
   into F1), deserialization (json only — cleared), secrets (no contents stored —
   cleared), dependencies (none added), authn/z & XSS (n/a for a local FS hook) all
   re-examined; nothing further surfaced.
4. **AC note.** Security dimension only; the cache/debounce behave as designed
   (fail-soft, failures never debounced), which the tests demonstrate.
5. **Confidence: Medium-High.** The hook is small and fully read; the only real
   judgment call is the Medium-vs-Low calibration on Finding 1, which I anchored to
   the local-write precondition and the "new surface beyond baseline" rule.
