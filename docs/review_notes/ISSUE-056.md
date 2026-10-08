# Review Notes — PR #101

## Code Review
_Source: reviewer-degraded_

- **[Medium] SPEC contract 3 deviation: flex-calc-width tell evaded by multi-line CSS declaration (no whitespace normalization in ai-tell sweep)**
  Evidence: scripts/verify_design_sweeps.py:325-327 — line-by-line sweep (`for lineno, line in enumerate(stripped.splitlines(), 1)`). SPEC-056 contract 3 mandates 'whitespace normalization for CSS mechanics patterns' (uiux SKILL.md: 'normalize spaces first'). Probe-confirmed: both `width:\n    calc(33% - 1rem);` and `width: calc(\n      33% - 1rem);` exit 0 (evaded); the pattern uses `\s*`/`[^)]*` which would match across lines, but splitlines() precludes it. Only the single-line form is caught and tested.
  Fix: For multi-line-capable tells (flex-calc-width is the only current one), search the comment-stripped FULL text, deriving lineno via `stripped.count('\n', 0, m.start()) + 1` (comment blanking preserves newlines, so line numbers stay exact). Add a mutation test with the wrapped form. Address before or with ISSUE-057 wiring.

- **[Medium] SPEC contract 5 deviation: `all --json` output is not machine-readable (concatenated JSON docs, plain-text line interleaved) and is untested**
  Evidence: scripts/verify_design_sweeps.py:418-425 — `all` calls each run_* which each print their own JSON object; with --class omitted a plain-text SKIPPED line is interleaved between JSON docs. Probe-confirmed: json.loads fails with 'Extra data: line 6 column 1'. SPEC contract 5: '--json emits a machine-readable violation list' — and `all` is the designated ISSUE-057 invocation. No `all --json` test exists.
  Fix: In `all` mode, have run_* return their payload dicts and emit one wrapper document, e.g. {"status": ..., "sweeps": [...]} with the signature-move skip as a payload entry. Add a TestJsonOutput case that json.loads the full `all --json` output. Address before or with ISSUE-057 wiring.

- **[Medium] `all` without --class exits 0 with signature-move unenforced — unrecorded skip recreates the skipped-self-check hole for ISSUE-057 wiring**
  Evidence: scripts/verify_design_sweeps.py:423-424 — `print("signature-move: SKIPPED (no --class provided)")` then aggregate returns 0 if the other two pass (probe-confirmed exit 0). SPEC-056 sanctions exactly one skip path (contract 1: literal_quote's recorded marker); exit-0 for an unenforced signature-move is script-invented. The skip is loud only in text mode; in --json mode it is a stray text line a JSON consumer never surfaces. If ISSUE-057 wiring fails to extract the class name, the aggregate gate silently passes — the exact failure mode this issue exists to eliminate.
  Fix: Require an explicit `--skip-signature-move` flag for exit 0 (omission of --class on `all` → exit 2 usage error), or at minimum include {"sweep": "signature-move", "status": "skip"} in the JSON payload. Update test_all_without_class_skips_signature_move_loudly accordingly. Address before or with ISSUE-057 wiring.

- **[Low] QUOTE_FIELD truncates a literal_quote containing a double-quote, silently degrading the verbatim check to a prefix check**
  Evidence: scripts/verify_design_sweeps.py:80 — `[^"]+` capture. Probe: `literal_quote: "it says "reconciled" right there"` captures only 'it says ' (false-fail with a confusing message in the common case; false-PASS if the prefix coincidentally appears). Bounded realism: the field is defined as 'a specific word, number, or glyph', so embedded quotes are off-format — but the failure is silent and misleading.
  Fix: After each match, check the remainder of the line for a stray '"' and exit 2 with a 'embedded double-quote not supported by the field format' message, so the off-format case fails loudly as a usage error.

- **[Low] literal-quote has no fence guard: a fenced format example in the philosophy doc is enforced as a real quote (ISSUE-042 lesson class)**
  Evidence: scripts/verify_design_sweeps.py:92 — findall scans the whole file. Probe: appending a fenced '- literal_quote: "<exact string>" — template example' block yields exit 1 naming the placeholder. The prose oracle reads the field from Reference Anchors; the ISSUE-042 lesson is exactly that hand-rolled parsers mirroring an oracle must handle fence edge cases. False-fail direction (fails closed), so Low.
  Fix: Blank fenced code blocks (```...``` with newline-preserving _blank) before the QUOTE_FIELD scan; add a fenced-example test.

- **[Low] Python hollow heuristic: a bare name containing 'mock' counts as an assertion mechanism — confirmed false pass (record-only, contract-compliant)**
  Evidence: scripts/verify_hollow_tests.py — `'mock' in node.id.lower()` on any ast.Name. Probe: `def test_loads_data(): mock_data = {'a': 1}; print(mock_data)` passes. Mirrors the binding SPEC contract 4 ('a mock reference') and the testgen prose grep, so contract-compliant — recorded because testgen wiring (ISSUE-057/060) will treat this exit 0 as 'not hollow'.
  Fix: Record-only now. Future tightening when the contract is next revised: count 'mock' names/attributes only when they participate in a Call or an assert_* attribute access.

- **[Low] JS segment heuristic: expect() in a helper between blocks masks a hollow test (false pass); it(/test( in string literals creates phantom boundaries (false positive)**
  Evidence: scripts/verify_hollow_tests.py — segment runs from each match to the NEXT match start. Probe-confirmed both directions: (a) hollow it() followed by a helper containing expect() before the next it( → exit 0; (b) `const msg = 'wrap in it("name", fn)'` inside a real asserting test → exit 1 flagging the real test. SPEC explicitly accepts the segment heuristic; the prose oracle is FILE-level, so the heuristic is strictly stronger on (a); (b) is a new false-positive class, and false-positive rate is the SPEC's stated rollback trigger.
  Fix: Record-only (accepted trade-off per SPEC). Comment stripping landed via the High security fix in this review, which removes comment-based phantom boundaries; string-literal contexts remain accepted. Keep the two reproducers for the ISSUE-057 wiring review.

- **[Low] Hollow validator crashes with a traceback on a non-UTF8 test file (realistic in the user-repo domain testgen scans)**
  Evidence: scripts/verify_hollow_tests.py — `path.read_text(encoding="utf-8")` with only SyntaxError handled; a latin-1/cp949 legacy test_*.py raises UnicodeDecodeError, exiting via interpreter traceback (coincidental exit 1, no HOLLOW message). The design sweeps' inputs are model-generated UTF-8 by construction, but this validator's wiring target is arbitrary user test directories.
  Fix: Catch UnicodeDecodeError alongside SyntaxError (or read with errors='replace' for the JS path) and emit a clean hollow entry (reason: 'undecodable (not UTF-8)') — fails closed with a usable message instead of a traceback.

- **[Low] Coverage gap: collect-ALL-occurrences for literal_quote is lesson-mandated, implemented correctly, but untested — a regression to .search() would pass the suite**
  Evidence: scripts/verify_design_sweeps.py:92 — findall (probe-confirmed: a second, unrendered quote fails naming it). TestLiteralQuote has no multi-quote case; every test uses the single pinned quote. The recalled lesson ('collect ALL duplicate-key occurrences') is exactly the behavior left unguarded.
  Fix: Add two tests: philosophy with two literal_quote fields where (a) both render → exit 0, (b) only the first renders → exit 1 naming the SECOND quote (paired with absence of the first in the failure lines).

- **[Low] Near-vacuous paired assertion in the signature-move pass test (OR of two negatives)**
  Evidence: tests/test_sweep_validators.py:168 — `assert "home.html" not in out or "not applied" not in out`. The disjunction is satisfied whenever either substring is absent, so the intended paired-absence guard is inert.
  Fix: Replace with the conjunction actually intended: `assert "not applied" not in out` (the PASS message contains neither substring).

- **[Low] [debt] Debt-ledger harvest: 3 no-trigger KIT-DEBT markers, all pre-existing harvester self-matches (record-only)**
  Evidence: checkpoint --phase debt: scripts/debt_harvest.py:44, tests/test_debt_harvest.py:27, tests/test_debt_harvest.py:59 flagged NO-TRIGGER. All three are debt_harvest's own docstring examples / test fixtures, not real deferrals; this PR introduces zero KIT-DEBT markers.
  Fix: No action for this PR. If the harvester keeps flagging its own documentation examples, teach it to skip its own docstring/test-fixture lines.

## Security Findings
_Source: reviewer-degraded_

- **[High] Gate bypass: JS hollow-test check counted expect() inside comments — a commented-out assertion passed the gate — FIXED in review**
  Evidence: scripts/verify_hollow_tests.py — JS_ASSERT_HINT was applied to the raw segment with no comment stripping. Probe: `it('does nothing', () => { run(); // expect(x).toBe(1) TODO re-enable });` → exit 0 pre-fix. Canonical hollow-test failure mode (model comments out a failing assertion) that the gate exists to catch; ISSUE-057 hardens this into a deterministic PASS signal.
  Fix: APPLIED in review commit: strip_js_comments() blanks `/* */` and `//` comments (newline/offset-preserving; `(?<!:)` lookbehind protects https:// in strings) before JS_TEST_CALL/JS_ASSERT_HINT matching; 3 mutation tests added (line-comment bypass, block-comment bypass, URL guard); SPEC-056 trade-off bullet amended.

- **[Medium] Gate bypass: any identifier containing 'mock' counts as an assertion mechanism in Python tests**
  Evidence: scripts/verify_hollow_tests.py — Attribute starting with 'assert' OR attr in ('raises','fail') OR 'mock' in any Name/Attribute. Probes: `def test_x(mock_db): mock_db.start()` → exit 0; `def test_trivial(): mocked = None` → exit 0. SPEC-056 blesses 'a mock reference', but this whitelists the kit's own documented hollow-pass class (mock fixture used without any assertion — ISSUE-037 lesson); response.fail / x.raises attributes also false-pass.
  Fix: Narrow the predicate: count ast.Assert, raises as a Call, attributes starting with 'assert', and fail only as pytest.fail/self.fail calls. Drop the bare mock-anywhere-in-name rule or require co-occurrence with an assert-attribute. Revise SPEC contract 4 accordingly.

- **[Medium] Gate bypass: ai-tell misses HTML-entity-encoded tells and case-variant CSS**
  Evidence: scripts/verify_design_sweeps.py:240-256 — em-dash pattern [—–] does not match &mdash;/&#8212;/&#x2014; (probe: `<p>Fast &mdash; reliable</p>` → exit 0) although the RENDERED output is an em-dash; \b100vh\b and the calc pattern lack re.I while CSS is case-insensitive (probe: `height: 100VH;` + `WIDTH: CALC(33% - 1rem);` → exit 0). Contradicts the occurrence-whitelist-over-RENDERED-strings lesson the script cites.
  Fix: Add entity alternatives to the em-dash tell (or decode entities in HTML before sweeping) and compile the CSS-mechanics tells with re.IGNORECASE. Mutation-test each added spelling. Address before or with ISSUE-057 wiring.

- **[Medium] Gate bypass: literal-quote satisfied by non-rendered placements (attribute values, <script> bodies)**
  Evidence: scripts/verify_design_sweeps.py:118-124 — haystack is full HTML with only <!-- --> stripped. Probes: quote present only in `data-note="Plate 47"` → exit 0; only in `<script>// Plate 47</script>` → exit 0. The sweep's contract is 'rendered verbatim'.
  Fix: Blank <script>/<style> element bodies the same way comments are blanked, and either strip attribute values or document attribute text (alt/aria-label) as an accepted rendered surface. At minimum record the limitation in SPEC-056.

- **[Medium] Partial vacuous pass: standalone ai-tell passes with zero screen files when styles.css exists**
  Evidence: scripts/verify_design_sweeps.py:302-317 — the empty-input guard fires only when targets (screens + css) is empty. Probe: screens dir empty, styles.css present → exit 0, with all five html-only tells vacuously unswept. Standalone ai-tell is a documented gate invocation; tests only cover the both-missing case.
  Fix: Treat an empty screens list as a violation in run_ai_tell (mirroring literal-quote and signature-move), independent of css presence; add the screens-empty-css-present mutation test.

- **[Medium] No input containment: symlinked screens dir / test files outside --project-path fully satisfy the gates**
  Evidence: scripts/verify_design_sweeps.py:380-383 — screens_dir.is_dir() + glob follow a symlinked directory; probe: prototype/screens → <dir outside project> passed `all` (exit 0) against content not in the project tree (the kit's own shipped pass fixtures under tests/fixtures/sweeps/proto_pass/ are a ready-made bypass target). scripts/verify_hollow_tests.py:134-140 — rglob likewise returns symlinked files. Minor read-and-echo vector: snippets of any readable file a symlink points at land in gate output.
  Fix: Resolve each discovered path and require containment under project.resolve() (or reject path.is_symlink()); emit a violation (exit 1) for out-of-tree targets so the gate fails closed.

- **[Low] Undecodable input files crash with a traceback instead of a clean finding (fail-closed on exit code, but --json contract breaks)**
  Evidence: verify_design_sweeps.py:91,119,180,193,321 and verify_hollow_tests.py — bare read_text(encoding='utf-8'). Probe: non-UTF-8 file → uncaught UnicodeDecodeError, exit 1 with traceback. Direction is safe (exit 1 = fail), but in --json mode no JSON is emitted — a lenient JSON-parsing caller in ISSUE-057 could misread that as absence of violations; infra errors indistinguishable from real violations.
  Fix: Catch UnicodeDecodeError/OSError per file and emit a violation/hollow entry (reason: unreadable/undecodable), keeping the JSON contract intact. ISSUE-057 wiring must treat missing/unparseable JSON as fail.

- **[Low] Output injection: raw file content echoed verbatim to stdout (ANSI escapes, spoofable PASS lines)**
  Evidence: verify_design_sweeps.py:333 line.strip()[:100] and :339 text emission; verify_hollow_tests.py echoes JS test titles. Probe: a screen line containing ESC[2J ESC[32m 'ai-tell: PASS' was echoed verbatim — exit code correctly stayed 1; risk only if ISSUE-057 greps stdout text or logs render in a terminal. --json mode safe (json.dumps escapes).
  Fix: Strip control characters from snippets/titles in text mode; have ISSUE-057 consume exit codes / --json only, never grep text output.

- **[Low] Quadratic regex scan on unclosed comment openers (resource exhaustion, not catastrophic)**
  Evidence: verify_design_sweeps.py:56-57 — <!--.*?--> and /\*.*?\*/ with re.S rescan to EOF per unclosed opener. Measured: 4000 unclosed <!-- in 28KB → 0.38s; extrapolates to minutes near ~1MB pathological input. No exponential backtracking anywhere; local dev gate limits impact.
  Fix: Optional hardening: cap input file size (refuse >2MB with a violation entry) or anchor comment patterns as linear scans.

- **[Low] signature-move matches class attributes inside <script>/CSS string literals**
  Evidence: verify_design_sweeps.py:159 _CLASS_ATTR and :181 selector search run over comment-stripped source only. Probe: screen whose only class="sig" occurrence is inside a JS string → exit 0; `content: ".sig"` in CSS satisfies the selector check. Ambiguous (JS-template-rendered prototypes make the match arguably legitimate), but allows a never-applied class to pass.
  Fix: Blank <script>/<style> bodies before the class-attribute scan; if JS-rendered prototypes must count, state that exception in SPEC-056.

## Over-Engineering

- **[Low] [delete] Tell.description is set for all 7 tells but never read — cut the field or render it as a remedy hint**
  Evidence: scripts/verify_design_sweeps.py:233 — violations print only tell_id + snippet; the description field is dead data (~8 lines).
  Fix: Either cut the field, or better: append it to the violation line (`[flex-calc-width] ... — use CSS Grid`) so the dead data becomes a user-helpful remedy hint.

- **[Low] [delete] _rel_dirname's live branch is dead — always returns the literal 'prototype/screens' (wrong under --screens-dir override)**
  Evidence: scripts/verify_design_sweeps.py:367-370 — only called from the quote-None violation path, which only executes when screens is empty, so `if screens:` never holds (~5 lines).
  Fix: Inline the actual screens_dir string passed from main.
