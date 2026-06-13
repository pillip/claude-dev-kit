"""Unit tests for scripts/validate_spec.py."""

from pathlib import Path

import pytest

from scripts.validate_spec import is_measurable_tradeoff, parse_spec, validate


def _spec(
    options: list[tuple[str, str, str]] | None = None,
    chosen: str = "A",
    title: str = "SPEC-007: Pick storage layer",
    linked: str = "ISSUE-007",
    status: str = "draft",
    date: str = "2026-06-13",
    omit_section: str | None = None,
) -> str:
    """Build a SPEC markdown string.

    options: list of (letter, name, tradeoff)
    omit_section: if set, that ## section is missing from output (for negative tests)
    """
    if options is None:
        options = [
            ("A", "Postgres", "+20% write latency, -1 service dep"),
            ("B", "DynamoDB", "+3 days impl, -50ms p99 read"),
        ]
    sections = {
        "Problem": "Storage layer choice forces a one-way decision.",
        "Context": "Current API is read-heavy; latency budget is 100ms p99.",
        "Options": "\n".join(
            f"### Option {l}: {n}\n- **Approach**: x\n- **Pros**:\n  - p\n- **Cons**:\n  - c\n- **Trade-off**: {t}\n"
            for l, n, t in options
        ),
        "Decision": f"**Chosen: Option {chosen}**\n\nBecause trade-off tipped it.",
        "Trade-offs Accepted": "- Acceptance",
        "Migration": "1. step",
        "Rollback": "Revert the schema.",
        "Open Questions": "- [ ] q",
    }
    if omit_section and omit_section in sections:
        del sections[omit_section]

    body = f"# {title}\n\n> Linked Issue: {linked}\n> Status: `{status}`\n> Date: {date}\n\n"
    for name, content in sections.items():
        body += f"## {name}\n\n{content}\n\n"
    return body


class TestParseSpec:
    def test_extracts_title_and_metadata(self):
        spec = parse_spec(_spec())
        assert spec["title"] == "SPEC-007"
        assert spec["linked_issue"] == "ISSUE-007"
        assert spec["status"] == "draft"
        assert spec["date"] == "2026-06-13"

    def test_extracts_options(self):
        spec = parse_spec(_spec())
        assert len(spec["options"]) == 2
        assert spec["options"][0]["letter"] == "A"
        assert spec["options"][0]["name"] == "Postgres"
        assert "+20%" in spec["options"][0]["tradeoff"]

    def test_extracts_chosen_option(self):
        spec = parse_spec(_spec(chosen="B"))
        assert spec["chosen_option"] == "B"


class TestMeasurableTradeoff:
    @pytest.mark.parametrize(
        "line",
        [
            "+20% write latency",
            "-50ms p99",
            "+3 days impl",
            "2x faster",
            "10 fewer dependencies",
            "+1 service",
        ],
    )
    def test_accepts_measurable(self, line: str):
        assert is_measurable_tradeoff(line)

    @pytest.mark.parametrize(
        "line",
        [
            "more flexible",
            "simpler to understand",
            "robust",
            "",
            "feels right",
        ],
    )
    def test_rejects_vague(self, line: str):
        assert not is_measurable_tradeoff(line)


class TestValidate:
    def test_passes_valid_spec(self):
        spec = parse_spec(_spec())
        assert validate(spec) == []

    def test_flags_single_option(self):
        text = _spec(options=[("A", "Only", "+1 day, -1 service")])
        spec = parse_spec(text)
        errs = validate(spec)
        assert any("minimum 2" in e for e in errs)

    def test_flags_vague_tradeoff(self):
        text = _spec(
            options=[
                ("A", "Vague", "more flexible"),
                ("B", "Concrete", "+20%, -1 dep"),
            ]
        )
        spec = parse_spec(text)
        errs = validate(spec)
        assert any("not measurable" in e for e in errs)
        # Concrete option B is OK; only A should flag.
        assert sum("not measurable" in e for e in errs) == 1

    def test_flags_missing_section(self):
        spec = parse_spec(_spec(omit_section="Rollback"))
        errs = validate(spec)
        assert any("Rollback" in e and "missing" in e for e in errs)

    def test_flags_chosen_not_in_options(self):
        spec = parse_spec(_spec(chosen="Z"))
        errs = validate(spec)
        assert any("Option Z" in e for e in errs)

    def test_flags_missing_linked_issue(self):
        spec = parse_spec(_spec(linked=""))
        # `Linked Issue:` with empty value still produces empty linked_issue string.
        errs = validate(spec)
        assert any("Linked Issue" in e for e in errs)


class TestValidatorCli:
    def test_cli_passes_on_valid_file(self, tmp_path: Path):
        spec_file = tmp_path / "SPEC-007.md"
        spec_file.write_text(_spec(), encoding="utf-8")
        from scripts.validate_spec import main

        rc = main([str(spec_file)])
        assert rc == 0

    def test_cli_fails_on_invalid_file(self, tmp_path: Path):
        spec_file = tmp_path / "SPEC-007.md"
        spec_file.write_text(
            _spec(options=[("A", "Only", "more flexible")]), encoding="utf-8"
        )
        from scripts.validate_spec import main

        rc = main([str(spec_file)])
        assert rc == 1
