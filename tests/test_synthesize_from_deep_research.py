import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import synthesize_from_deep_research as s  # noqa: E402


def _sample_payload(**overrides):
    base = {
        "title": "Business Analysis: AcmeWidget",
        "sections": [
            {
                "name": "Executive Summary",
                "claims": [
                    {
                        "text": "Go: niche viability is supported by 2 independent sources.",
                        "quote": "Annual spend in the segment grew 18% YoY",
                        "source_url": "https://gartner.example/r1",
                    }
                ],
            },
            {
                "name": "Market Analysis",
                "claims": [
                    {
                        "text": "TAM is in the $8-12B range.",
                        "quote": "TAM estimated at $8B to $12B for FY2025",
                        "source_url": "https://idc.example/r2",
                        "tags": ["range", "single-source"],
                    }
                ],
            },
            {"name": "Competitive Landscape", "claims": []},
            {"name": "Business Model", "claims": []},
            {"name": "Risks & Mitigations", "claims": []},
        ],
    }
    base.update(overrides)
    return base


class TestRender:
    def test_full_template_with_one_claim_per_section(self):
        out = s.render_bizanalysis(_sample_payload())
        assert "# Business Analysis: AcmeWidget" in out
        for section in s.BIZANALYSIS_SECTIONS:
            assert f"## {section}" in out
        assert "Annual spend in the segment grew 18% YoY" in out
        assert "https://gartner.example/r1" in out

    def test_empty_section_renders_no_data_literal(self):
        out = s.render_bizanalysis(_sample_payload())
        # Three empty sections in the sample payload — all must carry the literal
        assert out.count(s.NO_DATA_LINE) == 3
        # The literal must be exactly the SPEC-018 string
        assert s.NO_DATA_LINE.startswith("Data: not available")
        assert 're-run /deep-research' in s.NO_DATA_LINE

    def test_quote_preserved_verbatim_including_special_chars(self):
        payload = _sample_payload(
            sections=[
                {
                    "name": "Market Analysis",
                    "claims": [
                        {
                            "text": "Quoted growth.",
                            "quote": "Growth was 17.4% — driven by SMB churn down 8 bps",
                            "source_url": "https://a.example/x",
                        }
                    ],
                },
                {"name": "Executive Summary", "claims": []},
                {"name": "Competitive Landscape", "claims": []},
                {"name": "Business Model", "claims": []},
                {"name": "Risks & Mitigations", "claims": []},
            ]
        )
        out = s.render_bizanalysis(payload)
        # Verbatim: special chars (—, %, "bps") preserved
        assert "17.4% — driven by SMB churn down 8 bps" in out

    def test_tags_render_inline_before_quote(self):
        out = s.render_bizanalysis(_sample_payload())
        # "Market Analysis" claim carries [range] [single-source]
        assert "[range]" in out
        assert "[single-source]" in out

    def test_sections_rendered_in_canonical_order(self):
        # Even if input scrambles section order, output must match BIZANALYSIS_SECTIONS
        payload = {
            "title": "X",
            "sections": [
                {"name": "Risks & Mitigations", "claims": []},
                {"name": "Executive Summary", "claims": []},
                {"name": "Business Model", "claims": []},
                {"name": "Market Analysis", "claims": []},
                {"name": "Competitive Landscape", "claims": []},
            ],
        }
        out = s.render_bizanalysis(payload)
        positions = [out.index(f"## {sec}") for sec in s.BIZANALYSIS_SECTIONS]
        assert positions == sorted(positions)

    def test_brainstorm_landscape_mode_uses_only_existing_landscape(self):
        payload = {
            "title": None,
            "sections": [
                {
                    "name": "Existing Landscape",
                    "claims": [
                        {
                            "text": "Foo and Bar are direct competitors.",
                            "quote": "Foo serves SMB; Bar enterprise",
                            "source_url": "https://x.example/y",
                        }
                    ],
                }
            ],
        }
        out = s.render_brainstorm_landscape(payload)
        assert "## Existing Landscape" in out
        # bizanalysis section names must NOT appear
        assert "## Executive Summary" not in out
        assert "## Risks & Mitigations" not in out


class TestValidation:
    def test_missing_sections_field_raises(self):
        with pytest.raises(ValueError, match="sections"):
            s.render_bizanalysis({"title": "x"})

    def test_unknown_section_name_raises(self):
        payload = {
            "title": "x",
            "sections": [{"name": "Made-Up Section", "claims": []}],
        }
        with pytest.raises(ValueError, match="allowed set"):
            s.render_bizanalysis(payload)

    def test_claim_missing_quote_raises(self):
        payload = {
            "title": "x",
            "sections": [
                {
                    "name": "Market Analysis",
                    "claims": [
                        {"text": "no quote here", "source_url": "https://a.example/"}
                    ],
                }
            ],
        }
        with pytest.raises(ValueError, match="quote"):
            s.render_bizanalysis(payload)

    def test_claim_missing_source_url_raises(self):
        payload = {
            "title": "x",
            "sections": [
                {
                    "name": "Market Analysis",
                    "claims": [{"text": "x", "quote": "y"}],
                }
            ],
        }
        with pytest.raises(ValueError, match="source_url"):
            s.render_bizanalysis(payload)

    def test_duplicate_section_raises(self):
        payload = {
            "title": "x",
            "sections": [
                {"name": "Market Analysis", "claims": []},
                {"name": "Market Analysis", "claims": []},
            ],
        }
        with pytest.raises(ValueError, match="duplicated"):
            s.render_bizanalysis(payload)


class TestCli:
    def test_main_writes_to_out_file(self, tmp_path, monkeypatch):
        input_path = tmp_path / "input.json"
        input_path.write_text(json.dumps(_sample_payload()))
        out_path = tmp_path / "out.md"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "synthesize_from_deep_research.py",
                "--input",
                str(input_path),
                "--out",
                str(out_path),
            ],
        )
        code = s.main()
        assert code == 0
        rendered = out_path.read_text()
        assert "Business Analysis: AcmeWidget" in rendered

    def test_main_returns_2_on_invalid_payload(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"title": "x"}))
        monkeypatch.setattr(
            sys,
            "argv",
            ["synthesize_from_deep_research.py", "--input", str(bad)],
        )
        code = s.main()
        assert code == 2
        err = capsys.readouterr().err
        assert "Input validation failed" in err
