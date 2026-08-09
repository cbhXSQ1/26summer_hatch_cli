"""T1.4: 配置加载器 测试"""

import pytest
from hatch.config.loader import ConfigLoader, Config


class TestConfigLoader:
    """ConfigLoader"""

    def test_loads_valid_config(self, tmp_path) -> None:
        config_file = tmp_path / "hatch.yaml"
        config_file.write_text("""
llm:
  provider: deepseek
  model: deepseek-v4-pro
  api_base: https://api.deepseek.com
  max_tokens: 4096
  temperature: 0.1
loop:
  max_rounds: 3
  max_total_tokens: 100000
tools:
  enabled:
    - file_reader
    - file_writer
  shell_timeout: 30
  test_timeout: 120
guardrails:
  require_approval_for:
    - git_push_force
  blocked_commands:
    - "rm -rf /"
feedback:
  max_rounds: 3
  loop_detection: true
  auto_apply_style: false
memory:
  max_entries: 100
  persist_path: ~/.hatch/memory.json
""")
        config = ConfigLoader.load(str(config_file))
        assert config.llm.provider == "deepseek"
        assert config.llm.model == "deepseek-v4-pro"
        assert "deepseek-v4-flash" in config.llm.providers["deepseek"]["models"]
        assert config.loop.max_rounds == 3
        assert config.tools.shell_timeout == 30
        assert config.feedback.loop_detection is True
        assert config.memory.max_entries == 100

    def test_missing_file_uses_defaults(self, tmp_path) -> None:
        config = ConfigLoader.load(str(tmp_path / "nonexistent.yaml"))
        assert config.llm.provider == "deepseek"
        assert config.loop.max_rounds == 12
        assert config.tools.shell_timeout == 30
        assert config.feedback.max_rounds == 3
        assert config.memory.max_entries == 100

    def test_invalid_yaml_raises_error(self, tmp_path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("llm: {invalid: [yaml: indeed")
        with pytest.raises(ValueError, match="YAML"):
            ConfigLoader.load(str(config_file))

    def test_partial_config_merges_defaults(self, tmp_path) -> None:
        config_file = tmp_path / "partial.yaml"
        config_file.write_text("""
llm:
  provider: glm
  model: glm-5.2
""")
        config = ConfigLoader.load(str(config_file))
        assert config.llm.provider == "glm"
        assert config.llm.model == "glm-5.2"
        assert config.loop.max_rounds == 12        # default
        assert config.tools.shell_timeout == 30    # default

    def test_all_defaults_are_valid(self) -> None:
        config = ConfigLoader.load(None)
        assert config.llm.provider in ("deepseek", "glm", "claude")
        assert config.loop.max_rounds > 0
        assert config.tools.shell_timeout > 0
        assert config.tools.test_timeout > 0
        assert config.feedback.max_rounds > 0
        assert config.memory.max_entries > 0

    def test_returns_config_instance(self, tmp_path) -> None:
        config = ConfigLoader.load(None)
        assert isinstance(config, Config)

    def test_guardrails_config(self, tmp_path) -> None:
        config_file = tmp_path / "hatch.yaml"
        config_file.write_text("""
guardrails:
  require_approval_for:
    - git_push_force
    - pip_uninstall
  blocked_commands:
    - "rm -rf /"
    - "dd if="
""")
        config = ConfigLoader.load(str(config_file))
        assert "git_push_force" in config.guardrails.require_approval_for
        assert "rm -rf /" in config.guardrails.blocked_commands

    def test_feedback_config(self, tmp_path) -> None:
        config_file = tmp_path / "hatch.yaml"
        config_file.write_text("""
feedback:
  max_rounds: 5
  loop_detection: false
  auto_apply_style: true
""")
        config = ConfigLoader.load(str(config_file))
        assert config.feedback.max_rounds == 5
        assert config.feedback.loop_detection is False
        assert config.feedback.auto_apply_style is True
