"""Unit tests for scripts/capture_reference.py."""

import pytest

from scripts.capture_reference import main, slug_from_url


class TestSlugFromUrl:
    @pytest.mark.parametrize(
        ("url", "expected_contains"),
        [
            ("https://linear.app/", "linear-app"),
            ("https://linear.app/method", "linear-app-method"),
            ("https://example.com/path/to/page", "example-com-path-to-page"),
            ("https://a.b.c.com/", "a-b-c-com"),
        ],
    )
    def test_derives_slug(self, url: str, expected_contains: str):
        slug = slug_from_url(url)
        assert expected_contains in slug

    def test_strips_trailing_dashes(self):
        slug = slug_from_url("https://example.com////")
        assert not slug.endswith("-")

    def test_caps_length(self):
        long_path = "/" + "a" * 200
        slug = slug_from_url(f"https://example.com{long_path}")
        assert len(slug) <= 80


class TestMainCli:
    def test_rejects_non_http_url(self, capsys: pytest.CaptureFixture):
        rc = main(["ftp://example.com"])
        assert rc == 2
        assert "http://" in capsys.readouterr().err

    def test_rejects_bad_viewport(self, capsys: pytest.CaptureFixture):
        # URL is well-formed but viewport is garbage — should fail before any backend call.
        rc = main(["https://example.com", "--viewport", "garbage"])
        assert rc == 2
        assert "viewport" in capsys.readouterr().err

    def test_no_backend_returns_3(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        capsys: pytest.CaptureFixture,
    ):
        # Stub both backends to fail; assert we get the install-instructions error
        # without actually launching a browser.
        from scripts import capture_reference

        monkeypatch.setattr(capture_reference, "try_playwright", lambda *a, **kw: False)
        monkeypatch.setattr(capture_reference, "try_chrome", lambda *a, **kw: False)

        out = tmp_path / "ref.png"
        rc = main(["https://example.com", "--out", str(out)])
        assert rc == 3
        err = capsys.readouterr().err
        assert "no screenshot backend" in err
        assert "image paths directly" in err  # skip path is documented

    def test_playwright_success_writes_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        capsys: pytest.CaptureFixture,
    ):
        from scripts import capture_reference

        out = tmp_path / "out.png"

        def fake_playwright(url, target, viewport):
            target.write_bytes(b"\x89PNG\r\n\x1a\n")  # 8-byte PNG signature stub
            return True

        monkeypatch.setattr(capture_reference, "try_playwright", fake_playwright)
        monkeypatch.setattr(capture_reference, "try_chrome", lambda *a, **kw: False)

        rc = main(["https://example.com", "--out", str(out)])
        assert rc == 0
        assert out.exists()
        assert "playwright" in capsys.readouterr().out
