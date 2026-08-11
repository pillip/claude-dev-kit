"""Unit tests for scripts/validate_frontmatter.py — the release-gate frontmatter validator.

Covers the four fixture cases the gate must catch and the exit-code contract CI
relies on: valid frontmatter, malformed YAML, missing required keys, and
frontmatter NOT at byte 0 (the ISSUE-035 failure mode that silently drops every
field at runtime).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_frontmatter as vf


# ── Pure helpers ────────────────────────────────────────────────────


class TestFrontmatterExtraction:
    def test_valid_frontmatter_returns_block(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\nname: x\ndescription: y\n---\n# body\n", encoding="utf-8")
        block = vf._frontmatter(p)
        assert block is not None
        assert "name: x" in block

    def test_frontmatter_not_at_byte_0_returns_none(self, tmp_path):
        # ISSUE-035 failure mode: a leading blank line pushes '---' off byte 0.
        p = tmp_path / "SKILL.md"
        p.write_text("\n---\nname: x\ndescription: y\n---\n", encoding="utf-8")
        assert vf._frontmatter(p) is None

    def test_missing_closing_delimiter_returns_none(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\nname: x\ndescription: y\n", encoding="utf-8")
        assert vf._frontmatter(p) is None


class TestQuoted:
    def test_single_quoted(self):
        assert vf._quoted("'value'") is True

    def test_double_quoted(self):
        assert vf._quoted('"value"') is True

    def test_unquoted(self):
        assert vf._quoted("value") is False


class TestPatternErrors:
    def test_clean_scalars_have_no_errors(self):
        assert vf._pattern_errors("name: clean\ndescription: also clean\n") == []

    def test_unquoted_flow_sequence_is_flagged(self):
        errs = vf._pattern_errors("argument-hint: [a] [b]\n")
        assert any("flow-sequence" in e for e in errs)

    def test_unquoted_colon_space_is_flagged(self):
        errs = vf._pattern_errors("description: do X: then Y\n")
        assert any("': '" in e for e in errs)

    def test_quoted_value_is_not_flagged(self):
        assert vf._pattern_errors("description: 'do X: then Y'\n") == []


# ── main() exit-code contract ───────────────────────────────────────


def _write_skill(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


class TestMainExitCodes:
    def test_valid_frontmatter_exits_zero(self, tmp_path, monkeypatch, capsys):
        p = _write_skill(
            tmp_path,
            "skills/ok/SKILL.md",
            "---\nname: ok-skill\ndescription: A clean valid description\n---\n# Body\n",
        )
        monkeypatch.setattr(vf, "ROOT", tmp_path)
        monkeypatch.setattr(vf, "FILES", [str(p)])
        assert vf.main() == 0
        assert "OK" in capsys.readouterr().out

    def test_frontmatter_not_at_byte_0_exits_one(self, tmp_path, monkeypatch, capsys):
        p = _write_skill(
            tmp_path,
            "skills/late/SKILL.md",
            "\n---\nname: late\ndescription: pushed off byte 0\n---\n",
        )
        monkeypatch.setattr(vf, "ROOT", tmp_path)
        monkeypatch.setattr(vf, "FILES", [str(p)])
        assert vf.main() == 1
        assert "byte 0" in capsys.readouterr().err

    def test_malformed_yaml_exits_one(self, tmp_path, monkeypatch, capsys):
        pytest.importorskip("yaml")
        # Unclosed flow sequence → yaml.safe_load raises YAMLError.
        p = _write_skill(
            tmp_path,
            "skills/bad/SKILL.md",
            "---\nname: bad\ndescription: broken\ntags: [unclosed\n---\n",
        )
        monkeypatch.setattr(vf, "ROOT", tmp_path)
        monkeypatch.setattr(vf, "FILES", [str(p)])
        assert vf.main() == 1
        assert "YAML parse error" in capsys.readouterr().err

    def test_missing_required_key_exits_one(self, tmp_path, monkeypatch, capsys):
        pytest.importorskip("yaml")
        # Parses fine, but 'name' is absent → gate must reject.
        p = _write_skill(
            tmp_path,
            "skills/nokey/SKILL.md",
            "---\ndescription: has description but no name\n---\n",
        )
        monkeypatch.setattr(vf, "ROOT", tmp_path)
        monkeypatch.setattr(vf, "FILES", [str(p)])
        assert vf.main() == 1
        assert "dropped required key" in capsys.readouterr().err

    def test_all_clean_multiple_files_exit_zero(self, tmp_path, monkeypatch):
        files = [
            _write_skill(tmp_path, "skills/a/SKILL.md",
                         "---\nname: a\ndescription: first\n---\n"),
            _write_skill(tmp_path, "agents/b.md",
                         "---\nname: b\ndescription: second\n---\n"),
        ]
        monkeypatch.setattr(vf, "ROOT", tmp_path)
        monkeypatch.setattr(vf, "FILES", [str(f) for f in files])
        assert vf.main() == 0
