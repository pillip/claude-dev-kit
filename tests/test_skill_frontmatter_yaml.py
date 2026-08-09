"""Guard: every generated SKILL.md frontmatter is valid YAML.

`claude plugin tag` surfaced that unquoted `argument-hint` values (`[a] [b]`)
and descriptions containing ": " (colon-space) silently dropped ALL frontmatter
at runtime — name/description/allowed-tools lost. PyYAML isn't a kit dependency
(ISSUE-021), so this guard detects the two concrete break patterns with plain
string checks that always run, and additionally does a strict YAML parse when
PyYAML happens to be present.
"""

import glob
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(glob.glob(str(ROOT / "skills/*/SKILL.md")))
AGENTS = sorted(glob.glob(str(ROOT / "agents/*.md")))


def _frontmatter_lines(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: frontmatter must start at byte 0"
    return text.split("---", 2)[1].splitlines()


def _value_is_quoted(v: str) -> bool:
    v = v.strip()
    return (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"'))


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: Path(p).parent.name)
def test_frontmatter_scalars_are_yaml_safe(path):
    for line in _frontmatter_lines(path):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key not in {"name", "description", "argument-hint"}:
            continue
        if _value_is_quoted(value):
            continue
        # Unquoted scalar: a flow-sequence must be a *single* clean [...] with no
        # trailing tokens, and must not contain a ": " that YAML reads as a map.
        if value.startswith("["):
            assert value.endswith("]") and value.count("[") == 1, (
                f"{path}: unquoted argument-hint {value!r} breaks YAML — quote it"
            )
        assert ": " not in value, (
            f"{path}: unquoted {key} contains ': ' which YAML reads as a mapping — quote it"
        )


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: Path(p).stem)
def test_agent_frontmatter_scalars_are_yaml_safe(path):
    for line in _frontmatter_lines(path):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key not in {"name", "description"} or _value_is_quoted(value):
            continue
        assert ": " not in value, (
            f"{path}: unquoted {key} contains ': ' which YAML reads as a mapping — quote it"
        )


def test_strict_yaml_parse_when_pyyaml_present():
    yaml = pytest.importorskip("yaml")
    for path in SKILLS + AGENTS:
        block = "\n".join(_frontmatter_lines(path))
        data = yaml.safe_load(block)
        assert isinstance(data, dict), f"{path}: frontmatter did not parse to a mapping"
        for key in ("name", "description"):
            assert key in data, f"{path}: frontmatter dropped key {key!r}"
