"""配置加载与校验"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class LLMConfig:
    provider: str = "deepseek"
    model: str = "deepseek-v4-pro"
    api_base: str = "https://api.deepseek.com"
    max_tokens: int = 4096
    temperature: float = 0.1
    providers: dict[str, dict] = field(default_factory=lambda: {
        "deepseek": {
            "api_base": "https://api.deepseek.com",
            "models": ["deepseek-v4-pro", "deepseek-reasoner"],
        },
        "glm": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "models": ["glm-5.2", "glm-4-plus"],
        },
        "claude": {
            "api_base": "https://api.anthropic.com",
            "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        },
    })


@dataclass
class LoopConfig:
    max_rounds: int = 3
    max_total_tokens: int = 100000


@dataclass
class ToolsConfig:
    enabled: list[str] = field(default_factory=lambda: [
        "file_reader", "file_writer", "shell_executor",
        "test_runner", "linter", "type_checker",
    ])
    shell_timeout: int = 30
    test_timeout: int = 120


@dataclass
class GuardrailsConfig:
    require_approval_for: list[str] = field(default_factory=lambda: [
        "git_push_force", "pip_uninstall", "network_requests",
    ])
    blocked_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /", "dd if=",
    ])


@dataclass
class FeedbackConfig:
    max_rounds: int = 3
    loop_detection: bool = True
    auto_apply_style: bool = False


@dataclass
class MemoryConfig:
    max_entries: int = 100
    persist_path: str = "~/.hatch/memory.json"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    guardrails: GuardrailsConfig = field(default_factory=GuardrailsConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


class ConfigLoader:

    @staticmethod
    def load(path: Optional[str]) -> Config:
        config = Config()
        if path is None:
            return config
        file_path = Path(path)
        if not file_path.exists():
            return config
        try:
            raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误: {e}") from e
        if raw is None:
            return config
        if "llm" in raw:
            config.llm = LLMConfig(**{k: v for k, v in raw["llm"].items()
                                      if k in LLMConfig.__dataclass_fields__})
        if "loop" in raw:
            config.loop = LoopConfig(**{k: v for k, v in raw["loop"].items()
                                        if k in LoopConfig.__dataclass_fields__})
        if "tools" in raw:
            config.tools = ToolsConfig(**{k: v for k, v in raw["tools"].items()
                                          if k in ToolsConfig.__dataclass_fields__})
        if "guardrails" in raw:
            config.guardrails = GuardrailsConfig(**{k: v for k, v in raw["guardrails"].items()
                                                    if k in GuardrailsConfig.__dataclass_fields__})
        if "feedback" in raw:
            config.feedback = FeedbackConfig(**{k: v for k, v in raw["feedback"].items()
                                                if k in FeedbackConfig.__dataclass_fields__})
        if "memory" in raw:
            config.memory = MemoryConfig(**{k: v for k, v in raw["memory"].items()
                                            if k in MemoryConfig.__dataclass_fields__})
        return config