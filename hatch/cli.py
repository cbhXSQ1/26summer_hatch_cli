"""CLI 入口"""

import os
import json
import click

from hatch.core.llm import DeepSeekLLM, GLMLLM, ClaudeLLM, OpenAICompatLLM
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
from hatch.memory.session_manager import SessionManager


def _build_llm(config, api_key):
    if config.llm.provider == "deepseek":
        return DeepSeekLLM(api_key, model=config.llm.model)
    elif config.llm.provider == "glm":
        return GLMLLM(api_key, model=config.llm.model)
    elif config.llm.provider == "claude":
        return ClaudeLLM(api_key, model=config.llm.model)
    meta = config.llm.providers.get(config.llm.provider)
    if meta and meta.get("api_base"):
        return OpenAICompatLLM(api_key, meta["api_base"], model=config.llm.model)
    return None


def _build_registry(config):
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
    return registry


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Hatch — Coding Agent Harness"""
    pass


def _verbose_printer(event: dict) -> None:
    """格式化打印循环事件到终端"""
    etype = event["type"]

    if etype == "round_start":
        click.echo()
        click.secho(f"┌─ 第 {event['round']}/{event['max_rounds']} 轮 ──────────────────────", fg="cyan", bold=True)

    elif etype == "thinking":
        click.secho("  🧠 思考中...", fg="yellow")

    elif etype == "stream_chunk":
        click.echo(event["text"], nl=False)

    elif etype == "llm_output":
        pass  # 流式输出已显示内容，llm_output 仅内部使用

    elif etype == "tool_call":
        name = event["name"]
        params = event["params"]
        click.secho(f"│ 🔧 调用工具: {name}", fg="green")
        for k, v in params.items():
            val = str(v)[:100]
            click.echo(f"│    {k}: {val}")

    elif etype == "tool_result":
        success = event["success"]
        name = event["name"]
        output = event.get("output", "")
        if success:
            click.secho(f"│ ✅ {name} 成功", fg="green")
        else:
            click.secho(f"│ ❌ {name} 失败", fg="red")
        if output and output != "(no output)":
            for line in output.split("\n")[:3]:
                click.echo(f"│    {line}")

    elif etype == "guardrail_block":
        click.secho(f"│ 🛑 护栏拦截: {event['reason']}", fg="red", bold=True)

    elif etype == "guardrail_approve":
        click.secho(f"│ ⚠️  需要审批: {event['reason']}", fg="yellow")

    elif etype == "guardrail_denied":
        click.secho("│ ❌ 审批被拒绝", fg="red")

    elif etype == "feedback":
        if event["success"]:
            click.secho("│ ✅ 反馈: 全部通过", fg="green")
        else:
            click.secho(f"│ 📋 反馈: {event['issues']} 个问题", fg="yellow")
            ctx = event.get("context", "")
            if ctx:
                for line in ctx.split("\n")[:3]:
                    click.echo(f"│    {line}")

    elif etype == "round_end":
        if event["all_ok"]:
            click.secho("└─ 本轮通过 ✓", fg="green")
        else:
            click.secho("└─ 本轮未通过，进行下一轮...", fg="yellow")

    elif etype == "done":
        status = event["status"]
        if status == "success":
            click.secho(f"\n🎉 任务成功完成 ({event['rounds']} 轮)", fg="green", bold=True)
        elif status == "failed":
            click.secho(f"\n💥 任务失败 ({event['rounds']} 轮)", fg="red", bold=True)
        elif status == "stopped":
            click.secho("\n🛑 任务被护栏中止", fg="red", bold=True)

    elif etype == "llm_text":
        for line in event["text"].split("\n")[:20]:
            click.echo(f"│ {line}")

    elif etype == "warning":
        click.secho(f"│ ⚠️  {event['msg']}", fg="yellow")


@main.command()
@click.argument("task")
@click.option("--cwd", default=None, help="工作目录 (默认当前目录)")
@click.option("--verbose/--quiet", default=True, help="显示详细输出")
def run(task: str, cwd: str | None, verbose: bool) -> None:
    """执行 agent 任务"""
    if cwd:
        os.makedirs(cwd, exist_ok=True)
        os.chdir(cwd)

    if verbose:
        click.echo(f"📂 {os.getcwd()}")

    sm = SessionManager(os.getcwd())
    session_id, is_new = sm.get_latest_or_create(task)

    if verbose:
        label = "新对话" if is_new else "继续对话"
        click.echo(f"💬 {label}: {session_id}")

    config = ConfigLoader.load("hatch.yaml")
    km = KeyManager()
    api_key = km.get_key(config.llm.provider)

    if not api_key:
        click.echo(f"未找到 {config.llm.provider} 的 API Key，请先运行: hatch key set")
        return

    llm = _build_llm(config, api_key)
    if llm is None:
        click.echo(f"不支持的 provider: {config.llm.provider}")
        return

    registry = _build_registry(config)

    previous_turns = sm.get_conversation_turns(session_id, limit=10) if not is_new else []

    loop = AgentLoop()
    state = loop.run(
        task=task, llm=llm, registry=registry, config=config,
        on_event=_verbose_printer if verbose else None,
        conversation_history=previous_turns,
        workdir=os.getcwd(),
    )

    sm.update_status(session_id, state.round, state.status)
    sm.save_history(session_id, [
        {"round": h.round_number, "success": h.success, "issues": h.total_issues}
        for h in state.history
    ])
    sm.add_conversation_turn(session_id, "user", task)
    for turn in state.conversation_turns:
        sm.add_conversation_turn(session_id, turn["role"], turn["content"])

    if not verbose:
        click.echo(f"任务完成。状态: {state.status}，轮次: {state.round}/{state.max_rounds}")


@main.group()
def session() -> None:
    """会话管理"""
    pass


@session.command("new")
@click.option("--cwd", default=None, help="工作目录")
def session_new(cwd: str | None) -> None:
    """创建新对话"""
    if cwd:
        os.chdir(cwd)
    sm = SessionManager(os.getcwd())
    sid = sm.create("新对话")
    click.echo(f"新对话已创建: {sid}")


@session.command("use")
@click.argument("session_id")
@click.option("--cwd", default=None, help="工作目录")
def session_use(session_id: str, cwd: str | None) -> None:
    """切换到指定对话（更新其时间为最新）"""
    if cwd:
        os.chdir(cwd)
    sm = SessionManager(os.getcwd())
    info = sm.get_info(session_id)
    if info is None:
        click.echo(f"会话 {session_id} 不存在")
        return
    sm.update_status(session_id, info.get("rounds", 0), info.get("status", "active"))
    click.echo(f"已切换到对话: {session_id}")


@session.command("list")
@click.option("--cwd", default=None, help="工作目录")
def session_list(cwd: str | None) -> None:
    """列出所有对话"""
    if cwd:
        os.chdir(cwd)
    sm = SessionManager(os.getcwd())
    sessions = sm.list_sessions()
    latest = sm.get_latest()

    if not sessions:
        click.echo("暂无对话记录")
        return

    for s in sessions:
        marker = " *" if s["id"] == latest else ""
        click.echo(f"  {s['id']}{marker}")
        click.echo(f"    任务: {s['task']}")
        click.echo(f"    轮次: {s['rounds']}  状态: {s['status']}")
        click.echo(f"    更新: {s['updated']}")
        click.echo()


@session.command("info")
@click.option("--cwd", default=None, help="工作目录")
def session_info(cwd: str | None) -> None:
    """查看当前对话信息"""
    if cwd:
        os.chdir(cwd)
    sm = SessionManager(os.getcwd())
    sid = sm.get_latest()
    if sid is None:
        click.echo("无对话记录")
        return
    info = sm.get_info(sid)
    click.echo(f"会话 ID: {info['id']}")
    click.echo(f"任务:     {info['task']}")
    click.echo(f"创建:     {info['created']}")
    click.echo(f"轮次:     {info['rounds']}")
    click.echo(f"状态:     {info['status']}")


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


@main.command("chat")
@click.option("--cwd", default=None, help="Working directory")
def chat_command(cwd: str | None) -> None:
    """Start interactive TUI chat."""
    import asyncio
    if cwd:
        os.makedirs(cwd, exist_ok=True)
        os.chdir(cwd)

    workdir = os.getcwd()
    config = ConfigLoader.load("hatch.yaml")
    km = KeyManager()
    api_key = km.get_key(config.llm.provider)

    if not api_key:
        click.echo(f"No API key for {config.llm.provider}. Run: hatch key set")
        return

    llm = _build_llm(config, api_key)
    if llm is None:
        click.echo(f"Unsupported provider: {config.llm.provider}")
        return

    sm = SessionManager(workdir)
    session_id, is_new = sm.get_latest_or_create("新对话")
    info = sm.get_info(session_id)
    session_name = info["task"] if info else "新对话"

    from hatch.tui.app import HatchChatApp
    app = HatchChatApp(
        workdir=workdir,
        llm=llm,
        config=config,
        session_manager=sm,
        session_id=session_id,
        session_name=session_name,
        is_new=is_new,
        key_manager=km,
    )
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
