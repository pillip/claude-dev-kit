import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import capture_source  # noqa: E402


class TestSlugDerivation:
    def test_domain_only(self):
        assert capture_source.slug_from_url("https://example.com/") == "example-com"

    def test_path_included(self):
        slug = capture_source.slug_from_url("https://example.com/2025/report/full")
        assert "example-com" in slug
        assert "2025-report-full" in slug

    def test_query_string_ignored(self):
        slug = capture_source.slug_from_url("https://example.com/x?a=1&b=2")
        assert slug.startswith("example-com")
        # Query string should not bleed into the slug
        assert "a=1" not in slug

    def test_url_without_path(self):
        assert capture_source.slug_from_url("https://example.com") == "example-com"

    def test_empty_url_fallback(self):
        assert capture_source.slug_from_url("") == "src"


class TestPublishedAtExtraction:
    def test_open_graph_published_time(self):
        html = (
            '<html><head>'
            '<meta property="article:published_time" content="2025-03-01T10:00:00Z">'
            '</head></html>'
        )
        assert capture_source.extract_published_at(html) == "2025-03-01T10:00:00Z"

    def test_schema_org_date_published_via_itemprop(self):
        html = '<meta itemprop="datePublished" content="2025-04-02">'
        assert capture_source.extract_published_at(html) == "2025-04-02"

    def test_time_tag_datetime_attribute(self):
        html = '<time datetime="2025-05-05T12:00:00Z">May 5, 2025</time>'
        assert capture_source.extract_published_at(html) == "2025-05-05T12:00:00Z"

    def test_pubdate_meta_name(self):
        html = '<meta name="pubdate" content="2024-12-31">'
        assert capture_source.extract_published_at(html) == "2024-12-31"

    def test_no_meta_returns_none(self):
        html = "<html><body>Just text, no meta.</body></html>"
        assert capture_source.extract_published_at(html) is None

    def test_priority_open_graph_over_time_tag(self):
        # OpenGraph article:published_time is listed first in patterns, so when
        # both are present it should win — this prevents an unrelated <time>
        # later in the page from overriding the canonical published date.
        html = (
            '<meta property="article:published_time" content="2025-01-01T00:00:00Z">'
            '<time datetime="2024-06-01">old</time>'
        )
        assert capture_source.extract_published_at(html) == "2025-01-01T00:00:00Z"

    def test_case_insensitive_match(self):
        html = '<META PROPERTY="article:published_time" CONTENT="2025-07-07">'
        assert capture_source.extract_published_at(html) == "2025-07-07"


class TestWriteOutputs:
    def test_writes_html_and_meta(self, tmp_path):
        html_path, meta_path = capture_source.write_outputs(
            html="<html>hi</html>",
            backend="urllib",
            url="https://example.com/x",
            slug="example-com-x",
            out_dir=tmp_path,
        )
        assert html_path.read_text() == "<html>hi</html>"
        meta = json.loads(meta_path.read_text())
        assert meta["source_url"] == "https://example.com/x"
        assert meta["slug"] == "example-com-x"
        assert meta["backend"] == "urllib"
        assert meta["byte_count"] == len("<html>hi</html>".encode("utf-8"))
        assert meta["published_at"] is None  # no meta tags in source
        # accessed_at is an ISO-8601 timestamp
        assert "T" in meta["accessed_at"]

    def test_extracted_published_at_recorded(self, tmp_path):
        html = '<meta property="article:published_time" content="2025-06-06T00:00:00Z">'
        _, meta_path = capture_source.write_outputs(
            html=html,
            backend="playwright",
            url="https://example.com/post",
            slug="example-com-post",
            out_dir=tmp_path,
        )
        meta = json.loads(meta_path.read_text())
        assert meta["published_at"] == "2025-06-06T00:00:00Z"

    def test_published_override_wins_over_meta(self, tmp_path):
        html = '<meta property="article:published_time" content="2025-01-01">'
        _, meta_path = capture_source.write_outputs(
            html=html,
            backend="urllib",
            url="https://example.com/p",
            slug="p",
            out_dir=tmp_path,
            published_override="2026-12-31",
        )
        meta = json.loads(meta_path.read_text())
        assert meta["published_at"] == "2026-12-31"


class TestCliErrors:
    def test_main_rejects_non_http_url(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["capture_source.py", "ftp://example.com/"])
        code = capture_source.main()
        assert code == 2
        err = capsys.readouterr().err
        assert "valid http(s) URL" in err

    def test_main_returns_3_when_no_backend(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(capture_source, "try_playwright", lambda url: None)
        monkeypatch.setattr(capture_source, "try_chrome", lambda url: None)
        monkeypatch.setattr(capture_source, "try_urllib", lambda url: None)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "capture_source.py",
                "https://example.com/",
                "--out-dir",
                str(tmp_path / "out"),
            ],
        )
        code = capture_source.main()
        assert code == 3
        err = capsys.readouterr().err
        assert "no fetch backend" in err
