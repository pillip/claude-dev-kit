# SPEC-056: Promote four design sweeps to deterministic validators

> Linked Issue: ISSUE-056
> Status: `accepted`
> Date: 2026-10-09
> Author: pillip + Claude

## Problem

Four falsifiable gates live as model-executed grep instructions inside skill prose: the `literal_quote` verbatim render check and the Signature Move presence check (uiux/mobile-uiux/desktop-uiux Phase 5.5), the AI Tell sweep (same three skills), and the hollow-test predicate (testgen step 3d and the test-generator agent). Each is already a checkable predicate over files on disk, yet the gate is "the model asserts it swept" — the weakest verification exactly where free generation is longest (docs/evolution_audit.md finding 3). A skipped or hallucinated self-check passes today. The open design question (issue Implementation Notes) is packaging: one script with subcommands vs four small scripts, decided by call-site count in ISSUE-057/060 vs file count.

## Context

- docs/evolution_audit.md (2026-10-08), finding 3 and roadmap item 2: move the four model-executed sweeps to deterministic validators; this converts A-bucket prose into C-bucket assets and is the prerequisite for the uiux-triplet prose cut (ISSUE-060).
- Call-site topology is asymmetric: the three design sweeps (literal_quote, Signature Move, AI Tell) share the same three call sites (uiux / mobile-uiux / desktop-uiux Phase 5.5, wired by ISSUE-057) and the same input tree (`docs/design_philosophy.md` + `prototype/`). The hollow-test predicate has two disjoint call sites (testgen step 3d, test-generator agent) and a disjoint input domain (test directories, Python/JS test files).
- Existing verify_* family conventions (`verify_figma_compliance.py`, `verify_structural_match.py`, ISSUE-045 test pattern): exit 0 = pass, 1 = violations, 2 = usage error; `--json` where useful; pinned fixtures with mutation tests.
- Review lesson (native memory): absence-guards must use occurrence-whitelists against the ACTUAL banned rendered strings and get mutation-tested in both directions — not phrasing blacklists over prose.
- Skill-prose predicates being promoted (verbatim sources): uiux SKILL.md steps 17.5 (Signature Move: reusable class in `styles.css`, applied on every screen), 17.6 (literal_quote verbatim, no substring widening, not in comments), 22.7 (AI Tell sweep, whitespace-insensitive CSS matching, Brief-overrides exemptions); testgen SKILL.md step 3d (`def test_` + `assert`/`mock`/`raises`; `it(`/`test(` + `expect`/`toBe`/`toEqual`).
- Scope boundary: judgment-dependent tells (div-based fake product UI, three equal feature cards, invented-name plausibility) are not deterministically decidable; only the mechanically checkable tell subset is promoted. ISSUE-057/060 own all call-site wiring.

## Options

### Option A: One `verify_design_sweeps.py` with four subcommands (hollow-tests included)
- **Approach**: Single script exposing `literal-quote`, `signature-move`, `ai-tell`, `hollow-tests`, plus an `all-design` aggregate.
- **Pros**:
  - Minimum file count; one `--json` plumbing.
- **Cons**:
  - Grafts a disjoint domain (test-directory AST/heuristic analysis) into a design-named script: the hollow-tests subcommand shares zero input paths, zero helpers, and zero call sites with the design sweeps.
- **Trade-off**: 1 script file + 1 test file; 5 call-site invocations (3 design + 2 hollow); ~0 shared code between the hollow subcommand and the other 3 (2 unrelated domains in 1 CLI).

### Option B: Four separate scripts
- **Approach**: `verify_literal_quote.py`, `verify_signature_move.py`, `verify_ai_tells.py`, `verify_hollow_tests.py`.
- **Pros**:
  - Each validator independently evolvable; smallest per-file surface.
- **Cons**:
  - The three design validators share inputs (`docs/design_philosophy.md`, screens dir, `styles.css`) and comment-stripping/whitespace-normalization helpers — splitting them duplicates that plumbing and triples the design-sweep invocation lines at every ISSUE-057 call site.
- **Trade-off**: 4 script files; 3 skills × 3 design invocations + 2 hollow invocations = 11 call-site invocation lines (vs 5), plus 3 copies of shared arg/IO plumbing.

### Option C: Two scripts split by input domain
- **Approach**: `verify_design_sweeps.py` with subcommands `literal-quote`, `signature-move`, `ai-tell`, and `all` (runs the three against one prototype tree); separate `verify_hollow_tests.py` over a test directory.
- **Pros**:
  - Packaging follows the call-site topology: each ISSUE-057 design call site runs one `all` invocation; testgen/test-generator call one hollow invocation. Shared design-sweep helpers (comment stripping, whitespace normalization, screens discovery) live once.
  - Neither script carries a foreign domain.
- **Cons**:
  - One more file than Option A.
- **Trade-off**: 2 script files; 5 call-site invocation lines (3 design `all` + 2 hollow) — same 5 as Option A, +1 file vs A, −2 files and −6 invocation lines vs B.

## Decision

**Chosen: Option C**

The issue's own comparator (call-site count in ISSUE-057/060 vs file count) ties A and C at 5 invocation lines, so the tiebreak is domain cohesion: Option A's single CLI would carry two input domains with zero shared code, which is exactly the kind of accidental coupling the verify_* family has avoided (each existing verify_* script owns one input domain). Option B loses outright on both counts (11 invocation lines, 3x duplicated plumbing).

Validator contracts (binding for ISSUE-057/060 wiring):

1. `verify_design_sweeps.py literal-quote [--project-path P]` — parses `literal_quote: "<exact string>"` from `docs/design_philosophy.md`. Explicit `literal_quote: (skipped — interview not run)` marker → exit 0 (recorded skip, not vacuous). Missing field → exit 1. The exact characters must appear in at least one `prototype/screens/*.html` outside HTML comments, whitespace-insensitive (runs of whitespace in needle and haystack each collapse to one space — the only permitted normalization; no substring widening). Failure names the missing quote. Zero screen files → exit 1.
2. `verify_design_sweeps.py signature-move --class <name> [--project-path P]` — the class must appear as a selector in `prototype/styles.css` AND inside a `class="…"` attribute of every `prototype/screens/*.html`. Failure names each non-applying screen file. Zero screen files → exit 1.
3. `verify_design_sweeps.py ai-tell [--project-path P] [--exempt TELL_ID ...]` — occurrence-whitelist registry of banned RENDERED patterns (ids: `em-dash`, `100vh`, `flex-calc-width`, `generic-name`, `fake-perfect-number`, `filler-verb`, `scroll-cue`), swept over `prototype/screens/*.html` + `prototype/styles.css` after comment stripping (HTML `<!-- -->`, CSS `/* */`) and whitespace normalization for CSS mechanics patterns. `--exempt` implements recorded Brief overrides only; each exemption is reported. Violations print `file:line tell-id`. Zero target files → exit 1. Judgment tells stay model-executed (out of scope).
4. `verify_hollow_tests.py [--tests-dir D | FILES...]` — Python: every `def test_*` function (module or class level, via `ast`) must contain an `assert` statement, a `pytest.raises`/`raises` usage, a mock reference (`mock`/`Mock`/`.assert_*`), or `pytest.fail`. JS/TS: every `it(`/`test(` title segment must contain `expect`/`toBe`/`toEqual`. Failure names file + function (or test title). Zero test files or zero test functions → exit 1.
5. Shared: exit 0 pass / 1 violations / 2 usage error; `--json` emits a machine-readable violation list; no third-party dependencies (stdlib only).

## Trade-offs Accepted

- `signature-move` takes the class name as an argument rather than parsing it from prose — the caller (ISSUE-057 checkpoint wiring) remains the source of the name; a hallucinated class name still fails deterministically because the class must exist in CSS and on every screen.
- The AI Tell registry covers only the mechanically decidable subset (7 tell ids at introduction); judgment tells remain in skill prose until someone proves a deterministic predicate for them. The registry is data, extensible without CLI changes.
- The JS hollow-test check is a segment heuristic (text between consecutive `it(`/`test(` occurrences), not a parser — matching the existing testgen predicate's grep semantics; Python gets the stronger AST treatment because stdlib provides it for free. Review hardening (PR #101): JS comments (`//`, `/* */`) are blanked before matching, so a commented-out `expect()` can no longer vouch for a test; string-literal contexts remain unparsed (accepted residual heuristic).
- Web-HTML prototypes only for design sweeps (mobile RN/desktop trees differ structurally); ISSUE-057 may pass `--project-path`/future flags when those trees get wired.

## Migration

1. This PR (bundled with ISSUE-056): add `scripts/verify_design_sweeps.py`, `scripts/verify_hollow_tests.py`, pinned fixtures under `tests/fixtures/sweeps/`, and `tests/test_sweep_validators.py` (pass + mutation cases per validator). Purely additive — no call sites change.
2. ISSUE-057: wire `verify_design_sweeps.py all` into uiux/mobile-uiux/desktop-uiux checkpoint phases and `verify_hollow_tests.py` into the testgen flow via `verify_checkpoint.py`.
3. ISSUE-060: cut the now-redundant sweep prose from the three uiux skills, leaving one-line validator invocations.

## Rollback

`git revert` of the single PR — both scripts and their tests are additive; zero call sites reference them until ISSUE-057/060 land, so reverting cannot break any skill. Trigger: a validator proves systematically wrong (false-positive rate blocking legitimate prototypes) before wiring lands.

## Open Questions

- [ ] Should the AI Tell registry move to a data file (JSON) once per-project Brief-override persistence exists, so overrides are recorded machine-readably instead of via `--exempt` flags? — owner: pillip, by: ISSUE-057 wiring review.
- [ ] Do mobile (`prototype-mobile/src/screens/*.tsx`) and desktop (`prototype-desktop/`) trees get their own sweep target flags, or does ISSUE-057 normalize tree layout first? — owner: pillip, by: ISSUE-057.
