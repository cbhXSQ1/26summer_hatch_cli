"""CLI 入口"""

import sys
import click

from hatch.core.llm import DeepSeekLLM, GLMLLM, ClaudeLLM
from hatch.core.loop import AgentLoop
from hatch.tools.registry import ToolRegistry
from hatch.tools.file_reader import FileReader
from hatch.tools.file_writer import FileWriter
from hatch.tools.shell_executor import ShellExecutor
from hatch.tools.test_runner import TestRunner
from hatch.tools.linter import Linter
from hatch.tools.type_checker import TypeChecker
from hatch.config.loader import ConfigLoader
from hatch.security.key_manager import KeyManager


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Hatch — Coding Agent Harness"""
    pass


@main.command()
@click.argument("task")
def run(task: str) -> None:
    """执行 agent 任务"""
    config = ConfigLoader.load("hatch.yaml")
    km = KeyManager()
    api_key = km.get_key(config.llm.provider)

    if not api_key:
        click.echo(f"未找到 {config.llm.provider} 的 API Key，请先运行: hatch key set")
        return

    if config.llm.provider == "deepseek":
        llm = DeepSeekLLM(api_key, model=config.llm.model)
    elif config.llm.provider == "glm":
        llm = GLMLLM(api_key, model=config.llm.model)
    elif config.llm.provider == "claude":
        llm = ClaudeLLM(api_key, model=config.llm.model)
    else:
        click.echo(f"不支持的 provider: {config.llm.provider}")
        return

    registry = ToolRegistry()
    for tool_name in config.tools.enabled:
        if tool_name == "file_reader":
            registry.register(FileReader())
        elif tool_name == "file_writer":
            registry.register(FileWriter())
        elif tool_name == "shell_executor":
            registry.register(ShellExecutor())
        elif tool_name == "test_runner":
            registry.register(TestRunner())
        elif tool_name == "linter":
            registry.register(Linter())
        elif tool_name == "type_checker":
            registry.register(TypeChecker())

    loop = AgentLoop()
    state = loop.run(
        task=task,
        llm=llm,
        registry=registry,
        config=config,
    )

    click.echo(f"\n任务完成。状态: {state.status}，轮次: {state.round}/{state.max_rounds}")


@main.group()
def key() -> None:
    """凭据管理"""
    pass


@key.command("set")
@click.option("--provider", default="deepseek", help="LLM 供应商")
def key_set(provider: str) -> None:
    """录入 API Key"""
    km = KeyManager()
    api_key = input(f"请输入 {provider} 的 API Key: ").strip()
    km.set_key(provider, api_key)
    click.echo(f"已保存 {provider} 的 API Key")


@key.command("status")
def key_status() -> None:
    """查看凭据状态"""
    km = KeyManager()
    providers = km.list_providers()
    if not providers:
        click.echo("未存储任何 API Key")
        return
    for p in providers:
        key = km.get_key(p)
        masked = km.mask_key(key) if key else "****"
        click.echo(f"  {p}: {masked}")


@key.command("clear")
@click.option("--provider", default="deepseek", help="LLM 供应商")
def key_clear(provider: str) -> None:
    """清除凭据"""
    km = KeyManager()
    km.delete_key(provider)
    click.echo(f"已清除 {provider} 的 API Key")


@key.command("rotate")
@click.option("--provider", default="deepseek", help="LLM 供应商")
def key_rotate(provider: str) -> None:
    """替换 API Key"""
    key_clear.callback(provider)
    key_set.callback(provider)


@main.group()
def config() -> None:
    """配置管理"""
    pass


@config.command("show")
def config_show() -> None:
    """显示当前配置"""
    cfg = ConfigLoader.load("hatch.yaml")
    click.echo(f"LLM provider: {cfg.llm.provider}")
    click.echo(f"LLM model:    {cfg.llm.model}")
    click.echo(f"Max rounds:   {cfg.loop.max_rounds}")
    click.echo(f"Tools:        {', '.join(cfg.tools.enabled)}")


@config.command("validate")
def config_validate() -> None:
    """验证配置文件"""
    try:
        ConfigLoader.load("hatch.yaml")
        click.echo("配置文件有效")
    except Exception as e:
        click.echo(f"配置文件错误: {e}")


if __name__ == "__main__":
    main()