"""ISSUE-069: the sprint roster boundary is PINNED at sprint start.

Why this file exists (and why it is a new file rather than more cases in
``tests/test_sprint_queue.py``):

ISSUE-068 shipped ``augment_roster_from_board``, which re-derives
``watermark = max(rostered_nums)`` from the **mutable** sprint_state
``## Issue Progress`` table on every invocation, while
``compute_queues``/``choose_action`` order ``implement_ready`` by **priority,
not ID**. That single mechanism carries two High-severity harms:

* **Harm A — the control re-hides what it surfaced.** Once a higher-ID
  discovered issue is rostered, a lower-ID sibling drops *below* the new
  watermark and vanishes entirely: no target, no ``unrostered`` annotation, no
  ``stranded`` warning. Replay: ISSUE-063 + ISSUE-065 rostered, ISSUE-064 still
  Board ``backlog`` with its dependency resolved → a bare ``DONE``.
* **Harm B — above-boundary pre-existing backlog is auto-TARGETED, not merely
  flagged.** The watermark excludes only IDs *below* the roster max, so a sprint
  deliberately scoped on older debt auto-pulls everything newer into
  ``implement_ready`` and drives it through implement → review → ``gh pr merge``.

Every pre-existing test is a **single invocation** against a hand-written roster
whose max is also the global max ID, so the suite is structurally blind to both
harms. The structural gap is the **two-iteration replay harness** below: invoke
``next-action``, apply the resulting roster mutation to the fixture state, invoke
again, assert on the second result. Single-invocation tests cannot catch either
harm, which is why both shipped.

``tests/test_sprint_queue.py`` is deliberately untouched: its TC-068d (rostered
rows keep table-only dependency resolution) and TC-068i (legacy DONE/empty-table
``reason`` byte-pins) assertions are the backward-compatibility contract this
issue must not move, and two sibling issues (ISSUE-073, ISSUE-076) are editing
that file in parallel worktrees.

Symbol access note: ``parse_roster_watermark`` and ``diagnose_carry_forward_gaps``
are reached as ``sq.<name>`` rather than imported at module scope **on purpose**.
A module-scope import of a not-yet-written symbol collapses this whole file into
one collection error, which proves only that a name is missing. Attribute access
keeps every CLI/behaviour test running, so the RED phase fails on *behaviour*
(wrong action, wrong ``unrostered``, missing annotation) and a reviewer can read
the failures as a specification. There is no ``getattr`` default anywhere: the
unit tests raise an honest ``AttributeError`` until the symbol lands.
"""

import copy
import json
import re
from pathlib import Path

import pytest

import scripts.sprint_queue as sq
from scripts.sprint_queue import (
    compute_queues,
    parse_issues_metadata,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Opt-in knob for dispatching above-boundary (out-of-scope) Board issues.
KNOB = "KIT_SPRINT_DISPATCH_ABOVE_WATERMARK"

#: Canonical field name, as it must appear in the sprint_state ``## Meta`` block.
FIELD = "Roster-Watermark"

# CPython 3.11+ caps str→int conversion at sys.int_max_str_digits (4300), so an
# unbounded `\d+` handed to int() raises instead of returning JSON.
OVERLONG_DIGITS = "1" * 4301


@pytest.fixture(autouse=True)
def _hermetic_dispatch_knob(monkeypatch):
    """Clear ``KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`` for every test in this file.

    The knob widens ``sprint_queue.py``'s autonomous dispatch scope to Board
    issues above the pinned roster boundary, so a value leaking in from a
    developer's shell — or from an earlier test that set it — would silently flip
    the fail-closed default and make the withholding tests pass or fail for
    reasons they do not control (mock-isolation review lesson).

    Scoped to this file rather than the suite-wide ``tests/conftest.py`` for two
    reasons. (1) Reachability: the dispatch gate is inert unless the sprint_state
    fixture carries a ``Roster-Watermark`` field, and this is the only file whose
    fixtures emit one — ``tests/test_sprint_queue.py``'s builder never does, so a
    polluted environment cannot change any test outside this file. (2)
    ``verify_checkpoint.py``'s ``tests-written``/``red`` gates classify every
    ``.py`` under ``tests/`` as a test module and fail any that holds no test
    function, so a fixture-only ``conftest.py`` edit cannot pass an implement-phase
    gate at all (that is why ISSUE-058's ``conftest.py`` could only land during
    review hardening, PR #100). Promote this to ``tests/conftest.py`` the moment a
    second file's fixtures start emitting the field.
    """
    monkeypatch.delenv(KNOB, raising=False)


# ── Local fixture builders ──────────────────────────────────────────
#
# Self-contained on purpose: ISSUE-076 is concurrently tightening
# `parse_sprint_table` to an EXACT 5-column shape scoped to the Issue Progress
# table, so these builders emit exactly 5 columns and never place an `###` (h3)
# sub-table under `## Issue Progress` — any extra table goes under a new `## `
# (h2) heading.


def _sprint_state(
    rows,
    *,
    watermark=None,
    meta_extra=(),
    extra_sections="",
):
    """Build sprint_state.md text with a canonical 5-column progress table.

    ``watermark`` emits the canonical ``- Roster-Watermark: <value>`` line inside
    ``## Meta``. ``meta_extra`` appends raw lines to ``## Meta`` (used for
    mis-cased / decorated / duplicated field variants). ``extra_sections`` is
    appended after the last ``## `` heading, i.e. OUTSIDE ``## Meta``.
    """
    lines = [
        "# Sprint State",
        "",
        "## Meta",
        "- Started: 2026-10-11",
        "- Iteration: 1 / 20",
        "- Parallel: 3",
        "- Status: running",
    ]
    if watermark is not None:
        lines.append(f"- {FIELD}: {watermark}")
    lines.extend(meta_extra)
    lines += [
        "",
        "## Issue Progress",
        "| Issue | Status | Attempts | Last Error | Phase |",
        "|-------|--------|----------|------------|-------|",
    ]
    for issue, status, attempts, last_error, phase in rows:
        lines.append(f"| {issue} | {status} | {attempts} | {last_error} | {phase} |")
    lines += ["", "## Discovered Issues", "", "## Escalations", ""]
    text = "\n".join(lines) + "\n"
    if extra_sections:
        text += extra_sections if extra_sections.endswith("\n") else extra_sections + "\n"
    return text


def _issue_block(
    num,
    *,
    title="Do something",
    priority="P1",
    status="backlog",
    depends_on="none",
    manual="",
):
    """Build a minimal issues.md block (same shape parse_issues_metadata reads)."""
    manual_line = f"\n- Manual: {manual}" if manual else ""
    return f"""### ISSUE-{num}: {title}
- Track: platform
- Priority: {priority}
- Status: {status}
- Depends-On: {depends_on}{manual_line}

#### Acceptance Criteria (DoD)
- [ ] Given something, when action, then result
"""


def _board_text(board):
    """Render a ``{num: kwargs}`` Board dict to issues.md markdown."""
    return "\n".join(_issue_block(num, **kw) for num, kw in sorted(board.items()))


def _meta(status="backlog", depends_on=None, priority="p1", manual=False, pr=""):
    """An issues_meta entry for direct unit calls.

    The ``pr`` key is NOT optional padding: ``parse_issues_metadata`` really
    emits it, and a hand-built dict missing it is the GAP-068i fixture-drift
    shape — a test that passes against a fixture the engine never produces.
    """
    return {
        "manual": manual,
        "depends_on": list(depends_on or []),
        "priority": priority,
        "status": status,
        "pr": pr,
    }


def _row(issue, phase="shipped", status="active", attempts="1", last_error="—"):
    """A parsed sprint-table row dict (parse_sprint_table output shape)."""
    return {
        "issue": issue,
        "status": status,
        "attempts": attempts,
        "last_error": last_error,
        "phase": phase,
    }


# Test-local oracle for "a line that LOOKS like the field". Used only by the
# fixture mutation helper to delete a line this file itself wrote — and it
# asserts that exactly one line disappeared, so it cannot silently drift from
# the implementation's own detection regex.
#
# `re.MULTILINE` is load-bearing for the `.search()` call site in
# TestShippedTemplateCarriesTheField: without it `^` anchors to the start of the
# whole `## Meta` block, which would quietly narrow that pin from "the field
# lives inside ## Meta" (what it asserts) to "the field is the FIRST line of
# ## Meta" (a template line-order constraint nothing else states). The
# `.match(line)` call site in `drop_watermark_line` is per-line and unaffected.
_FIELD_LINE_RE = re.compile(
    r"^\s*[-*]?\s*\*{0,2}roster-watermark\*{0,2}\s*:", re.I | re.MULTILINE
)


def _meta_block(text):
    """The raw body of the ``## Meta`` section (through the next ``## `` / EOF)."""
    match = re.search(r"^## Meta$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def _append_progress_rows(sprint_text, new_rows):
    """Insert rows after the last Issue Progress table line, byte-preserving the rest.

    This mirrors what a phase executor actually does — it appends rows, it does
    not regenerate the file — so the ``## Meta`` pin survives the mutation.
    """
    lines = sprint_text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## Issue Progress")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    last_table_line = start
    for i in range(start + 1, end):
        if lines[i].strip().startswith("|"):
            last_table_line = i
    inserted = [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in new_rows]
    merged = lines[: last_table_line + 1] + inserted + lines[last_table_line + 1 :]
    return "\n".join(merged) + "\n"


class _Replay:
    """Two-iteration replay harness — the structural gap ISSUE-069 closes.

    Holds a sprint_state + issues.md pair on disk, runs ``next-action`` against
    them, and can apply "the orchestrator rostered these targets" to the fixture
    between invocations so a *second* invocation can be asserted on. A
    single-invocation test cannot observe a boundary that moves as the roster
    grows, which is precisely why Harm A shipped.
    """

    def __init__(self, tmp_path, rows, board, *, watermark=None, meta_extra=(),
                 extra_sections="", name="replay"):
        self.sprint_path = tmp_path / f"sprint_state_{name}.md"
        self.issues_path = tmp_path / f"issues_{name}.md"
        self.rows = [tuple(r) for r in rows]
        self.board = {num: dict(kw) for num, kw in board.items()}
        self.sprint_path.write_text(
            _sprint_state(
                self.rows,
                watermark=watermark,
                meta_extra=meta_extra,
                extra_sections=extra_sections,
            ),
            encoding="utf-8",
        )
        self._write_board()
        self.last_stdout = ""

    # -- fixture state ------------------------------------------------

    def _write_board(self):
        self.issues_path.write_text(_board_text(self.board), encoding="utf-8")

    def issues_meta(self):
        """Board metadata as the ENGINE will see it.

        Derived by running the real ``parse_issues_metadata`` over the generated
        markdown rather than hand-built, so a direct unit call in a test cannot
        drift from the CLI path (the GAP-068i fixture-drift hollow-pass).
        """
        return parse_issues_metadata(self.issues_path.read_text(encoding="utf-8"))

    def sprint_rows(self):
        return sq.parse_sprint_table(self.sprint_path.read_text(encoding="utf-8"))

    def board_backlog_ids(self):
        return [
            f"ISSUE-{num}"
            for num, kw in sorted(self.board.items())
            if kw.get("status", "backlog") == "backlog"
        ]

    # -- invocation ---------------------------------------------------

    def run(self, capsys, *extra_argv):
        """Invoke ``next-action`` and return ``(exit_code, parsed_json)``.

        ``--no-check-merged`` is always passed so no test can reach a real ``gh``.
        """
        exit_code = sq.main([
            "next-action",
            "--sprint-state", str(self.sprint_path),
            "--issues", str(self.issues_path),
            "--no-check-merged",
            *extra_argv,
        ])
        self.last_stdout = capsys.readouterr().out
        return exit_code, json.loads(self.last_stdout)

    # -- mutation -----------------------------------------------------

    def apply_roster(self, issue_ids, *, phase="shipped"):
        """Replay the orchestrator's roster mutation for ``issue_ids``.

        Appends Issue Progress rows and flips the Board ``Status`` to ``done``.
        Self-checking: asserts the ``## Meta`` block (and therefore the pin under
        test) is byte-preserved, because a harness that quietly dropped the pin
        would make every pinned-boundary assertion below vacuous.
        """
        text = self.sprint_path.read_text(encoding="utf-8")
        meta_before = _meta_block(text)
        new_rows = [(iid, "active", "1", "—", phase) for iid in issue_ids]
        self.sprint_path.write_text(
            _append_progress_rows(text, new_rows), encoding="utf-8"
        )
        meta_after = _meta_block(self.sprint_path.read_text(encoding="utf-8"))
        assert meta_after == meta_before, (
            "replay harness must preserve the ## Meta block — a phase executor "
            "appends table rows, it does not rewrite Meta"
        )
        self.rows += new_rows
        for iid in issue_ids:
            self.board.setdefault(iid.split("-", 1)[1], {})["status"] = "done"
        self._write_board()
        return self

    def drop_watermark_line(self):
        """Negative-control mutation: remove the pin, keep everything else identical."""
        text = self.sprint_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        kept = [line for line in lines if not _FIELD_LINE_RE.match(line)]
        assert len(kept) == len(lines) - 1, (
            "negative control must remove exactly one field line "
            f"(removed {len(lines) - len(kept)})"
        )
        self.sprint_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        return self


def _visible(result):
    """The IDs an invocation made visible: surfaced in ``unrostered`` OR targeted."""
    return set(result.get("unrostered", [])) | set(result.get("targets", []))


def _monotonicity_gaps(first, second, board_backlog_ids):
    """Violations of the within-sprint visibility invariant.

    Invariant: *every issue surfaced (in ``unrostered``) or targeted by iteration
    1 that is still Board ``backlog`` when iteration 2 runs is surfaced or
    targeted by iteration 2.* An empty list means the invariant holds. The same
    predicate drives both the positive tests (expect ``[]``) and the pin-removed
    negative controls (expect the exact ID that vanishes), so the predicate
    itself is mutation-tested.
    """
    still_open = _visible(first) & set(board_backlog_ids)
    return sorted(still_open - _visible(second))


# ── Scenario fixtures ───────────────────────────────────────────────


def _ac1_replay(tmp_path, *, watermark="ISSUE-062", name="ac1"):
    """Pinned boundary ISSUE-062; the roster has SINCE GROWN to 063 and 065.

    ISSUE-064 is still Board ``backlog`` with its dependency (ISSUE-063) shipped.
    Pinned boundary 62 → 064 is above it → surfaced. Re-derived boundary 65 →
    064 falls below → vanishes entirely (Harm A).
    """
    shipped = list(range(56, 63)) + [63, 65]
    rows = [(f"ISSUE-{n:03d}", "active", "1", "—", "shipped") for n in shipped]
    board = {f"{n:03d}": {"status": "done"} for n in shipped}
    board["064"] = {"status": "backlog", "priority": "P2", "depends_on": "ISSUE-063"}
    return _Replay(tmp_path, rows, board, watermark=watermark, name=name)


def _discovery_replay(tmp_path, *, watermark="ISSUE-062", name="disc"):
    """The SPEC-055 063/064/065 shape at SPRINT START (nothing discovered rostered yet)."""
    rows = [(f"ISSUE-{n:03d}", "active", "1", "—", "shipped") for n in range(56, 63)]
    board = {f"{n:03d}": {"status": "done"} for n in range(56, 63)}
    board["063"] = {"status": "backlog", "priority": "P1", "depends_on": "ISSUE-056"}
    board["064"] = {"status": "backlog", "priority": "P2", "depends_on": "ISSUE-063"}
    board["065"] = {"status": "backlog", "priority": "P1", "depends_on": "ISSUE-058"}
    return _Replay(tmp_path, rows, board, watermark=watermark, name=name)


def _inversion_replay(tmp_path, *, watermark="ISSUE-062", name="inv"):
    """Priority inverts ID order: a P0 ISSUE-064 above an open P1 ISSUE-063.

    ``implement_ready`` is priority-sorted, so the HIGHER ID dispatches first and
    a re-derived boundary then buries the lower-ID P1. This is the general class
    of Harm A; the 063/064/065 fixture is only one instance of it.
    """
    rows = [(f"ISSUE-{n:03d}", "active", "1", "—", "shipped") for n in range(56, 63)]
    board = {f"{n:03d}": {"status": "done"} for n in range(56, 63)}
    board["063"] = {"status": "backlog", "priority": "P1"}
    board["064"] = {"status": "backlog", "priority": "P0"}
    return _Replay(tmp_path, rows, board, watermark=watermark, name=name)


#: The reviewer's verified Harm B fixture: five higher-ID Board issues open while
#: the sprint is deliberately scoped on ISSUE-010/011 debt.
HARM_B_ABOVE = [
    "ISSUE-040", "ISSUE-055", "ISSUE-066", "ISSUE-067", "ISSUE-068",
]


def _harm_b_replay(tmp_path, *, watermark="ISSUE-011", rostered_backlog=False,
                   name="harmb"):
    """Roster ISSUE-010..011 (pinned ISSUE-011); 040/055/066/067/068 open, dep-free.

    ``rostered_backlog`` leaves ISSUE-011 as an actionable rostered backlog row so
    a test can prove the gate withholds ONLY the above-boundary synthesized rows
    and never touches a rostered row's own outcome.
    """
    rows = [("ISSUE-010", "active", "1", "—", "shipped")]
    board = {"010": {"status": "done"}}
    if rostered_backlog:
        rows.append(("ISSUE-011", "active", "0", "—", "backlog"))
        board["011"] = {"status": "backlog", "priority": "P2"}
    else:
        rows.append(("ISSUE-011", "active", "1", "—", "shipped"))
        board["011"] = {"status": "done"}
    for num in ("040", "055", "066", "067", "068"):
        board[num] = {"status": "backlog", "priority": "P1"}
    return _Replay(tmp_path, rows, board, watermark=watermark, name=name)


#: ``unrostered`` the DERIVATION produces for `_matrix_replay` (boundary = 56).
#: Every rejected field variant must fall back to exactly this — the GAP-068h
#: "one bad ID disables the whole control" shape is a silently EMPTIED list.
MATRIX_FALLBACK = ["ISSUE-057", "ISSUE-058"]


def _matrix_replay(tmp_path, *, watermark=None, meta_extra=(), extra_sections="",
                   name="mx"):
    """Untrusted-input fixture where fallback and honour-the-value differ visibly.

    Roster: ISSUE-056 shipped (derivation boundary = 56). Board: 056 done, 057 +
    058 backlog, 066 done (so the live Board max is 66 and a benign ``ISSUE-062``
    passes range sanity — a duplicate must be rejected for being a duplicate, not
    for being out of range). Honouring any of 062/101/999/1101 yields an EMPTY
    ``unrostered``; falling back yields ``MATRIX_FALLBACK``.
    """
    rows = [("ISSUE-056", "active", "1", "—", "shipped")]
    board = {
        "056": {"status": "done"},
        "057": {"status": "backlog", "priority": "P1"},
        "058": {"status": "backlog", "priority": "P1"},
        "066": {"status": "done"},
    }
    return _Replay(
        tmp_path, rows, board,
        watermark=watermark, meta_extra=meta_extra,
        extra_sections=extra_sections, name=name,
    )


# ── parse_roster_watermark: the 3-tuple contract ────────────────────


class TestParseRosterWatermarkContract:
    """``parse_roster_watermark(sprint_text, issues_meta)`` → ``(num, detail, present)``.

    ``present`` is keyed on *field-shaped line found anywhere in the document*,
    independent of acceptance, because the dispatch gate fails CLOSED on a
    mangled pin: "we found a boundary declaration and refused it" and "there is
    no boundary declaration" must be distinguishable by the caller.
    """

    def test_canonical_accepted_field_returns_num_and_no_detail(self):
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark="ISSUE-062")
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num == 62
        assert detail is None
        assert present is True

    def test_absent_field_returns_none_none_false(self):
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")])
        assert sq.parse_roster_watermark(text, {"ISSUE-065": _meta()}) == (
            None, None, False,
        )

    def test_prose_mention_mid_line_is_not_detected(self):
        """Detection is START-anchored: prose must not manufacture a `present` flag.

        A ``present`` false positive closes the dispatch gate, so loose matching
        here would silently stop the engine dispatching discovered work.
        """
        text = _sprint_state(
            [("ISSUE-056", "active", "1", "—", "shipped")],
            meta_extra=("- Note: the roster-watermark: boundary is pinned at start",),
        )
        assert sq.parse_roster_watermark(text, {}) == (None, None, False)

    @pytest.mark.parametrize("line", [
        f"- {FIELD}: ISSUE-062",
        f"{FIELD}: ISSUE-062",
        f"- **{FIELD}**: ISSUE-062",
        "- roster-watermark: ISSUE-062",
        "- ROSTER-WATERMARK: ISSUE-062",
        f"* {FIELD}: ISSUE-062",
    ])
    def test_detection_is_broad_enough_that_nothing_sneaks_past(self, line):
        """Detection is deliberately BROAD (occurrence-whitelist, not a blacklist).

        A variant the detector misses is honoured-by-omission: the gate opens and
        the boundary silently reverts to the derivation with no announcement.
        """
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             meta_extra=(line,))
        _, _, present = sq.parse_roster_watermark(text, {})
        assert present is True, f"field-shaped line not detected: {line!r}"

    def test_miscased_field_name_is_found_and_rejected(self):
        """Found (announced) AND rejected — never silently honoured, never ignored."""
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             meta_extra=("- roster-watermark: ISSUE-062",))
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num is None
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_decorated_field_name_is_found_and_rejected(self):
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             meta_extra=(f"- **{FIELD}**: ISSUE-062",))
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num is None
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_duplicate_field_benign_value_first_is_rejected(self):
        """ISSUE-042 duplicate-key pattern: collect ALL occurrences, then refuse.

        A first-match parser would honour the benign ``ISSUE-062`` and ignore the
        appended ``ISSUE-999`` — which is exactly how this control loosens
        silently, since the loosened boundary looks identical to a correct one.
        """
        text = _sprint_state(
            [("ISSUE-056", "active", "1", "—", "shipped")],
            meta_extra=(f"- {FIELD}: ISSUE-062", f"- {FIELD}: ISSUE-999"),
        )
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num is None, "neither duplicate value may be honoured"
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_second_copy_in_a_fenced_block_still_counts_as_a_duplicate(self):
        """Occurrence counting is deliberately FENCE-BLIND.

        A fence-aware count and a fence-blind count degrade to the same announced
        fallback here, so the simpler rule is chosen: both directions are safe,
        and the fence-blind one cannot be defeated by wrapping a second field in
        backticks.
        """
        text = _sprint_state(
            [("ISSUE-056", "active", "1", "—", "shipped")],
            watermark="ISSUE-062",
            extra_sections=f"## Notes\n```\n- {FIELD}: ISSUE-999\n```\n",
        )
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num is None
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_field_outside_any_meta_section_is_rejected(self):
        text = _sprint_state(
            [("ISSUE-056", "active", "1", "—", "shipped")],
            extra_sections=f"## Notes\n- {FIELD}: ISSUE-062\n",
        )
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num is None
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_meta_section_ends_at_the_next_h2_heading(self):
        """The ``## Meta`` window is ``## Meta`` → next ``## `` → EOF.

        Pins the boundary explicitly: an otherwise-canonical field under a LATER
        ``## `` heading is outside Meta and must be refused, so a stray paste into
        a sibling section cannot redefine the sprint's dispatch scope.
        """
        text = (
            "# Sprint State\n\n"
            "## Meta\n- Status: running\n\n"
            "## Issue Progress\n"
            "| Issue | Status | Attempts | Last Error | Phase |\n"
            "|-------|--------|----------|------------|-------|\n"
            "| ISSUE-056 | active | 1 | — | shipped |\n\n"
            f"## Notes\n- {FIELD}: ISSUE-062\n"
        )
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert (num, present) == (None, True)
        assert isinstance(detail, str) and detail.strip()

    @pytest.mark.parametrize("value", [
        "ISSUE-abc", "62", "ISSUE-", "", "ISSUE--1",
        "**ISSUE-101**", "ISSUE-101 (retry)", "`ISSUE-101`", "ISSUE-NNN",
    ])
    def test_value_must_fullmatch_the_canonical_id_shape(self, value):
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark=value)
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-105": _meta()})
        assert num is None, f"{value!r} must not be honoured"
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_nine_digit_value_is_accepted_and_ten_digit_is_rejected(self):
        """The digit run is BOUNDED at ``\\d{1,9}`` — pin both sides of the bound.

        An unbounded ``\\d+`` fed to ``int()`` raises past CPython's 4300-digit
        cap, i.e. a traceback instead of JSON from the script that drives the
        sprint loop.
        """
        nine = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark="ISSUE-123456789")
        assert sq.parse_roster_watermark(nine, {}) == (123456789, None, True)

        ten = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                            watermark="ISSUE-1234567890")
        num, detail, present = sq.parse_roster_watermark(ten, {})
        assert num is None
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_overlong_digit_run_is_rejected_without_valueerror_and_truncated(self):
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark=f"ISSUE-{OVERLONG_DIGITS}")
        num, detail, present = sq.parse_roster_watermark(text, {"ISSUE-065": _meta()})
        assert num is None
        assert present is True
        assert isinstance(detail, str) and detail.strip()
        assert "1" * 60 not in detail, (
            "a rejected raw value must be truncated (max 40 chars + ellipsis) — "
            "a pathological value must not be amplified through the message"
        )
        assert len(detail) < 300

    def test_value_above_the_live_board_max_is_rejected(self):
        """Range sanity against the LIVE Board.

        A boundary above every real ID silences the whole control while looking
        perfectly well-formed — the GAP-068h "one bad ID disables the control"
        shape, except the value is not even malformed.
        """
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark="ISSUE-1101")
        meta = {"ISSUE-056": _meta(status="done"), "ISSUE-058": _meta()}
        num, detail, present = sq.parse_roster_watermark(text, meta)
        assert num is None
        assert isinstance(detail, str) and detail.strip()
        assert present is True

    def test_value_equal_to_the_board_max_is_accepted(self):
        """The range check is ``<=``, not ``<`` — pin the inclusive boundary."""
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark="ISSUE-058")
        meta = {"ISSUE-056": _meta(status="done"), "ISSUE-058": _meta()}
        assert sq.parse_roster_watermark(text, meta) == (58, None, True)

    @pytest.mark.parametrize("meta", [{}, {"TASK-7": {}}, {"ISSUE-abc": {}}])
    def test_range_check_skipped_when_board_has_no_parseable_ids(self, meta):
        """No parseable Board ID → no range oracle → do not invent one.

        Refusing every value when the Board is unreadable would turn an unrelated
        issues.md problem into a silent loss of the pinned boundary.
        """
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark="ISSUE-999")
        assert sq.parse_roster_watermark(text, meta) == (999, None, True)

    def test_board_max_computation_ignores_overlong_board_ids(self):
        """The range check scans ``issues_meta`` — that scan needs the bound too.

        An overlong Board heading reaching ``int()`` on the second scan site is
        the same CPython 4300-digit crash, just via a different input file.
        """
        text = _sprint_state([("ISSUE-056", "active", "1", "—", "shipped")],
                             watermark="ISSUE-062")
        meta = {f"ISSUE-{'9' * 4301}": _meta(), "ISSUE-065": _meta()}
        assert sq.parse_roster_watermark(text, meta) == (62, None, True)

    def test_never_raises_on_hostile_input(self):
        """``parse_roster_watermark`` NEVER raises — ``## Meta`` is untrusted input.

        The block is a workspace-writable file the queue reads back and acts on
        (review lesson: validate at read time; treat any violation as "fall back
        + announce", never as data, and never as a traceback).
        """
        hostile = [
            "",
            "no headings at all",
            "## Meta",
            f"## Meta\n- {FIELD}:",
            f"## Meta\n- {FIELD}: ",
            f"## Meta\n- {FIELD} : ISSUE-062",
            f"## Meta\n-   {FIELD}  :  ISSUE-062  ",
            f"## Meta\n- {FIELD}: ISSUE-062\\nISSUE-999",
            f"## Meta\n- {FIELD}: ISSUE-0\x0062",
            "\x00\x01\x02\xff﻿## Meta\n- %s: \x00\n" % FIELD,
            "\n".join(["filler line"] * 10_000),
            "\n".join(["## Meta", f"- {FIELD}: ISSUE-062"] * 50),
            f"## meta\n- {FIELD}: ISSUE-062",
        ]
        metas = [{}, {"ISSUE-065": _meta()}, {f"ISSUE-{'9' * 4301}": _meta()}]
        for text in hostile:
            for meta in metas:
                result = sq.parse_roster_watermark(text, meta)
                assert isinstance(result, tuple) and len(result) == 3, (
                    f"bad shape for {text[:40]!r}: {result!r}"
                )
                num, detail, present = result
                assert num is None or isinstance(num, int)
                assert detail is None or isinstance(detail, str)
                assert isinstance(present, bool)
                if num is not None:
                    assert detail is None, "an accepted value carries no rejection"


# ── augment_roster_from_board: the pinned boundary ──────────────────


class TestAugmentRosterPinnedBoundary:
    """``pinned_watermark`` is keyword-only and additive.

    The whole point is that the boundary STOPS being a function of the mutable
    roster. These tests assert the pin wins over ``max(rostered_nums)`` and that
    every legacy path (positional call, 2-tuple return, empty table, no canonical
    cell) is byte-identical when the pin is absent.
    """

    def test_positional_call_and_2_tuple_return_unchanged(self):
        rows = [_row("ISSUE-056")]
        result = sq.augment_roster_from_board(rows, {"ISSUE-063": _meta()})
        assert isinstance(result, tuple) and len(result) == 2
        augmented, unrostered = result
        assert unrostered == ["ISSUE-063"]
        assert augmented[: len(rows)] == rows

    def test_pin_none_preserves_the_legacy_max_derivation(self):
        rows = [_row("ISSUE-056"), _row("ISSUE-065")]
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-064": _meta()}, pinned_watermark=None
        )
        assert unrostered == [], "derivation boundary 65 hides ISSUE-064"
        assert augmented == rows

    def test_pinned_boundary_is_not_moved_by_a_grown_roster(self):
        """The Harm A unit: same inputs, pinned boundary → ISSUE-064 stays visible."""
        rows = [_row("ISSUE-056"), _row("ISSUE-065")]
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-064": _meta()}, pinned_watermark=62
        )
        assert unrostered == ["ISSUE-064"]
        assert augmented[-1]["issue"] == "ISSUE-064"
        assert augmented[-1]["unrostered"] is True

    def test_pin_ignores_max_rostered_num_in_both_directions(self):
        """A pin ABOVE the roster max also wins — the pin IS the boundary."""
        rows = [_row("ISSUE-056"), _row("ISSUE-057")]
        meta = {"ISSUE-058": _meta(), "ISSUE-060": _meta()}
        _, unrostered = sq.augment_roster_from_board(rows, meta, pinned_watermark=59)
        assert unrostered == ["ISSUE-060"], (
            "boundary 59 must exclude ISSUE-058 even though the roster max is 57"
        )

    def test_empty_sprint_rows_short_circuits_even_with_a_pin(self):
        """The legacy empty-table path stays FIRST, pin or no pin."""
        augmented, unrostered = sq.augment_roster_from_board(
            [], {"ISSUE-063": _meta()}, pinned_watermark=10
        )
        assert augmented == []
        assert unrostered == []

    def test_pin_synthesizes_without_any_canonical_rostered_cell(self):
        """With a pin, ``max(rostered_nums)`` is not consulted at all.

        A roster of non-canonical cells used to mean "no watermark → no-op"; with
        an explicit boundary that fallback is no longer needed.
        """
        rows = [_row("TASK-7", phase="backlog", attempts="0")]
        _, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-063": _meta()}, pinned_watermark=62
        )
        assert unrostered == ["ISSUE-063"]

    def test_no_pin_and_no_canonical_cell_is_still_a_noop(self):
        rows = [_row("TASK-7", phase="backlog", attempts="0")]
        augmented, unrostered = sq.augment_roster_from_board(
            rows, {"ISSUE-063": _meta()}
        )
        assert unrostered == []
        assert augmented == rows

    def test_inputs_are_never_mutated_by_a_pinned_call(self):
        rows = [_row("ISSUE-056"), _row("ISSUE-065")]
        meta = {"ISSUE-064": _meta()}
        rows_snapshot = copy.deepcopy(rows)
        meta_snapshot = copy.deepcopy(meta)
        sq.augment_roster_from_board(rows, meta, pinned_watermark=62)
        assert rows == rows_snapshot
        assert meta == meta_snapshot

    def test_pin_keeps_every_other_candidate_filter(self):
        """The pin replaces the BOUNDARY only — manual/status/rostered filters hold."""
        rows = [_row("ISSUE-056")]
        meta = {
            "ISSUE-063": _meta(manual=True),
            "ISSUE-064": _meta(status="done"),
            "ISSUE-065": _meta(status="backlog (blocked — do NOT dispatch)"),
            "ISSUE-066": _meta(),
        }
        _, unrostered = sq.augment_roster_from_board(rows, meta, pinned_watermark=10)
        assert unrostered == ["ISSUE-066"]


# ── AC-1 ────────────────────────────────────────────────────────────


class TestAC1PinnedBoundaryKeepsLowerIdSiblingVisible:
    """AC-1: pinned ISSUE-062, roster grown to 063+065, ISSUE-064 still backlog.

    This is ISSUE-068's own motivating case, replayed one iteration later. On the
    re-derived boundary it returns a BARE ``DONE``: the control re-hides exactly
    the issue it was built to surface.
    """

    def test_ac1_issue_064_is_surfaced_and_the_done_is_annotated(self, tmp_path, capsys):
        replay = _ac1_replay(tmp_path)
        exit_code, out = replay.run(capsys)
        assert out["unrostered"] == ["ISSUE-064"]
        assert out["stranded"] == ["ISSUE-064"]
        assert out["action"] == "DONE"
        assert "ISSUE-064" in out["reason"]
        assert "stranded" in out["reason"]
        assert "pinned at ISSUE-062" in out["reason"]
        assert exit_code == 1

    def test_ac1_negative_control_without_the_pin_064_vanishes_entirely(
        self, tmp_path, capsys
    ):
        """The harm, reproduced — so the pin is proven load-bearing.

        Byte-identical fixture with only the ``Roster-Watermark`` line removed:
        ISSUE-064 is absent from the output ENTIRELY and the ``reason`` is the
        bare legacy DONE text. If this ever stops holding, the two fixtures are no
        longer differing by one line and the AC-1 assertion above is vacuous.
        """
        replay = _ac1_replay(tmp_path, name="ac1neg").drop_watermark_line()
        exit_code, out = replay.run(capsys)
        assert out == {
            "action": "DONE",
            "targets": [],
            "reason": "All issues are shipped, waiting, or dropped",
        }
        assert "ISSUE-064" not in json.dumps(out)
        assert exit_code == 1

    def test_ac1_with_the_optin_064_is_actually_targeted(self, tmp_path, capsys,
                                                         monkeypatch):
        """Surfacing is the AC; dispatchability is the proof the row is real."""
        monkeypatch.setenv(KNOB, "1")
        replay = _ac1_replay(tmp_path, name="ac1opt")
        exit_code, out = replay.run(capsys)
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-064"]
        assert out["unrostered"] == ["ISSUE-064"]
        assert KNOB in out["reason"]
        assert exit_code == 0


# ── AC-2 ────────────────────────────────────────────────────────────


class TestAC2TwoIterationReplayMonotonicity:
    """AC-2: visibility is MONOTONIC within a sprint.

    The invariant: every issue surfaced or targeted by iteration 1 that is still
    Board ``backlog`` when iteration 2 runs is surfaced or targeted by iteration
    2. The opt-in knob is set in these tests only so iteration 1 genuinely
    *dispatches* and there is a real roster mutation to replay; the invariant
    itself is about visibility, not dispatch.
    """

    def test_ac2_replay_063_064_065_is_monotonic(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setenv(KNOB, "1")
        replay = _discovery_replay(tmp_path, name="ac2a")

        _, first = replay.run(capsys)
        assert first["action"] == "PIPELINE"
        assert first["targets"] == ["ISSUE-063", "ISSUE-065"]
        assert first["unrostered"] == ["ISSUE-063", "ISSUE-064", "ISSUE-065"]

        replay.apply_roster(first["targets"])

        _, second = replay.run(capsys)
        assert _monotonicity_gaps(first, second, replay.board_backlog_ids()) == []
        assert "ISSUE-064" in _visible(second)
        assert second["targets"] == ["ISSUE-064"]

    def test_ac2_replay_priority_inverted_shape_is_monotonic(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setenv(KNOB, "1")
        replay = _inversion_replay(tmp_path, name="ac2b")

        _, first = replay.run(capsys, "--max-parallel", "1")
        assert first["targets"] == ["ISSUE-064"], "priority must invert ID order"
        assert first["unrostered"] == ["ISSUE-063", "ISSUE-064"]

        replay.apply_roster(first["targets"])

        _, second = replay.run(capsys, "--max-parallel", "1")
        assert _monotonicity_gaps(first, second, replay.board_backlog_ids()) == []
        assert "ISSUE-063" in _visible(second)

    def test_ac2_negative_control_invariant_is_violated_without_the_pin(
        self, tmp_path, capsys, monkeypatch
    ):
        """Mutation test for the invariant itself.

        Same fixture state, pin line removed. If ``_monotonicity_gaps`` could not
        detect the regression the positive tests above would be decorative — so
        the exact vanished ID is pinned here. Reverting the implementation to the
        ``max()`` derivation makes the positive tests fail; this one keeps
        documenting the legacy behaviour the fallback must preserve.
        """
        monkeypatch.setenv(KNOB, "1")
        replay = _discovery_replay(tmp_path, name="ac2neg").drop_watermark_line()

        _, first = replay.run(capsys)
        assert first["targets"] == ["ISSUE-063", "ISSUE-065"]

        replay.apply_roster(first["targets"])

        _, second = replay.run(capsys)
        assert _monotonicity_gaps(first, second, replay.board_backlog_ids()) == [
            "ISSUE-064"
        ]
        assert "ISSUE-064" not in json.dumps(second)

    def test_ac2_harness_preserves_the_meta_pin_across_the_rewrite(self, tmp_path):
        """The harness is only trustworthy if the rewrite keeps the pin.

        Pinned here directly (not just via the in-helper assertion) because a
        harness that dropped the field would turn every AC-2/AC-3 assertion into
        an unannounced legacy-path test.
        """
        replay = _ac1_replay(tmp_path, name="ac2meta")
        replay.apply_roster(["ISSUE-066"])
        text = replay.sprint_path.read_text(encoding="utf-8")
        assert f"- {FIELD}: ISSUE-062" in _meta_block(text)
        assert "| ISSUE-066 | active | 1 | — | shipped |" in text
        rows = replay.sprint_rows()
        assert rows[-1]["issue"] == "ISSUE-066"
        assert rows[-1]["phase"] == "shipped"


# ── AC-3 ────────────────────────────────────────────────────────────


class TestAC3PriorityInversionAsAClass:
    """AC-3: the harm is fixed as a CLASS, not for the 063/064/065 shape.

    ``implement_ready`` is priority-sorted, so any P0 with a higher ID than an
    open P1 reproduces Harm A — the dispatch order and the boundary derivation
    disagree about what "newest" means.
    """

    def test_ac3_optin_dispatch_then_lower_id_p1_still_surfaced(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setenv(KNOB, "1")
        replay = _inversion_replay(tmp_path, name="ac3a")

        _, first = replay.run(capsys, "--max-parallel", "1")
        assert first["action"] == "PIPELINE"
        assert first["targets"] == ["ISSUE-064"]

        replay.apply_roster(["ISSUE-064"])

        _, second = replay.run(capsys, "--max-parallel", "1")
        assert second["unrostered"] == ["ISSUE-063"]
        assert second["targets"] == ["ISSUE-063"]
        assert "ISSUE-063" in second["reason"]

    def test_ac3_manual_roster_between_iterations_keeps_p1_surfaced(
        self, tmp_path, capsys, monkeypatch
    ):
        """No opt-in: the orchestrator rosters the P0 by hand between iterations."""
        monkeypatch.delenv(KNOB, raising=False)
        replay = _inversion_replay(tmp_path, name="ac3b")

        _, first = replay.run(capsys)
        assert first["action"] == "DONE"
        assert first["unrostered"] == ["ISSUE-063", "ISSUE-064"]
        assert first["stranded"] == ["ISSUE-063", "ISSUE-064"]

        replay.apply_roster(["ISSUE-064"])

        _, second = replay.run(capsys)
        assert second["unrostered"] == ["ISSUE-063"]
        assert "ISSUE-063" in second["reason"]
        assert _monotonicity_gaps(first, second, replay.board_backlog_ids()) == []

    def test_ac3_negative_control_without_the_pin_the_p1_vanishes(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setenv(KNOB, "1")
        replay = _inversion_replay(tmp_path, name="ac3neg").drop_watermark_line()

        _, first = replay.run(capsys, "--max-parallel", "1")
        assert first["targets"] == ["ISSUE-064"]

        replay.apply_roster(["ISSUE-064"])

        _, second = replay.run(capsys, "--max-parallel", "1")
        assert "ISSUE-063" not in json.dumps(second)
        assert _monotonicity_gaps(first, second, replay.board_backlog_ids()) == [
            "ISSUE-063"
        ]


# ── AC-4 ────────────────────────────────────────────────────────────


class TestAC4AboveBoundaryFlaggedNeverTargeted:
    """AC-4 (Harm B): out-of-scope work is FLAGGED, never auto-driven to merge.

    ISSUE-068's AC only required *flagging*. Autonomous *targeting* of unscoped
    work is a choice, and this fixture is the reviewer's verified reproduction:
    a sprint scoped on ISSUE-010/011 debt pulled 040/055/066/067/068 through
    implement → review → ``gh pr merge``.
    """

    def test_ac4_five_newer_issues_are_flagged_and_nothing_targets_them(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.delenv(KNOB, raising=False)
        _, out = _harm_b_replay(tmp_path, name="ac4a").run(capsys)
        # The harm first, so a RED run reads as "out-of-scope work was dispatched".
        assert out["targets"] == [], "out-of-scope work must never be targeted"
        assert out["action"] == "DONE"
        assert out["unrostered"] == HARM_B_ABOVE
        assert out["stranded"] == HARM_B_ABOVE
        for issue_id in HARM_B_ABOVE:
            assert issue_id in out["reason"]

    def test_ac4_reason_names_the_knob_as_the_way_to_opt_in(
        self, tmp_path, capsys, monkeypatch
    ):
        """Withholding must be legible in the sprint log, not inferred from silence."""
        monkeypatch.delenv(KNOB, raising=False)
        _, out = _harm_b_replay(tmp_path, name="ac4b").run(capsys)
        assert KNOB in out["reason"]
        assert "not dispatched" in out["reason"].lower()
        assert "pinned at ISSUE-011" in out["reason"]

    def test_ac4_rostered_rows_own_outcome_is_unaffected(
        self, tmp_path, capsys, monkeypatch
    ):
        """The gate withholds ONLY the synthesized above-boundary ids.

        Contract relaxation scoped to the new caller class (review lesson): an
        actionable ROSTERED backlog row must still dispatch in the same
        invocation in which five above-boundary issues are withheld.
        """
        monkeypatch.delenv(KNOB, raising=False)
        replay = _harm_b_replay(tmp_path, rostered_backlog=True, name="ac4c")
        exit_code, out = replay.run(capsys)
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-011"]
        assert out["unrostered"] == HARM_B_ABOVE
        assert not set(out["targets"]) & set(HARM_B_ABOVE)
        assert KNOB in out["reason"]
        assert exit_code == 0

    def test_ac4_withheld_ids_stay_out_of_implement_ready_only(
        self, tmp_path, capsys, monkeypatch
    ):
        """Withheld ≠ dropped: they remain in ``unrostered`` and in ``stranded``."""
        monkeypatch.delenv(KNOB, raising=False)
        _, out = _harm_b_replay(tmp_path, name="ac4d").run(capsys)
        assert set(out["unrostered"]) == set(HARM_B_ABOVE)
        assert set(out["stranded"]) == set(HARM_B_ABOVE)


# ── AC-5 ────────────────────────────────────────────────────────────


class TestAC5DispatchOptIn:
    """AC-5: the knob opens the gate and names itself in ``reason``.

    Env-knob documentation lesson: the broadened scope has to be visible in the
    sprint log rather than inferred, because the same JSON shape otherwise
    describes both a deliberately widened sprint and a runaway one.
    """

    def test_ac5_optin_targets_above_boundary_and_names_the_knob(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setenv(KNOB, "1")
        exit_code, out = _harm_b_replay(tmp_path, name="ac5a").run(capsys)
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-040", "ISSUE-055", "ISSUE-066"]
        assert out["unrostered"] == HARM_B_ABOVE
        assert KNOB in out["reason"]
        assert "not dispatched" not in out["reason"].lower()
        assert exit_code == 0

    @pytest.mark.parametrize("value,opt_in", [
        ("1", True), ("true", True), ("TRUE", True), ("True", True),
        ("yes", True), ("on", True), ("ON", True), (" 1 ", True),
        ("0", False), ("false", False), ("", False), ("maybe", False),
        ("2", False), ("no", False), ("off", False), ("1 1", False),
    ])
    def test_ac5_knob_value_matrix_fails_closed(
        self, tmp_path, capsys, monkeypatch, value, opt_in
    ):
        """Only the documented truthy vocabulary opts in; everything else is OFF.

        Fail-closed matters in both directions here: ``0``/``false`` reading as
        truthy would dispatch unscoped work, which is the harm itself.
        """
        monkeypatch.setenv(KNOB, value)
        _, out = _harm_b_replay(tmp_path, name=f"ac5_{abs(hash(value))}").run(capsys)
        if opt_in:
            assert out["action"] == "PIPELINE", f"{value!r} should opt in"
            assert set(out["targets"]) <= set(HARM_B_ABOVE)
            assert out["targets"]
            # Not just "it dispatched" — the legacy no-gate engine also
            # dispatches. The knob's NAME in `reason` is what distinguishes a
            # deliberately widened sprint from an ungated one.
            assert KNOB in out["reason"], f"{value!r} opted in without saying so"
        else:
            assert out["action"] == "DONE", f"{value!r} must NOT opt in"
            assert out["targets"] == []
            assert out["stranded"] == HARM_B_ABOVE

    def test_ac5_knob_is_read_at_call_time_not_at_import_time(
        self, tmp_path, capsys, monkeypatch
    ):
        """``scripts.sprint_queue`` was imported long before this test ran.

        If the knob were snapshotted at import time (the shape
        ``GH_MERGE_PROBE_TIMEOUT`` uses) the second invocation below could not
        change behaviour, and the knob would be unsettable by a sprint operator.
        """
        replay = _harm_b_replay(tmp_path, name="ac5call")
        monkeypatch.delenv(KNOB, raising=False)
        _, off = replay.run(capsys)
        monkeypatch.setenv(KNOB, "1")
        _, on = replay.run(capsys)
        assert off["action"] == "DONE"
        assert off["targets"] == []
        assert on["action"] == "PIPELINE"
        assert on["targets"]


# ── AC-6 ────────────────────────────────────────────────────────────


class TestAC6BackwardCompatibilityAbsentField:
    """AC-6: with no ``Roster-Watermark`` line, behaviour is the legacy derivation.

    Pinned by byte-identity, not by eyeball — this is why every existing ISSUE-068
    test (including the TC-068i ``reason`` byte-pins) stays green, and it is the
    reason the dispatch gate keys on field PRESENCE rather than acceptance.
    """

    def test_ac6_legacy_done_output_is_byte_identical(self, tmp_path, capsys):
        """The TC-068i shape: below-boundary Board backlog only → untouched DONE."""
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = {"010": {"status": "backlog"}, "056": {"status": "done"}}
        replay = _Replay(tmp_path, rows, board, name="ac6a")
        exit_code, out = replay.run(capsys)
        assert out == {
            "action": "DONE",
            "targets": [],
            "reason": "All issues are shipped, waiting, or dropped",
        }
        assert "unrostered" not in out
        assert "stranded" not in out
        assert exit_code == 1

    def test_ac6_legacy_empty_table_output_is_byte_identical(self, tmp_path, capsys):
        replay = _Replay(tmp_path, [], {"063": {"status": "backlog"}}, name="ac6b")
        exit_code, out = replay.run(capsys)
        assert out == {
            "action": "DONE",
            "targets": [],
            "reason": "No issues found in sprint_state.md Issue Progress table",
        }
        assert exit_code == 1

    def test_ac6_empty_table_with_a_pin_is_still_the_legacy_output(
        self, tmp_path, capsys
    ):
        """``if not sprint_rows`` stays FIRST, even with a pin.

        A pin must not turn an un-started sprint into a dispatcher for the whole
        Board — the empty-table DONE is the only signal that no roster exists.
        """
        replay = _Replay(
            tmp_path, [], {"063": {"status": "backlog"}},
            watermark="ISSUE-010", name="ac6c",
        )
        exit_code, out = replay.run(capsys)
        assert out == {
            "action": "DONE",
            "targets": [],
            "reason": "No issues found in sprint_state.md Issue Progress table",
        }
        assert exit_code == 1

    def test_ac6_absent_field_note_appears_when_unrostered_is_non_empty(
        self, tmp_path, capsys, monkeypatch
    ):
        """The one documented deviation from legacy: a named fallback note.

        Also the "gate open" half of the presence pin — with NO field the legacy
        dispatch behaviour is preserved and ISSUE-057 is targeted.
        """
        monkeypatch.delenv(KNOB, raising=False)
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = {"056": {"status": "done"}, "057": {"status": "backlog"}}
        _, out = _Replay(tmp_path, rows, board, name="ac6d").run(capsys)
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-057"]
        assert out["unrostered"] == ["ISSUE-057"]
        assert "roster-watermark" in out["reason"].lower()
        assert "absent" in out["reason"].lower()
        assert "fell back" in out["reason"]
        assert KNOB not in out["reason"], (
            "no field → no dispatch note; the gate was never engaged"
        )

    def test_ac6_absent_field_stays_quiet_when_unrostered_is_empty(
        self, tmp_path, capsys
    ):
        """Clean runs stay quiet — this is what keeps the TC-068i byte-pins intact."""
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = {"056": {"status": "done"}}
        _, out = _Replay(tmp_path, rows, board, name="ac6e").run(capsys)
        assert out["reason"] == "All issues are shipped, waiting, or dropped"
        assert "roster-watermark" not in out["reason"].lower()


# ── AC-7 ────────────────────────────────────────────────────────────


#: ``Roster-Watermark`` VALUES that must be refused. Each is paired with the
#: fixture `_matrix_replay`, where honouring any of them empties ``unrostered``
#: and falling back yields ``MATRIX_FALLBACK`` — so "rejected" is behaviourally
#: observable, not merely a message.
_REJECTED_VALUES = [
    ("malformed_non_numeric", "ISSUE-abc"),
    ("malformed_bare_number", "62"),
    ("malformed_no_digits", "ISSUE-"),
    ("malformed_empty_value", ""),
    ("malformed_negative", "ISSUE--1"),
    ("decorated_bold", "**ISSUE-101**"),
    ("decorated_suffix", "ISSUE-101 (retry)"),
    ("decorated_backticks", "`ISSUE-101`"),
    ("out_of_live_board_range", "ISSUE-1101"),
    ("template_placeholder", "ISSUE-NNN"),
    ("overlong_digit_run", f"ISSUE-{OVERLONG_DIGITS}"),
]

#: Field-LAYOUT violations (name casing, decoration, duplication, placement).
_REJECTED_LAYOUTS = [
    ("duplicate_benign_value_first", {
        "meta_extra": (f"- {FIELD}: ISSUE-062", f"- {FIELD}: ISSUE-999"),
    }),
    ("miscased_field_name", {"meta_extra": ("- roster-watermark: ISSUE-062",)}),
    ("decorated_field_name", {"meta_extra": (f"- **{FIELD}**: ISSUE-062",)}),
    ("outside_any_meta_section", {
        "extra_sections": f"## Notes\n- {FIELD}: ISSUE-062\n",
    }),
    ("second_copy_in_a_fenced_block", {
        "watermark": "ISSUE-062",
        "extra_sections": f"## Notes\n```\n- {FIELD}: ISSUE-999\n```\n",
    }),
]


class TestAC7UntrustedFieldMatrix:
    """AC-7: every refused variant is announced, falls back, and stays useful.

    The ``## Meta`` block is workspace-writable state the queue reads back and
    acts on (review lesson: untrusted input — validate on read). The failure mode
    this matrix exists to prevent is GAP-068h: one bad value silently EMPTYING
    ``unrostered``, so the control reports nothing while looking healthy. Each
    variant therefore asserts in BOTH directions — refused *and* still reporting
    exactly what the derivation would.
    """

    def _assert_rejected_and_fell_back(self, exit_code, out, raw, label):
        # (v) no crash / valid JSON on stdout — json.loads already ran in run().
        assert exit_code in (0, 1), label
        # (i)+(ii) rejected, and the rejection is named in the output.
        assert "rejected" in out["reason"].lower(), f"{label}: {out['reason']}"
        assert "roster-watermark" in out["reason"].lower(), label
        # (iii) the boundary fell back to the max-rostered-ID derivation.
        assert "fell back" in out["reason"].lower(), label
        # (iv) `unrostered_ids` is NOT silently emptied (the GAP-068h shape).
        assert out.get("unrostered") == MATRIX_FALLBACK, label
        assert out.get("stranded") == MATRIX_FALLBACK, label
        # Fail closed: a mangled pin must not re-enable autonomous dispatch.
        assert out["action"] == "DONE", label
        assert out["targets"] == [], label
        assert KNOB in out["reason"], label
        assert "1" * 60 not in raw, (
            f"{label}: a rejected raw value must be truncated before it is "
            "echoed to stdout"
        )

    @pytest.mark.parametrize("label,value", _REJECTED_VALUES,
                             ids=[label for label, _ in _REJECTED_VALUES])
    def test_ac7_rejected_value_variants(self, tmp_path, capsys, monkeypatch,
                                         label, value):
        monkeypatch.delenv(KNOB, raising=False)
        replay = _matrix_replay(tmp_path, watermark=value, name=f"ac7v_{label}")
        exit_code, out = replay.run(capsys)
        self._assert_rejected_and_fell_back(
            exit_code, out, replay.last_stdout, label
        )

    @pytest.mark.parametrize("label,kwargs", _REJECTED_LAYOUTS,
                             ids=[label for label, _ in _REJECTED_LAYOUTS])
    def test_ac7_rejected_layout_variants(self, tmp_path, capsys, monkeypatch,
                                          label, kwargs):
        monkeypatch.delenv(KNOB, raising=False)
        replay = _matrix_replay(tmp_path, name=f"ac7l_{label}", **kwargs)
        exit_code, out = replay.run(capsys)
        self._assert_rejected_and_fell_back(
            exit_code, out, replay.last_stdout, label
        )

    def test_ac7_template_placeholder_is_louder_than_a_deletion(
        self, tmp_path, capsys, monkeypatch
    ):
        """``ISSUE-NNN`` is what a lazy regenerate-from-template rewrite leaves.

        Deliberately pinned as a REJECTION rather than an absence: a placeholder
        means the orchestrator skipped the sprint-start write, which is a process
        bug worth announcing — whereas an absent field is a legitimate in-flight
        sprint from before this feature existed.
        """
        monkeypatch.delenv(KNOB, raising=False)
        replay = _matrix_replay(tmp_path, watermark="ISSUE-NNN", name="ac7nnn")
        _, out = replay.run(capsys)
        assert "rejected" in out["reason"].lower()
        assert "ISSUE-NNN" in out["reason"] or "issue-nnn" in out["reason"].lower()

    def test_ac7_duplicate_honours_neither_value(self, tmp_path, capsys, monkeypatch):
        """Not "first wins", not "last wins" — refuse and announce.

        With this fixture honouring ``ISSUE-062`` and honouring ``ISSUE-999`` both
        empty ``unrostered``, so the non-empty fallback list is proof that neither
        was used.
        """
        monkeypatch.delenv(KNOB, raising=False)
        replay = _matrix_replay(
            tmp_path,
            meta_extra=(f"- {FIELD}: ISSUE-062", f"- {FIELD}: ISSUE-999"),
            name="ac7dup",
        )
        _, out = replay.run(capsys)
        assert out["unrostered"] == MATRIX_FALLBACK
        assert "pinned at" not in out["reason"]
        # Falling back silently looks identical to never having read the field,
        # so the announcement is part of "honours neither".
        assert "rejected" in out["reason"].lower()


class TestAC7PositiveControl:
    """AC-7 positive control: a good value is honoured and BEHAVIOURALLY load-bearing.

    "No rejection message" is not evidence of acceptance — a parser that returned
    ``(None, None, False)`` for everything would pass every rejection test above.
    This fixture is the AC-1 shape, where the pinned boundary (62) and the derived
    one (65) disagree about ISSUE-064.
    """

    def test_ac7_accepted_value_changes_the_outcome_versus_the_derivation(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.delenv(KNOB, raising=False)
        pinned = _ac1_replay(tmp_path, name="ac7pos")
        _, with_pin = pinned.run(capsys)

        derived = _ac1_replay(tmp_path, name="ac7posneg").drop_watermark_line()
        _, without_pin = derived.run(capsys)

        assert with_pin["unrostered"] == ["ISSUE-064"]
        assert "unrostered" not in without_pin
        assert "pinned at ISSUE-062" in with_pin["reason"]
        assert "rejected" not in with_pin["reason"].lower()
        assert "fell back" not in with_pin["reason"].lower()

    def test_ac7_accepted_value_direct_unit_call(self, tmp_path):
        replay = _ac1_replay(tmp_path, name="ac7posunit")
        text = replay.sprint_path.read_text(encoding="utf-8")
        assert sq.parse_roster_watermark(text, replay.issues_meta()) == (
            62, None, True,
        )


class TestAC7GatePresenceFailsClosed:
    """The one place where "fall back" does NOT mean "behave exactly like legacy".

    The dispatch gate keys on field PRESENCE, not acceptance. A mangled pin must
    not silently re-enable autonomous dispatch — otherwise corrupting one line of
    ``## Meta`` becomes a way to widen a sprint's scope without opting in. An
    ABSENT field, by contrast, is an in-flight pre-feature sprint and keeps the
    legacy dispatch behaviour (AC-6). Both directions are asserted here because
    they are easy to conflate in an implementation.
    """

    FIXTURE_ROWS = [("ISSUE-056", "active", "1", "—", "shipped")]
    FIXTURE_BOARD = {"056": {"status": "done"}, "057": {"status": "backlog"}}

    def test_rejected_field_closes_the_gate(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv(KNOB, raising=False)
        replay = _Replay(
            tmp_path, self.FIXTURE_ROWS, self.FIXTURE_BOARD,
            watermark="ISSUE-abc", name="gateclosed",
        )
        exit_code, out = replay.run(capsys)
        assert out["action"] == "DONE"
        assert out["targets"] == []
        assert out["unrostered"] == ["ISSUE-057"]
        assert out["stranded"] == ["ISSUE-057"]
        assert "rejected" in out["reason"].lower()
        assert "fell back" in out["reason"].lower()
        assert KNOB in out["reason"]
        assert exit_code == 1

    def test_absent_field_leaves_the_gate_open(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv(KNOB, raising=False)
        replay = _Replay(
            tmp_path, self.FIXTURE_ROWS, self.FIXTURE_BOARD, name="gateopen",
        )
        exit_code, out = replay.run(capsys)
        assert out["action"] == "PIPELINE"
        assert out["targets"] == ["ISSUE-057"]
        assert KNOB not in out["reason"]
        assert exit_code == 0

    def test_accepted_field_closes_the_gate_without_the_optin(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.delenv(KNOB, raising=False)
        replay = _Replay(
            tmp_path, self.FIXTURE_ROWS, self.FIXTURE_BOARD,
            watermark="ISSUE-056", name="gateaccepted",
        )
        _, out = replay.run(capsys)
        assert out["action"] == "DONE"
        assert out["unrostered"] == ["ISSUE-057"]
        assert "pinned at ISSUE-056" in out["reason"]
        assert KNOB in out["reason"]


# ── reason annotation shapes (Notes A and B) ────────────────────────


class TestReasonAnnotationShapes:
    """All new signals land in ``reason``; NO new top-level JSON key is added.

    ``unrostered`` / ``stranded`` are read by the sprint skill and team-lead, so
    the key set is frozen. The quiet-on-clean-runs rule is what keeps TC-068i's
    byte-pinned ``reason`` untouched.
    """

    def test_no_new_top_level_json_keys(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv(KNOB, raising=False)
        _, out = _harm_b_replay(tmp_path, name="shape_keys").run(capsys)
        assert set(out) == {"action", "targets", "reason", "unrostered", "stranded"}

    def test_accepted_and_clean_run_emits_no_boundary_note(self, tmp_path, capsys):
        """Pin present and ACCEPTED, nothing above it → ``reason`` stays byte-legacy.

        The acceptance is asserted separately so "quiet" cannot be satisfied by a
        parser that rejected the pin (which must be loud) or ignored the field
        entirely (which must emit the absent-field note).
        """
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = {"056": {"status": "done"}}
        replay = _Replay(tmp_path, rows, board, watermark="ISSUE-056",
                         name="shape_clean")
        assert sq.parse_roster_watermark(
            replay.sprint_path.read_text(encoding="utf-8"), replay.issues_meta()
        ) == (56, None, True)
        _, out = replay.run(capsys)
        assert out == {
            "action": "DONE",
            "targets": [],
            "reason": "All issues are shipped, waiting, or dropped",
        }

    def test_rejected_field_is_announced_even_with_empty_unrostered(
        self, tmp_path, capsys, monkeypatch
    ):
        """A refused boundary is always announced — silence would look like health.

        Note B is still omitted here: nothing was withheld, so there is no
        dispatch decision to report.
        """
        monkeypatch.delenv(KNOB, raising=False)
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = {"056": {"status": "done"}}
        replay = _Replay(tmp_path, rows, board, watermark="ISSUE-abc",
                         name="shape_rej")
        _, out = replay.run(capsys)
        assert "rejected" in out["reason"].lower()
        assert "fell back" in out["reason"].lower()
        assert "unrostered" not in out
        assert KNOB not in out["reason"]

    def test_optin_note_omits_the_withheld_wording(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setenv(KNOB, "yes")
        _, out = _harm_b_replay(tmp_path, name="shape_optin").run(capsys)
        assert KNOB in out["reason"]
        assert "not dispatched" not in out["reason"].lower()
        assert "pinned at ISSUE-011" in out["reason"]


# ── Note C: prior-sprint carry-forward diagnosis ────────────────────


class TestCarryForwardGapDiagnosis:
    """``diagnose_carry_forward_gaps`` — a DIAGNOSIS, never a relaxation.

    The rostered-row dependency contract stays TABLE-ONLY (TC-068d pins that: a
    rostered backlog row whose dep is Board-done but has no Issue Progress row
    stays filtered, byte-identically to legacy). That is correct but silent —
    the row simply never dispatches and nothing says why. This helper explains
    the stall in ``reason`` without touching ``action``, ``targets`` or any queue,
    so the contract-relaxation-scoped-to-the-caller-class lesson holds.
    """

    def _gap_fixture(self):
        rows = [_row("ISSUE-056"), _row("ISSUE-069", phase="backlog", attempts="0")]
        meta = {
            "ISSUE-056": _meta(status="done"),
            "ISSUE-068": _meta(status="done"),  # Board-resolved, NO sprint row
            "ISSUE-069": _meta(depends_on=["ISSUE-068"]),
        }
        return rows, meta

    def test_board_resolved_rowless_dep_is_diagnosed(self):
        rows, meta = self._gap_fixture()
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == [], "TC-068d: table-only, still filtered"
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == [
            ("ISSUE-069", ["ISSUE-068"]),
        ]

    @pytest.mark.parametrize("board_status", ["done", "drop", "dropped"])
    def test_each_board_resolved_status_is_diagnosed(self, board_status):
        rows, meta = self._gap_fixture()
        meta["ISSUE-068"] = _meta(status=board_status)
        queues = compute_queues(rows, meta)
        gaps = sq.diagnose_carry_forward_gaps(rows, meta, queues)
        assert gaps == [("ISSUE-069", ["ISSUE-068"])], board_status

    def test_annotated_board_status_is_not_diagnosed(self):
        """Exact-match vocabulary, consistent with the ISSUE-068 filters.

        ``done (sign-off pending)`` does not resolve a dependency, so claiming the
        dep is "Board-resolved" and only its row is missing would be false advice.
        """
        rows, meta = self._gap_fixture()
        meta["ISSUE-068"] = _meta(status="done (security sign-off pending)")
        queues = compute_queues(rows, meta)
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == []

    def test_dep_with_a_row_in_the_table_is_not_diagnosed(self):
        """Isolates the "no row at all" condition.

        The dep is Board-``done`` AND has an Issue Progress row (phase backlog),
        so the dependent is stalled by ordinary in-sprint sequencing — there is
        nothing to carry forward and the hint would be noise.
        """
        rows = [
            _row("ISSUE-056"),
            _row("ISSUE-068", phase="backlog", attempts="0"),
            _row("ISSUE-069", phase="backlog", attempts="0"),
        ]
        meta = {
            "ISSUE-056": _meta(status="done"),
            "ISSUE-068": _meta(status="done"),
            "ISSUE-069": _meta(depends_on=["ISSUE-068"]),
        }
        queues = compute_queues(rows, meta)
        assert "ISSUE-069" not in queues["implement_ready"]
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == []

    def test_ordinary_unresolved_in_sprint_dep_is_not_diagnosed(self):
        rows = [
            _row("ISSUE-068", phase="backlog", attempts="0"),
            _row("ISSUE-069", phase="backlog", attempts="0"),
        ]
        meta = {
            "ISSUE-068": _meta(status="backlog"),
            "ISSUE-069": _meta(depends_on=["ISSUE-068"]),
        }
        queues = compute_queues(rows, meta)
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == []

    def test_synthesized_rows_are_not_diagnosed(self):
        """Scoped to ROSTERED rows: a synthesized row already accepts Board deps."""
        rows = [_row("ISSUE-056")]
        meta = {
            "ISSUE-056": _meta(status="done"),
            "ISSUE-068": _meta(status="done"),
            "ISSUE-069": _meta(depends_on=["ISSUE-068"]),
        }
        augmented, unrostered = sq.augment_roster_from_board(
            rows, meta, pinned_watermark=60
        )
        assert unrostered == ["ISSUE-069"]
        queues = compute_queues(augmented, meta)
        assert queues["implement_ready"] == ["ISSUE-069"]
        assert sq.diagnose_carry_forward_gaps(augmented, meta, queues) == []

    @pytest.mark.parametrize("mutation", [
        {"manual": True},
        {"status_cell": "dropped"},
        {"status_cell": "waiting"},
    ])
    def test_manual_dropped_and_waiting_rows_are_not_diagnosed(self, mutation):
        """Those rows are deliberately out of the pipeline — no stall to explain."""
        rows, meta = self._gap_fixture()
        if "manual" in mutation:
            meta["ISSUE-069"]["manual"] = True
        else:
            rows[1] = _row(
                "ISSUE-069", phase="backlog", attempts="0",
                status=mutation["status_cell"],
            )
        queues = compute_queues(rows, meta)
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == [], mutation

    def test_a_queued_row_is_not_diagnosed(self):
        """Only rows in NO queue are diagnosed — a dispatchable row is not stalled."""
        rows = [_row("ISSUE-069", phase="backlog", attempts="0")]
        meta = {
            "ISSUE-068": _meta(status="done"),
            "ISSUE-069": _meta(depends_on=[]),
        }
        queues = compute_queues(rows, meta)
        assert queues["implement_ready"] == ["ISSUE-069"]
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == []

    def test_diagnosis_mutates_neither_rows_nor_queues(self):
        rows, meta = self._gap_fixture()
        queues = compute_queues(rows, meta)
        rows_snapshot = copy.deepcopy(rows)
        meta_snapshot = copy.deepcopy(meta)
        queues_snapshot = copy.deepcopy(queues)
        sq.diagnose_carry_forward_gaps(rows, meta, queues)
        assert rows == rows_snapshot
        assert meta == meta_snapshot
        assert queues == queues_snapshot

    def test_multiple_deps_are_collected_into_one_clause(self):
        rows = [_row("ISSUE-069", phase="backlog", attempts="0")]
        meta = {
            "ISSUE-067": _meta(status="done"),
            "ISSUE-068": _meta(status="dropped"),
            "ISSUE-069": _meta(depends_on=["ISSUE-067", "ISSUE-068"]),
        }
        queues = compute_queues(rows, meta)
        assert sq.diagnose_carry_forward_gaps(rows, meta, queues) == [
            ("ISSUE-069", ["ISSUE-067", "ISSUE-068"]),
        ]


class TestCarryForwardGapAnnotation:
    """Note C reaches the operator through ``reason`` only."""

    def _carry_forward_replay(self, tmp_path, name="noteC"):
        rows = [
            ("ISSUE-056", "active", "1", "—", "shipped"),
            ("ISSUE-069", "active", "0", "—", "backlog"),
        ]
        board = {
            "056": {"status": "done"},
            "068": {"status": "done"},  # Board-resolved, never rostered
            "069": {"status": "backlog", "depends_on": "ISSUE-068"},
        }
        return _Replay(tmp_path, rows, board, watermark="ISSUE-069", name=name)

    def test_reason_names_the_gap_and_the_carry_forward_remedy(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.delenv(KNOB, raising=False)
        exit_code, out = self._carry_forward_replay(tmp_path).run(capsys)
        assert "ISSUE-069" in out["reason"]
        assert "ISSUE-068" in out["reason"]
        assert "Issue Progress row" in out["reason"]
        assert "carry" in out["reason"].lower()
        assert exit_code == 1

    def test_diagnosis_changes_neither_action_nor_targets(
        self, tmp_path, capsys, monkeypatch
    ):
        """TC-068d intact: the row is explained, not dispatched."""
        monkeypatch.delenv(KNOB, raising=False)
        _, out = self._carry_forward_replay(tmp_path, name="noteCb").run(capsys)
        assert out["action"] == "DONE"
        assert out["targets"] == []
        assert "unrostered" not in out

    def test_no_gap_means_no_note(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv(KNOB, raising=False)
        rows = [("ISSUE-056", "active", "1", "—", "shipped")]
        board = {"056": {"status": "done"}}
        replay = _Replay(tmp_path, rows, board, watermark="ISSUE-056",
                         name="noteCc")
        _, out = replay.run(capsys)
        assert out["reason"] == "All issues are shipped, waiting, or dropped"


# ── Shipped-artifact realism pins ───────────────────────────────────


class TestShippedTemplateCarriesTheField:
    """The engine's contract is worthless if the orchestrator never writes the field.

    Review lesson (generated numbers / derived facts): assert against the SHIPPED
    artifact, not a hand-built fixture, so a template that silently lost the field
    is caught here rather than on the next real sprint.
    """

    def _template_text(self):
        path = REPO_ROOT / "templates" / "sprint_state.md"
        assert path.is_file(), f"missing shipped template: {path}"
        return path.read_text(encoding="utf-8")

    def test_template_meta_block_carries_a_field_shaped_line(self):
        text = self._template_text()
        assert FIELD in text
        assert _FIELD_LINE_RE.search(_meta_block(text)), (
            "the Roster-Watermark line must live inside the template's ## Meta "
            "block — a field outside Meta is rejected by the parser"
        )
        _, _, present = sq.parse_roster_watermark(text, {})
        assert present is True

    def test_template_placeholder_value_is_rejected_not_honoured(self):
        """A from-template rewrite must ANNOUNCE, never honour a fake boundary.

        The template ships a placeholder. If the parser accepted it, a sprint
        regenerated from the template would silently run against an invented
        boundary instead of falling back with a named reason.
        """
        num, detail, present = sq.parse_roster_watermark(self._template_text(), {})
        assert present is True
        assert num is None, "the template placeholder must never parse as a boundary"
        assert isinstance(detail, str) and detail.strip()


class TestSprintSkillDocumentsTheNewContract:
    """``skills/sprint/SKILL.md`` is model-read: stale instructions are live bugs.

    The ratchet workaround the skill currently prescribes ("roster in ascending ID
    order or siblings stop being reported") becomes FALSE once the boundary is
    pinned — and a false instruction is worse than a missing one, because the
    model follows it. The absence assertions below quote the actual current
    sentences (occurrence-whitelist, not a guessed blacklist phrase).
    """

    #: Verbatim fragments of the ratchet workaround as it stands today
    #: (skills/sprint/SKILL.md lines 161-164). Each becomes false once the
    #: boundary is pinned at sprint start.
    NOW_FALSE_FRAGMENTS = [
        "boundary is re-derived from the table on every run",
        "pushes its lower-ID siblings below the",
        "they stop being reported at all",
    ]

    def _skill_text(self):
        path = REPO_ROOT / "skills" / "sprint" / "SKILL.md"
        assert path.is_file(), f"missing generated skill: {path}"
        return path.read_text(encoding="utf-8")

    def test_skill_names_the_dispatch_knob(self):
        assert KNOB in self._skill_text(), (
            "env-knob lesson: a knob that changes autonomous dispatch scope must "
            "be documented where the operating model reads it"
        )

    def test_skill_names_the_meta_field(self):
        assert FIELD in self._skill_text()

    @pytest.mark.parametrize("fragment", NOW_FALSE_FRAGMENTS)
    def test_skill_no_longer_prescribes_the_ratchet_workaround(self, fragment):
        assert fragment not in self._skill_text(), (
            f"stale ratchet instruction still shipped: {fragment!r}"
        )

    def test_generated_skill_opens_with_frontmatter_not_the_autogen_marker(self):
        """ISSUE-035 byte-0 rule: Claude Code drops frontmatter unless it is first.

        Pinned here because this issue edits ``SKILL.md.tmpl`` and regenerates —
        the regeneration step is exactly where the marker gets hoisted above the
        frontmatter by accident.
        """
        text = self._skill_text()
        assert text.startswith("---\n")
        marker = "<!-- AUTO-GENERATED"
        assert marker in text
        assert text.index(marker) > text.index("\n---\n"), (
            "the AUTO-GEN marker must sit BELOW the YAML frontmatter"
        )
