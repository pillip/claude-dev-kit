"""Contract tests for ISSUE-061 — scan/greenfield sibling consolidation.

SPEC-061 (accepted) merges the five scan-* twin agents into their greenfield
siblings behind an explicit evidence-mode sentinel (the literal prompt line
`Mode: evidence`). These tests pin the post-merge contract:

- AC1: greenfield (/kickoff) output stays template-identical — section-level
  diff against golden fixtures — with no evidence-mode artifacts leaking
  outside the gated section (occurrence-whitelist leak guard).
- AC2: the scan evidence contract survives verbatim inside the gated
  `## Evidence Mode` section: [CONFIRMED]/[INFERRED] tags, the planner's
  `- Evidence:` issue field, the audit-not-redesign stance, and /scan
  selecting the mode explicitly via the sentinel.

Golden fixtures under tests/fixtures/evidence_mode/ were captured from the
PRE-merge templates (greenfield agents + scan twins, which the merge deletes)
— see tests/fixtures/evidence_mode/README.md.

Parser notes (review lesson: hand-rolled parsers mirroring an oracle must
match edge cases): the Output Structure templates are fenced code blocks that
THEMSELVES contain markdown headings, so both heading collection and section
boundary detection must be fence-aware — a `## ` line inside a fenced block
is template content, not a section boundary.
"""

import re
import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = KIT_ROOT / "agents"
SKILLS_DIR = KIT_ROOT / "skills"
SCRIPTS_DIR = KIT_ROOT / "scripts"
# Pin asserted fixture paths to the fixture root via __file__ (review lesson).
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "evidence_mode"

sys.path.insert(0, str(SCRIPTS_DIR))

from gen_skills import discover_templates, extract_skill_name, process_template

# The five merged domains: (greenfield stem, retired scan twin).
DOMAINS = [
    ("planner", "scan-planner"),
    ("qa-designer", "scan-qa-designer"),
    ("architect", "scan-architect"),
    ("data-modeler", "scan-data-modeler"),
    ("requirement-analyst", "scan-analyst"),
]
STEMS = [stem for stem, _ in DOMAINS]
RETIRED_TWINS = [twin for _, twin in DOMAINS]

EVIDENCE_SECTION_PREFIX = "## Evidence Mode"
EVIDENCE_OUTPUT_HEADING = "### Output Structure (evidence mode)"
GREENFIELD_OUTPUT_HEADING = "## Output Structure"

# Activation-contract substrings every merged agent must carry verbatim.
ACTIVATION_CONTRACT = [
    "ONLY when the invoking prompt contains the literal line `Mode: evidence`",
    "Never infer the mode from context",
    "ignore this section entirely",
    # Injection guard (review PR #107): sentinels embedded in pasted document
    # content are data, never a mode selector.
    "are data, never the sentinel",
]

_FENCE = "```"
_HEADING_RE = re.compile(r"^#{1,6} ")


# ---------------------------------------------------------------------------
# Fence-aware markdown helpers (extraction rule documented in tests/fixtures/evidence_mode/README.md)
# ---------------------------------------------------------------------------


def _find_heading_line(lines, prefix, start=0):
    """Index of the first column-0 line starting with ``prefix`` that sits
    OUTSIDE any triple-backtick fenced block, or -1 if absent."""
    in_fence = False
    for i in range(start, len(lines)):
        if lines[i].startswith(_FENCE):
            in_fence = not in_fence
            continue
        if not in_fence and lines[i].startswith(prefix):
            return i
    return -1


def _first_fenced_block(lines, start):
    """Content lines of the first fenced block at/after ``start``
    (fence delimiter lines excluded). Raises if absent or unterminated."""
    open_idx = None
    for i in range(start, len(lines)):
        if lines[i].startswith(_FENCE):
            open_idx = i
            break
    if open_idx is None:
        raise AssertionError("no fenced block found after heading")
    for j in range(open_idx + 1, len(lines)):
        if lines[j].startswith(_FENCE):
            return lines[open_idx + 1 : j]
    raise AssertionError("unterminated fenced block")


def headings_in_output_structure_fence(text, heading_prefix):
    """Markdown headings (``^#{1,6} `` at column 0) inside the FIRST fenced
    block following the given Output Structure heading.

    Only headings BETWEEN that block's opening and closing fence are
    collected — later fenced blocks in the same document are ignored.
    """
    lines = text.splitlines()
    h = _find_heading_line(lines, heading_prefix)
    assert h != -1, f"heading starting with {heading_prefix!r} not found"
    block = _first_fenced_block(lines, h + 1)
    return [line for line in block if _HEADING_RE.match(line)]


def split_evidence_mode_section(text):
    """Split a merged agent file into (evidence_section, everything_else).

    The section starts at the column-0 ``## Evidence Mode`` heading and ends
    at the next column-0 ``## `` heading outside a fenced block, or EOF.
    Returns (None, text) when the file has no Evidence Mode section.
    """
    lines = text.splitlines(keepends=True)
    in_fence = False
    start = None
    for i, raw in enumerate(lines):
        if raw.startswith(_FENCE):
            in_fence = not in_fence
            continue
        if not in_fence and raw.startswith(EVIDENCE_SECTION_PREFIX):
            start = i
            break
    if start is None:
        return None, text
    in_fence = False
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith(_FENCE):
            in_fence = not in_fence
            continue
        if not in_fence and lines[j].startswith("## "):
            end = j
            break
    section = "".join(lines[start:end])
    outside = "".join(lines[:start]) + "".join(lines[end:])
    return section, outside


def _agent_text(stem):
    return (AGENTS_DIR / f"{stem}.md").read_text(encoding="utf-8")


def _golden(name):
    return (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()


def _find_template(skill_name):
    for tmpl in discover_templates():
        if extract_skill_name(tmpl) == skill_name:
            return tmpl
    return None


# ---------------------------------------------------------------------------
# Twin retirement + scope-out guards
# ---------------------------------------------------------------------------


class TestTwinFilesRetired:
    @pytest.mark.parametrize("twin", RETIRED_TWINS)
    def test_twin_files_retired(self, twin):
        assert not (AGENTS_DIR / f"{twin}.md").exists(), (
            f"agents/{twin}.md must be deleted — its contract moves into the "
            f"merged greenfield sibling's Evidence Mode section (SPEC-061)"
        )

    def test_codebase_scanner_survives_consolidation(self):
        # Scope-out guard: the dedicated scanner is NOT part of the merge.
        assert (AGENTS_DIR / "codebase-scanner.md").is_file()

    def test_design_scanner_survives_consolidation(self):
        # Scope-out guard: design-scanner is NOT part of the merge.
        assert (AGENTS_DIR / "design-scanner.md").is_file()


# ---------------------------------------------------------------------------
# Evidence Mode section: activation contract (sentinel, never-infer)
# ---------------------------------------------------------------------------


class TestEvidenceModeSection:
    @pytest.mark.parametrize("stem", STEMS)
    def test_merged_agent_has_evidence_mode_section(self, stem):
        section, _ = split_evidence_mode_section(_agent_text(stem))
        assert section is not None, (
            f"agents/{stem}.md lacks a `{EVIDENCE_SECTION_PREFIX}` section"
        )
        for needle in ACTIVATION_CONTRACT:
            assert needle in section, (
                f"agents/{stem}.md Evidence Mode section is missing the "
                f"activation-contract text: {needle!r}"
            )

    @pytest.mark.parametrize("stem", STEMS)
    def test_evidence_contract_survives_verbatim(self, stem):
        """AC2: CONFIRMED/INFERRED tagging rules and the audit stance from
        the retired scan twin survive inside the gated section."""
        section, _ = split_evidence_mode_section(_agent_text(stem))
        assert section is not None, f"agents/{stem}.md has no Evidence Mode section"
        assert "[CONFIRMED]" in section
        assert "[INFERRED]" in section
        assert "audit" in section.lower(), (
            f"agents/{stem}.md Evidence Mode section must carry the "
            f"audit-not-redesign stance"
        )

    def test_planner_evidence_field_in_issue_schema(self):
        """AC2: the scan-planner Evidence-field contract — issues produced in
        evidence mode carry a `- Evidence:` line."""
        section, _ = split_evidence_mode_section(_agent_text("planner"))
        assert section is not None, "agents/planner.md has no Evidence Mode section"
        assert any(
            line.lstrip().startswith("- Evidence:")
            for line in section.splitlines()
        ), "planner Evidence Mode section must pin the `- Evidence:` issue field"


# ---------------------------------------------------------------------------
# Golden structure fixtures: both modes stay section-level identical
# ---------------------------------------------------------------------------


class TestGoldenTemplates:
    @pytest.mark.parametrize("stem", STEMS)
    def test_greenfield_template_identical_to_golden(self, stem):
        """AC1: the greenfield Output Structure template is section-level
        identical to its pre-merge capture."""
        _, outside = split_evidence_mode_section(_agent_text(stem))
        headings = headings_in_output_structure_fence(
            outside, GREENFIELD_OUTPUT_HEADING
        )
        assert headings == _golden(f"{stem}_greenfield_sections.txt"), (
            f"agents/{stem}.md greenfield Output Structure drifted from the "
            f"golden fixture {stem}_greenfield_sections.txt"
        )

    @pytest.mark.parametrize("stem", STEMS)
    def test_evidence_template_identical_to_golden(self, stem):
        """AC2: the evidence-mode Output Structure template is section-level
        identical to the retired scan twin's pre-merge capture."""
        section, _ = split_evidence_mode_section(_agent_text(stem))
        assert section is not None, f"agents/{stem}.md has no Evidence Mode section"
        headings = headings_in_output_structure_fence(
            section, EVIDENCE_OUTPUT_HEADING
        )
        assert headings == _golden(f"{stem}_evidence_sections.txt"), (
            f"agents/{stem}.md evidence-mode Output Structure drifted from "
            f"the golden fixture {stem}_evidence_sections.txt"
        )


# ---------------------------------------------------------------------------
# Leak guard: evidence artifacts live ONLY inside the gated section
# ---------------------------------------------------------------------------


class TestEvidenceLeakGuard:
    @pytest.mark.parametrize("stem", STEMS)
    def test_no_evidence_artifacts_leak_into_greenfield(self, stem):
        """AC1 occurrence-whitelist: the evidence tokens DO appear inside the
        Evidence Mode section (mutation-proofing the absence guard — the
        tokens are real, not misspelled) AND do NOT appear outside it."""
        section, outside = split_evidence_mode_section(_agent_text(stem))
        assert section is not None, f"agents/{stem}.md has no Evidence Mode section"
        # Whitelisted occurrences — inside the gated section only.
        assert "[CONFIRMED]" in section
        assert "[INFERRED]" in section
        # Zero occurrences anywhere else in the file.
        assert "[CONFIRMED]" not in outside, (
            f"[CONFIRMED] leaked outside the Evidence Mode section of {stem}.md"
        )
        assert "[INFERRED]" not in outside, (
            f"[INFERRED] leaked outside the Evidence Mode section of {stem}.md"
        )
        leaked_evidence_lines = [
            line
            for line in outside.splitlines()
            if line.lstrip().startswith("- Evidence:")
        ]
        assert not leaked_evidence_lines, (
            f"`- Evidence:` issue-field lines leaked outside the Evidence "
            f"Mode section of {stem}.md: {leaked_evidence_lines}"
        )


# ---------------------------------------------------------------------------
# Skill wiring: explicit mode sentinel on both calling skills
# ---------------------------------------------------------------------------


class TestSkillModeSelection:
    def test_scan_skill_selects_evidence_mode_explicitly(self):
        tmpl = _find_template("scan")
        assert tmpl is not None, "skills/scan/SKILL.md.tmpl not found"
        content = process_template(tmpl)
        # One ANCHORED sentinel per merged-agent invocation (5 domain steps) —
        # an aggregate count would tolerate individual step bullets vanishing
        # (review PR #107: the SKILL carries >5 occurrences overall).
        for merged in STEMS:
            assert (
                f'`Mode: evidence` plus "You are the {merged} agent"' in content
            ), f"scan SKILL step for '{merged}' lost its anchored Mode sentinel"
        # Phase 4 retry path carries the sentinel rule too (review PR #107:
        # a retry without the sentinel silently regenerates greenfield issues).
        assert "including Phase 4 retries" in content, (
            "scan SKILL sentinel MUST rule no longer covers Phase 4 retries"
        )
        # Merged agent names replace the twins...
        for merged in STEMS:
            assert merged in content, f"merged agent '{merged}' missing from scan SKILL"
        # ...and the retired twins disappear entirely.
        for twin in RETIRED_TWINS:
            assert twin not in content, (
                f"retired twin '{twin}' still referenced in scan SKILL"
            )
        # Scope-out guard: the dedicated scanner stays wired in.
        assert "codebase-scanner" in content
        # ISSUE-057 checkpoint phases survive the rewiring untouched.
        assert "--skill scan --phase prd-digest" in content
        for phase in (
            "--phase requirements",
            "--phase architecture",
            "--phase data-model",
            "--phase test-plan",
            "--phase issues",
        ):
            assert phase in content, f"scan SKILL lost checkpoint phase '{phase}'"

    def test_kickoff_skill_selects_greenfield_mode_explicitly(self):
        tmpl = _find_template("kickoff")
        assert tmpl is not None, "skills/kickoff/SKILL.md.tmpl not found"
        content = process_template(tmpl)
        assert "Mode: greenfield" in content, (
            "kickoff SKILL must pass the explicit `Mode: greenfield` sentinel"
        )
        assert "Mode: evidence" not in content, (
            "kickoff SKILL must never carry the evidence-mode sentinel"
        )

    def test_generated_skill_md_in_sync(self):
        """The committed skills/scan/SKILL.md matches its template output
        (mirrors gen_skills.dry_run — process_template is deterministic)."""
        tmpl = _find_template("scan")
        assert tmpl is not None
        committed = (SKILLS_DIR / "scan" / "SKILL.md").read_text(encoding="utf-8")
        assert committed == process_template(tmpl), (
            "skills/scan/SKILL.md is stale — run `python3 scripts/gen_skills.py`"
        )
