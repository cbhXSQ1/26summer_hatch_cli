"""CLI 入口 测试"""

from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import pytest
from hatch.cli import main
from hatch.config.loader import Config, LLMConfig, LoopConfig, ToolsConfig
from hatch.core.models import LoopState


class TestBuildLLM:
    """_build_llm 自定义 provider 支持"""

    def test_builds_custom_provider_openai_compat(self) -> None:
        from hatch.cli import _build_llm
        from hatch.core.llm import OpenAICompatLLM

        config = Config()
        config.llm.provider = "myllm"
        config.llm.model = "my-model-1"
        config.llm.providers["myllm"] = {
            "api_base": "https://api.myllm.example/v1",
            "models": ["my-model-1"],
        }
        llm = _build_llm(config, "sk-key")
        assert isinstance(llm, OpenAICompatLLM)
        assert llm.base_url == "https://api.myllm.example/v1"
        assert llm.model == "my-model-1"

    def test_custom_provider_without_base_returns_none(self) -> None:
        from hatch.cli import _build_llm

        config = Config()
        config.llm.provider = "ghost"
        config.llm.providers["ghost"] = {"models": ["m"]}  # 无 api_base
        assert _build_llm(config, "sk-key") is None

    def test_known_providers_unchanged(self) -> None:
        from hatch.cli import _build_llm
        from hatch.core.llm import DeepSeekLLM, GLMLLM, ClaudeLLM

        cfg = Config()
        cfg.llm.provider = "deepseek"
        assert isinstance(_build_llm(cfg, "k"), DeepSeekLLM)
        cfg.llm.provider = "glm"
        assert isinstance(_build_llm(cfg, "k"), GLMLLM)
        cfg.llm.provider = "claude"
        assert isinstance(_build_llm(cfg, "k"), ClaudeLLM)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_sm():
    """返回 mock SessionManager"""
    with patch("hatch.cli.SessionManager") as mock_class:
        mock = mock_class.return_value
        mock.get_latest_or_create.return_value = ("abc123", True)
        mock.get_latest.return_value = "abc123"
        mock.get_conversation_turns.return_value = []
        yield mock


class TestMainVersion:
    """main --version"""

    def test_main_version_outputs_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestRunCommand:
    """run TASK"""

    def test_run_no_api_key(self, runner, mock_sm):
        mock_config = Config()
        mock_config.llm.provider = "deepseek"

        with patch("hatch.cli.ConfigLoader.load", return_value=mock_config), \
             patch("hatch.cli.KeyManager") as mock_km_class:
            mock_km = mock_km_class.return_value
            mock_km.get_key.return_value = None

            result = runner.invoke(main, ["run", "fix the bug"])
            assert result.exit_code == 0
            assert "未找到" in result.output

    def test_run_unsupported_provider(self, runner, mock_sm):
        mock_config = Config()
        mock_config.llm.provider = "unknown"

        with patch("hatch.cli.ConfigLoader.load", return_value=mock_config), \
             patch("hatch.cli.KeyManager") as mock_km_class:
            mock_km = mock_km_class.return_value
            mock_km.get_key.return_value = "sk-fake-key"

            result = runner.invoke(main, ["run", "fix the bug"])
            assert result.exit_code == 0
            assert "不支持的 provider" in result.output

    def test_run_with_valid_deepseek(self, runner, mock_sm):
        mock_config = Config()
        mock_config.llm.provider = "deepseek"
        mock_config.llm.model = "deepseek-v4-pro"

        mock_state = LoopState()
        mock_state.status = "success"
        mock_state.round = 3
        mock_state.max_rounds = 3

        with patch("hatch.cli.ConfigLoader.load", return_value=mock_config), \
             patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("hatch.cli.DeepSeekLLM"), \
             patch("hatch.cli.AgentLoop") as mock_loop_class:
            mock_km = mock_km_class.return_value
            mock_km.get_key.return_value = "sk-test-key"

            mock_loop = mock_loop_class.return_value
            mock_loop.run.return_value = mock_state

            result = runner.invoke(main, ["run", "--quiet", "fix the bug"])
            assert result.exit_code == 0
            assert "任务完成" in result.output
            mock_sm.update_status.assert_called_with("abc123", 3, "success")
            assert mock_sm.save_history.called

    def test_run_with_cwd_option(self, runner, tmp_path, mock_sm):
        workdir = tmp_path / "my_project"
        workdir.mkdir()

        mock_config = Config()
        mock_config.llm.provider = "deepseek"
        mock_config.llm.model = "deepseek-v4-pro"

        mock_state = LoopState()
        mock_state.status = "success"
        mock_state.round = 1
        mock_state.max_rounds = 3

        with patch("hatch.cli.ConfigLoader.load", return_value=mock_config), \
             patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("hatch.cli.DeepSeekLLM"), \
             patch("hatch.cli.AgentLoop") as mock_loop_class:
            mock_km = mock_km_class.return_value
            mock_km.get_key.return_value = "sk-test-key"

            mock_loop = mock_loop_class.return_value
            mock_loop.run.return_value = mock_state

            result = runner.invoke(main, ["run", "--quiet", "--cwd", str(workdir), "write code"])
            assert result.exit_code == 0
            assert "任务完成" in result.output

    def test_run_with_valid_glm(self, runner, mock_sm):
        mock_config = Config()
        mock_config.llm.provider = "glm"
        mock_config.llm.model = "glm-5.2"

        mock_state = LoopState()
        mock_state.status = "success"
        mock_state.round = 1
        mock_state.max_rounds = 3

        with patch("hatch.cli.ConfigLoader.load", return_value=mock_config), \
             patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("hatch.cli.GLMLLM"), \
             patch("hatch.cli.AgentLoop") as mock_loop_class:
            mock_km = mock_km_class.return_value
            mock_km.get_key.return_value = "sk-glm-key"

            mock_loop = mock_loop_class.return_value
            mock_loop.run.return_value = mock_state

            result = runner.invoke(main, ["run", "--quiet", "fix the bug"])
            assert result.exit_code == 0
            assert "任务完成" in result.output


class TestSessionCommands:
    """session 命令"""

    def test_session_new(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.create.return_value = "abc123"

            result = runner.invoke(main, ["session", "new", "--cwd", str(workdir)])
            assert result.exit_code == 0
            assert "abc123" in result.output

    def test_session_use(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.get_info.return_value = {"id": "abc123", "rounds": 3, "status": "success"}

            result = runner.invoke(main, ["session", "use", "--cwd", str(workdir), "abc123"])
            assert result.exit_code == 0
            mock.update_status.assert_called_once_with("abc123", 3, "success")
            assert "已切换" in result.output

    def test_session_use_not_found(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.get_info.return_value = None

            result = runner.invoke(main, ["session", "use", "--cwd", str(workdir), "abc123"])
            assert "不存在" in result.output

    def test_session_list_empty(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.list_sessions.return_value = []
            mock.get_latest.return_value = None

            result = runner.invoke(main, ["session", "list", "--cwd", str(workdir)])
            assert result.exit_code == 0
            assert "暂无" in result.output

    def test_session_list_with_items(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.list_sessions.return_value = [
                {"id": "abc123", "task": "fix bug", "created": "2026-01-01",
                 "updated": "2026-01-02", "rounds": 3, "status": "success"},
                {"id": "def456", "task": "add feature", "created": "2026-01-02",
                 "updated": "2026-01-01", "rounds": 1, "status": "active"},
            ]
            mock.get_latest.return_value = "abc123"

            result = runner.invoke(main, ["session", "list", "--cwd", str(workdir)])
            assert result.exit_code == 0
            assert "abc123" in result.output
            assert "def456" in result.output
            assert "*" in result.output

    def test_session_info(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.get_latest.return_value = "abc123"
            mock.get_info.return_value = {
                "id": "abc123", "task": "fix bug", "created": "2026-01-01",
                "rounds": 3, "status": "success",
            }

            result = runner.invoke(main, ["session", "info", "--cwd", str(workdir)])
            assert result.exit_code == 0
            assert "abc123" in result.output
            assert "fix bug" in result.output

    def test_session_info_no_active(self, runner, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch("hatch.cli.SessionManager") as mock_class:
            mock = mock_class.return_value
            mock.get_latest.return_value = None

            result = runner.invoke(main, ["session", "info", "--cwd", str(workdir)])
            assert "无对话" in result.output


class TestKeySet:
    """key set --provider"""

    def test_key_set_prompts_and_saves(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("builtins.input") as mock_input:
            mock_input.return_value = "sk-my-secret-key"
            mock_km = mock_km_class.return_value

            result = runner.invoke(main, ["key", "set", "--provider", "deepseek"])
            assert result.exit_code == 0
            assert "已保存" in result.output
            mock_km.set_key.assert_called_once_with("deepseek", "sk-my-secret-key")

    def test_key_set_default_provider(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("builtins.input") as mock_input:
            mock_input.return_value = "sk-another-key"
            mock_km = mock_km_class.return_value

            result = runner.invoke(main, ["key", "set"])
            assert result.exit_code == 0
            mock_km.set_key.assert_called_once_with("deepseek", "sk-another-key")


class TestKeyStatus:
    """key status"""

    def test_key_status_no_keys(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class:
            mock_km = mock_km_class.return_value
            mock_km.list_providers.return_value = []

            result = runner.invoke(main, ["key", "status"])
            assert result.exit_code == 0
            assert "未存储" in result.output

    def test_key_status_with_keys(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class:
            mock_km = mock_km_class.return_value
            mock_km.list_providers.return_value = ["deepseek", "glm"]
            mock_km.get_key.side_effect = lambda p: {
                "deepseek": "sk-1234567890abcdef",
                "glm": "sk-fedcba0987654321",
            }.get(p)
            mock_km.mask_key.side_effect = lambda k: "****" + k[-4:]

            result = runner.invoke(main, ["key", "status"])
            assert result.exit_code == 0
            assert "deepseek" in result.output
            assert "glm" in result.output
            assert "****cdef" in result.output
            assert "****4321" in result.output


class TestKeyClear:
    """key clear --provider"""

    def test_key_clear_deletes_key(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class:
            mock_km = mock_km_class.return_value

            result = runner.invoke(main, ["key", "clear", "--provider", "deepseek"])
            assert result.exit_code == 0
            assert "已清除" in result.output
            mock_km.delete_key.assert_called_once_with("deepseek")

    def test_key_clear_default_provider(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class:
            mock_km = mock_km_class.return_value

            result = runner.invoke(main, ["key", "clear"])
            assert result.exit_code == 0
            mock_km.delete_key.assert_called_once_with("deepseek")


class TestKeyRotate:
    """key rotate --provider"""

    def test_key_rotate_clears_and_sets(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("builtins.input") as mock_input:
            mock_input.return_value = "sk-new-rotated-key"
            mock_km = mock_km_class.return_value

            result = runner.invoke(main, ["key", "rotate", "--provider", "glm"])
            assert result.exit_code == 0
            mock_km.delete_key.assert_called_once_with("glm")
            mock_km.set_key.assert_called_once_with("glm", "sk-new-rotated-key")

    def test_key_rotate_default_provider(self, runner):
        with patch("hatch.cli.KeyManager") as mock_km_class, \
             patch("builtins.input") as mock_input:
            mock_input.return_value = "sk-rotated-default"
            mock_km = mock_km_class.return_value

            result = runner.invoke(main, ["key", "rotate"])
            assert result.exit_code == 0
            mock_km.delete_key.assert_called_with("deepseek")
            mock_km.set_key.assert_called_with("deepseek", "sk-rotated-default")


class TestConfigShow:
    """config show"""

    def test_config_show_displays_values(self, runner):
        mock_config = Config(
            llm=LLMConfig(provider="deepseek", model="deepseek-v4-pro"),
            loop=LoopConfig(max_rounds=3),
            tools=ToolsConfig(enabled=["file_reader", "file_writer"]),
        )

        with patch("hatch.cli.ConfigLoader.load", return_value=mock_config):
            result = runner.invoke(main, ["config", "show"])
            assert result.exit_code == 0
            assert "deepseek" in result.output
            assert "deepseek-v4-pro" in result.output
            assert "3" in result.output
            assert "file_reader" in result.output
            assert "file_writer" in result.output

    def test_config_show_defaults(self, runner):
        with patch("hatch.cli.ConfigLoader.load", return_value=Config()):
            result = runner.invoke(main, ["config", "show"])
            assert result.exit_code == 0
            assert "LLM provider" in result.output
            assert "LLM model" in result.output
            assert "Max rounds" in result.output
            assert "Tools" in result.output


class TestConfigValidate:
    """config validate"""

    def test_config_validate_valid(self, runner):
        with patch("hatch.cli.ConfigLoader.load", return_value=Config()):
            result = runner.invoke(main, ["config", "validate"])
            assert result.exit_code == 0
            assert "有效" in result.output

    def test_config_validate_error(self, runner):
        with patch("hatch.cli.ConfigLoader.load", side_effect=ValueError("YAML 解析错误")):
            result = runner.invoke(main, ["config", "validate"])
            assert result.exit_code == 0
            assert "配置文件错误" in result.output
            assert "YAML 解析错误" in result.output
