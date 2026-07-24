import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import has_skill  # noqa: E402


class TestRuntimeBuiltinAllowlist:
    def test_deep_research_returns_unknown(self, monkeypatch, tmp_path):
        # No filesystem trace; allowlist hit -> exit code 2
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        code, evidence = has_skill.find_skill("deep-research")
        assert code == 2
        assert "runtime-built-in" in evidence

    def test_code_review_returns_unknown(self, monkeypatch, tmp_path):
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        code, _ = has_skill.find_skill("code-review")
        assert code == 2

    def test_unknown_skill_returns_miss(self, monkeypatch, tmp_path):
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        code, evidence = has_skill.find_skill("not-a-real-skill")
        assert code == 1
        assert "not found" in evidence


class TestFilesystemDetection:
    def test_user_skill_found(self, monkeypatch, tmp_path):
        user = tmp_path / "user"
        (user / "my-skill").mkdir(parents=True)
        (user / "my-skill" / "SKILL.md").write_text("---\nname: my-skill\n---\n")
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: user)
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        code, evidence = has_skill.find_skill("my-skill")
        assert code == 0
        assert "found at" in evidence

    def test_project_skill_found(self, monkeypatch, tmp_path):
        proj = tmp_path / "proj"
        (proj / "my-skill").mkdir(parents=True)
        (proj / "my-skill" / "SKILL.md").write_text("---\nname: my-skill\n---\n")
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: proj)
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        code, _ = has_skill.find_skill("my-skill")
        assert code == 0

    def test_plugin_skill_found_via_nested_layout(self, monkeypatch, tmp_path):
        plugin_root = tmp_path / "plugin-x"
        (plugin_root / "skills" / "my-skill").mkdir(parents=True)
        (plugin_root / "skills" / "my-skill" / "SKILL.md").write_text("---\n---\n")
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [plugin_root])
        code, _ = has_skill.find_skill("my-skill")
        assert code == 0

    def test_filesystem_visible_overrides_builtin_allowlist(self, monkeypatch, tmp_path):
        # A skill that's BOTH a runtime builtin AND filesystem-visible (e.g. a
        # user-installed override) should report exit 0, not 2.
        user = tmp_path / "user"
        (user / "deep-research").mkdir(parents=True)
        (user / "deep-research" / "SKILL.md").write_text("---\n---\n")
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: user)
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        code, _ = has_skill.find_skill("deep-research")
        assert code == 0


class TestPluginManifestParsing:
    def test_missing_manifest_returns_empty_list(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        # No ~/.claude/plugins/installed_plugins.json
        assert has_skill.plugin_install_paths() == []

    def test_malformed_manifest_returns_empty_list(self, monkeypatch, tmp_path):
        plugins = tmp_path / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text("not json {")
        monkeypatch.setenv("HOME", str(tmp_path))
        assert has_skill.plugin_install_paths() == []

    def test_well_formed_manifest_returns_install_paths(self, monkeypatch, tmp_path):
        plugins = tmp_path / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        manifest = {
            "version": 2,
            "plugins": {
                "alpha@m": [{"installPath": "/opt/alpha"}],
                "beta@m": [{"installPath": "/opt/beta"}, {"installPath": "/opt/beta-2"}],
            },
        }
        (plugins / "installed_plugins.json").write_text(json.dumps(manifest))
        monkeypatch.setenv("HOME", str(tmp_path))
        paths = has_skill.plugin_install_paths()
        assert Path("/opt/alpha") in paths
        assert Path("/opt/beta") in paths
        assert Path("/opt/beta-2") in paths


class TestCliExitCode:
    def test_main_returns_exit_code_for_unknown(self, monkeypatch, tmp_path):
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        monkeypatch.setattr(sys, "argv", ["has_skill.py", "deep-research"])
        code = has_skill.main()
        assert code == 2

    def test_main_handles_leading_slash(self, monkeypatch, tmp_path):
        monkeypatch.setattr(has_skill, "user_skills_dir", lambda: tmp_path / "user")
        monkeypatch.setattr(has_skill, "project_skills_dir", lambda: tmp_path / "proj")
        monkeypatch.setattr(has_skill, "plugin_install_paths", lambda: [])
        monkeypatch.setattr(sys, "argv", ["has_skill.py", "/deep-research"])
        code = has_skill.main()
        assert code == 2
