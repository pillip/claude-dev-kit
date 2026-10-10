# Review Notes — PR #115

## Code Review
_Source: reviewer-degraded_

- **[Medium] F3: quote inside an UNCLOSED <script> still satisfies literal-quote (script-body blanking requires a closing tag)**
  Evidence: scripts/verify_design_sweeps.py:135 — _SCRIPT_BODY = re.compile(r"(<script\b[^>]*>)(.*?)(?=</script\b)", re.S | re.I). The lazy body group only matches when a `</script` lookahead exists; with no closing tag the body is never blanked. Reproduced: replacing the rendered span with `<script>\n// 47.2-A\nvar x = 1;` (no closing tag) exits 0. A browser treats an unclosed <script> as script data to EOF — the quote never renders, so the gate false-passes on exactly the surface F3 claims to blank.
  Fix: Allow end-of-input as the body terminator: re.compile(r"(<script\b[^>]*>)(.*?)(?=</script\b|\Z)", re.S | re.I), and add the mutation pair (unclosed-script probe fails, restored span passes) to TestLiteralQuoteNonRenderedPlacements. — APPLIED in review (step 4): _SCRIPT_BODY lookahead now accepts \Z (unterminated <script> body blanks to EOF, mirroring the HTML parser's script-data-to-EOF rule); mutation-pair test test_quote_in_unterminated_script_block_fails_then_rendered_restores added and verified to FAIL against the unfixed regex. Also removes the quadratic failing-match behavior. Suite after fix: 1682 passed.

- **[Low] F1 incomplete for declaration-level tells: entity-encoded inline-style declarations evade the flex-calc-width scan**
  Evidence: scripts/verify_design_sweeps.py:446 — decl_text = strip_css_comments(stripped) if kind == "html" else stripped; no html.unescape on the declaration-level text (unescape runs only in the line-wise loop at :430). Reproduced: `<div style="width&colon; calc(33% - 1rem)">x</div>` exits 0, though browsers decode character references in attribute values before CSS parsing, so the banned declaration renders.
  Fix: For html targets, decode decl_text per line before collapse, mapping any decoded newline to a space to keep the line map stable: decl_text = "\n".join(html.unescape(l).replace("\n", " ") for l in decl_text.split("\n")). Note <style> element bodies are RAWTEXT (entities NOT decoded by browsers), so strictly correct decoding is attribute-value-scoped; the per-line approximation only over-matches (fail-closed).

- **[Low] F6 cost: document-wide CSS-comment stripping can blank a REAL declaration bracketed by /* and */ appearing in rendered body text**
  Evidence: scripts/verify_design_sweeps.py:446 — strip_css_comments runs over the whole HTML document, not scoped to style=""/<style> contexts. Reproduced: `<p>open /* note</p>` + `<div style="width: calc(33% - 1rem)">x</div>` + `<p>end */ done</p>` exits 0 — the rendered-text /* */ pair swallows the genuine inline-style declaration in the decl pass. The F6 tests cover evasion->caught and the line-wise scope pin, but not this decl-pass false-negative direction.
  Fix: Either scope CSS-comment blanking to extracted style attribute values and <style> element bodies (mirrors the browser exactly), or accept and document the trade-off in the header docstring plus a pinning test so the gap is recorded rather than silent.

- **[Low] F3 _DATA_ATTR_VALUE edge pair: unquoted data-* values evade blanking; data-attr-like syntax in rendered text is over-blanked**
  Evidence: scripts/verify_design_sweeps.py:136 — alternation only covers "..." and '...'. Reproduced both directions: (a) `<span data-note=47.2-A>` (valid HTML5 unquoted value, not rendered) exits 0 — evasion; (b) `<p>Tag rows with data-order="47.2-A" in your markup</p>` (rendered documentation text) exits 1 — false fail, because the regex matches attribute-like syntax anywhere, not only inside tags.
  Fix: Add an unquoted-value branch ("[^\"]*"|'[^']*'|[^\s>\"']+) to close the evasion; the over-blanking direction is fail-closed and may be accepted, but record it with a comment/test so the behavior is deliberate.

- **[Low] F5 containment gates files only: an out-of-tree screens-dir symlink is enumerated (glob) before the check, and an empty foreign dir exits 1 instead of 2**
  Evidence: scripts/verify_design_sweeps.py:546 — screens = _discover_screens(screens_dir) runs BEFORE the containment loop at :554-576, so screens_dir.glob() lists an arbitrary out-of-tree directory pre-gate. Reproduced: screens symlinked to an out-of-tree dir containing no *.html → directory enumerated, run proceeds and exits 1 (empty-input) rather than 2 (containment). File contents are never read (the stated F5 guarantee holds), but the breach decision differs by whether the foreign dir happens to contain *.html.
  Fix: Containment-check the resolved screens_dir (and philosophy/css parents) before discovery: if screens_dir.resolve() falls outside every sanctioned root, exit 2 without globbing. Keeps the exit-2-on-breach contract uniform and removes the pre-gate metadata enumeration.

- **[Low] F2 reason/docstring says a fail(...) call counts, but a bare `fail` Name does not (asymmetric with bare `raises`)**
  Evidence: scripts/verify_hollow_tests.py:89 counts Attribute attr in ("raises", "fail"); :95 counts ast.Name only for "raises". `from pytest import fail; fail("boom")` is therefore flagged hollow despite the docstring (:11-15) and the new reason string "no assert/raises/assert_*/fail" (:121) implying fail(...) vouches. Pre-existing asymmetry, but the diff touched this exact predicate, docstring, and reason string, cementing the mismatch. Fail-closed, so low impact.
  Fix: Either extend :95 to `node.id in ("raises", "fail")` to match the documented contract, or correct the docstring/reason to say `pytest.fail` (attribute form) only.

- **[Low] F4 empty-input violation names the hardcoded default dir even when --screens-dir overrides it**
  Evidence: scripts/verify_design_sweeps.py:407 — "file": _rel_dirname(screens, project) with screens == [] returns the literal fallback "prototype/screens" (:498). With `ai-tell --screens-dir /elsewhere/empty`, the failure report points the user at a directory the run never consulted.
  Fix: Pass the actual screens_dir into run_ai_tell (or thread it through _rel_dirname) so the empty-input violation names the directory that was actually swept.

- **[Low] [debt] Debt-ledger harvest: 3 no-trigger + 1 malformed KIT-DEBT markers, all pre-existing harvester self-matches/fixtures (record-only)**
  Evidence: checkpoint review/debt advisory — scripts/debt_harvest.py:44 (usage docstring), tests/test_debt_harvest.py:27,:35,:59 (test fixtures). None introduced by PR #115; same set recorded in ISSUE-062/065 reviews.
  Fix: No action for this PR; markers are harvester documentation/test data, not real deferrals.

## Security Findings
_Source: reviewer-degraded_

- **[Medium] Unterminated <script> defeats F3 blanking: quote inside script body passes literal-quote; same pattern is quadratic on adversarial input**
  Evidence: scripts/verify_design_sweeps.py:135 `_SCRIPT_BODY = re.compile(r"(<script\b[^>]*>)(.*?)(?=</script\b)", re.S | re.I)` — the positive lookahead REQUIRES a closing tag, so a screen file whose <script> is never closed has its body left un-blanked. Verified end-to-end: a fixture whose only copy of the literal quote sits inside an unterminated <script> body makes `literal-quote` exit 0 ('PASS (1 quote(s) rendered verbatim)'); the properly-terminated control exits 1. Browsers treat an unterminated <script> as script-to-EOF (nothing after it renders), so this is a full bypass of the exact evasion class F3 closes, reachable by omitting one close tag. Secondary: the failing lazy-dot match is O(n^2) — 8,000 unmatched `<script>` opens (~72KB) take 3.2s, quadrupling per doubling; a few-hundred-KB pathological fixture hangs the gate for minutes.
  Fix: Change the lookahead to `(?=</script\b|\Z)` so an unterminated script body is blanked to EOF (mirroring the HTML parser's script-to-EOF rule). This one-token fix also removes the quadratic behavior: the lazy expansion always finds a terminator, so the match never retries to failure. Add a mutation-pair test with the close tag deleted. — APPLIED in review (step 4): _SCRIPT_BODY lookahead now accepts \Z (unterminated <script> body blanks to EOF, mirroring the HTML parser's script-data-to-EOF rule); mutation-pair test test_quote_in_unterminated_script_block_fails_then_rendered_restores added and verified to FAIL against the unfixed regex. Also removes the quadratic failing-match behavior. Suite after fix: 1682 passed.

- **[Low] F5 check/read gap: containment resolves the path, but the later read re-follows the original (unresolved) path**
  Evidence: scripts/verify_design_sweeps.py:567-568 checks `resolved = target.resolve()` / `is_relative_to(root)`, but the runners then read the ORIGINAL Path objects (`philosophy.read_text` :159, `s.read_text` :194, `css_path.read_text` :259, `path.read_text` :418). A symlink swapped between the containment check and the read is re-followed at read time, re-opening the escape the check just closed. In this threat model (local dev gate; repo content is static during a run; a concurrent attacker already has same-user write access) no privilege boundary is crossed — hence Low, not High.
  Fix: Resolve each would-read path once in main() and pass the RESOLVED paths to the runners (read `resolved`, not `target`). Closes the race class for free and guarantees the checked object and the read object are identical.

- **[Low] F3 data-* blanking misses unquoted attribute values**
  Evidence: scripts/verify_design_sweeps.py:136 `_DATA_ATTR_VALUE = re.compile(r"(\bdata-[\w-]+\s*=\s*)(\"[^\"]*\"|'[^']*')", re.I)` matches only double/single-quoted values. `<div data-note=47.2-A>` is valid HTML; its value stays countable as rendered text (verified: not blanked). Narrow vector — unquoted values cannot contain whitespace, so only a single-token literal_quote can hide there — but it is the same non-rendered surface F3 declares blanked.
  Fix: Add an unquoted-value alternative: `("[^"]*"|'[^']*'|[^\s>]+)`. One-line change plus a mutation-pair test with a single-token quote in an unquoted data attribute.

- **[Low] verify_hollow_tests.py (touched by this PR) still reads uncontained paths — no F5-style guard**
  Evidence: scripts/verify_hollow_tests.py:185-196 — explicit FILES get only `is_file()` (follows symlinks) and `--tests-dir` discovery reads whatever `rglob` finds; a symlinked `test_evil.py` inside the tests dir resolving out-of-tree is read with no containment check. This is the exact class F5 just closed in the sibling gate (recalled lesson: path-like input read by gates is untrusted — realpath containment). Pre-existing, not introduced by this diff, and the leak surface is small (file is only ast.parse'd; output prints test names / SyntaxError messages, never content) — hence Low.
  Fix: Apply the same resolved-roots containment as verify_design_sweeps.py F5: sanctioned roots = resolved cwd/tests-dir plus explicitly passed FILES (caller's decision, matching the F5 override doctrine); fail closed exit 2 before any read. Candidate follow-up issue rather than a blocker for this PR.

## Over-Engineering

_No findings._
