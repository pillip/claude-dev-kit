"""Guard: every repo-mutating orchestrator skill sets disable-model-invocation: true.

The implement/review/ship/kickoff/scan/sprint orchestrators mutate the repo
(branches, commits, PRs) and must only run on explicit user invocation — never
via autonomous model invocation. ISSUE-042 surfaced that sprint, the heaviest
orchestrator, shipped without the flag. PyYAML isn't a kit dependency
(ISSUE-021), so this guard uses plain string parsing that always runs,
mirroring scripts/validate_frontmatter.py.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Frozen literal set of repo-mutating orchestrator skills. Adding a future
# orchestrator to the kit? Add it here as a conscious decision — every skill
# in this tuple must keep `disable-model-invocation: true` in its generated
# SKILL.md frontmatter.
ORCHESTRATOR_SKILLS = ("implement", "review", "ship", "kickoff", "scan", "sprint")


def _frontmatter_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: frontmatter must start at byte 0"
    return text.split("---", 2)[1].splitlines()


@pytest.mark.parametrize("skill", ORCHESTRATOR_SKILLS)
def test_orchestrator_sets_disable_model_invocation_true(skill):
    path = ROOT / "skills" / skill / "SKILL.md"
    assert path.exists(), f"{skill}: generated skills/{skill}/SKILL.md not found"
    for line in _frontmatter_lines(path):
        key, sep, value = line.partition(":")
        if not sep or key != "disable-model-invocation":
            continue
        assert value.strip() == "true", (
            f"{skill}: disable-model-invocation is set to {value.strip()!r} — "
            f"repo-mutating orchestrators must set it to exactly 'true'"
        )
        return
    pytest.fail(
        f"{skill}: frontmatter lacks disable-model-invocation — repo-mutating "
        f"orchestrators must set 'disable-model-invocation: true' in "
        f"skills/{skill}/SKILL.md"
    )
