"""Lint tests for README consistency (ISSUE-040 staleness sweep).

The README must match shipped reality:
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

def _readme() -> str:
    return README.read_text(encoding="utf-8")


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
