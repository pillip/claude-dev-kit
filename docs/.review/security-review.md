# Security review (degraded-path, dimension: security)

PR #73 (ISSUE-045) — TESTS-ONLY. Scope: risk introduced by the TEST code itself
(argv injection, path traversal, untrusted input, out-of-tree execution).

## Verification performed

- The only `subprocess.run` (test_figma_verify_family.py:89-95) uses a fixed
  argv list `[sys.executable, "-c", code]` — no `shell=True`, and `code` is a
  hardcoded literal with no interpolation of dynamic/untrusted values. `cwd` is
  derived from `__file__` (`Path(__file__).resolve().parents[1]`), a trusted
  in-tree path. No injection surface, no out-of-tree file execution.
- No network egress from the tests: `_check_playwright` and the browser
  extraction functions are mocked to constants, and every `main()` invocation
  supplies `--implementation`/`--url` so the real `_check_dev_server`
  (localhost probes) and the pip/playwright auto-install path are never reached.
- No path traversal / untrusted input: all filesystem paths are `tmp_path`
  fixtures or the `__file__`-relative `FIXTURE`. Writes (`generate_css_file`,
  skill fixture writers) stay under `tmp_path`.
- No secrets, credentials, or hardcoded tokens in the test code or the
  `design_data.json` fixture (fixture holds only synthetic colors/text nodes).
- No `eval`/`exec` of untrusted data. The `_EXTRACT_JS` browser payload is never
  executed by tests (the extraction seam is mocked).

## Findings

No findings.
