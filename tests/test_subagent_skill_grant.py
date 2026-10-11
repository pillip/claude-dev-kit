"""Guards for ISSUE-072 — the sub-agent `Skill` grant on the kit's review path.

Three invariants, each pinned in BOTH directions (the real artifact must
satisfy the predicate, and a one-at-a-time mutation of it must be rejected —
review lesson "a newly added defence must be tested in the DISARM direction
and through its real consumer, not only in the arm direction at its helper"):

1. **The matrix row (AC-1, the ISSUE-014 artifact).**
   `docs/cc_feature_matrix.md` carries exactly ONE row for skill invocation
   from Task sub-agent context, with a non-empty Status, a `local`
   verification note naming the probe's own CC version and ISO date, the
   observed NEGATIVE results (not a cleaned-up summary), and ISSUE-066/072
   as consumers. The row is the deliverable that survives even if the grant
   turns out to be impossible, so it must not be silently droppable.

2. **The grant, and the refuted token (the grant + AC-3's live clause).**
   `agents/reviewer.md` and `agents/team-lead.md` grant `Skill`, and NO
   review-path agent grants `SlashCommand` — the token the 2026-10-11 probe
   refuted (absent in every probed sub-agent context on CC 2.1.224, not
   loaded and not deferred). AC-3's own branch does not apply: its premise
   ("the probe shows a sub-agent CANNOT invoke skills") is false. Only its
   second clause is landed here, narrowed to the token that is actually
   unusable. Deliberately scoped to `agents/*.md`: `skills/review/SKILL.md`
   keeps its `SlashCommand` grant, because the probe covered sub-task
   contexts only and the main-session path was NOT probed — do not extend
   this guard to skill frontmatter on the strength of this evidence.

3. **The call site (AC-4).** A `Skill` grant whose only call site names a
   DIFFERENT tool is a grant with no call site: the review path would keep
   asking the model about `SlashCommand`, the answer would always be
   "absent", and `decide` would return `context-unreachable` forever — the
   grant would be inert. So step 3.1 of the review skill must name `Skill`
   as the tool to look for, positioned BEFORE the `review_context.py decide`
   call it feeds (position, not mere presence — review lesson 12), in both
   the template and the generated artifact; and the `--invocation-tools`
   help a user actually sees must name it too.

Scoping note for AC-4, recorded rather than built: this file pins the
skill-invocation token family (`Skill` / `SlashCommand`) — the grant this
issue adds and the one it refutes. It does not attempt a general
"every granted tool form on the review path has a call site" sweep over
`Read`/`Write`/`Edit`/`Bash`/`Task`/`Glob`/`Grep`; that is a different and
much larger guard surface, and `Glob`/`Grep` in particular are the
granted-but-NOT-provisioned pair this issue's own evidence is about.

Primary evidence: `docs/sprint_state.md` section
`## ISSUE-072 Capability Probe Evidence (team-lead, 2026-10-11, CC 2.1.224)`.
AC-2 ("evidenced by a live run") is NOT testable here by construction — the
agent registry is frozen at session start and the live agents are served
from the installed plugin cache — and inventing a unit fixture for it would
be exactly the hollow pass AC-2 forbids. Its durable carrier is ISSUE-082.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = KIT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import has_skill  # noqa: E402
import review_context as rc  # noqa: E402

MATRIX = KIT_ROOT / "docs" / "cc_feature_matrix.md"
REVIEW_TMPL = KIT_ROOT / "skills" / "review" / "SKILL.md.tmpl"
REVIEW_SKILL = KIT_ROOT / "skills" / "review" / "SKILL.md"

# The review path's two sub-agent entry points. `team-lead` dispatches the
# review sub-task; `reviewer` runs the degraded dimensions inside it.
REVIEW_PATH_AGENTS = ("reviewer", "team-lead")

# The probe's own build + date — deliberately NOT the matrix file's global
# 2.1.185 floor (the row carries its own, which is newer).
PROBE_VERSION = "2.1.224"
PROBE_DATE = "2026-10-11"


# ── matrix row: parse + completeness predicate ───────────────────────

# Key on the FEATURE name, never on a row number: the matrix numbers rows
# and a later insertion would renumber them.
_FEATURE_CUE = re.compile(r"sub-agent context", re.IGNORECASE)
_SKILL_WORD = re.compile(r"\bSkill\b")

CELL_NAMES = ("number", "feature", "status", "verified", "notes", "consumer")

# Required content per cell, as (cell, regex, why) — an occurrence WHITELIST,
# not a phrasing blacklist, so a rewording that keeps the observation passes
# and a rewording that drops it fails.
ROW_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    ("feature", r"\bSkill\b", "the feature cell must name the `Skill` tool"),
    ("verified", r"\blocal\b", "the verification level must be `local` (AC-1)"),
    (
        "verified",
        re.escape(PROBE_VERSION),
        f"the Verified cell must name the probe's own build {PROBE_VERSION} "
        "(not the file's global 2.1.185 floor)",
    ),
    (
        "verified",
        re.escape(PROBE_DATE),
        f"the Verified cell must name the probe's date {PROBE_DATE}",
    ),
    ("notes", r"\bSkill\b", "the `Skill` tool was the capability observed"),
    (
        "notes",
        r"SlashCommand",
        "`SlashCommand` was absent in every probed context — a negative "
        "result the row must carry",
    ),
    (
        "notes",
        r"defer",
        "`SlashCommand` was absent NOT EVEN AS A DEFERRED tool — the "
        "stronger half of that negative result",
    ),
    (
        "notes",
        r"namespac",
        "the observed `Skill` listing was bare, not `claude-dev-kit:`-"
        "namespaced",
    ),
    (
        "notes",
        r"allowed-tools",
        "the sub-agent's `tools:` wins over the skill's `allowed-tools` — "
        "the precedence that made the capability look absent",
    ),
    (
        "notes",
        r"\bGlob\b",
        "the granted-but-not-provisioned result for `Glob`",
    ),
    (
        "notes",
        r"\bGrep\b",
        "the granted-but-not-provisioned result for `Grep`",
    ),
    (
        "notes",
        r"provision",
        "a grant does not imply provisioning — the counter-evidence inside "
        "this row's own subject",
    ),
    (
        "notes",
        r"contradict",
        "the two same-session reports about `Glob`/`Grep` CONTRADICT each "
        "other; the row must keep the contradiction, not average it away",
    ),
    (
        "notes",
        r"unreliable",
        "the epistemic conclusion: a sub-agent's narration of its own tool "
        "list is unreliable evidence, weaker than an observed call outcome",
    ),
    (
        "notes",
        r"disable-model-invocation",
        "the grant does NOT re-enable the kit's own disabled pipeline skills",
    ),
    (
        "notes",
        r"refut",
        "SPEC-066's categorical runtime-limitation claim is refuted, not "
        "merely confounded",
    ),
    (
        "notes",
        r"ISSUE-082",
        "the grant's materialisation is UNVERIFIED and ISSUE-082 is its "
        "durable carrier (a PR body is not one)",
    ),
    ("consumer", r"ISSUE-066", "ISSUE-066 is a consumer of this row (AC-1)"),
    ("consumer", r"ISSUE-072", "ISSUE-072 is a consumer of this row (AC-1)"),
)


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) == len(CELL_NAMES):
            rows.append(cells)
    return rows


def _subagent_rows(text: str) -> list[dict[str, str]]:
    """Every matrix row whose FEATURE cell is about sub-agent skill invocation."""
    return [
        dict(zip(CELL_NAMES, cells))
        for cells in _table_rows(text)
        if _FEATURE_CUE.search(cells[1]) and _SKILL_WORD.search(cells[1])
    ]


def _row_defects(row: dict[str, str]) -> list[str]:
    """Every way the row falls short of AC-1. Empty list = complete row."""
    defects = []
    if not row["status"].strip(" *_-—"):
        defects.append("the Status cell is empty")
    for cell, pattern, why in ROW_REQUIREMENTS:
        if not re.search(pattern, row[cell]):
            defects.append(f"{cell} cell is missing /{pattern}/ — {why}")
    return defects


class TestMatrixRowIsTheIssue014Artifact:
    """AC-1 — the row lands FIRST and carries the observations verbatim."""

    def test_exactly_one_subagent_skill_invocation_row_exists(self):
        rows = _subagent_rows(MATRIX.read_text(encoding="utf-8"))
        assert len(rows) == 1, (
            f"expected exactly 1 sub-agent skill-invocation row in {MATRIX}, "
            f"found {len(rows)}. ISSUE-082 amends THIS row in place; a second "
            "row is not appended."
        )

    def test_row_is_complete(self):
        (row,) = _subagent_rows(MATRIX.read_text(encoding="utf-8"))
        assert _row_defects(row) == []

    def test_row_does_not_restate_the_files_global_floor_as_the_probe_build(self):
        """The probe ran on 2.1.224; the file's global floor is 2.1.185.

        Naming the floor in this row's Verified cell would silently
        misattribute the measurement to a build it was never run on.
        """
        (row,) = _subagent_rows(MATRIX.read_text(encoding="utf-8"))
        assert "2.1.185" not in row["verified"], (
            "the Verified cell names 2.1.185 — the file's global floor, not "
            f"the build this row was probed on ({PROBE_VERSION})"
        )


class TestMatrixRowGuardRejectsMutations:
    """Disarm direction: every one-at-a-time deletion must be caught.

    Without these, a guard that merely *finds* a row would pass against a
    row whose evidence had been quietly trimmed to a tidy summary — which is
    the exact failure mode ISSUE-014's rule exists to prevent.
    """

    @staticmethod
    def _real_row() -> dict[str, str]:
        (row,) = _subagent_rows(MATRIX.read_text(encoding="utf-8"))
        return row

    def test_empty_status_is_rejected(self):
        row = self._real_row()
        row["status"] = "   "
        assert any("Status cell is empty" in d for d in _row_defects(row))

    @pytest.mark.parametrize(
        "cell,pattern,why", ROW_REQUIREMENTS, ids=lambda v: str(v)[:40]
    )
    def test_each_required_observation_is_load_bearing(self, cell, pattern, why):
        """Delete just this observation from the real row -> guard fails."""
        row = self._real_row()
        row[cell] = re.sub(pattern, "", row[cell])
        defects = _row_defects(row)
        assert any(pattern in d for d in defects), (
            f"removing /{pattern}/ from the {cell} cell left the guard green, "
            f"so the guard does not actually pin it. Rationale: {why}"
        )


# ── the grant, and the refuted token ─────────────────────────────────


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"{path} has no YAML frontmatter"
    return parts[1]


def _tool_grants(frontmatter: str, key: str = "tools") -> list[str]:
    """Comma-split a frontmatter tool list, ignoring commas inside `Bash(...)`.

    Not imported from `tests/test_registry_lock_contract.py`'s `_tools`: that
    helper is agent-only (it resolves `agents/<stem>.md` itself and reads the
    `tools:` key), while this guard must also parse the `allowed-tools:` key
    of a SKILL file. That module's real-file pin on `agents/team-lead.md` is
    updated in the same commit as the grant.
    """
    lines = re.findall(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
    assert len(lines) == 1, (
        f"expected exactly one `{key}:` line in frontmatter, found "
        f"{len(lines)} — a second line is an invisible privilege grant "
        "(ISSUE-074 precedent)"
    )
    grants, depth, current = [], 0, ""
    for ch in lines[0]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            grants.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        grants.append(current.strip())
    return grants


def _grant_defects(grants: list[str]) -> list[str]:
    defects = []
    if "Skill" not in grants:
        defects.append(
            "no `Skill` grant — the review path cannot reach the SPEC-019 "
            "primary path from sub-task context without it (probe finding 1)"
        )
    if "SlashCommand" in grants:
        defects.append(
            "carries a `SlashCommand` grant — the token the 2026-10-11 probe "
            "refuted (absent in every probed sub-agent context on CC "
            f"{PROBE_VERSION}, not loaded and not deferred). Granting it "
            "reproduces the very defect ISSUE-072 fixes: a grant naming a "
            "tool nothing provisions. Grant `Skill` instead."
        )
    return defects


class TestReviewPathAgentsGrantSkillAndNotSlashCommand:
    @pytest.mark.parametrize("stem", REVIEW_PATH_AGENTS)
    def test_agent_grant_is_correct(self, stem):
        grants = _tool_grants(_frontmatter(KIT_ROOT / "agents" / f"{stem}.md"))
        assert _grant_defects(grants) == [], f"agents/{stem}.md: {_grant_defects(grants)}"

    def test_no_other_agent_gains_the_grant(self):
        """Scope In says the grant lands on the review path ONLY.

        A symmetry grant riding along would widen privilege with no call
        site — the other direction of the same review lesson.
        """
        offenders = []
        for path in sorted((KIT_ROOT / "agents").glob("*.md")):
            if path.stem in REVIEW_PATH_AGENTS:
                continue
            if "Skill" in _tool_grants(_frontmatter(path)):
                offenders.append(path.name)
        assert offenders == [], (
            f"agents outside the review path grant `Skill`: {offenders}. "
            "ISSUE-072's Scope Out forbids it — each grant needs its own "
            "verified call site."
        )

    @pytest.mark.parametrize(
        "grants,expected_cue",
        [
            (["Read", "Glob", "Grep", "Edit", "Bash", "Write"], "no `Skill` grant"),
            (
                ["Read", "Edit", "Bash", "Write", "Skill", "SlashCommand"],
                "`SlashCommand` grant",
            ),
        ],
        ids=["skill-grant-deleted", "refuted-token-added"],
    )
    def test_grant_guard_rejects_mutations(self, grants, expected_cue):
        defects = _grant_defects(grants)
        assert any(expected_cue in d for d in defects), defects

    def test_review_skill_frontmatter_keeps_slashcommand_and_gains_skill(self):
        """The SKILL's own `allowed-tools` is a different surface.

        Inside a sub-task the agent's `tools:` wins, so the skill grant is
        not what unlocks the sub-task path — but interactively the skill
        frontmatter IS the grant, and step 3.1 now tells the model to look
        for `Skill`. `SlashCommand` stays: the main-session path was NOT
        probed, so removing it would be an unevidenced change.
        """
        for path in (REVIEW_TMPL, REVIEW_SKILL):
            grants = _tool_grants(_frontmatter(path), key="allowed-tools")
            assert "Skill" in grants, (
                f"{path.name}: step 3.1 asks the model about `Skill` but the "
                "skill's own allowed-tools does not grant it"
            )
            assert "SlashCommand" in grants, (
                f"{path.name}: `SlashCommand` was removed from allowed-tools. "
                "The probe covered sub-task contexts only; the main-session "
                "path is unprobed, so this removal is unevidenced."
            )


# ── the call site (AC-4) ─────────────────────────────────────────────

_STEP_HEADER_RE = re.compile(r"^3\.\d+\)", re.MULTILINE)


def _step_block(text: str, step: str = "3.1)") -> str:
    """The text of one `3.N)` step, header-anchored to the next step header."""
    start = text.find(f"\n{step}")
    if start == -1:
        return ""
    start += 1
    nxt = _STEP_HEADER_RE.search(text, start + len(step))
    return text[start : nxt.start() if nxt else len(text)]


def _call_site_defects(step_text: str) -> list[str]:
    """Every way step 3.1 fails to be a real call site for the `Skill` grant."""
    if not step_text:
        return ["step 3.1 not found — the decision call site is gone"]
    defects = []
    skill_at = step_text.find("`Skill`")
    decide_at = step_text.find("review_context.py decide")
    if skill_at == -1:
        defects.append(
            "step 3.1 never names `Skill` — the granted token has no call "
            "site, so the grant is INERT: the model is asked about a "
            "different tool, answers `absent`, and `decide` returns "
            "`context-unreachable` forever"
        )
    if decide_at == -1:
        defects.append("step 3.1 does not run `review_context.py decide`")
    if skill_at != -1 and decide_at != -1 and skill_at > decide_at:
        defects.append(
            "`Skill` is named AFTER the `decide` call it feeds — the "
            "detection question must precede the decision it answers "
            "(position, not mere presence)"
        )
    slash_at = step_text.find("`SlashCommand`")
    if slash_at != -1 and skill_at != -1 and slash_at < skill_at:
        defects.append(
            "`SlashCommand` is named before `Skill` in the detection "
            "question — the refuted token must not be the one the model "
            "checks first"
        )
    return defects


class TestDetectionQuestionNamesTheGrantedToken:
    """AC-4 — deleting the call site must fail the test."""

    @pytest.mark.parametrize("path", [REVIEW_TMPL, REVIEW_SKILL], ids=["tmpl", "generated"])
    def test_step_31_is_a_real_call_site(self, path):
        defects = _call_site_defects(_step_block(path.read_text(encoding="utf-8")))
        assert defects == [], f"{path.name}: {defects}"

    def test_deleting_the_call_site_fails(self):
        """The real template with its `Skill` mention removed -> rejected."""
        block = _step_block(REVIEW_TMPL.read_text(encoding="utf-8"))
        assert block, "step 3.1 missing from the template"
        defects = _call_site_defects(block.replace("`Skill`", "`SlashCommand`"))
        assert any("never names `Skill`" in d for d in defects), defects

    def test_call_site_guard_rejects_inverted_order(self):
        inverted = (
            "3.1) decision\n"
            "   python3 scripts/review_context.py decide --invocation-tools x\n"
            "   ...and by the way check for `Skill` afterwards.\n"
        )
        assert any("named AFTER" in d for d in _call_site_defects("\n" + inverted))

    def test_call_site_guard_rejects_refuted_token_first(self):
        slash_first = (
            "3.1) decision\n"
            "   Is `SlashCommand` in your tool list? (or `Skill`)\n"
            "   python3 scripts/review_context.py decide --invocation-tools x\n"
        )
        assert any(
            "named before `Skill`" in d for d in _call_site_defects("\n" + slash_first)
        )

    def test_call_site_guard_rejects_missing_step(self):
        assert _call_site_defects("") == [
            "step 3.1 not found — the decision call site is gone"
        ]


def _help_defects(help_text: str) -> list[str]:
    defects = []
    skill_at = help_text.find("Skill")
    slash_at = help_text.find("SlashCommand")
    if skill_at == -1:
        defects.append(
            "the --invocation-tools help never names `Skill` — it asks the "
            "operator about a tool the probe found in no sub-agent context"
        )
    if slash_at != -1 and skill_at != -1 and slash_at < skill_at:
        defects.append("the help names `SlashCommand` ahead of `Skill`")
    return defects


class TestInvocationToolsHelpNamesTheGrantedToken:
    """Through the real consumer: the help text a user actually sees."""

    def test_decide_help_names_skill(self, capsys):
        assert rc.main(["decide", "--help"]) == 2  # argparse exits; main returns 2
        out = capsys.readouterr().out
        assert "--invocation-tools" in out
        assert _help_defects(out) == []

    @pytest.mark.parametrize(
        "help_text,cue",
        [
            (
                "Model-reported context half: is the runtime skill-invocation "
                "tool (SlashCommand) in the current tool list?",
                "never names `Skill`",
            ),
            ("is SlashCommand or Skill in your tool list?", "ahead of `Skill`"),
        ],
        ids=["skill-missing", "refuted-token-first"],
    )
    def test_help_guard_rejects_mutations(self, help_text, cue):
        assert any(cue in d for d in _help_defects(help_text))


# ── AC-2's testable half (a live run is ISSUE-082's, not a fixture's) ──


class TestDecideTableIsWhatTheGrantUnlocks:
    """The grant makes `present` reachable; `decide` turns it into `delegated`.

    This is the half of AC-2 that is testable without a live run. It is NOT
    AC-2: AC-2 requires `decide` to return `delegated` from inside a real
    Task sub-agent with findings reaching the synthesizer, "not by a unit
    fixture alone". Carrier: ISSUE-082.
    """

    def test_live_probe_returns_unknown_for_both_review_skills(self):
        """Fixture-pin: the capability half is 2 for both dimensions today.

        This is why the `--invocation-tools` flag — and therefore the grant —
        is the deciding input: exit 2 never degrades on its own (probe
        evidence finding 7, `context-unreachable` not `capability-absent`).
        """
        for skill in ("code-review", "security-review"):
            code, _evidence = has_skill.find_skill(skill)
            assert code == 2, f"{skill}: expected probe exit 2, got {code}"

    @pytest.mark.parametrize(
        "invocation_tools,expected_path,expected_reason",
        [
            ("present", "delegated", ""),
            ("absent", "degraded", "context-unreachable"),
        ],
    )
    def test_decide_cli_pairs_the_flag_to_the_path(
        self, invocation_tools, expected_path, expected_reason, capsys, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        assert (
            rc.main(["decide", "--invocation-tools", invocation_tools, "--issue", "ISSUE-072"])
            == 0
        )
        payload = json.loads(capsys.readouterr().out)
        for dimension in ("code", "security"):
            assert payload["dimensions"][dimension] == {
                "path": expected_path,
                "reason": expected_reason,
            }, payload
