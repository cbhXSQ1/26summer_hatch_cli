# Hatch - Coding Agent Harness

面向 AI4SE 暑期学校的 Python 编码 Agent 脚手架，**深度维度：反馈闭环引擎**。

## 快速开始

```bash
python -m venv venv
venv\Scripts\pip install -e .[dev]
venv\Scripts\python.exe -m hatch.cli key set      # 录入 API Key（存系统凭据管理器）
venv\Scripts\python.exe -m hatch.cli run "写一个 add 函数到 app.py"
```

## 分发

**包管理器（PyPI）**

```bash
pip install hatch-agent
hatch key set               # 引导录入 API Key
hatch run "修复 app.py 中的类型错误"
```

**GitHub 直接安装（无需 PyPI 发布）**

```bash
pip install git+https://github.com/<username>/hatch.git
hatch key set
hatch run "修复测试"
```

**本地开发安装**

```bash
git clone <仓库地址>
cd hatch
pip install -e .[dev]
```

## 架构

```
hatch/
├── core/           # 核心：Loop, LLM, Parser, Context, Models
├── tools/          # 工具：FileReader/Writer, Shell, Test, Lint, TypeCheck
├── guardrails/     # 护栏：规则链 + HITL
├── feedback/       # ★ 反馈引擎：解析器 → 分类器 → 策略 → 聚合
├── memory/         # 会话记忆
├── config/         # 配置加载器
└── cli.py          # CLI 入口
```

## 反馈闭环流程

```
LLM生成代码 → 工具执行 → 反馈引擎解析
    ↑                        ↓
    └── 上下文注入 ←── 分类(语法/类型/逻辑/风格)
```

## 支持的 LLM 提供商

| 提供商 | 模型 | API 地址 |
|--------|------|---------|
| DeepSeek | deepseek-v4-pro | api.deepseek.com |
| GLM | glm-5.2 | open.bigmodel.cn/api/paas/v4 |
| Claude | claude-sonnet-4-20250514 | api.anthropic.com |

## 运行演示

```bash
venv\Scripts\python.exe tests/demo_guardrail.py   # 护栏拦截
venv\Scripts\python.exe tests/demo_feedback.py    # 反馈闭环
venv\Scripts\python.exe tests/demo_multiround.py  # 多轮反馈
```

## 测试

```bash
venv\Scripts\python.exe -m pytest -q
```

## 安全边界

**API Key 管理**

- Key 通过 `hatch key set [--provider <name>]` 录入，存储在操作系统凭据管理器（Windows Credential Manager / macOS Keychain / Linux Secret Service），service_name 为 `hatch/<provider>`，各供应商独立存储
- Key 绝不写入代码、日志、终端输出或明文配置文件；`hatch key status` 只显示掩码 `****` + 末 4 位
- 后备方案：`~/.hatch/.env` 文件（仅当凭据管理器不可用时使用；**明文存储，有泄露风险**，已被 `.gitignore` 排除）

**治理护栏**

- 危险命令（如 `rm -rf /`、fork bomb）直接拦截；`git push --force`、`pip uninstall`、网络请求等需人工审批（HITL）；文件读写限定在工作目录内
- 文件写入前自动备份到 `.hatch_backup/`

**已知限制**

- Windows 原生无 `make` 命令：本地用 `python -m pytest` / `python -m build` 替代，`Makefile` 供 CI/Linux 使用
- Shell 命令超时上限 30s、测试 120s；工具执行范围限定在 `--cwd` 指定的工作目录内
- 纯 CLI 工具，无 WebUI