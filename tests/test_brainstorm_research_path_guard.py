"""Structural guards for ISSUE-036 — /brainstorm degraded-path snapshot dir.

The degraded-path research-auditor invocation in the /brainstorm skill must
name the CANONICAL snapshot directory `docs/references/research/` as its
input — not the vague phrase "snapshot directory", which leaves the auditor
guessing where captured sources live.

NOTE: `docs/references/research/` already appears elsewhere in the file
(the NEVER-list line about Source traceability), so a whole-file substring
check would pass vacuously. The canonical-dir assertion is therefore scoped
to the research-auditor invocation line itself.

Guards both the template (the edit surface) and the generated SKILL.md
(the shipped artifact).
"""

from __future__ import annotations

from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_SNAPSHOT_DIR = "docs/references/research/"
AUDITOR_MARKER = "subagent_type: research-auditor"


def _auditor_lines(path: Path) -> list[str]:
    assert path.is_file(), f"missing expected file {path}"
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if AUDITOR_MARKER in ln]
    assert lines, (
        f"{path}: no line containing {AUDITOR_MARKER!r} found — the "
        "degraded-path research-auditor invocation is missing."
    )
    return lines


class TestResearchAuditorInputsNameCanonicalDir:
    def test_generated_skill_auditor_invocation_names_canonical_dir(self):
        path = KIT_ROOT / "skills" / "brainstorm" / "SKILL.md"
        for line in _auditor_lines(path):
            assert CANONICAL_SNAPSHOT_DIR in line, (
                f"{path}: the research-auditor invocation must pass the "
                f"canonical snapshot directory {CANONICAL_SNAPSHOT_DIR!r} "
                f"as its input, but the line reads: {line.strip()!r} "
                "(ISSUE-036)."
            )

    def test_skill_template_auditor_invocation_names_canonical_dir(self):
        path = KIT_ROOT / "skills" / "brainstorm" / "SKILL.md.tmpl"
        for line in _auditor_lines(path):
            assert CANONICAL_SNAPSHOT_DIR in line, (
                f"{path}: the research-auditor invocation must pass the "
                f"canonical snapshot directory {CANONICAL_SNAPSHOT_DIR!r} "
                f"as its input, but the line reads: {line.strip()!r} "
                "(ISSUE-036)."
            )


class TestNoVagueSnapshotDirectoryPhrase:
    def test_generated_skill_has_no_vague_snapshot_directory_phrase(self):
        path = KIT_ROOT / "skills" / "brainstorm" / "SKILL.md"
        assert path.is_file(), f"missing expected file {path}"
        text = path.read_text(encoding="utf-8")
        assert "snapshot directory" not in text, (
            f"{path}: the vague phrase 'snapshot directory' must not appear "
            f"— name the canonical dir {CANONICAL_SNAPSHOT_DIR!r} instead "
            "(ISSUE-036)."
        )

    def test_skill_template_has_no_vague_snapshot_directory_phrase(self):
        path = KIT_ROOT / "skills" / "brainstorm" / "SKILL.md.tmpl"
        assert path.is_file(), f"missing expected file {path}"
        text = path.read_text(encoding="utf-8")
        assert "snapshot directory" not in text, (
            f"{path}: the vague phrase 'snapshot directory' must not appear "
            f"— name the canonical dir {CANONICAL_SNAPSHOT_DIR!r} instead "
            "(ISSUE-036)."
        )
