"""Unit tests for scripts/validate_issues.py."""

from pathlib import Path

from scripts.validate_issues import parse_issues, validate


def _make_issue(
    num: str = "001",
    title: str = "Do something",
    estimate: str = "1d",
    prd_ref: str = "FR-001",
    depends_on: str = "none",
    ac_items: list[str] | None = None,
    status: str = "backlog",
    spec_required: str | None = None,
    spec: str | None = None,
) -> str:
    """Build a minimal issue markdown block.

    spec_required / spec: if not None, the corresponding metadata field is emitted.
    """
    if ac_items is None:
        ac_items = [
            "Given a user is logged in, when they click save, then data is persisted",
            "Given a user is logged out, when they click save, then an error is shown",
        ]
    ac_lines = "\n".join(f"- [ ] {ac}" for ac in ac_items)
    spec_meta = ""
    if spec_required is not None:
        spec_meta += f"- Spec-Required: {spec_required}\n"
    if spec is not None:
        spec_meta += f"- Spec: {spec}\n"
    return f"""### ISSUE-{num}: {title}
- Track: product
- PRD-Ref: {prd_ref}
- Priority: P1
- Estimate: {estimate}
- Status: {status}
{spec_meta}- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: {depends_on}

#### Goal
Something is done.

#### Scope (In/Out)
- In: deliverable
- Out: nothing

#### Acceptance Criteria (DoD)
{ac_lines}

#### Implementation Notes
Some notes.

#### Tests
- [ ] Test case 1

#### Rollback
Revert the commit.
"""


class TestParseIssues:
    def test_parses_single_issue(self):
        text = _make_issue()
        issues = parse_issues(text)
        assert len(issues) == 1
        assert issues[0]["id"] == "ISSUE-001"
        assert issues[0]["num"] == "001"
        assert issues[0]["estimate"] == "1d"
        assert len(issues[0]["ac_items"]) == 2

    def test_parses_multiple_issues(self):
        text = _make_issue(num="001") + "\n" + _make_issue(num="002")
        issues = parse_issues(text)
        assert len(issues) == 2
        assert issues[0]["id"] == "ISSUE-001"
        assert issues[1]["id"] == "ISSUE-002"

    def test_parses_empty_text(self):
        assert parse_issues("") == []
        assert parse_issues("# Just a header\nSome text.") == []


class TestValidate:
    def test_valid_issue_no_warnings(self):
        text = _make_issue()
        issues = parse_issues(text)
        warnings = validate(issues)
        assert warnings == []

    def test_invalid_estimate(self):
        text = _make_issue(estimate="3d")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("invalid estimate" in w for w in warnings)

    def test_too_few_ac(self):
        text = _make_issue(
            ac_items=["Given x, when y, then z"],
        )
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("only 1 AC" in w for w in warnings)

    def test_ac_not_gwt_format(self):
        text = _make_issue(
            ac_items=[
                "The button should be blue",
                "Users can log in",
            ],
        )
        issues = parse_issues(text)
        warnings = validate(issues)
        gwt_warnings = [w for w in warnings if "Given/When/Then" in w]
        assert len(gwt_warnings) == 2

    def test_empty_prd_ref(self):
        text = _make_issue(prd_ref="")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("PRD-Ref is empty" in w for w in warnings)

    def test_empty_depends_on(self):
        text = _make_issue(depends_on="")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("Depends-On is empty" in w for w in warnings)

    def test_duplicate_issue_numbers(self):
        text = _make_issue(num="001") + "\n" + _make_issue(num="001", title="Other task")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("duplicate number" in w for w in warnings)

    def test_depends_on_none_is_valid(self):
        text = _make_issue(depends_on="none")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert warnings == []

    def test_multiple_violations_reported(self):
        text = _make_issue(estimate="5d", prd_ref="", depends_on="", ac_items=["bad ac"])
        issues = parse_issues(text)
        warnings = validate(issues)
        # invalid estimate, too few AC, bad AC format, empty PRD-Ref, empty Depends-On
        assert len(warnings) == 5


class TestSpecRequired:
    def test_no_warning_when_spec_required_false(self):
        text = _make_issue(spec_required="false", status="done")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert not any("Spec-Required" in w for w in warnings)

    def test_no_warning_when_status_backlog(self):
        # Even with Spec-Required=true, backlog status does not enforce.
        text = _make_issue(spec_required="true", status="backlog", spec="none")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert not any("Spec-Required" in w for w in warnings)

    def test_warns_when_doing_and_spec_none(self):
        text = _make_issue(spec_required="true", status="doing", spec="none")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("Spec-Required" in w and "ISSUE-001" in w for w in warnings)

    def test_warns_when_done_and_spec_empty(self):
        # Field present but empty.
        text = _make_issue(spec_required="true", status="done", spec="")
        issues = parse_issues(text)
        warnings = validate(issues)
        assert any("Spec-Required" in w for w in warnings)

    def test_warns_when_waiting_and_spec_missing_file(self, tmp_path: Path):
        # File path is given but does not exist on disk.
        text = _make_issue(
            spec_required="true",
            status="waiting",
            spec="docs/specs/SPEC-001.md",
        )
        issues = parse_issues(text)
        warnings = validate(issues, issues_md_dir=tmp_path)
        assert any("Spec-Required" in w and "missing or unreadable" in w for w in warnings)

    def test_passes_when_spec_file_exists(self, tmp_path: Path):
        specs_dir = tmp_path / "docs" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "SPEC-001.md").write_text("# SPEC-001\n", encoding="utf-8")
        text = _make_issue(
            spec_required="true",
            status="done",
            spec="docs/specs/SPEC-001.md",
        )
        issues = parse_issues(text)
        warnings = validate(issues, issues_md_dir=tmp_path)
        assert not any("Spec-Required" in w for w in warnings)
