"""Lint tests for README consistency (ISSUE-040 staleness sweep).

The README must match shipped reality:
- every stated agent count equals the actual roster (agents/*.md) and the
  roster count asserted by tests/test_agent_effort.py
- the agents table has a row per agents/*.md file (no missing auditors)
- retired-era strings are gone: the "v0.1" version pin (VERSION /
  .claude-plugin/plugin.json are the single source of version truth), the
  pre-ISSUE-030 model-mix line ("opus (21 ..."), and the retired
  `.claude-kit/` submodule install layout — the live `.claude-kit/`
  runtime-state mention (freeze markers, wt_setup.sh) is deliberately exempt
- every skill has a Usage entry, including /spec
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
AGENT_STEMS = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))

# Every phrasing the README uses to state the agent count.
COUNT_PATTERNS = (
    r"(\d+)\s+(?:core\s+)?engineering agents",  # "32 engineering agents", "32 core engineering agents"
    r"[Cc]ore engineering agents \((\d+)\)",    # project-structure comment "agents/  # Core engineering agents (32)"
)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _stated_counts(readme: str) -> list[int]:
    counts = []
    for pattern in COUNT_PATTERNS:
        counts += [int(n) for n in re.findall(pattern, readme)]
    return counts


def test_stated_agent_counts_match_roster():
    counts = _stated_counts(_readme())
    assert counts, "README states no agent count — expected at least one 'N engineering agents' mention"
    for count in counts:
        assert count == len(AGENT_STEMS), (
            f"README states {count} agents but agents/ has {len(AGENT_STEMS)} files"
        )


def test_readme_count_matches_effort_test_roster():
    effort_test = (ROOT / "tests" / "test_agent_effort.py").read_text(encoding="utf-8")
    m = re.search(r"len\(AGENTS\) == (\d+)", effort_test)
    assert m, "tests/test_agent_effort.py no longer asserts len(AGENTS) == N"
    roster = int(m.group(1))
    for count in _stated_counts(_readme()):
        assert count == roster, (
            f"README states {count} agents but test_agent_effort.py pins the roster at {roster}"
        )


def _agent_table_names() -> set[str]:
    lines = _readme().splitlines()
    header = "| Agent | Effort | Role | Tools |"
    assert header in lines, "README agents table header missing or reformatted"
    start = lines.index(header)
    names = set()
    for line in lines[start + 2:]:  # skip header + separator row
        if not line.startswith("|"):
            break
        m = re.match(r"\|\s*`([^`]+)`\s*\|", line)
        assert m, f"unparseable agents-table row: {line!r}"
        names.add(m.group(1))
    return names


def test_agents_table_has_row_per_agent_file():
    table = _agent_table_names()
    missing = set(AGENT_STEMS) - table
    phantom = table - set(AGENT_STEMS)
    assert not missing, f"agents table missing rows for: {sorted(missing)}"
    assert not phantom, f"agents table lists nonexistent agents: {sorted(phantom)}"


def test_stale_version_and_model_mix_strings_absent():
    readme = _readme()
    assert "v0.1" not in readme, "stale v0.1 version pin still in README"
    assert "33 agents" not in readme, "stale 33-agent count still in README"
    assert "opus (21" not in readme, "pre-ISSUE-030 model-mix line still in README"
    title = readme.splitlines()[0]
    assert title == "# claude-kit", (
        f"README title should be the unpinned '# claude-kit', got {title!r} "
        "(VERSION / .claude-plugin/plugin.json are the single source of version truth)"
    )


def test_retired_submodule_install_absent():
    readme = _readme()
    assert "`.claude-kit/` submodule" not in readme, (
        "retired submodule-install layout still described in README prose"
    )
    offenders = [
        line for line in readme.splitlines()
        if ".claude-kit/" in line and "# submodule" in line
    ]
    assert not offenders, (
        "team-layout diagram still shows the retired submodule install:\n"
        + "\n".join(offenders)
    )


def test_spec_skill_has_usage_entry():
    readme = _readme()
    m = re.search(r"^## Usage\n(.*?)(?=^## )", readme, flags=re.M | re.S)
    assert m, "README has no ## Usage section"
    usage = m.group(1)
    assert re.search(r"^### Spec\b", usage, flags=re.M), (
        "/spec has no '### Spec' entry in the Usage section"
    )
    assert re.search(r"^/spec\b", usage, flags=re.M), (
        "/spec Usage entry has no code-block invocation example"
    )


# ── Agents-table Tools/Effort cells vs agent frontmatter (ISSUE-050) ──
#
# The agent frontmatter (agents/*.md) is the oracle; the README table must
# reconcile to it. Tools are compared set-equal (order/whitespace normalized)
# so a future desync fails the build naming the offending row.

AGENTS_DIR = ROOT / "agents"


def _frontmatter_block(path: Path) -> str:
    """Return the YAML frontmatter block (validate_frontmatter.py approach)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


def _fm_field(block: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def _toolset(cell: str) -> frozenset[str]:
    """Normalize a comma-separated tool list to an order-insensitive set."""
    return frozenset(t.strip() for t in cell.split(",") if t.strip())


def _agent_table_rows() -> dict[str, dict[str, str]]:
    """Map each agents-table agent name -> {'effort', 'tools'} raw cell text."""
    lines = _readme().splitlines()
    header = "| Agent | Effort | Role | Tools |"
    assert header in lines, "README agents table header missing or reformatted"
    start = lines.index(header)
    rows: dict[str, dict[str, str]] = {}
    for line in lines[start + 2:]:  # skip header + separator row
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 4, f"agents-table row not 4 cells: {line!r}"
        name = cells[0].strip("`")
        rows[name] = {"effort": cells[1], "tools": cells[3]}
    return rows


def test_agents_table_tools_match_frontmatter():
    mismatches = []
    for name, row in _agent_table_rows().items():
        agent_file = AGENTS_DIR / f"{name}.md"
        assert agent_file.exists(), f"agents table row has no agent file: {name}"
        fm_tools = _toolset(_fm_field(_frontmatter_block(agent_file), "tools"))
        readme_tools = _toolset(row["tools"])
        if fm_tools != readme_tools:
            mismatches.append(
                f"{name}: README {sorted(readme_tools)} != frontmatter {sorted(fm_tools)}"
            )
    assert not mismatches, (
        "agents-table Tools cells drift from agent frontmatter (source wins):\n"
        + "\n".join(mismatches)
    )


def test_agents_table_effort_match_frontmatter():
    mismatches = []
    for name, row in _agent_table_rows().items():
        fm_effort = _fm_field(_frontmatter_block(AGENTS_DIR / f"{name}.md"), "effort")
        if fm_effort and fm_effort != row["effort"]:
            mismatches.append(
                f"{name}: README effort {row['effort']!r} != frontmatter {fm_effort!r}"
            )
    assert not mismatches, (
        "agents-table Effort cells drift from agent frontmatter (source wins):\n"
        + "\n".join(mismatches)
    )
