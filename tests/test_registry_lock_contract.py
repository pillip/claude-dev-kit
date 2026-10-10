"""ISSUE-074 — the registry-lock contract must be satisfiable by its named actor.

The defect this file guards: `agents/team-lead.md` forbade itself every
`issues.md` write and delegated them all to `agents/planner.md`, whose `tools:`
line carries no `Bash` — so the designated lock-taker could not invoke
`scripts/flock_edit.sh` / `scripts/registry_edit.sh` at all. The contract
therefore resolved to a **silently unlocked write**: the planner reaches for
`Edit`, the lock is never taken, the write SUCCEEDS, and nothing errors.

Invariant: **every registry write either holds the lock or is impossible —
never "succeeds without it."**

Both halves of that invariant are derived from the files here, never from a
hand-maintained capability table (AC-1):

* capability — parsed out of each `agents/*.md` YAML frontmatter `tools:` line
  (bare `Bash` and prefix-scoped `Bash(...)` both count as "can invoke the
  wrapper");
* responsibility — parsed out of the audited instruction text itself: where the
  text hands the write off, the committer's agent name must be parseable out of
  that very sentence; where it does not, the host agent is on the hook.

Occurrence-whitelist discipline, NOT a phrasing blacklist: a blacklist of
forbidden phrasings passes hollowly the moment someone rewords the sentence, so
instead every audited mutating instruction is pinned by the **entire line** of
its post-fix text plus the actor that text makes responsible for the on-disk
write. A reword FAILS LOUDLY and forces re-triage.

**Pins are whole lines, not slices** (`test_pin_spans_its_whole_line`). A slice
pin resists rewording only of the slice it covers: text APPENDED to the same
line leaves the slice intact, and the drift guard below counts mentioning
*lines*, so a same-line append moves no count either — both halves of the guard
go quiet while the file gains new instruction text. That hole was demonstrated
during the ISSUE-074 review (an "append to `issues.md` yourself with `Edit`"
escape clause tacked onto the end of Append Mode step 5 kept the whole suite
green), so the pins were widened to whole lines rather than answered with a
phrasing blacklist, which AC-1 forbids.

**The brittleness is intentional.** `ISSUES_MD_MENTION_COUNTS` pins the exact
set of agent files that mention `issues.md` and the per-file count of lines that
do. That count pin catches mutating instructions added on NEW lines, while the
whole-line pins catch edits to the audited lines themselves; together they are
what makes the whitelist a whitelist. When either trips, re-audit the new or
changed mention, classify it (read / reference / mutating), then update the
whitelist and the count in the same commit.

Lines classified NON-mutating during the ISSUE-074 audit (hence absent from the
whitelist, but still covered by the count pin): every "Load / Parse / Read
`issues.md`" input line (`developer.md`, `qa-designer.md`, `issue-writer.md`,
`planner.md`, `team-lead.md`), the `templates/issues.md` format references
(`issue-writer.md`), the `issues.md`-as-spec-source line (`figma-converter.md`),
the Output-Structure headings (`planner.md`), the sprint-queue description of
Board auto-consideration (`team-lead.md`), the planner-invocation lines that
merely pass `issues.md` as context (`team-lead.md`), and `agents/planner.md`'s
`description:` role claim ("Maintain issues.md as SSOT"), which designates no
write mechanism — the mechanism lives in Workflow step 10 and Append Mode
step 5, both whitelisted below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = KIT_ROOT / "agents"
SCRIPT_DIR = KIT_ROOT / "scripts"

# The two lock wrappers a registry write must go through. Both execute "$@",
# so invoking either one requires the `Bash` tool.
LOCK_WRAPPERS = ("registry_edit.sh", "flock_edit.sh")

ALL_AGENT_STEMS = tuple(sorted(p.stem for p in AGENT_DIR.glob("*.md")))


# ── file/frontmatter parsing (both halves are derived, never tabulated) ──


def _agent_text(stem: str) -> str:
    path = AGENT_DIR / f"{stem}.md"
    assert path.exists(), f"agents/{stem}.md not found"
    return path.read_text(encoding="utf-8")


def _frontmatter(stem: str) -> str:
    """Return the leading YAML frontmatter block of an agent file."""
    parts = _agent_text(stem).split("---")
    assert len(parts) >= 3, f"agents/{stem}.md: no frontmatter block"
    return parts[1]


def _split_tools(raw: str) -> list[str]:
    """Comma-split a `tools:` value, ignoring commas inside `Bash(...)` args."""
    raw = raw.strip().strip("[]")
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in raw:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _tools_lines(stem: str) -> list[str]:
    """Every `tools:` declaration in the agent's frontmatter (normally one)."""
    return re.findall(r"^tools:\s*(.+)$", _frontmatter(stem), re.MULTILINE)


def _tools(stem: str) -> list[str]:
    """Parse the agent's declared tool entries out of its frontmatter.

    Refuses a duplicate `tools:` key rather than silently reading the first
    one: YAML resolves a duplicate mapping key to the LAST occurrence, while
    this parser reads the FIRST, so a second `tools:` line is a capability the
    oracle cannot see. Demonstrated during the ISSUE-074 review — appending
    `tools: Read, Glob, Grep, Write, Edit, Bash` under agents/planner.md's real
    `tools:` line left the whole suite green while the planner genuinely held
    `Bash`, a hollow pass on AC-4, the one pin that must not be hollow.
    (ISSUE-042's duplicate-key lesson, recurring.)
    """
    declarations = _tools_lines(stem)
    assert declarations, f"agents/{stem}.md: no `tools:` line in frontmatter"
    assert len(declarations) == 1, (
        f"agents/{stem}.md declares {len(declarations)} `tools:` lines in its "
        f"frontmatter: {declarations}. YAML resolves a duplicate key to the "
        f"LAST occurrence while this parser reads the FIRST, so the extra line "
        f"can grant a capability (notably `Bash`) that the capability oracle "
        f"never sees. Collapse them into a single `tools:` line."
    )
    return _split_tools(declarations[0])


def _is_bash_entry(tool: str) -> bool:
    """True for a bare `Bash` grant or a prefix-scoped `Bash(...)` grant."""
    return re.fullmatch(r"bash(\s*\(.*\))?", tool.strip(), re.IGNORECASE) is not None


def _can_take_the_lock(stem: str) -> bool:
    """Can this agent invoke the lock wrappers at all? (i.e. does it have Bash)"""
    return any(_is_bash_entry(t) for t in _tools(stem))


def _mention_counts(needle: str) -> dict[str, int]:
    """{agent filename: number of lines mentioning `needle`} for mentioning files."""
    counts = {}
    for path in sorted(AGENT_DIR.glob("*.md")):
        n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if needle in line)
        if n:
            counts[path.name] = n
    return counts


def _line_with(stem: str, substring: str) -> str | None:
    for line in _agent_text(stem).splitlines():
        if substring in line:
            return line
    return None


def _agents_named_in(text: str, exclude: str) -> set[str]:
    """Agent names (other than `exclude`) appearing as whole tokens in `text`.

    The `[\\w-]` lookarounds keep "developer" from matching inside
    "uiux-developer", so a delegation naming one agent cannot be read as
    naming another.
    """
    return {
        name
        for name in ALL_AGENT_STEMS
        if name != exclude
        and re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text)
    }


# ── the audited occurrence whitelist ────────────────────────────────────


@dataclass(frozen=True)
class RegistryWrite:
    """One audited instruction that mutates `issues.md` on disk.

    `substring` is an exact slice of the post-fix sentence (reword guard).
    `writer` is the agent the text makes responsible for the actual on-disk
    write — equal to `agent` when the host agent writes it itself, otherwise the
    agent the text hands the commit to (and that name must be parseable out of
    the occurrence itself).
    `exempt_reason` is non-empty only for the single legitimate single-writer
    path, and the exemption must additionally be justified in the agent's own
    contract text (see `justification`).
    """

    agent: str
    label: str
    substring: str
    writer: str
    exempt_reason: str = ""
    justification: str = ""

    @property
    def is_delegated(self) -> bool:
        return self.writer != self.agent


REGISTRY_WRITES: tuple[RegistryWrite, ...] = (
    # ── developer: owns its own registry field updates, and has Bash ──
    RegistryWrite(
        agent="developer",
        label="workflow step 14 (registry field update)",
        substring=(
            "14. **Update registry**: Set Branch/GH-Issue/PR/Status in "
            "`issues.md`."
        ),
        writer="developer",
    ),
    # ── issue-writer: appends under the lock itself, and has Bash ──
    RegistryWrite(
        agent="issue-writer",
        label="workflow step 4 (append under the lock)",
        substring=(
            "4. **Append to issues.md**: Use `flock_edit.sh` for safe "
            "concurrent access."
        ),
        writer="issue-writer",
    ),
    # ── planner: greenfield generation (the one single-writer path) ──
    RegistryWrite(
        agent="planner",
        label="workflow step 10 (greenfield generation)",
        substring=(
            "10. **Write output**: Generate `issues.md` using the template "
            "conventions. This is the **only single-writer path**, and it is "
            "gated on the file's **absence**, not on which skill invoked you: "
            "it applies only when no `issues.md` exists yet (greenfield "
            "generation at `/kickoff`, before any sprint exists), so there is "
            "no concurrent writer to lock against and no existing registry "
            "content to clobber. Where `issues.md` already exists — "
            "**including an evidence-mode `/scan` of a brownfield repo**, "
            "which reaches this same step — that licence does **not** apply, "
            "and regenerating the file would clobber a live registry you "
            "cannot lock. Every later modification goes through Append Mode "
            "step 5's prepare-and-hand-off shape — never a direct `Edit` of an "
            "existing `issues.md`."
        ),
        writer="planner",
        exempt_reason=(
            "generation into the ABSENCE of the file (greenfield /kickoff), "
            "before any sprint exists — no concurrent writer to lock against "
            "and no existing content to clobber"
        ),
        justification=(
            "This is the **only single-writer path**, and it is gated on the "
            "file's **absence**, not on which skill invoked you: it applies "
            "only when no `issues.md` exists yet"
        ),
    ),
    # ── planner: Append Mode hands the commit to a Bash-capable caller ──
    RegistryWrite(
        agent="planner",
        label="append mode step 5 (prepare + hand off)",
        substring=(
            "5. **Prepare the `issues.md` append — never write the file "
            "yourself**: this agent's `tools:` line carries **no `Bash`**, so "
            "it **cannot take the `issues.md` lock**, and writing the registry "
            "with `Edit` would be an **unlocked write that still succeeds** — "
            "the one outcome this contract forbids. So **emit, as your output, "
            "an idempotent apply script** that appends the new "
            "`### ISSUE-NNN:` detail blocks AND their `### Backlog` Board "
            "lines. The **idempotence guard is mandatory**: the script must "
            "no-op when its `### ISSUE-NNN:` anchor is already present in "
            "`issues.md` — an apply script re-run without that guard is itself "
            "a duplicate-registry-entry bug. Match that anchor "
            "**line-anchored** (`^### ISSUE-NNN:`) so a "
            "`<!-- ### ISSUE-NNN SHIP NOTE -->` comment or a prose citation "
            "cannot satisfy it, and make the no-op **announce itself on "
            "stderr**, because a silent skip is indistinguishable from a "
            "successful write — the very failure shape this contract exists to "
            "remove. The **Bash-capable caller** (the invoking skill, or "
            "**team-lead**) commits it under the lock via `bash "
            "scripts/registry_edit.sh issues.md -- bash -c "
            "'<apply script>'`. **Quote the payload with a heredoc**: emit the "
            "block body inside `<<'KIT_EOF'` … `KIT_EOF` and never interpolate "
            "a bare `'` into that single-quoted `bash -c` argument — "
            "apostrophes are routine in issue titles and ACs, and one of them "
            "closes the argument early, drops the heredoc delimiter, and "
            "appends a **truncated** block while holding the lock, with no "
            "error raised."
        ),
        writer="team-lead",
    ),
    # ── team-lead: authoring is delegated, committing is not ──
    RegistryWrite(
        agent="team-lead",
        label="quick summary (authoring vs committing split)",
        substring=(
            "- Delegate `issues.md` **authoring** to the planner agent; "
            "**commit** the planner's prepared edit yourself under the "
            "registry lock (team-lead has `Bash`; the planner does not)"
        ),
        writer="team-lead",
    ),
    RegistryWrite(
        agent="team-lead",
        label="ship step 5d (testgen registry registration)",
        substring=(
            "- The testgen flow will create a GH Issue + PR and register in "
            "`issues.md` via Sprint Integration."
        ),
        writer="team-lead",
    ),
    RegistryWrite(
        agent="team-lead",
        label="finalize step 3 (registry finalization under the lock)",
        substring=(
            "3. Complete registry finalization (issues.md Status=done + "
            "backlog [x], CHANGELOG) via `registry_edit.sh`, then the "
            "post-ship test-gap check (same as SHIP step 5)."
        ),
        writer="team-lead",
    ),
    RegistryWrite(
        agent="team-lead",
        label="dynamic issue management (registry write contract)",
        substring=(
            "**Registry write contract.** Every `issues.md` write splits in "
            "two: the **planner authors** the content (decomposition, scope, "
            "AC — never yours to write), and **team-lead commits** it under "
            "the registry lock via `bash scripts/registry_edit.sh issues.md "
            "-- bash -c '<planner's idempotent apply script>'`. The planner "
            "cannot take the lock itself — `agents/planner.md` carries no "
            "`Bash` — so leaving the write to it degrades to an `Edit` that "
            "bypasses the lock and still succeeds. Team-lead therefore never "
            "authors new registry content and never writes the file with "
            "`Write`/`Edit`. The apply script is guarded to no-op when its "
            "`### ISSUE-NNN:` anchor is already present, and team-lead reviews "
            "the script's content before running it — shape validation is not "
            "provenance, so the committing actor is accountable for what it "
            "applies. Compose the payload with a quoted heredoc "
            "(`<<'KIT_EOF'`); never interpolate planner prose straight into "
            "the single-quoted `bash -c` argument, because a single apostrophe "
            "terminates it early and appends a truncated block **under the "
            "lock** without erroring."
        ),
        writer="team-lead",
    ),
    RegistryWrite(
        agent="team-lead",
        label="quality criteria NEVER list (no unlocked write)",
        substring=(
            "- Author `issues.md` content yourself, or write the file with "
            "`Write`/`Edit` — delegate authoring to the planner and commit its "
            "prepared apply script via `registry_edit.sh` so the write always "
            "holds the lock"
        ),
        writer="team-lead",
    ),
)

# Drift guard (see module docstring): the exact set of agent files mentioning
# `issues.md` and the per-file count of lines that do. Audited for ISSUE-074.
ISSUES_MD_MENTION_COUNTS = {
    "developer.md": 2,
    "figma-converter.md": 1,
    "issue-writer.md": 4,
    "planner.md": 8,
    "qa-designer.md": 1,
    "team-lead.md": 9,
}

_DRIFT_FIX = (
    "Re-audit the new or changed `{needle}` mention: read the line, classify "
    "it (read-only input / format reference / MUTATING instruction). If it "
    "mutates the file on disk, add a whitelist entry naming the actor that "
    "performs the write; if it does not, leave it out of the whitelist. Then "
    "update {const} in the SAME commit. This pin is deliberately brittle — it "
    "is what keeps the whitelist a whitelist instead of a sampling."
)


# ── Bash/`tools:` parsing — the capability oracle must not be hollow ─────


class TestToolsParsing:
    """The parser IS the capability oracle, so pin its edge cases."""

    def test_parses_real_agent_tools_lines(self):
        assert _tools("planner") == ["Read", "Glob", "Grep", "Write", "Edit"]
        assert _tools("team-lead") == [
            "Read",
            "Glob",
            "Grep",
            "Write",
            "Edit",
            "Bash",
            "Task",
        ]

    def test_prefix_scoped_bash_keeps_its_commas(self):
        # A prefix-scoped grant is still arbitrary-command capable through the
        # wrappers, so it must not be split into bogus entries.
        assert _split_tools("Read, Bash(git add:*, git commit:*), Edit") == [
            "Read",
            "Bash(git add:*, git commit:*)",
            "Edit",
        ]

    @pytest.mark.parametrize(
        "tool",
        ["Bash", "bash", " Bash ", "Bash(git:*)", "Bash (git add:*, git commit:*)"],
    )
    def test_bash_entry_recognized_in_every_grant_form(self, tool):
        assert _is_bash_entry(tool), f"{tool!r} should count as a Bash grant"

    @pytest.mark.parametrize("tool", ["Read", "Write", "Edit", "WebSearch", "Task"])
    def test_non_bash_entries_rejected(self, tool):
        assert not _is_bash_entry(tool), f"{tool!r} is not a Bash grant"

    def test_every_agent_declares_exactly_one_tools_line(self):
        """A duplicate `tools:` key is an invisible privilege grant.

        Swept across every agent, not just the ones the whitelist happens to
        resolve, because the shape defeats the AC-4 privilege pin outright and
        is the one grant form `test_parses_real_agent_tools_lines` cannot
        catch (that test compares against the FIRST declaration too).
        """
        offenders = {
            stem: _tools_lines(stem)
            for stem in ALL_AGENT_STEMS
            if len(_tools_lines(stem)) != 1
        }
        assert not offenders, (
            "every agent must declare exactly one frontmatter `tools:` line; "
            f"these do not: {offenders}. YAML takes the LAST duplicate key, "
            "this parser takes the FIRST, so the mismatch hides a real grant."
        )

    def test_lock_wrappers_exist(self):
        # AC-1: "can invoke the wrapper" is meaningless if the wrapper is gone.
        for wrapper in LOCK_WRAPPERS:
            assert (SCRIPT_DIR / wrapper).exists(), (
                f"scripts/{wrapper} is missing, but the agent contracts "
                f"designate it as the registry lock path"
            )


# ── the occurrence whitelist + drift guard ───────────────────────────────


def _assert_pin_spans_whole_line(agent: str, label: str, pin: str, const: str) -> None:
    """A pin must BE its line, not a slice of it.

    A *slice* pin only resists rewording of the slice it covers. Text
    APPENDED to the same line leaves the slice intact, and the drift guard
    counts mentioning LINES — so a same-line append changes no count either.
    Both halves of the guard therefore go quiet while the file gains new
    instruction text. Demonstrated during the ISSUE-074 review: appending
    "If no Bash-capable caller is available, append the blocks to
    `issues.md` yourself with `Edit` and carry on." to the end of
    `agents/planner.md`'s Append Mode step 5, and "If no `STATUS.md` exists
    yet, Write one at the repo root first." to the end of
    `agents/issue-writer.md`'s step 5, each left the whole suite green.

    Pinning the whole line closes it without reaching for a phrasing
    blacklist (which AC-1 forbids): the audited occurrence IS the line, so
    any edit to that line — reword, truncate, or append — fails loudly and
    forces re-triage.
    """
    line = _line_with(agent, pin)
    assert line is not None, (
        f"agents/{agent}.md no longer contains the audited {label} text:\n"
        f"  {pin!r}\n"
        f"Re-audit the sentence, then update {const}."
    )
    assert pin == line.strip(), (
        f"agents/{agent}.md {label}: the pin in {const} is a SLICE of its "
        f"line, not the whole line.\n"
        f"  pinned ({len(pin)} chars): {pin!r}\n"
        f"  actual ({len(line.strip())} chars): {line.strip()!r}\n"
        "A slice pin cannot see text appended to the same line, and the "
        "per-file mention-count drift guard counts LINES, so a same-line "
        "append evades both. Widen the pin to the entire line (leading and "
        "trailing whitespace stripped)."
    )


class TestRegistryWriteWhitelist:
    @pytest.mark.parametrize(
        "occ", REGISTRY_WRITES, ids=lambda o: f"{o.agent}:{o.label}"
    )
    def test_pin_spans_its_whole_line(self, occ):
        _assert_pin_spans_whole_line(
            occ.agent, occ.label, occ.substring, "REGISTRY_WRITES"
        )

    def test_whitelist_substrings_are_single_line(self):
        # `_line_with` resolves the responsible actor from the matched LINE, so
        # a multi-line pin would silently never match.
        for occ in REGISTRY_WRITES:
            assert "\n" not in occ.substring, (
                f"agents/{occ.agent}.md {occ.label}: whitelist substrings must "
                f"be single-line so the actor can be resolved from the line"
            )

    @pytest.mark.parametrize(
        "occ", REGISTRY_WRITES, ids=lambda o: f"{o.agent}:{o.label}"
    )
    def test_pinned_occurrence_is_present(self, occ):
        assert occ.substring in _agent_text(occ.agent), (
            f"agents/{occ.agent}.md no longer contains the audited "
            f"{occ.label} instruction:\n  {occ.substring!r}\n"
            "A reword is not a free edit: the registry-lock contract is pinned "
            "by exact text so that rephrasing it forces re-triage. Re-audit "
            "the sentence, confirm the on-disk write still lands on a "
            "Bash-capable actor, then update REGISTRY_WRITES."
        )

    def test_issues_md_mention_files_match_the_audit(self):
        actual = set(_mention_counts("issues.md"))
        expected = set(ISSUES_MD_MENTION_COUNTS)
        assert actual == expected, (
            "the set of agent files mentioning `issues.md` drifted.\n"
            f"  added:   {sorted(actual - expected)}\n"
            f"  removed: {sorted(expected - actual)}\n"
            + _DRIFT_FIX.format(
                needle="issues.md", const="ISSUES_MD_MENTION_COUNTS"
            )
        )

    def test_issues_md_mention_counts_match_the_audit(self):
        actual = _mention_counts("issues.md")
        drifted = {
            name: (ISSUES_MD_MENTION_COUNTS.get(name), count)
            for name, count in actual.items()
            if ISSUES_MD_MENTION_COUNTS.get(name) != count
        }
        assert not drifted, (
            "per-file `issues.md` line counts drifted "
            f"(file: expected -> actual): { {k: f'{v[0]} -> {v[1]}' for k, v in drifted.items()} }\n"
            + _DRIFT_FIX.format(
                needle="issues.md", const="ISSUES_MD_MENTION_COUNTS"
            )
        )


# ── AC-1 / AC-3: the designated lock-taker must be able to take the lock ─


def _resolve_writer(occ: RegistryWrite) -> str:
    """Resolve, from the file text, which agent performs the on-disk write.

    If the audited sentence is gone, nobody is designated any more and the host
    agent is on the hook. If the sentence delegates, the committer's name must
    be parseable out of that sentence — otherwise the delegation does not exist
    in the text and, again, the host agent is on the hook.
    """
    line = _line_with(occ.agent, occ.substring)
    if line is None or not occ.is_delegated:
        return occ.agent
    named = _agents_named_in(line, exclude=occ.agent)
    return occ.writer if occ.writer in named else occ.agent


NON_EXEMPT_WRITES = tuple(o for o in REGISTRY_WRITES if not o.exempt_reason)


class TestDesignatedWriterCanTakeTheLock:
    @pytest.mark.parametrize(
        "occ",
        [o for o in REGISTRY_WRITES if o.is_delegated],
        ids=lambda o: f"{o.agent}:{o.label}",
    )
    def test_delegated_committer_is_named_in_the_occurrence(self, occ):
        line = _line_with(occ.agent, occ.substring)
        assert line is not None, (
            f"agents/{occ.agent}.md lost the audited {occ.label} sentence, so "
            f"it no longer designates {occ.writer} as the committer"
        )
        assert occ.writer in _agents_named_in(line, exclude=occ.agent), (
            f"agents/{occ.agent}.md {occ.label} is audited as handing the "
            f"`issues.md` write to `{occ.writer}`, but that agent is not named "
            f"in the instruction itself. An undesignated hand-off collapses "
            f"back onto agents/{occ.agent}.md, which must never write the "
            f"registry without the lock."
        )

    @pytest.mark.parametrize(
        "occ", NON_EXEMPT_WRITES, ids=lambda o: f"{o.agent}:{o.label}"
    )
    def test_resolved_writer_matches_the_audit(self, occ):
        resolved = _resolve_writer(occ)
        assert resolved == occ.writer, (
            f"agents/{occ.agent}.md {occ.label}: the text now makes "
            f"`{resolved}` responsible for the on-disk `issues.md` write, but "
            f"the audit recorded `{occ.writer}`. Re-triage the sentence and "
            f"update REGISTRY_WRITES — silently re-delegating a registry write "
            f"is how the unlocked-write defect was introduced."
        )

    @pytest.mark.parametrize(
        "occ", NON_EXEMPT_WRITES, ids=lambda o: f"{o.agent}:{o.label}"
    )
    def test_resolved_writer_has_bash(self, occ):
        writer = _resolve_writer(occ)
        assert _can_take_the_lock(writer), (
            f"agents/{occ.agent}.md {occ.label} puts the on-disk `issues.md` "
            f"write on agents/{writer}.md, whose parsed tools: "
            f"({', '.join(_tools(writer))}) contains no `Bash` entry — the "
            f"missing invocation capability means it cannot run "
            f"scripts/registry_edit.sh or scripts/flock_edit.sh, so the write "
            f"degrades to an `Edit` that never takes the lock and still "
            f"SUCCEEDS. Fix the contract text in agents/{occ.agent}.md to hand "
            f"the commit to a Bash-capable caller (team-lead or the invoking "
            f"skill). Do NOT grant `Bash` to a Bash-free agent: both wrappers "
            f"execute \"$@\", so any Bash grant on them is arbitrary command "
            f"execution."
        )


class TestNoBashFreeAgentIsToldToWriteTheRegistry:
    """AC-2, swept from the files rather than from the whitelist's own claims."""

    def test_bash_free_agents_exist_so_the_sweep_is_meaningful(self):
        bash_free = [s for s in ALL_AGENT_STEMS if not _can_take_the_lock(s)]
        assert "planner" in bash_free, (
            "agents/planner.md gained a `Bash` entry — see AC-4; the sweep "
            "below relies on the Bash-free population being real"
        )

    def test_no_bash_free_agent_is_the_resolved_registry_writer(self):
        bash_free = {s for s in ALL_AGENT_STEMS if not _can_take_the_lock(s)}
        violations = [
            f"agents/{occ.agent}.md {occ.label} -> agents/{_resolve_writer(occ)}.md "
            f"(tools: {', '.join(_tools(_resolve_writer(occ)))})"
            for occ in NON_EXEMPT_WRITES
            if _resolve_writer(occ) in bash_free
        ]
        assert not violations, (
            "an agent holding only `Write`/`Edit` is instructed to write "
            "`issues.md`, which is an unlocked write that still succeeds:\n  "
            + "\n  ".join(violations)
        )


# ── the single-writer exemption must be justified in the contract text ───


class TestSingleWriterExemption:
    def test_exactly_one_exemption_exists(self):
        exempt = [o for o in REGISTRY_WRITES if o.exempt_reason]
        assert len(exempt) == 1, (
            "the registry-lock contract allows exactly ONE single-writer path "
            "(greenfield `issues.md` generation at /kickoff). Found "
            f"{len(exempt)}: {[(o.agent, o.label) for o in exempt]}"
        )
        assert exempt[0].agent == "planner", (
            "the only single-writer exemption belongs to agents/planner.md's "
            f"greenfield generation step, not agents/{exempt[0].agent}.md"
        )

    def test_exemption_is_justified_in_the_agents_own_text(self):
        # The exemption may not be a silent test-side carve-out: the agent file
        # must state why it is the only legitimate single-writer path.
        for occ in (o for o in REGISTRY_WRITES if o.exempt_reason):
            assert occ.justification, (
                f"agents/{occ.agent}.md {occ.label} is exempted without a "
                "justification pin"
            )
            assert occ.justification in _agent_text(occ.agent), (
                f"agents/{occ.agent}.md does not state its single-writer "
                f"exemption:\n  {occ.justification!r}\n"
                f"Reason on record: {occ.exempt_reason}. Without that sentence "
                "in the contract, the exemption exists only in this test — and "
                "an unjustified exemption is indistinguishable from the "
                "unlocked write this guard forbids."
            )

    def test_exemption_premise_holds_for_every_caller_of_the_exempt_step(self):
        """The exemption must be gated on the FILE, not on the happy caller.

        Workflow step 10 is also the write mechanism for **evidence mode**:
        the planner's evidence-mode section ends "All other rules (sizing,
        ordering, AC format, quality criteria) from the main Workflow section
        apply unchanged", and `skills/scan/SKILL.md` dispatches "Step 6:
        planner (evidence mode) → `issues.md`" against a repo whose existing
        `issues.md` the scan preamble explicitly expects ("if true, this
        project uses the sprint system"). An exemption justified only as
        "greenfield, nothing to clobber" therefore licenses a Bash-free
        `Write` over a live registry — the exact defect ISSUE-074 closes,
        re-admitted as the one blessed exemption. Gating on the file's
        absence makes the premise true for every caller of the step.
        """
        text = _agent_text("planner")
        assert "gated on the file's **absence**" in text, (
            "agents/planner.md's single-writer exemption must be gated on "
            "`issues.md` being ABSENT, not on the invoking skill — Workflow "
            "step 10 is reached by evidence-mode `/scan` too, where the file "
            "already exists."
        )
        assert "including an evidence-mode `/scan` of a brownfield repo" in text, (
            "agents/planner.md must name the evidence-mode `/scan` path as "
            "excluded from the single-writer exemption. `/scan` reaches "
            "Workflow step 10 on a repo that already carries `issues.md`, so "
            "an unqualified exemption there is an unlocked whole-file "
            "overwrite of a live registry by a Bash-free agent."
        )

    def test_later_modifications_are_routed_through_the_hand_off_shape(self):
        assert (
            "Every later modification goes through Append Mode step 5's "
            "prepare-and-hand-off shape — never a direct `Edit`"
        ) in _agent_text("planner"), (
            "agents/planner.md must scope its single-writer path to the "
            "one-time greenfield run; without that scoping the exemption reads "
            "as a standing licence to `Edit` an existing issues.md"
        )


# ── AC-4: the planner must stay Bash-free ────────────────────────────────


class TestPlannerPrivilegePin:
    def test_planner_tools_has_no_bash_entry_in_any_form(self):
        offenders = [t for t in _tools("planner") if _is_bash_entry(t)]
        assert not offenders, (
            f"agents/planner.md `tools:` now grants {offenders} — the fix for "
            "the registry-lock contract is explicitly NOT to give the planner "
            "Bash. scripts/flock_edit.sh and scripts/registry_edit.sh both "
            'execute "$@", so even a prefix-scoped grant on them is arbitrary '
            "command execution wearing a narrow prefix. The planner prepares "
            "the apply script; a Bash-capable caller commits it."
        )

    def test_planner_still_holds_write_and_edit(self):
        # The hazard this contract closes off is real only while the planner
        # *can* write files — it just must not write the registry.
        tools = _tools("planner")
        assert "Write" in tools and "Edit" in tools, (
            "agents/planner.md lost `Write`/`Edit`; it still authors the "
            f"planning docs. Parsed tools: {tools}"
        )


# ── AC-6: STATUS.md is never created by a kit agent ──────────────────────


@dataclass(frozen=True)
class StatusMention:
    """One audited `STATUS.md` mention, with the form the audit classified."""

    agent: str
    label: str
    substrings: tuple[str, ...]
    form: str


# None of these forms creates the file: "update" mutates an existing file,
# "conditional" is explicitly scoped to projects that already carry one, and
# "output-listing" only names the artifact.
ALLOWED_STATUS_FORMS = {"update", "conditional", "output-listing"}

STATUS_MENTIONS: tuple[StatusMention, ...] = (
    StatusMention(
        agent="issue-writer",
        label="workflow step 5",
        substrings=(
            "5. **Update STATUS.md**: Use `flock_edit.sh` to update the issue "
            "count summary.",
        ),
        form="update",
    ),
    StatusMention(
        agent="planner",
        label="append mode step 6",
        substrings=(
            "6. **`STATUS.md` (only where one already exists)**: this step "
            "applies **only** in projects that already carry a `STATUS.md` — "
            "**never create one**. Where it exists, prepare the updated "
            "issue-count summary the same way as step 5 and hand it to the "
            "Bash-capable caller to commit under the lock.",
        ),
        form="conditional",
    ),
    StatusMention(
        agent="team-lead",
        label="after-any-phase step 2",
        substrings=(
            "2. **Update STATUS.md**: Reflect progress (via flock_edit.sh).",
        ),
        form="update",
    ),
    StatusMention(
        agent="team-lead",
        label="output listing",
        substrings=(
            "- `STATUS.md` — overall project progress (via flock_edit.sh)",
        ),
        form="output-listing",
    ),
)

STATUS_MD_MENTION_COUNTS = {
    "issue-writer.md": 1,
    "planner.md": 1,
    "team-lead.md": 2,
}

_CREATION_VERB = re.compile(
    r"\b(creat\w*|generat\w*|scaffold\w*|initializ\w*|bootstrap\w*)\b", re.IGNORECASE
)
_NEGATOR = re.compile(
    r"\b(never|not|no|don't|cannot|can't|without|avoid)\b", re.IGNORECASE
)


def _unnegated_creation_verbs(line: str) -> list[str]:
    """Creation verbs in `line` that are not negated by nearby wording."""
    found = []
    for m in _CREATION_VERB.finditer(line):
        if not _NEGATOR.search(line[max(0, m.start() - 40) : m.start()]):
            found.append(m.group(0))
    return found


class TestStatusMdIsNeverCreated:
    @pytest.mark.parametrize(
        "mention", STATUS_MENTIONS, ids=lambda m: f"{m.agent}:{m.label}"
    )
    def test_pins_span_their_whole_line(self, mention):
        for pin in mention.substrings:
            _assert_pin_spans_whole_line(
                mention.agent, mention.label, pin, "STATUS_MENTIONS"
            )

    def test_status_md_mention_files_match_the_audit(self):
        actual = set(_mention_counts("STATUS.md"))
        expected = set(STATUS_MD_MENTION_COUNTS)
        assert actual == expected, (
            "the set of agent files mentioning `STATUS.md` drifted.\n"
            f"  added:   {sorted(actual - expected)}\n"
            f"  removed: {sorted(expected - actual)}\n"
            + _DRIFT_FIX.format(
                needle="STATUS.md", const="STATUS_MD_MENTION_COUNTS"
            )
        )

    def test_status_md_mention_counts_match_the_audit(self):
        actual = _mention_counts("STATUS.md")
        drifted = {
            name: (STATUS_MD_MENTION_COUNTS.get(name), count)
            for name, count in actual.items()
            if STATUS_MD_MENTION_COUNTS.get(name) != count
        }
        assert not drifted, (
            "per-file `STATUS.md` line counts drifted "
            f"(file: expected -> actual): { {k: f'{v[0]} -> {v[1]}' for k, v in drifted.items()} }\n"
            + _DRIFT_FIX.format(
                needle="STATUS.md", const="STATUS_MD_MENTION_COUNTS"
            )
        )

    @pytest.mark.parametrize(
        "mention", STATUS_MENTIONS, ids=lambda m: f"{m.agent}:{m.label}"
    )
    def test_audited_status_mention_is_present_and_non_creating(self, mention):
        assert mention.form in ALLOWED_STATUS_FORMS, (
            f"agents/{mention.agent}.md {mention.label}: form "
            f"{mention.form!r} is not an allowed non-creating form "
            f"{sorted(ALLOWED_STATUS_FORMS)}"
        )
        text = _agent_text(mention.agent)
        for substring in mention.substrings:
            assert substring in text, (
                f"agents/{mention.agent}.md {mention.label} no longer contains "
                f"the audited {mention.form} wording:\n  {substring!r}\n"
                "`STATUS.md` does not exist in every project (this repo has "
                "none), so a kit agent may update one where it exists but must "
                "never create one. Re-audit the sentence and update "
                "STATUS_MENTIONS."
            )

    def test_no_agent_instructs_creating_status_md(self):
        offenders = []
        for path in sorted(AGENT_DIR.glob("*.md")):
            for n, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "STATUS.md" not in line:
                    continue
                verbs = _unnegated_creation_verbs(line)
                if verbs:
                    offenders.append(f"agents/{path.name}:{n} -> {verbs}")
        assert not offenders, (
            "a kit agent instructs CREATING `STATUS.md`:\n  "
            + "\n  ".join(offenders)
            + "\nAgents may update a STATUS.md that a project already carries; "
            "they must never bring one into existence (this repo has no "
            "STATUS.md and must not gain one)."
        )

    def test_planner_append_mode_status_step_is_not_unconditional(self):
        assert (
            "**`STATUS.md` (only where one already exists)**"
            in _agent_text("planner")
        ), (
            "agents/planner.md Append Mode must scope its `STATUS.md` step to "
            "projects that already carry the file. The pre-fix step 6 ordered "
            "an unconditional `STATUS.md` update via flock_edit.sh — "
            "unsatisfiable (no Bash) and, in a project without STATUS.md, an "
            "instruction to create one."
        )


# ── the caller layer must not forward the lock to a Bash-free agent ──────

# Both the template and its generated artifact: the runtime loads the
# generated file, so pinning only the source would let `gen_skills.py` drift.
SKILL_ISSUE_FILES = ("skills/issue/SKILL.md.tmpl", "skills/issue/SKILL.md")


class TestCallerLayerDoesNotForwardTheLockToThePlanner:
    """A caller instruction can override an agent's own contract (GAP-074a).

    `skills/issue/SKILL.md` batch mode is the one site that dispatches the
    planner for a registry append, so its prompt is where the unsatisfiable
    "use `flock_edit.sh`" instruction can be re-issued to an agent that holds
    no `Bash` — and everything above this line scans `agents/*.md` only. Until
    this pin existed, the agent-layer fix was reachable but the causal
    caller-side instruction was not guarded at all.

    The sibling dispatch in the same skill (step 7a) targets `issue-writer`,
    which DOES hold `Bash`, so its `flock_edit.sh` instruction is satisfiable
    and is deliberately not pinned here.
    """

    @pytest.mark.parametrize("rel", SKILL_ISSUE_FILES)
    def test_planner_dispatch_states_the_missing_capability(self, rel):
        text = (KIT_ROOT / rel).read_text(encoding="utf-8")
        assert (
            "you hold **no `Bash`**, so do NOT attempt `flock_edit.sh` / "
            "`registry_edit.sh` yourself and never fall back to `Edit` on "
            "`issues.md`"
        ) in text, (
            f"{rel} must tell the planner it cannot take the registry lock. "
            "Re-issuing 'use `flock_edit.sh`' to a Bash-free agent is the "
            "caller-side twin of the ISSUE-074 defect: the agent either fails "
            "the tool call or silently falls back to an unlocked `Edit`."
        )

    @pytest.mark.parametrize("rel", SKILL_ISSUE_FILES)
    def test_skill_commits_the_prepared_edit_itself(self, rel):
        text = (KIT_ROOT / rel).read_text(encoding="utf-8")
        assert "7c) **Commit the planner's prepared registry edit**" in text, (
            f"{rel} lost the step that COMMITS the planner's apply script. "
            "Without a receiver, batch-mode /issue emits an apply script into "
            "the transcript and the registry is never written — while step 10 "
            "still reports the issues as created."
        )
        assert "bash scripts/registry_edit.sh issues.md" in text, (
            f"{rel}'s commit step must take the lock via registry_edit.sh"
        )


# ── template parity: N/A, recorded with its evidence ─────────────────────


class TestAgentTemplateParity:
    def test_agents_have_no_generated_templates(self):
        """Template-parity is N/A for ISSUE-074 — recorded, not dropped.

        `agents/*.md` are hand-written sources: there is no `agents/*.tmpl` and
        `scripts/gen_skills.py` generates only `skills/*/SKILL.md`. So there is
        no generated artifact whose text could drift from a template. If
        `.tmpl` sources are ever introduced for agents, this test fails and
        forces the parity check (tmpl AND generated file must carry every
        pinned contract substring) to be written.
        """
        assert sorted(AGENT_DIR.glob("*.tmpl")) == [], (
            "agents/ now carries .tmpl sources, so the pinned registry-lock "
            "contract text must be asserted in BOTH the template and the "
            "generated agent file — see tests/test_agent_dissolution.py's "
            "_skill_texts() for the two-file pattern."
        )
