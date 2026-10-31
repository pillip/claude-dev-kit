"""Contract tests for the committed ``docs/specs/SPEC-088.md`` decision artifact.

ISSUE-088 is a DECISION issue: the SPEC is the deliverable. SPEC-088's Decision is
**Option C — DECLINE** the disarm-direction property, so this branch lands no engine,
no ``review/gate-evidence`` phase and no attestation surface. These tests therefore
drive the one real consumer that exists for the deliverable: ``scripts/validate_spec.py``,
through both its ``validate()`` entry point and its ``main()`` CLI.

**What these tests pin.** That the committed SPEC-088 is structurally a *decision*:
it carries at least 2 named options, every option carries a measurable trade-off
comparator, the required sections (Problem / Context / Options / Decision /
Trade-offs Accepted / Migration / Rollback / Open Questions) are present and
non-empty, and the Decision section names **exactly one** chosen option which is one
of the options actually declared. ``TestSpec088ValidatorDisarmDirection`` is the
disarm half: each of those properties is mutated out of the committed bytes and the
validator is required to refuse, so a green result above cannot be a hollow pass.
``test_the_cli_refuses_an_absent_spec_088`` closes the one hollow-pass route the
oracle actually has — a vanished file must yield exit 2, never exit 0.

**What these tests do NOT pin, stated plainly so nobody reads more into them.**
They do not pin that DECLINE is the correct outcome; no test can, and SPEC-088's
"Trade-offs Accepted" says so. They do not assert occurrence counts of claim strings
across ``skills/review/SKILL.md.tmpl``, the generated ``skills/review/SKILL.md``,
``agents/team-lead.md`` or ``scripts/verify_gate_evidence.py``: that count is already
**0** on main because ISSUE-081 was dropped unmerged, so such an assertion would pass
trivially and could never fail. Commit ``2a93d09`` deflated exactly that
manufactured-record pattern in this repo, and documentation-accuracy tests are issue
generators. The record lives in SPEC-088's AC audit instead.

**ISSUE-088 ACs that are vacuous or unroutable on main, measured — not covered here
because they cannot be:** AC-4 (``_refusal_shaped`` / ``REFUSAL_PATTERNS`` /
``_CONSUMER_RE`` / ``BLOCKING_KINDS`` byte-unchanged) is vacuous because
``scripts/verify_gate_evidence.py`` does not exist. AC-5 and AC-6 drive
``bash scripts/checkpoint.sh --skill review --phase gate-evidence``, which exits 2 with
``unknown phase``; no detector-shaped gate fixture whose battery is written
``assert detected is True`` can be replayed through a consumer that is not registered,
and no gate-list hand-off is landed to mutate out. AC-7's four committed fixtures
(``issue_078_pre_fix`` 1, ``issue_078_post_fix`` 1, ``issue_074_non_gate`` 0,
``issue_056_colliding_main`` 1) do not exist on main, so the exit-code replay and its
blocking-versus-advisory finding split have nothing to replay and the tier is untouched
in either direction.
"""

from pathlib import Path

import pytest

from scripts.validate_spec import main, parse_spec, validate

SPEC_PATH = Path(__file__).resolve().parents[1] / "docs" / "specs" / "SPEC-088.md"


def _spec_text() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def _errors(text: str) -> list[str]:
    return validate(parse_spec(text), str(SPEC_PATH))


class TestSpec088PassesTheRealValidator:
    """Arm direction: the committed artifact satisfies the oracle."""

    def test_committed_spec_088_has_no_violations(self):
        assert _errors(_spec_text()) == []

    def test_cli_exits_zero_on_the_committed_spec_088(self, capsys):
        assert main([str(SPEC_PATH)]) == 0
        capsys.readouterr()

    def test_the_decision_names_exactly_one_declared_option(self):
        spec = parse_spec(_spec_text())
        letters = {o["letter"] for o in spec["options"]}
        assert spec["chosen_option"], "Decision names no option — a deferral, not a decision"
        assert spec["chosen_option"] in letters, (
            f"chosen {spec['chosen_option']!r} not among declared options {sorted(letters)}"
        )
        assert len(spec["options"]) >= 2, "a decision needs a rejected alternative to be credible"


class TestSpec088ValidatorDisarmDirection:
    """Disarm direction: each property the arm half relies on, mutated out of the
    committed bytes, must make the real validator refuse. A surviving mutant means
    the arm assertions above are unevidenced."""

    def test_stripping_the_trade_off_lines_is_refused(self):
        mutated = "\n".join(
            line for line in _spec_text().splitlines()
            if not line.lstrip().startswith("- **Trade-off**:")
        )
        errors = _errors(mutated)
        assert any("missing **Trade-off:** line" in e for e in errors), errors

    def test_reducing_the_spec_to_one_option_is_refused(self):
        text = _spec_text()
        start = text.index("### Option B:")
        end = text.index("## Decision")
        errors = _errors(text[:start] + text[end:])
        assert any("minimum 2 required" in e for e in errors), errors

    def test_a_decision_naming_an_undeclared_option_is_refused(self):
        mutated = _spec_text().replace("**Chosen: Option C**", "**Chosen: Option Z**")
        assert "**Chosen: Option Z**" in mutated, "mutation did not apply"
        errors = _errors(mutated)
        assert any("but options defined are" in e for e in errors), errors

    @pytest.mark.parametrize(
        "section",
        ["Decision", "Trade-offs Accepted", "Rollback", "Open Questions"],
    )
    def test_removing_a_required_section_is_refused(self, section: str):
        text = _spec_text()
        start = text.index(f"## {section}\n")
        nxt = text.find("\n## ", start + 1)
        mutated = text[:start] + (text[nxt + 1:] if nxt != -1 else "")
        errors = _errors(mutated)
        assert any(f"`## {section}` is missing or empty" in e for e in errors), errors

    def test_an_unmeasurable_trade_off_is_refused(self):
        """The Decision's comparators are load-bearing: strip the numbers from the
        chosen option's trade-off and the oracle must stop accepting it."""
        text = _spec_text()
        start = text.index("### Option C:")
        end = text.index("### Option D:")
        body = text[start:end]
        vague = "- **Trade-off**: cheaper and more honest than the alternatives.\n"
        tradeoff_start = body.index("- **Trade-off**:")
        tradeoff_end = body.index("\n", body.index("\n", tradeoff_start) + 1) + 1
        mutated = text[:start] + body[:tradeoff_start] + vague + text[end:]
        assert body[tradeoff_start:tradeoff_end] not in mutated, "mutation did not apply"
        errors = _errors(mutated)
        assert any("not measurable" in e for e in errors), errors

    def test_the_cli_refuses_an_absent_spec_088(self, tmp_path: Path, capsys):
        """The one hollow-pass route the oracle has. ``main()`` returns 0 for a
        directory containing no SPECs, so if SPEC-088 ever vanishes the arm test
        must not silently keep passing — an absent *file* path must exit 2."""
        assert main([str(tmp_path / "SPEC-088.md")]) == 2
        capsys.readouterr()
