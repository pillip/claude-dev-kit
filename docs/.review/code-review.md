# Code review — correctness / testing (degraded-path, dimension: code)

PR #73 (ISSUE-045) — TESTS-ONLY: `tests/test_validate_frontmatter.py`,
`tests/test_figma_verify_family.py`, `tests/fixtures/figma/design_data.json`.

## Verification performed

Every test was diffed against the real production function it exercises (not
trusted on its docstring). Result: **the tests pin real production behavior.**

- Browser/network seams are mocked at the correct delegation boundary and the
  pure logic under test runs UNMOCKED:
  - `vvd._check_playwright`, `vvd.visual_diff`, `vvd.visual_diff_against_renders`,
    `vvd.take_screenshots` (test_figma_verify_family.py:125-126,149-150,202,211).
  - `vcs._check_playwright`, `vcs.extract_computed_styles` (…:343-347).
  - The pure comparison/generation/extraction functions
    (`build_figma_reference`, `compare_computed_vs_figma`,
    `extract_figma_text_nodes`, `match_and_compare_per_node`,
    `extract_expected_elements`, `compare_structure`,
    `extract_layout_relationships`, `check_layout_in_source`, all of
    `generate_figma_css`) are called directly with real inputs. Confirmed by
    tracing each assertion to the code path that produces it.
- No hollow assertions. The threshold-capture tests assert a value chosen by the
  REAL `main()` branch logic, not by the mock: `captured["threshold"]` is set by
  `_fake_visual_diff`, but the VALUE (1.0 / 5.0) is produced by
  `verify_visual_diff.main()` (`args.threshold` default vs `max(args.threshold, 5.0)`
  at verify_visual_diff.py:566,571), so drift in that logic fails the test.
- No test spawns a real browser, network call, or recursive pytest. The single
  `subprocess.run` (test_figma_verify_family.py:89-95) launches a fresh
  interpreter that only `import`s the two browser modules and asserts playwright
  is absent from `sys.modules`; playwright imports in both scripts are lazy
  (inside `_check_playwright`/`take_screenshots`/`extract_computed_styles`), so
  this is a fast import-hygiene probe, not real work. Verified: full suite runs
  in ~0.34s, 76 passed.
- LESSON 4 (threshold predictability) satisfied in BOTH directions:
  1% is pinned twice — `DEFAULT_THRESHOLD == 1.0` (…:108) and the same-renderer
  `main()` path (…:133); 5% is pinned by the cross-renderer fallback (…:157).
  Changing either literal fails a test.
- LESSON 2 (oracle fidelity) satisfied: the frontmatter tests `import vf` and
  drive the REAL `_frontmatter`/`_quoted`/`_pattern_errors`/`main` oracle — no
  re-implemented parser. The ISSUE-035 "frontmatter not at byte 0" case
  (test_validate_frontmatter.py:29-33, 90-99) asserts the actual oracle result
  (`_frontmatter` returns `None`; `main()` returns 1 and emits "byte 0").
- Coverage AC ("each of six scripts non-zero") holds. Measured with
  yaml+Pillow present: validate_frontmatter 91%, generate_figma_css 77%,
  verify_layout 79%, verify_structural_match 75%, verify_computed_styles 68%,
  verify_visual_diff 51% (the 51% is the un-mocked real browser functions,
  correctly NOT exercised). All six non-zero in the minimal env too.

## Findings

### [Low] AA-aware `_pixel_diff` and the yaml gate branch are optional-dep-gated — coverage of the primary algorithms is silent and env-dependent

Evidence: this repo's own `.venv` (Python 3.11) has NEITHER PyYAML nor Pillow.
In that environment:
- `test_malformed_yaml_exits_one` and `test_missing_required_key_exits_one`
  (test_validate_frontmatter.py:101-125) skip via `pytest.importorskip("yaml")`,
  so `validate_frontmatter.main()`'s yaml-parse + missing-required-key branch
  (validate_frontmatter.py:81-93) is never exercised.
- `test_identical_images_report_zero_diff` / `test_different_images_report_nonzero_diff`
  (test_figma_verify_family.py:161-172) fall into `_pixel_diff`'s byte-level
  `except ImportError` fallback (verify_visual_diff.py:189-202); the AA-aware
  Pillow branch (verify_visual_diff.py:119-187) — the module's stated "sub-1%
  precision" core — goes unexercised. The assertions (`diff_percent == 0.0` /
  `> 0`, `total_pixels > 0`) deliberately hold in both branches, so this is NOT
  a hollow/flaky test, but the coverage of the load-bearing path is invisible
  and depends on optional deps.

Mitigation already present: the AA building blocks `_is_antialiased` and
`_color_distance_sq` ARE tested directly and unconditionally
(test_figma_verify_family.py:174-193), so the core AA math is genuinely covered;
only the `_pixel_diff` Pillow glue that orchestrates them is env-gated. Impact is
therefore limited — this is the "importorskip can hollow the coverage claim"
class (LESSON 3), but it does not breach the non-zero AC.

Fix: run the coverage-AC measurement in the canonical env with PyYAML+Pillow
installed (CI does, per each script's docstring) rather than the bare `.venv`;
optionally add a Pillow-gated test that asserts the AA branch classifies a
sharp-edge pixel as anti-aliased and thereby drops it from `diff_pixels`, so the
primary `_pixel_diff` path is pinned when the dep is available.

## Notes (no action required)

- `TestNoBrowserAtCollection.test_playwright_not_imported_at_collection`
  (…:75-77) depends on a module-level `sys.modules` snapshot taken at import
  time, which is cross-module-fragile if another suite imported playwright first.
  It fails CLOSED (loud failure, never a silent pass) and the subprocess test
  is the pollution-immune superset, so this is acceptable as a cheap guard.
- Tests are robust to the yaml/Pillow optional-dep variance: assertions hold in
  both the present-dep and absent-dep code paths, so there is no flakiness.
