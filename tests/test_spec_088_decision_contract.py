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
``test_the_cli_refuses_an_absent_spec_088`` closes the hollow-pass route that
``main()``'s *file* path has — a missing path must yield exit 2, never exit 0.
It is **not** the only one: ``main()`` ends with ``return 1 if args.strict or
target.is_file() else 0``, so a **directory** target exits 0 even with violations,
and that is exactly how CI invokes it (``.github/workflows/ci.yml:45``, no
``--strict``). That route is live, out of this issue's scope, and named in the
review notes rather than asserted away here.

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

import re
from pathlib import Path

import pytest

from scripts.validate_spec import main, parse_spec, validate

SPEC_PATH = Path(__file__).resolve().parents[1] / "docs" / "specs" / "SPEC-088.md"

#: Mirror of the oracle's inline chosen-option regex (``validate_spec.py:110-112``),
#: which the module does not export. Used ONLY to count occurrences — ``parse_spec``
#: itself uses ``re.search`` and keeps the first match, so it cannot see a second
#: ``**Chosen:`` line. Every use pins the mirror against the oracle's own answer
#: first, so a drifted mirror fails loudly instead of counting the wrong thing.
_CHOSEN_RE = re.compile(r"\*\*Chosen:\s*Option\s+(\w+)\b", re.IGNORECASE)

#: Mirror of the oracle's trade-off regex (``validate_spec.py:100-102``). The oracle
#: does **not** require a ``- `` bullet, so a mutator that only strips bulleted lines
#: would silently under-cover; this matches the shape the oracle actually accepts.
_TRADEOFF_RE = re.compile(r"\*\*Trade-off\*\*:")


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
        """The ONLY assertion in this module that ``validate()`` does not already make.

        ``validate_spec.py:176`` reads ``if spec["chosen_option"] and spec["options"]``,
        so an **empty** chosen option short-circuits the whole check: a deferral-shaped
        Decision passes ``validate()`` with zero errors. ISSUE-088's AC-1 says in terms
        that a Decision deferring the choice to a further carrier fails that AC, and
        this is the only guard in the repo against it.
        """
        spec = parse_spec(_spec_text())
        letters = {o["letter"] for o in spec["options"]}
        assert spec["chosen_option"], "Decision names no option — a deferral, not a decision"
        assert spec["chosen_option"] in letters, (
            f"chosen {spec['chosen_option']!r} not among declared options {sorted(letters)}"
        )
        assert len(spec["options"]) >= 2, "a decision needs a rejected alternative to be credible"

        # "Exactly one" was claimed but not tested until review: parse_spec uses
        # re.search and keeps only the FIRST match, so a second `**Chosen: Option A**`
        # left every assertion above green while the SPEC named two outcomes.
        # _CHOSEN_RE mirrors the oracle's inline regex (validate_spec.py:110-112),
        # which is not exported; the mirror is pinned against the oracle below so it
        # cannot drift into agreeing with nothing.
        named = _CHOSEN_RE.findall(spec["sections"]["Decision"])
        assert named[:1] == [spec["chosen_option"]], (
            f"mirror {named[:1]!r} disagrees with the oracle {spec['chosen_option']!r} — "
            "re-read validate_spec.py:110 before trusting the count below"
        )
        assert len(named) == 1, f"Decision names {len(named)} options {named}, expected exactly one"


class TestSpec088ValidatorDisarmDirection:
    """Disarm direction: each property the arm half relies on, mutated out of the
    committed bytes, must make the real validator refuse. A surviving mutant means
    the arm assertions above are unevidenced."""

    def test_stripping_the_trade_off_lines_is_refused(self):
        text = _spec_text()
        kept = [line for line in text.splitlines() if not _TRADEOFF_RE.search(line)]
        # Mirror-vs-oracle pin (review lesson 4): the mutator must remove every line
        # the oracle would have accepted as a trade-off, not just the bulleted ones.
        # Before review this filtered on `line.lstrip().startswith("- **Trade-off**:")`,
        # which is strictly tighter than the oracle's `\*\*Trade-off\*\*:\s*(.+?)$`.
        removed = len(text.splitlines()) - len(kept)
        assert removed == len(_TRADEOFF_RE.findall(text)) >= 2, (
            f"mutator removed {removed} lines but the oracle sees "
            f"{len(_TRADEOFF_RE.findall(text))} trade-off lines"
        )
        errors = _errors("\n".join(kept))
        assert any("missing **Trade-off:** line" in e for e in errors), errors

    def test_reducing_the_spec_to_one_option_is_refused(self):
        text = _spec_text()
        start = text.index("\n### Option B:") + 1
        end = text.index("\n## Decision\n") + 1
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
        start = text.index(f"\n## {section}\n") + 1
        nxt = text.find("\n## ", start + 1)
        mutated = text[:start] + (text[nxt + 1:] if nxt != -1 else "")
        errors = _errors(mutated)
        assert any(f"`## {section}` is missing or empty" in e for e in errors), errors

    def test_an_unmeasurable_trade_off_is_refused(self):
        """The Decision's comparators are load-bearing: strip the numbers from the
        chosen option's trade-off and the oracle must stop accepting it."""
        text = _spec_text()
        start = text.index("\n### Option C:") + 1
        end = text.index("\n### Option D:") + 1
        body = text[start:end]
        vague = "- **Trade-off**: cheaper and more honest than the alternatives.\n"
        tradeoff_start = body.index("- **Trade-off**:")
        tradeoff_end = body.index("\n", body.index("\n", tradeoff_start) + 1) + 1
        original_tradeoff = body[tradeoff_start:tradeoff_end]
        # Surgical splice: replace ONLY the trade-off, keeping whatever follows it in
        # Option C. Before review this was `text[:start] + body[:tradeoff_start] +
        # vague + text[end:]`, which discarded everything from the trade-off to the end
        # of the section — so the guard below could never fail (the slice was absent by
        # construction) and any content added after Option C's trade-off would have
        # been deleted silently, greening the test for the wrong reason.
        mutated = text[:start] + body[:tradeoff_start] + vague + body[tradeoff_end:] + text[end:]
        assert original_tradeoff not in mutated, "mutation did not apply"
        # Non-vacuous splice invariant: the result must differ from the committed bytes
        # by exactly this one substitution and nothing else. A guard phrased as "the old
        # text is absent" alone passes for a mutation that deleted half the document.
        assert text.count(original_tradeoff) == 1, "Option C's trade-off is not unique"
        assert mutated == text.replace(original_tradeoff, vague), (
            "splice changed more than Option C's trade-off line"
        )
        errors = _errors(mutated)
        assert any("not measurable" in e for e in errors), errors

    def test_the_cli_refuses_an_absent_spec_088(self, tmp_path: Path, capsys):
        """``main()`` must exit 2 on a path that does not exist.

        Corrected in review: this previously claimed to stop a *vanished SPEC-088*
        from passing silently. It cannot — ``_spec_text()`` would raise
        ``FileNotFoundError`` first, and this call passes ``tmp_path``, a file that
        never existed. What it genuinely pins is ``validate_spec.py:207-208``, the
        only statements in the oracle no other test in the repo reaches.
        """
        assert main([str(tmp_path / "SPEC-088.md")]) == 2
        capsys.readouterr()
