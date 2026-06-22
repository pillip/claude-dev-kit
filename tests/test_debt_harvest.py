"""Unit tests for scripts/debt_harvest.py."""

from pathlib import Path

from scripts.debt_harvest import harvest, parse_line, render_text


def test_parse_valid_marker_extracts_ceiling_and_trigger():
    m = parse_line(
        "# KIT-DEBT(ceiling=<=100 items, trigger=list grows unbounded): linear scan"
    )
    assert m is not None
    assert m["status"] == "ok"
    assert m["ceiling"] == "<=100 items"
    assert m["trigger"] == "list grows unbounded"
    assert m["description"] == "linear scan"


def test_parse_slash_comment_marker():
    m = parse_line("    // KIT-DEBT(ceiling=single region, trigger=multi-region): endpoint")
    assert m is not None
    assert m["status"] == "ok"
    assert m["trigger"] == "multi-region"


def test_marker_without_trigger_is_flagged_no_trigger():
    m = parse_line("# KIT-DEBT(ceiling=small input): no upgrade path here")
    assert m is not None
    assert m["status"] == "no-trigger"
    assert m["trigger"] is None
    assert m["ceiling"] == "small input"


def test_marker_without_params_is_malformed():
    m = parse_line("# KIT-DEBT: just a vague note")
    assert m is not None
    assert m["status"] == "malformed"


def test_line_without_marker_returns_none():
    assert parse_line("# a perfectly ordinary comment") is None
    assert parse_line("x = 1  # TODO: not a debt marker") is None


def test_harvest_clean_tree(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    entries = harvest(tmp_path)
    assert entries == []
    assert render_text(entries) == "No KIT-DEBT. Clean ledger."


def test_harvest_collects_and_locates_markers(tmp_path: Path):
    (tmp_path / "svc.py").write_text(
        "def f():\n"
        "    pass  # KIT-DEBT(ceiling=N<100, trigger=N grows): linear scan\n",
        encoding="utf-8",
    )
    (tmp_path / "web.js").write_text(
        "// KIT-DEBT(ceiling=one region): hardcoded url\n",
        encoding="utf-8",
    )
    entries = harvest(tmp_path)
    assert len(entries) == 2
    by_file = {e["file"]: e for e in entries}
    assert by_file["svc.py"]["line"] == 2
    assert by_file["svc.py"]["status"] == "ok"
    assert by_file["web.js"]["status"] == "no-trigger"
    text = render_text(entries)
    assert "no-trigger (silent-rot risk): 1" in text


def test_harvest_excludes_vendor_dirs(tmp_path: Path):
    vendor = tmp_path / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.js").write_text(
        "// KIT-DEBT(trigger=x): should be ignored\n", encoding="utf-8"
    )
    entries = harvest(tmp_path)
    assert entries == []


def test_harvest_skips_binary_files(tmp_path: Path):
    # A binary file containing the token bytes must not crash the walk.
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01KIT-DEBT\xff\xfe")
    (tmp_path / "ok.py").write_text(
        "# KIT-DEBT(ceiling=a, trigger=b): real one\n", encoding="utf-8"
    )
    entries = harvest(tmp_path)
    assert len(entries) == 1
    assert entries[0]["file"] == "ok.py"
