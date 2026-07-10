# Hatch - Coding Agent Harness

面向 AI4SE 暑期学校的 Python 编码 Agent 脚手架，**深度维度：反馈闭环引擎**。

## 快速开始

```bash
python -m venv venv
venv\Scripts\pip install -e .
venv\Scripts\python.exe -m pytest -q
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