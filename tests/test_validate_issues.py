"""Unit tests for scripts/validate_issues.py."""

from scripts.validate_issues import parse_issues, validate


def _make_issue(
    num: str = "001",
    title: str = "Do something",
    estimate: str = "1d",
    prd_ref: str = "FR-001",
    depends_on: str = "none",
    ac_items: list[str] | None = None,
) -> str:
    """Build a minimal issue markdown block."""
    if ac_items is None:
        ac_items = [
            "Given a user is logged in, when they click save, then data is persisted",
            "Given a user is logged out, when they click save, then an error is shown",
        ]
    ac_lines = "\n".join(f"- [ ] {ac}" for ac in ac_items)
    return f"""### ISSUE-{num}: {title}
- Track: product
- PRD-Ref: {prd_ref}
- Priority: P1
- Estimate: {estimate}
- Status: backlog
- Owner:
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
