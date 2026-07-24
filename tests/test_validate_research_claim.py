import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_research_claim as v  # noqa: E402


def _write_snapshot(
    refs: Path,
    slug: str,
    html: str,
    *,
    published_at: str | None = None,
    source_url: str = "https://example.com/x",
) -> None:
    refs.mkdir(parents=True, exist_ok=True)
    (refs / f"{slug}.html").write_text(html, encoding="utf-8")
    meta = {
        "source_url": source_url,
        "slug": slug,
        "accessed_at": "2026-06-18T12:00:00+00:00",
        "published_at": published_at,
        "backend": "test",
        "byte_count": len(html.encode("utf-8")),
    }
    (refs / f"{slug}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


class TestVerdicts:
    def test_ok_when_quote_present_and_fresh(self, tmp_path):
        _write_snapshot(
            tmp_path,
            "example-com-x",
            "<html>… global TAM is $12.4B in 2025 …</html>",
            published_at="2026-01-01",
        )
        claim = {
            "quote": "global TAM is $12.4B in 2025",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is True
        assert verdict.code == "ok"

    def test_quote_missing_fails_with_snapshot_path(self, tmp_path):
        _write_snapshot(
            tmp_path, "example-com-x", "<html>nothing matching</html>"
        )
        claim = {
            "quote": "TAM was $99B in 2025",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is False
        assert verdict.code == "quote_missing"
        assert "example-com-x.html" in verdict.reason

    def test_snapshot_absent_fails_clearly(self, tmp_path):
        claim = {
            "quote": "anything",
            "source_url": "https://example.com/missing",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is False
        assert verdict.code == "snapshot_absent"
        assert "capture_source.py" in verdict.reason

    def test_stale_when_published_outside_window(self, tmp_path):
        # 400-day gap with default 365-day window → stale
        _write_snapshot(
            tmp_path,
            "example-com-x",
            "<html>… known number 7 …</html>",
            published_at="2025-05-15",  # ~400 days before accessed_at below
        )
        claim = {
            "quote": "known number 7",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is False
        assert verdict.code == "stale"
        assert "before accessed_at" in verdict.reason

    def test_inside_window_not_stale(self, tmp_path):
        # 11 months gap < 12-month default → ok
        _write_snapshot(
            tmp_path,
            "example-com-x",
            "<html>… fresh stat 42 …</html>",
            published_at="2025-07-20",
        )
        claim = {
            "quote": "fresh stat 42",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is True

    def test_claim_published_at_overrides_meta(self, tmp_path):
        _write_snapshot(
            tmp_path,
            "example-com-x",
            "<html>quote</html>",
            published_at="2010-01-01",  # very old per meta
        )
        # Claim overrides with a fresh date
        claim = {
            "quote": "quote",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
            "published_at": "2026-01-01",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is True

    def test_no_published_at_anywhere_passes(self, tmp_path):
        # When neither claim nor meta has published_at, stale check is skipped.
        # SPEC-018 trade-off: snapshot recency is a positive signal, absence is
        # not a failure — over-warn is the degraded-path's job, not here.
        _write_snapshot(tmp_path, "example-com-x", "<html>q</html>", published_at=None)
        claim = {
            "quote": "q",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is True

    def test_custom_max_age_tightens_window(self, tmp_path):
        _write_snapshot(
            tmp_path,
            "example-com-x",
            "<html>q</html>",
            published_at="2026-01-15",  # ~5 months before access
        )
        claim = {
            "quote": "q",
            "source_url": "https://example.com/x",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        # 180 days vs ~155 days gap → ok
        assert v.validate_claim(claim, tmp_path, max_age_days=180).ok is True
        # 90 days vs ~155 days gap → stale
        verdict = v.validate_claim(claim, tmp_path, max_age_days=90)
        assert verdict.code == "stale"


class TestBadInput:
    def test_missing_required_field(self, tmp_path):
        claim = {"source_url": "https://example.com/x", "accessed_at": "2026-06-18"}
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.code == "bad_input"
        assert "quote" in verdict.reason

    def test_unparseable_accessed_at(self, tmp_path):
        _write_snapshot(tmp_path, "example-com-x", "<html>q</html>")
        claim = {
            "quote": "q",
            "source_url": "https://example.com/x",
            "accessed_at": "yesterday lol",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.code == "bad_input"


class TestSlugOverride:
    def test_explicit_slug_used_when_provided(self, tmp_path):
        _write_snapshot(tmp_path, "custom-slug", "<html>q</html>")
        claim = {
            "quote": "q",
            "source_url": "https://different.example.com/path",
            "slug": "custom-slug",
            "accessed_at": "2026-06-18T12:00:00+00:00",
        }
        verdict = v.validate_claim(claim, tmp_path)
        assert verdict.ok is True


class TestCliEntrypoint:
    def test_main_exits_0_on_ok(self, tmp_path, monkeypatch, capsys):
        _write_snapshot(tmp_path, "example-com-x", "<html>quote here</html>")
        claim_file = tmp_path / "claim.json"
        claim_file.write_text(
            json.dumps(
                {
                    "quote": "quote here",
                    "source_url": "https://example.com/x",
                    "accessed_at": "2026-06-18T12:00:00+00:00",
                }
            )
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "validate_research_claim.py",
                "--claim-file",
                str(claim_file),
                "--references-dir",
                str(tmp_path),
            ],
        )
        code = v.main()
        out = capsys.readouterr().out
        assert code == 0
        assert json.loads(out)["verdict"] == "ok"

    def test_main_exits_1_on_quote_missing(self, tmp_path, monkeypatch, capsys):
        _write_snapshot(tmp_path, "example-com-x", "<html>different content</html>")
        claim_file = tmp_path / "claim.json"
        claim_file.write_text(
            json.dumps(
                {
                    "quote": "not in source",
                    "source_url": "https://example.com/x",
                    "accessed_at": "2026-06-18T12:00:00+00:00",
                }
            )
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "validate_research_claim.py",
                "--claim-file",
                str(claim_file),
                "--references-dir",
                str(tmp_path),
            ],
        )
        code = v.main()
        assert code == 1
        out = capsys.readouterr().out
        assert json.loads(out)["verdict"] == "quote_missing"
