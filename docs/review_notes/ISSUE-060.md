# Review Notes — PR #116

## Code Review
_Source: reviewer-degraded_

- **[Medium] Web Phase 5.5 sweeps moved ahead of content-mutating steps 18-22; content added there escapes the gates — FIXED in review**
  Evidence: skills/uiux/SKILL.md.tmpl:253 placed 'Design verification sweeps' at 17.5, before '18) PRD feature cross-check' (adds missing features), 21) accessibility fixes, 22) state-demo fixes. On main, contrast/AI-tell/mechanics ran at 21.5/22.7/22.8 — after those mutations. No re-run clause existed downstream and verify_checkpoint.py has no sweep phase; tests pin call-site presence, not position, so the suite stayed green.
  Fix: FIXED in review: the block moved to 22.4 — terminal among the content-mutating Phase 5.5 steps, before the read-only 22.5 issues.md coverage cross-check — in skills/uiux/SKILL.md.tmpl, with the Signature Move cross-reference ('Phase 5.5 step 17.5' -> '22.4') updated and SKILL.md regenerated via gen_skills.py (regen clean). Suite re-run: 1798 passed; test checkpoint re-run PASS. Mobile/desktop placements were already terminal.

- **[Low] K1 'zero behavior' claim inaccurate for mobile/desktop — unified {{PILOT_GATE}} strictly strengthens their gates**
  Evidence: scripts/fragments.py:285,689 claim 'Extraction changes location, zero behavior'; the pre-conversion mobile/desktop tmpls carried a condensed gate lacking the ui-reviewer co-invocation, banned-word restart rule, Phase-1.5-skipped branch, and 4-way patch-layer mapping that the unified template now gives them.
  Fix: Record-only (strictly additive strengthening, direction is safe). Amend the pilot_gate_fragment docstring and K1 comment at the next touch of fragments.py: 'web: zero behavior; mobile/desktop: unified up to the full web protocol (strictly additive).' No code change.

- **[Low] Mobile Phase 5 step numbering skips 18 (17 -> 19) after the config-step merge**
  Evidence: skills/mobile-uiux/SKILL.md:333-335 — step 17 (merged old 17/17-a/17-b/17-c/18) is followed by step 19. No stale cross-references remain, but numbered steps are cross-referenced by checkpoints/critique layers.
  Fix: Record-only, non-blocking. Renumber 19-23 down by one in the tmpl at next touch, or append '(step 18 folded into 17)' to step 17.

- **[Low] test_exempt_maps_recorded_override_and_only_that overclaims — the 'only that' direction is not exercised in this file**
  Evidence: tests/test_uiux_contract_conversion.py:215-238 proves exempt->pass but never injects a second unexempted tell; the direction is covered only at the validator level (tests/test_sweep_validators.py:348).
  Fix: Record-only (the direction IS covered at the validator layer; the caller-level gap is naming, not coverage). Rename to test_exempt_maps_recorded_override, or add a second mutation (e.g. a generic-name hit) asserting --exempt em-dash still exits 1 naming the other tell through the all --class call shape.

- **[Low] README '6 subagents' edit flagged as drive-by — resolved: explicitly in scope as a taken optional Low**
  Evidence: README.md:353 — '6 subagents' -> 'a team of subagents'; lesson-aligned (unguardable counts regenerate or get dropped) but belongs to no ISSUE-060 AC or D/K row.
  Fix: No action: the issue dispatch explicitly lists this edit as a taken optional Low in scope for ISSUE-060 (alongside the verify_checkpoint.py:305 docstring wording). Recorded here so the scope question does not resurface at ship.

- **[Low] [debt] Debt-ledger no-trigger markers are all pre-existing harvester self-fixtures — none introduced by this PR**
  Evidence: Advisory debt checkpoint: 14 KIT-DEBT markers total, 3 no-trigger (scripts/debt_harvest.py:44 doc-comment example; tests/test_debt_harvest.py:27,59 intentional negative fixtures), 1 malformed (tests/test_debt_harvest.py:35, also an intentional fixture). All pre-date this PR; the ISSUE-060 diff adds zero KIT-DEBT markers.
  Fix: No action from this PR. If the harvester's self-fixture noise recurs in future reviews, teach debt_harvest.py to skip its own test fixtures/doc examples.

## Security Findings
_Source: reviewer-degraded_

- **[Low] Prescribed sweep command interpolates --class value without quoting or format guidance**
  Evidence: skills/uiux/SKILL.md:422 (source: _DESIGN_SWEEPS_PLATFORM["uiux"]["lead"] in scripts/fragments.py): `python3 scripts/verify_design_sweeps.py all --class <signature-move-class> [--exempt <tell-id> ...]` — the class value comes from model-authored docs/design_philosophy.md (brief/PRD-influenced) and is pasted into a Bash command with no CSS-identifier constraint or quoting instruction; validator side is argparse-only (no shell), executor already holds Bash, so no new privilege.
  Fix: In the web lead param of _DESIGN_SWEEPS_PLATFORM, state the class must be a plain CSS identifier ([A-Za-z_][A-Za-z0-9_-]*) and/or quote the placeholder in the command template: --class '<signature-move-class>'.

- **[Low] Mobile .gitignore guidance no longer names secret-bearing patterns (.env, *.keystore, *.jks)**
  Evidence: skills/mobile-uiux/SKILL.md.tmpl: deleted step 17-b ("Standard Expo gitignore: node_modules, .expo, dist, *.jks, *.keystore, .env") collapsed into step 17 (skills/mobile-uiux/SKILL.md:333), which requires .gitignore to exist but no longer enumerates secret-file patterns; the boot gate cannot catch a missing gitignore entry.
  Fix: Add one clause to step 17's boot-gate bullet: .gitignore must cover node_modules, .expo, dist, and secret-bearing files (.env*, *.jks, *.keystore) — a K-class secrets contract line, not a D3 config pin.

- **[Low] K8 test pin covers 2 of 3 legs — contextBridge-only IPC is not asserted**
  Evidence: tests/test_uiux_contract_conversion.py:506-522 asserts contextIsolation: true and nodeIntegration: false in desktop skill + agent, but not the contextBridge-only typed IPC / main-preload-renderer separation leg of SPEC-060 K8; the contextBridge lines (skills/desktop-uiux/SKILL.md:369,375,476; agents/desktop-uiux-developer.md:88,187) are inline, not fragment drift-guarded, so a future shrink could delete them without failing any test.
  Fix: Extend test_k8_electron_security_pins_survive_as_contract_lines with a contextBridge assertion per file (e.g. "contextBridge" + "ONLY bridge" in the skill, "never expose `ipcRenderer` directly" in the agent) so all three K8 legs are pinned.

## Over-Engineering

- **[Low] [shrink] K9-handover and literal-quote bullets byte-identical between mobile and desktop _DESIGN_SWEEPS_PLATFORM leads**
  Evidence: scripts/fragments.py:590 and :607 carry identical '- **Script handover (K9 trigger)**' bullets; the '**Literal quote verbatim render check**' bullet is also byte-identical between the two leads — the AC2 drift class reproduced intra-file (single-platform wording edits diverge silently; the trigger test only catches removal of one exact substring). Extends, does not re-raise, the recorded mechanics-procedure carry-in.
  Fix: Hoist to module constants (_K9_HANDOVER, _LITERAL_QUOTE_SWEEP_TSX) interpolated into both leads, or promote to shared template slots with a per-platform param. Net ~-8 lines. Fold into the post-064 K4 mechanics-sweep issue that already owns the recorded mechanics_body duplicate.

- **[Low] [shrink] Test scaffolding re-declared across the three sweep-test files**
  Evidence: tests/test_uiux_contract_conversion.py:66-112 duplicates QUOTE/SIG_CLASS/_run_cli/_mutate from tests/test_sweep_contract_conformance.py; _fragment_resolver duplicates _resolver_for in tests/test_design_fragments.py:66-75; both new test files hardcode the skill triple instead of importing fragments.UIUX_SKILLS.
  Fix: Optional hygiene: move _run_cli/_mutate/fixture constants to a shared conftest helper (~-30 lines). Per-file pin duplication is the suite's existing convention, so leave if untouched.
