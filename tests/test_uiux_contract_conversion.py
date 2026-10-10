"""ISSUE-060 / SPEC-060: contract-convert the uiux triplet (keep/delete lists).

Acceptance criteria pinned here (RED until the Stage-2 conversion lands):

- AC1: every gate that passed/failed before conversion passes/fails
  identically on a fixture brief — gate behaviour is the regression surface
  (gate-parity fixtures). The gate-parity tests drive
  scripts/verify_design_sweeps.py through the EXACT call shape the converted
  web skill instructs (`all --class <name> --json`, `all --class <name>
  --exempt <id>`) over pass/violating prototype trees, and the wiring tests
  pin that the generated skills actually instruct that call shape.
- AC2: shared surviving text exists once in scripts/fragments.py and zero
  times as per-skill copies — owned by tests/test_design_fragments.py
  (once-only sentinels for {{PILOT_GATE}} / {{AI_TELLS}} /
  {{DESIGN_SWEEPS}}); the call-site pins here complement it.
- AC3: every retained prescription names its depreciation trigger;
  everything else gone (no orphaned MUSTs without an owner gate). The
  D-table absence guards assert actually-removed strings (occurrence
  guards, mutation-tested: every needle was grep-verified present in its
  target file before this test was written); the K-table pins assert the
  named depreciation triggers and surviving contract lines.

Boundary notes:
- scripts/verify_design_sweeps.py is CONSUMED, never modified (ISSUE-064
  hardens it in a parallel worktree; the CLI contract is frozen post-063).
  Parity tests pin the CALLER's call shape, not validator internals —
  internals are covered by tests/test_sweep_validators.py and
  tests/test_sweep_contract_conformance.py, whose proto_pass fixture and
  conventions are reused here.
- Raw-tmpl pins in tests/test_agent_dissolution.py (Phase 4.5 copy
  contract) and tests/test_uiux_reference_fabrication_guard.py (Reference
  Research) stay inline — nothing here contradicts those blocks remaining
  in the raw templates.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import fragments as fragments_module  # noqa: E402

SCRIPT = SCRIPTS_DIR / "verify_design_sweeps.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sweeps"
PROTO_PASS = FIXTURES / "proto_pass"

UIUX_SKILLS = ("uiux", "mobile-uiux", "desktop-uiux")
AGENT_FILES = (
    "agents/uiux-developer.md",
    "agents/mobile-uiux-developer.md",
    "agents/desktop-uiux-developer.md",
)

# Pinned pass-fixture facts (tests/fixtures/sweeps/proto_pass; same anchors
# test_sweep_contract_conformance.py uses).
QUOTE = "47.2-A"
SIG_CLASS = "signature-ledger-rule"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _generated(skill: str) -> str:
    return _read(f"skills/{skill}/SKILL.md")


def _fragment_resolver(name: str):
    """Fetch a SPEC-060 resolver from scripts/fragments.py.

    getattr (not import-from) so a missing resolver is a clean assertion
    failure naming the gap, never a collection-time ImportError that would
    mask the rest of the suite.
    """
    fn = getattr(fragments_module, name, None)
    assert fn is not None, (
        f"scripts/fragments.py defines no {name}() resolver "
        f"(SPEC-060 Migration step 1: {{{{PILOT_GATE}}}} / {{{{AI_TELLS}}}} "
        f"/ {{{{DESIGN_SWEEPS}}}} templates + resolver functions)"
    )
    return fn


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Invoke the validator exactly like the skill call site does."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )


def _mutate(path: Path, old: str, new: str) -> None:
    """Replace `old` with `new`, asserting the needle actually existed
    (guards against fixture drift turning the mutation hollow)."""
    text = path.read_text(encoding="utf-8")
    assert old in text, (
        f"mutation needle {old!r} not present in {path} (fixture drift)"
    )
    path.write_text(text.replace(old, new), encoding="utf-8")


@pytest.fixture()
def proto(tmp_path: Path) -> Path:
    """Fresh copy of the pinned prototype pass fixture."""
    root = tmp_path / "proj"
    shutil.copytree(PROTO_PASS, root)
    return root


# ════════════════════════════════════════════════════════════════════
# AC1 — gate-parity fixtures: the script verdict equals the predicate the
# prose sweeps asserted; every gate passes/fails identically on a fixture
# brief through the converted skill's exact call shape.
# ════════════════════════════════════════════════════════════════════


class TestGateParityCallShape:
    """AC1: every gate that passed/failed before conversion passes/fails
    identically on a fixture brief — gate behaviour is the regression
    surface. Call shape under test: `all --class <name> --json` (and
    `all --class <name> --exempt <id>`), exactly what the converted web
    skill's Phase 5.5 instructs."""

    def test_pass_tree_all_class_json_exits_zero_single_document(self):
        cp = _run_cli(
            "all", "--class", SIG_CLASS,
            "--project-path", str(PROTO_PASS), "--json",
        )
        assert cp.returncode == 0, cp.stdout + cp.stderr
        # A SINGLE json.loads must consume the whole stdout (the frozen
        # post-063 contract: exactly ONE top-level JSON object).
        payload = json.loads(cp.stdout)
        assert set(payload) == {"literal-quote", "signature-move", "ai-tell"}
        for sweep, result in payload.items():
            assert result["status"] == "pass", (sweep, result)
            assert result["violations"] == [], (sweep, result)

    def test_literal_quote_violation_fails_through_all_call_shape(self, proto):
        _mutate(
            proto / "prototype/screens/order-detail.html", QUOTE, "47-2-A"
        )
        cp = _run_cli(
            "all", "--class", SIG_CLASS,
            "--project-path", str(proto), "--json",
        )
        assert cp.returncode == 1, cp.stdout + cp.stderr
        payload = json.loads(cp.stdout)
        assert payload["literal-quote"]["status"] == "fail"
        assert any(
            v["quote"] == QUOTE
            for v in payload["literal-quote"]["violations"]
        ), payload["literal-quote"]
        # The other gates stay green on the same tree — parity is per-gate.
        assert payload["signature-move"]["status"] == "pass"
        assert payload["ai-tell"]["status"] == "pass"

    def test_signature_move_violation_fails_through_all_call_shape(
        self, proto
    ):
        _mutate(
            proto / "prototype/screens/home.html",
            f'class="card {SIG_CLASS}"',
            'class="card"',
        )
        cp = _run_cli(
            "all", "--class", SIG_CLASS,
            "--project-path", str(proto), "--json",
        )
        assert cp.returncode == 1, cp.stdout + cp.stderr
        payload = json.loads(cp.stdout)
        assert payload["signature-move"]["status"] == "fail"
        assert any(
            v["file"] == "prototype/screens/home.html"
            for v in payload["signature-move"]["violations"]
        ), payload["signature-move"]
        assert payload["literal-quote"]["status"] == "pass"
        assert payload["ai-tell"]["status"] == "pass"

    def test_ai_tell_violation_fails_through_all_call_shape(self, proto):
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Open — ledgers</h1>",
        )
        cp = _run_cli(
            "all", "--class", SIG_CLASS,
            "--project-path", str(proto), "--json",
        )
        assert cp.returncode == 1, cp.stdout + cp.stderr
        payload = json.loads(cp.stdout)
        assert payload["ai-tell"]["status"] == "fail"
        hits = [
            v
            for v in payload["ai-tell"]["violations"]
            if v["tell_id"] == "em-dash"
        ]
        assert hits, payload["ai-tell"]
        assert hits[0]["file"] == "prototype/screens/home.html"
        assert payload["literal-quote"]["status"] == "pass"
        assert payload["signature-move"]["status"] == "pass"

    def test_exempt_maps_recorded_override_and_only_that(self, proto):
        """K2 ledger wiring: --exempt ids map 1:1 from recorded `Brief
        overrides:` bullets; an exempted tell no longer fails the gate."""
        _mutate(
            proto / "prototype/screens/home.html",
            "<h1>Open ledgers</h1>",
            "<h1>Open — ledgers</h1>",
        )
        cp = _run_cli(
            "all", "--class", SIG_CLASS, "--exempt", "em-dash",
            "--project-path", str(proto), "--json",
        )
        assert cp.returncode == 0, cp.stdout + cp.stderr
        payload = json.loads(cp.stdout)
        assert payload["ai-tell"]["status"] == "pass"
        assert payload["ai-tell"]["exemptions"] == ["em-dash"]

        # Text-mode shape of the same call reports the exemption.
        text_cp = _run_cli(
            "all", "--class", SIG_CLASS, "--exempt", "em-dash",
            "--project-path", str(proto),
        )
        assert text_cp.returncode == 0, text_cp.stdout + text_cp.stderr
        assert "exempt: em-dash" in text_cp.stdout

    def test_all_without_class_is_usage_error_exit_2(self):
        """The skill may never drop the signature-move sweep to get past a
        usage error: `all` without --class fails closed (exit 2)."""
        cp = _run_cli("all", "--project-path", str(PROTO_PASS))
        assert cp.returncode == 2, cp.stdout + cp.stderr
        assert "signature-move" in cp.stderr

        cp_json = _run_cli("all", "--project-path", str(PROTO_PASS), "--json")
        assert cp_json.returncode == 2, cp_json.stdout + cp_json.stderr
        assert "signature-move" in cp_json.stdout + cp_json.stderr


# ════════════════════════════════════════════════════════════════════
# AC1 — call-site wiring: the generated skills instruct the exact call
# shape the parity fixtures exercise; the ISSUE-057 checkpoints survive.
# ════════════════════════════════════════════════════════════════════


class TestSweepCallSiteWiring:
    """AC1 wiring: the web skill's deterministic Phase 5.5 sweeps become
    one `verify_design_sweeps.py all --class` call site; mobile/desktop
    keep contract-shaped prose sweeps (K9) until the validator accepts
    non-HTML trees."""

    def test_generated_web_skill_contains_all_class_call_site(self):
        text = _generated("uiux")
        assert "scripts/verify_design_sweeps.py all --class" in text, (
            "skills/uiux/SKILL.md does not instruct the "
            "`verify_design_sweeps.py all --class` call site "
            "(SPEC-060 sweep wiring)"
        )
        assert "--exempt" in text, (
            "skills/uiux/SKILL.md does not wire recorded Brief overrides "
            "to the validator's --exempt flag (K2 ledger mapping)"
        )

    def test_web_design_sweeps_resolution_emits_the_call_site(self):
        frag = _fragment_resolver("design_sweeps_fragment")("uiux")
        assert "scripts/verify_design_sweeps.py all --class" in frag, (
            "the web {{DESIGN_SWEEPS}} resolution does not contain the "
            "validator call site (SPEC-060 Option A)"
        )

    @pytest.mark.parametrize("skill", ["mobile-uiux", "desktop-uiux"])
    def test_mobile_desktop_keep_contract_shaped_prose_sweeps(self, skill):
        text = _generated(skill)
        assert "AI Tell sweep" in text, (
            f"skills/{skill}/SKILL.md lost the model-executed AI Tell "
            f"sweep (K9: prose sweeps stay until the validator accepts "
            f"non-HTML trees)"
        )
        assert "Contrast sweep" in text, (
            f"skills/{skill}/SKILL.md lost the contrast sweep (K6)"
        )


class TestCheckpointInvocationsSurvive:
    """ISSUE-057 wiring: every checkpoint invocation line in the three
    generated skills survives the conversion — no existing gate weakened
    (AC1)."""

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    @pytest.mark.parametrize("phase", ["context", "philosophy", "system"])
    def test_checkpoint_invocation_survives_exactly_once(self, skill, phase):
        text = _generated(skill)
        line = f"bash scripts/checkpoint.sh --skill {skill} --phase {phase}"
        count = text.count(line)
        assert count == 1, (
            f"skills/{skill}/SKILL.md: expected exactly 1 occurrence of "
            f"{line!r}, found {count} — the ISSUE-057 checkpoint wiring "
            f"must survive the conversion"
        )


# ════════════════════════════════════════════════════════════════════
# AC3 — D-table absence guards (SPEC-060 delete-list D1-D8): everything
# else gone. Occurrence guards on actually-removed strings; every needle
# below was grep-verified PRESENT in its target file pre-conversion
# (mutation-tested guards, never phrasing blacklists).
# ════════════════════════════════════════════════════════════════════

# (delete-class, file relative to kit root, verbatim string that must be
# absent post-conversion). Grep evidence 2026-10-10: every needle occurs
# >= 1 time in its file today, so each guard is red and falsifiable now.
D_TABLE_ABSENCE: tuple[tuple[str, str, str], ...] = (
    # D1 — motion duration-band tables / band prose
    ("D1", "agents/uiux-developer.md",
     "Micro (hover, focus, color change): 100–150ms"),
    ("D1", "agents/mobile-uiux-developer.md",
     "Micro (press feedback, toggle): 80–120ms"),
    ("D1", "agents/desktop-uiux-developer.md",
     "Micro (hover feedback, toggle): 60–100ms"),
    ("D1", "skills/mobile-uiux/SKILL.md.tmpl",
     "micro 80-120ms to large 400-600ms"),
    ("D1", "skills/mobile-uiux/SKILL.md",
     "micro 80-120ms to large 400-600ms"),
    ("D1", "skills/desktop-uiux/SKILL.md.tmpl",
     "micro 60-100ms to large 300-500ms"),
    ("D1", "skills/desktop-uiux/SKILL.md",
     "micro 60-100ms to large 300-500ms"),
    # D2 — typography tutorials
    ("D2", "agents/uiux-developer.md", "Choose fonts that create TENSION"),
    ("D2", "agents/mobile-uiux-developer.md",
     "tighter modular scale than web (1.125 or 1.2 ratio)"),
    ("D2", "agents/desktop-uiux-developer.md",
     "JetBrains Mono, Fira Code, SF Mono, Cascadia Code"),
    # D3 — Expo dependency/config pins (replaced by the K10 boot gate)
    ("D3", "skills/mobile-uiux/SKILL.md.tmpl",
     "node_modules/expo/AppEntry.js"),
    ("D3", "skills/mobile-uiux/SKILL.md", "node_modules/expo/AppEntry.js"),
    ("D3", "agents/mobile-uiux-developer.md",
     "node_modules/expo/AppEntry.js"),
    ("D3", "skills/mobile-uiux/SKILL.md.tmpl",
     "react-native-reanimated/plugin"),
    ("D3", "agents/mobile-uiux-developer.md",
     "react-native-reanimated/plugin"),
    ("D3", "skills/mobile-uiux/SKILL.md.tmpl", "Expo project setup check"),
    ("D3", "skills/mobile-uiux/SKILL.md", "Expo project setup check"),
    ("D3", "skills/mobile-uiux/SKILL.md.tmpl", "MUST use `React.memo`"),
    ("D3", "agents/mobile-uiux-developer.md",
     "`React.memo` on list item components"),
    # D4 — Electron perf prescriptions (replaced by the K10 boot gate)
    ("D4", "skills/desktop-uiux/SKILL.md.tmpl", "500KB gzip"),
    ("D4", "skills/desktop-uiux/SKILL.md", "500KB gzip"),
    ("D4", "agents/desktop-uiux-developer.md", "500KB gzip"),
    ("D4", "skills/desktop-uiux/SKILL.md.tmpl", "manualChunks"),
    ("D4", "agents/desktop-uiux-developer.md", "manualChunks"),
    ("D4", "skills/desktop-uiux/SKILL.md.tmpl", "utilityProcess"),
    ("D4", "agents/desktop-uiux-developer.md", "utilityProcess"),
    ("D4", "skills/desktop-uiux/SKILL.md.tmpl", "`will-change` budget"),
    ("D4", "agents/desktop-uiux-developer.md", "max 5 concurrent"),
    ("D4", "skills/desktop-uiux/SKILL.md.tmpl", "MUST use `React.memo`"),
    # D5 — confidence-rating ritual (ISSUE-059 class, 060-owned; the
    # fragments.py chunk guard lives in tests/test_design_fragments.py and
    # the whitelist in tests/test_scaffolding_residue.py is emptied)
    ("D5", "agents/uiux-developer.md", "**Confidence rating**"),
    ("D5", "agents/mobile-uiux-developer.md", "**Confidence rating**"),
    ("D5", "agents/desktop-uiux-developer.md", "**Confidence rating**"),
    # D7 — mood-board craft essays
    ("D7", "agents/uiux-developer.md", "### Spatial Composition"),
    ("D7", "agents/mobile-uiux-developer.md", "### Spatial Composition"),
    ("D7", "agents/desktop-uiux-developer.md", "### Spatial Composition"),
    ("D7", "agents/uiux-developer.md", "### Backgrounds & Depth"),
    ("D7", "agents/desktop-uiux-developer.md", "### Keyboard (deep)"),
    # D8 — GPU-composited trivia and scroll-driven recipes
    ("D8", "skills/uiux/SKILL.md.tmpl", "Do NOT list `box-shadow`"),
    ("D8", "skills/uiux/SKILL.md", "Do NOT list `box-shadow`"),
    ("D8", "agents/uiux-developer.md", "is NOT GPU-composited"),
    ("D8", "agents/uiux-developer.md", "animation-timeline: scroll()"),
)


class TestDeleteTableAbsence:
    """AC3: everything else gone — every D-table prescription class is
    deleted, asserted via verbatim strings copied from the pre-conversion
    files (no orphaned MUSTs without an owner gate)."""

    @pytest.mark.parametrize(
        ("d_class", "rel_path", "needle"),
        D_TABLE_ABSENCE,
        ids=[f"{d}:{p}:{s[:28]}" for d, p, s in D_TABLE_ABSENCE],
    )
    def test_deleted_prescription_absent(self, d_class, rel_path, needle):
        text = _read(rel_path)
        assert needle not in text, (
            f"{rel_path} still contains the SPEC-060 {d_class} deletion "
            f"target {needle!r} — the model-absorbed prescription must be "
            f"deleted, not kept as an orphaned MUST"
        )

    @pytest.mark.parametrize("agent_rel", AGENT_FILES)
    def test_d6_webfetch_tool_grant_removed(self, agent_rel):
        """D6: the WebFetch grant has no call site (the skills already ban
        WebFetch extraction) — tool grants map to real call sites, so the
        grant is dropped from the agents' frontmatter tools: line."""
        text = _read(agent_rel)
        assert text.startswith("---"), f"{agent_rel} has no frontmatter"
        frontmatter = text.split("---", 2)[1]
        m = re.search(r"^tools:\s*(.+)$", frontmatter, re.MULTILINE)
        assert m, f"{agent_rel} has no tools: frontmatter line"
        tools = [t.strip() for t in m.group(1).split(",")]
        assert "WebFetch" not in tools, (
            f"{agent_rel} still grants WebFetch (SPEC-060 D6: no call "
            f"site — the skills ban WebFetch extraction)"
        )

    def test_d7_command_palette_contract_survives_the_keyboard_deletion(
        self,
    ):
        """D7 scope boundary: deleting the desktop §Keyboard (deep)
        tutorial must NOT take the Command-Palette contract with it."""
        assert "Command Palette" in _read("agents/desktop-uiux-developer.md")
        assert "Command Palette" in _generated("desktop-uiux")

    def test_d8_reduced_motion_requirement_survives_as_contract_line(self):
        """D8 scope boundary: the prefers-reduced-motion how-to essay is
        deleted but the requirement survives as one contract line owned by
        the Phase 5.5 check (web skill or web agent)."""
        combined = _generated("uiux") + _read("agents/uiux-developer.md")
        assert "prefers-reduced-motion" in combined, (
            "the reduced-motion requirement vanished entirely — D8 keeps "
            "one contract line"
        )


# ════════════════════════════════════════════════════════════════════
# AC3 — K-table trigger pins: every retained prescription names its
# depreciation trigger.
# ════════════════════════════════════════════════════════════════════


class TestKeepTableTriggers:
    """AC3: every retained prescription names its depreciation trigger —
    the trigger phrases from the SPEC-060 keep-list are pinned in the
    artifacts the next editor reads."""

    @pytest.mark.parametrize("skill", ["mobile-uiux", "desktop-uiux"])
    def test_k9_trigger_in_mobile_desktop_sweep_resolutions(self, skill):
        """K9: mobile/desktop prose sweeps are script-owned the day the
        validator accepts non-HTML trees — the trigger line is embedded in
        the {{DESIGN_SWEEPS}} resolution so the next editor sees it."""
        frag = _fragment_resolver("design_sweeps_fragment")(skill)
        assert "accepts non-HTML prototype trees" in frag, (
            f"{{{{DESIGN_SWEEPS}}}} resolution for {skill} does not carry "
            f"the K9 depreciation trigger"
        )
        assert "verify_design_sweeps.py" in frag, (
            f"{{{{DESIGN_SWEEPS}}}} resolution for {skill} does not name "
            f"the validator the K9 trigger hands over to"
        )

    @pytest.mark.parametrize("skill", ["mobile-uiux", "desktop-uiux"])
    def test_k9_trigger_in_generated_skills(self, skill):
        assert "accepts non-HTML prototype trees" in _generated(skill), (
            f"skills/{skill}/SKILL.md does not carry the K9 depreciation "
            f"trigger line"
        )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_k3_per_tell_deletion_trigger(self, skill):
        """K3: per tell, two consecutive design runs with zero sweep hits
        delete that prose line — the rule must be stated where the tells
        live."""
        assert "two consecutive design runs" in _generated(skill), (
            f"skills/{skill}/SKILL.md does not name the K3/K4 per-rule "
            f"depreciation trigger (two consecutive zero-hit design runs)"
        )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_k4_mechanics_sweep_promotion_trigger(self, skill):
        """K4/K5: the mechanics block is replaced by a validator call the
        day verify_design_sweeps.py grows a mechanics sweep."""
        assert "grows a mechanics sweep" in _generated(skill), (
            f"skills/{skill}/SKILL.md does not name the K4 mechanics-sweep "
            f"promotion trigger"
        )

    @pytest.mark.parametrize("skill", UIUX_SKILLS)
    def test_k2_cluster_list_keeps_its_dating_note(self, skill):
        """K2: the banned-cluster list carries its own dating note; the
        ledger ('Brief overrides:') and self-similarity check are
        contract."""
        text = _generated(skill)
        assert "what everyone is producing this year" in text
        assert "Brief overrides:" in text

    def test_k8_electron_security_pins_survive_as_contract_lines(self):
        """K8: contextIsolation: true / nodeIntegration: false are named
        contract lines in the desktop skill AND agent — security
        invariants, not craft; no depreciation trigger."""
        for label, text in (
            ("skills/desktop-uiux/SKILL.md", _generated("desktop-uiux")),
            (
                "agents/desktop-uiux-developer.md",
                _read("agents/desktop-uiux-developer.md"),
            ),
        ):
            assert "contextIsolation: true" in text, (
                f"{label} lost the contextIsolation: true security pin (K8)"
            )
            assert "nodeIntegration: false" in text, (
                f"{label} lost the nodeIntegration: false security pin (K8)"
            )

    def test_k10_mobile_boot_gate_contract(self):
        """K10: the runnability contract replaces the D3 pin lists — the
        prototype must boot; any pin the boot gate catches is never
        re-documented."""
        text = _generated("mobile-uiux")
        assert "npm install && npx expo install --fix" in text, (
            "skills/mobile-uiux/SKILL.md lost the Expo install step of the "
            "K10 boot gate"
        )
        assert "npx expo start" in text, (
            "skills/mobile-uiux/SKILL.md lost the Expo run instruction"
        )
        assert "must boot" in text, (
            "skills/mobile-uiux/SKILL.md does not state the K10 boot-gate "
            "contract (the prototype must boot on simulator)"
        )

    def test_k10_desktop_boot_gate_contract(self):
        text = _generated("desktop-uiux")
        assert "npm run dev" in text, (
            "skills/desktop-uiux/SKILL.md lost the Electron dev-run step "
            "of the K10 boot gate"
        )
        assert "must launch" in text, (
            "skills/desktop-uiux/SKILL.md does not state the K10 boot-gate "
            "contract (`npm run dev` must launch)"
        )

    def test_k5_input_state_rules_survive(self):
        """K5: the 8-state input rules stay, owned by the Phase 5.5
        mechanics sweep (deletion trigger shared with K4)."""
        assert "constant `border-width`" in _generated("uiux")
        assert "constant `border-width`" in _generated("desktop-uiux")
        assert "constant `borderWidth`" in _generated("mobile-uiux")
