"""Unit tests for scripts/validate_pack_manifest.py."""

from pathlib import Path

import pytest

from scripts.validate_pack_manifest import main, validate_packs


def _make_pack(
    tmp_path: Path,
    name: str = "demo",
    depends_on: list[str] | None = None,
    agents: list[str] | None = None,
    skills: list[str] | None = None,
    templates: list[str] | None = None,
    description: str = "A demo pack",
    settings_snippet: str | None = None,
    omit_field: str | None = None,
) -> Path:
    """Build a pack on disk and return its manifest path.

    The directory layout is:
        tmp_path/packs/<name>/manifest.yaml
        tmp_path/packs/<name>/agents/<entry>
        tmp_path/packs/<name>/skills/<entry>/SKILL.md (created as a stub)
        tmp_path/packs/<name>/templates/<entry>
    """
    if depends_on is None:
        depends_on = ["core"]
    if agents is None:
        agents = ["sample-agent.md"]
    if skills is None:
        skills = ["sample-skill"]
    if templates is None:
        templates = ["sample-template.md"]

    pack_root = tmp_path / "packs" / name
    (pack_root / "agents").mkdir(parents=True)
    (pack_root / "skills").mkdir(parents=True)
    (pack_root / "templates").mkdir(parents=True)

    for a in agents:
        (pack_root / "agents" / a).write_text("# agent stub\n", encoding="utf-8")
    for s in skills:
        skill_dir = pack_root / "skills" / s
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# skill stub\n", encoding="utf-8")
    for t in templates:
        (pack_root / "templates" / t).write_text("# template stub\n", encoding="utf-8")

    if settings_snippet:
        (pack_root / settings_snippet).write_text("{}\n", encoding="utf-8")

    # Build manifest content
    manifest_lines = [
        f"name: {name}",
        f"description: {description}",
        "depends_on:",
    ]
    for d in depends_on:
        manifest_lines.append(f"  - {d}")
    if agents:
        manifest_lines.append("agents:")
        for a in agents:
            manifest_lines.append(f"  - {a}")
    if skills:
        manifest_lines.append("skills:")
        for s in skills:
            manifest_lines.append(f"  - {s}")
    if templates:
        manifest_lines.append("templates:")
        for t in templates:
            manifest_lines.append(f"  - {t}")
    if settings_snippet:
        manifest_lines.append(f"settings_snippet: {settings_snippet}")

    # Optionally drop a field for negative tests.
    if omit_field:
        manifest_lines = [
            ln
            for ln in manifest_lines
            if not (
                ln.startswith(f"{omit_field}:")
                or (omit_field == "depends_on" and ln.strip().startswith("- "))
            )
        ]

    manifest_path = pack_root / "manifest.yaml"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return manifest_path


class TestValidPack:
    def test_valid_manifest_passes(self, tmp_path: Path):
        manifest = _make_pack(tmp_path)
        count, errors = validate_packs(manifest)
        assert count == 1
        assert errors == []

    def test_directory_target_walks_all_packs(self, tmp_path: Path):
        _make_pack(tmp_path, name="alpha")
        _make_pack(
            tmp_path,
            name="beta",
            agents=["beta-agent.md"],
            skills=["beta-skill"],
            templates=["beta-tmpl.md"],
        )
        packs_dir = tmp_path / "packs"
        count, errors = validate_packs(packs_dir)
        assert count == 2
        assert errors == []


class TestMissingFile:
    def test_agent_path_must_exist(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, agents=["missing.md"])
        # Remove the file the helper created so the listed path doesn't exist.
        (manifest.parent / "agents" / "missing.md").unlink()
        _, errors = validate_packs(manifest)
        assert any("missing.md" in e and "does not exist" in e for e in errors)

    def test_skill_dir_must_exist(self, tmp_path: Path):
        manifest = _make_pack(tmp_path)
        # Remove the skill dir
        skill = manifest.parent / "skills" / "sample-skill"
        for child in skill.iterdir():
            child.unlink()
        skill.rmdir()
        _, errors = validate_packs(manifest)
        assert any("sample-skill" in e and "does not exist" in e for e in errors)

    def test_template_path_must_exist(self, tmp_path: Path):
        manifest = _make_pack(tmp_path)
        (manifest.parent / "templates" / "sample-template.md").unlink()
        _, errors = validate_packs(manifest)
        assert any(
            "sample-template.md" in e and "does not exist" in e for e in errors
        )


class TestDependsOn:
    def test_must_include_core(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, depends_on=["something"])
        _, errors = validate_packs(manifest)
        assert any("must include 'core'" in e for e in errors)

    def test_unknown_pack_dep_flagged(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, depends_on=["core", "nonexistent"])
        _, errors = validate_packs(manifest)
        assert any("nonexistent" in e and "unknown pack" in e for e in errors)

    def test_known_pack_dep_accepted(self, tmp_path: Path):
        _make_pack(tmp_path, name="alpha")
        beta_manifest = _make_pack(
            tmp_path,
            name="beta",
            depends_on=["core", "alpha"],
            agents=["beta-a.md"],
            skills=["beta-s"],
            templates=["beta-t.md"],
        )
        packs_dir = tmp_path / "packs"
        _, errors = validate_packs(packs_dir)
        assert errors == [], f"unexpected: {errors}"


class TestDuplicates:
    def test_duplicate_entry_across_packs_flagged(self, tmp_path: Path):
        _make_pack(
            tmp_path,
            name="alpha",
            agents=["shared.md"],
            skills=["alpha-only"],
            templates=["alpha-tmpl.md"],
        )
        # beta declares the same agent filename
        _make_pack(
            tmp_path,
            name="beta",
            agents=["shared.md"],  # collision with alpha
            skills=["beta-only"],
            templates=["beta-tmpl.md"],
        )
        # File exists at both locations (the helper writes both stubs).
        packs_dir = tmp_path / "packs"
        _, errors = validate_packs(packs_dir)
        assert any(
            "shared.md" in e and "duplicates" in e for e in errors
        ), f"expected duplicate error; got: {errors}"


class TestNameMustMatchDir:
    def test_name_mismatch_flagged(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, name="demo")
        # Edit manifest to rename to something else
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace("name: demo", "name: notdemo"), encoding="utf-8")
        _, errors = validate_packs(manifest)
        assert any("does not match directory name" in e for e in errors)


class TestRequiredFields:
    def test_missing_description_flagged(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, omit_field="description")
        _, errors = validate_packs(manifest)
        assert any("missing required field" in e and "description" in e for e in errors)

    def test_missing_depends_on_flagged(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, omit_field="depends_on")
        _, errors = validate_packs(manifest)
        assert any("missing required field" in e and "depends_on" in e for e in errors)


class TestSettingsSnippet:
    def test_valid_snippet_passes(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, settings_snippet="settings.snippet.json")
        _, errors = validate_packs(manifest)
        assert errors == []

    def test_missing_snippet_flagged(self, tmp_path: Path):
        manifest = _make_pack(tmp_path)
        # Manually inject a settings_snippet line pointing at a non-existent file.
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text + "settings_snippet: nope.json\n", encoding="utf-8")
        _, errors = validate_packs(manifest)
        assert any("nope.json" in e and "does not exist" in e for e in errors)


class TestCli:
    def test_cli_passes_on_valid_manifest(self, tmp_path: Path):
        manifest = _make_pack(tmp_path)
        rc = main([str(manifest)])
        assert rc == 0

    def test_cli_fails_on_invalid_manifest(self, tmp_path: Path):
        manifest = _make_pack(tmp_path, depends_on=["something-else"])
        rc = main([str(manifest)])
        assert rc == 1

    def test_cli_exits_2_on_missing_target(self, tmp_path: Path):
        rc = main([str(tmp_path / "nonexistent")])
        assert rc == 2


class TestRealSalesManifest:
    """The actual packs/sales/manifest.yaml in the repo must pass."""

    def test_repo_sales_manifest_valid(self):
        manifest = Path("packs/sales/manifest.yaml")
        if not manifest.exists():
            pytest.skip("packs/sales/manifest.yaml not present in this checkout")
        rc = main([str(manifest)])
        assert rc == 0
