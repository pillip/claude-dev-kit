"""Integration tests for scripts/install_packs.py.

Builds a synthetic kit (tmpdir with agents/, skills/, packs/<name>/ structure)
and runs the install logic against another tmpdir project. Verifies the
selection model, depends_on enforcement, collision detection, snippet
forwarding, and the migration note for legacy directory symlinks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.install_packs import (
    discover_packs,
    resolve_pack_selection,
    run_install,
)


def _write(path: Path, text: str = "stub\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _build_synthetic_kit(
    root: Path,
    core_agents: list[str] | None = None,
    core_skills: list[str] | None = None,
    packs: dict[str, dict] | None = None,
) -> Path:
    """Build a synthetic kit with the layout install_packs.py expects.

    packs: {pack_name: {agents: [...], skills: [...], depends_on: [...],
                        settings_snippet: <name> or None}}
    """
    if core_agents is None:
        core_agents = ["core-a.md", "core-b.md"]
    if core_skills is None:
        core_skills = ["core-s1", "core-s2"]

    for a in core_agents:
        _write(root / "agents" / a)
    for s in core_skills:
        _write(root / "skills" / s / "SKILL.md")

    if packs:
        for name, spec in packs.items():
            agents = spec.get("agents", [])
            skills = spec.get("skills", [])
            templates = spec.get("templates", [])
            depends_on = spec.get("depends_on", ["core"])
            snippet = spec.get("settings_snippet")
            pack_root = root / "packs" / name
            for a in agents:
                _write(pack_root / "agents" / a)
            for s in skills:
                _write(pack_root / "skills" / s / "SKILL.md")
            for t in templates:
                _write(pack_root / "templates" / t)
            if snippet:
                _write(pack_root / snippet, "{}\n")

            lines = [
                f"name: {name}",
                f"description: pack {name}",
                "depends_on:",
            ]
            for d in depends_on:
                lines.append(f"  - {d}")
            if agents:
                lines.append("agents:")
                for a in agents:
                    lines.append(f"  - {a}")
            if skills:
                lines.append("skills:")
                for s in skills:
                    lines.append(f"  - {s}")
            if templates:
                lines.append("templates:")
                for t in templates:
                    lines.append(f"  - {t}")
            if snippet:
                lines.append(f"settings_snippet: {snippet}")
            (pack_root / "manifest.yaml").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
    return root


class TestResolveSelection:
    def test_default_is_core_only(self, tmp_path: Path):
        kit = _build_synthetic_kit(tmp_path / "kit")
        packs = discover_packs(kit)
        assert resolve_pack_selection([], packs) == ["core"]

    def test_explicit_core_normalizes(self, tmp_path: Path):
        kit = _build_synthetic_kit(tmp_path / "kit")
        packs = discover_packs(kit)
        assert resolve_pack_selection(["core"], packs) == ["core"]

    def test_named_pack_implies_core(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={"sales": {"agents": ["s-a.md"], "skills": ["s-s"]}},
        )
        packs = discover_packs(kit)
        assert resolve_pack_selection(["sales"], packs) == ["core", "sales"]

    def test_all_expands_to_every_pack(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "alpha": {"agents": ["a.md"], "skills": ["a-s"]},
                "beta": {"agents": ["b.md"], "skills": ["b-s"]},
            },
        )
        packs = discover_packs(kit)
        assert resolve_pack_selection(["all"], packs) == ["core", "alpha", "beta"]

    def test_multiple_pack_flags_dedup(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "alpha": {"agents": ["a.md"], "skills": ["a-s"]},
                "beta": {"agents": ["b.md"], "skills": ["b-s"]},
            },
        )
        packs = discover_packs(kit)
        result = resolve_pack_selection(["alpha", "beta", "alpha"], packs)
        assert result == ["core", "alpha", "beta"]

    def test_unknown_pack_raises(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={"sales": {"agents": ["s-a.md"], "skills": ["s-s"]}},
        )
        packs = discover_packs(kit)
        with pytest.raises(ValueError, match="unknown pack"):
            resolve_pack_selection(["nope"], packs)


class TestInstallCore:
    def test_default_install_yields_core_entries(self, tmp_path: Path):
        kit = _build_synthetic_kit(tmp_path / "kit")
        proj = tmp_path / "proj"
        proj.mkdir()
        run_install(kit, proj, ["core"])
        agents = sorted(p.name for p in (proj / ".claude" / "agents").iterdir())
        skills = sorted(p.name for p in (proj / ".claude" / "skills").iterdir())
        assert agents == ["core-a.md", "core-b.md"]
        assert skills == ["core-s1", "core-s2"]
        # Entries must be symlinks pointing at the kit source.
        for entry in (proj / ".claude" / "agents").iterdir():
            assert entry.is_symlink()
            assert entry.resolve().is_relative_to(kit)


class TestInstallPack:
    def test_sales_adds_pack_entries(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "sales": {
                    "agents": ["sales-a.md", "sales-b.md"],
                    "skills": ["sales-s1"],
                }
            },
        )
        proj = tmp_path / "proj"
        proj.mkdir()
        run_install(kit, proj, ["core", "sales"])
        agents = sorted(p.name for p in (proj / ".claude" / "agents").iterdir())
        skills = sorted(p.name for p in (proj / ".claude" / "skills").iterdir())
        assert "core-a.md" in agents and "sales-a.md" in agents
        assert "core-s1" in skills and "sales-s1" in skills
        assert len(agents) == 4  # 2 core + 2 sales
        assert len(skills) == 3  # 2 core + 1 sales

    def test_collision_between_packs_raises(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "alpha": {"agents": ["shared.md"], "skills": ["alpha-s"]},
                "beta": {"agents": ["shared.md"], "skills": ["beta-s"]},
            },
        )
        proj = tmp_path / "proj"
        proj.mkdir()
        with pytest.raises(ValueError, match="entry collision"):
            run_install(kit, proj, ["core", "alpha", "beta"])

    def test_depends_on_unsatisfied_raises(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "alpha": {"agents": ["a.md"], "skills": ["a-s"]},
                "beta": {
                    "agents": ["b.md"],
                    "skills": ["b-s"],
                    "depends_on": ["core", "alpha"],
                },
            },
        )
        proj = tmp_path / "proj"
        proj.mkdir()
        # Install beta without alpha → must raise
        with pytest.raises(ValueError, match="depends_on"):
            run_install(kit, proj, ["core", "beta"])

    def test_settings_snippet_returned_for_merge(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "sales": {
                    "agents": ["s-a.md"],
                    "skills": ["s-s"],
                    "settings_snippet": "settings.snippet.json",
                }
            },
        )
        proj = tmp_path / "proj"
        proj.mkdir()
        snippets = run_install(kit, proj, ["core", "sales"])
        assert len(snippets) == 1
        assert snippets[0].name == "settings.snippet.json"
        assert snippets[0].is_file()

    def test_reinstall_is_idempotent(self, tmp_path: Path):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "sales": {"agents": ["sales-a.md"], "skills": ["sales-s1"]}
            },
        )
        proj = tmp_path / "proj"
        proj.mkdir()
        run_install(kit, proj, ["core", "sales"])
        # Reinstall — must not raise (clean+rebuild).
        run_install(kit, proj, ["core", "sales"])
        agents = sorted(p.name for p in (proj / ".claude" / "agents").iterdir())
        # Same set, no doubling.
        assert agents.count("sales-a.md") == 1

    def test_switching_from_with_pack_to_without_removes_pack_entries(
        self, tmp_path: Path
    ):
        kit = _build_synthetic_kit(
            tmp_path / "kit",
            packs={
                "sales": {"agents": ["sales-a.md"], "skills": ["sales-s"]}
            },
        )
        proj = tmp_path / "proj"
        proj.mkdir()
        # First install with sales
        run_install(kit, proj, ["core", "sales"])
        assert (proj / ".claude" / "agents" / "sales-a.md").exists()
        # Reinstall without sales → sales-a.md must be gone
        run_install(kit, proj, ["core"])
        assert not (proj / ".claude" / "agents" / "sales-a.md").exists()


class TestRealKit:
    """Smoke test against the actual kit checkout."""

    def test_core_only_install_against_real_kit(self, tmp_path: Path):
        repo = Path.cwd()
        if not (repo / "packs" / "sales" / "manifest.yaml").exists():
            pytest.skip("not in claude-dev-kit checkout")
        proj = tmp_path / "proj"
        proj.mkdir()
        snippets = run_install(repo, proj, ["core"])
        # No pack snippets when only core installed.
        assert snippets == []
        # Core agents must include /spec /implement etc. by name presence.
        agents = sorted(p.name for p in (proj / ".claude" / "agents").iterdir())
        # No sales agents in core-only install
        assert "account-researcher.md" not in agents
        assert "proposal-writer.md" not in agents
        # Some core agents that we expect to remain
        assert any("reviewer" in a or "auditor" in a for a in agents)

    def test_pack_sales_install_against_real_kit(self, tmp_path: Path):
        repo = Path.cwd()
        if not (repo / "packs" / "sales" / "manifest.yaml").exists():
            pytest.skip("not in claude-dev-kit checkout")
        proj = tmp_path / "proj"
        proj.mkdir()
        run_install(repo, proj, ["core", "sales"])
        agents = sorted(p.name for p in (proj / ".claude" / "agents").iterdir())
        skills = sorted(p.name for p in (proj / ".claude" / "skills").iterdir())
        # Sales entries must be present
        assert "account-researcher.md" in agents
        assert "proposal-writer.md" in agents
        assert "proposal" in skills
        assert "account-brief" in skills
