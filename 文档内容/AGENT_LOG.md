# AGENT_LOG: Hatch 开发阶段概要

> 按时间顺序记录关键节点。每完成一个 task 或发生重要事件时更新。

---

## Superpowers 使用说明

**冷启动验证阶段（Claude Code）**：Claude Code 作为 §4.5 冷启动验证 agent，未安装 Superpowers 插件，直接使用其原生 subagent 机制完成 T0.1–T1.1 的实现与验证。这是有意的偏离——冷启动验证的目的是检测 SPEC/PLAN 在"无共享上下文"下的清晰度，不应叠加 Superpowers 的流程辅助。

**正式开发阶段（opencode）**：2026-07-08 已配置 opencode + Superpowers 插件，后续所有 task 将严格遵循 Superpowers 七步工作流（subagent-driven-development → TDD → code-review → verification），通过 `skill` 工具加载对应技能。

---

## 项目时间线

| 日期 | 阶段 | 关键事件 |
|------|------|---------|
| 2026-07-08 | 规约 | 选定项目类型 A（Coding Agent Harness），确定深入维度为反馈闭环 |
| 2026-07-08 | 规约 | 完成 `SPEC.md` 初稿 |
| 2026-07-08 | 规约 | 完成 `PLAN.md`（31 个 task，8 个 Phase） |
| 2026-07-08 | 实现 | T0.1 项目初始化 — Claude subagent 完成 |
| 2026-07-08 | 实现 | T0.2 配置文件与 Makefile — Claude subagent 完成 |
| 2026-07-08 | 实现 | T1.1 数据模型 — Claude subagent 完成（41 tests passed） |
| 2026-07-08 | 规约 | 根据 Claude 冷启动验证反馈修正 SPEC（TypeError→TypeCheckError）、PLAN（补充 Git/make 说明） |
| 2026-07-08 | 评审 | Claude 评审 CHECKLIST.md 和 AGENT_LOG.md，修复状态标记和文件命名 |
| 2026-07-08 | 实现 | T2.2 FileReader + FileWriter — opencode (Superpowers TDD) 完成（4 tests） |

---

## 冷启动验证（§4.5）

Claude 作为全新 agent，仅凭 `SPEC.md` + `PLAN.md` 实现 T0.1–T1.1，过程中暴露以下问题：

| 问题 | 类型 | 处理 |
|------|------|------|
| `TypeError` 与 Python 内置异常同名 | SPEC 命名冲突 | 实现时重命名为 `TypeCheckError`，SPEC 已同步修正 |
| `git init` 和初始 commit 遗漏 | PLAN 缺失步骤 | PLAN 已补充 `git init` 和 `git log` 验证 |
| Windows 无 `make` 命令 | PLAN 未覆盖平台差异 | PLAN 已补充 Windows 替代命令 |

无歧义可直接实现的部分：目录结构、hatch.yaml 格式、数据模型字段、依赖版本、CLI 入口。

---

## Task 完成记录

### T0.1 — 项目初始化 ✅

- **Subagent**: Claude
- **Commit**: `ffc0210`
- **产物**: `pyproject.toml`, 8 个 `__init__.py`, `.gitignore`, `venv/`
- **验证**: `pip install -e .` 成功，`import hatch` 不报错
- **偏差**: 无

### T0.2 — 配置文件与 Makefile ✅

- **Subagent**: Claude
- **Commit**: `ffc0210`
- **产物**: `hatch.yaml`, `Makefile`, `.gitlab-ci.yml`
- **验证**: `make test` 可执行（0 tests），`make build` 产出 `.whl`
- **偏差**: Windows 无 `make`，本地用 `python -m pytest` 替代

### T1.1 — 数据模型 ✅

- **Subagent**: Claude
- **Commit**: `ffc0210`
- **产物**: `hatch/core/models.py`（14 个实体），`tests/test_models.py`（41 tests）
- **验证**: 41 passed, 0 failed
- **偏差**: `TypeError` 重命名为 `TypeCheckError`（避免与 Python 内置异常冲突）→ 已同步更新 SPEC

### T1.2 — LLM 抽象层 + MockLLM ✅

- **Subagent**: opencode (Superpowers TDD)
- **Commit**: `70a539e`
- **产物**: `hatch/core/llm.py`（LLMBackend ABC + MockLLM），`tests/test_llm.py`（8 tests）
- **验证**: 8 passed, 0 failed；全量 49 passed
- **偏差**: 无

### T1.3 — LLM 适配器（DeepSeek / GLM / Claude） ✅

- **Subagent**: opencode (Superpowers TDD)
- **Commit**: `34d2696`
- **产物**: `hatch/core/llm.py`（追加 OpenAICompatLLM + DeepSeekLLM + GLMLLM + ClaudeLLM），`tests/test_llm.py`（追加 10 tests）
- **验证**: 10 passed, 0 failed；全量 59 passed
- **偏差**: 无

### T1.4 — 配置加载器 ✅

- **Subagent**: opencode (Superpowers TDD)
- **Commit**: `77eab91`
- **产物**: `hatch/config/loader.py`（Config + 6 个子配置 dataclass + ConfigLoader），`tests/test_config.py`（8 tests）
- **验证**: 8 passed, 0 failed；全量 67 passed
- **偏差**: 无

### T1.5 — 凭据管理器 ✅

- **Subagent**: opencode (Superpowers TDD)
- **Commit**: `b3c62f8`
- **产物**: `hatch/security/key_manager.py`（KeyManager + keyring + mask_key），`tests/test_security.py`（8 tests）
- **验证**: 8 passed, 0 failed；全量 75 passed
- **偏差**: 无

---

## 后续阶段完成记录（摘要）

| 阶段 | 完成情况 | 说明 |
|------|---------|------|
| T1.2–T1.5 | ✅ | LLM 抽象层、3 适配器、配置加载、凭据管理（commits `70a539e`–`b3c62f8`） |
| T2.1–T2.4c | ✅ | 6 个工具 + ToolRegistry（commits `ea10f23`–`cede033`） |
| T3.1–T3.3 | ✅ | 4 条护栏规则 + GuardrailChain + HITL（commits `27658c2`–`e47752f`） |
| T4.1–T4.2 | ✅ | ActionParser + ContextBuilder（commits `2a2a3c2`、`23c666a`） |
| T5.1–T5.8 | ✅ | 反馈引擎（★ 深入维度，commits `19a663b`–`390c627`） |
| T6.1 | ✅ | SessionMemory（commit `aad43a8`） |
| T7.1–T7.2 | ✅ | AgentLoop 主循环 + CLI 入口（commits `bb289e1`、`7983b7e`） |
| T8.1–T8.5 | ✅ | 3 个机制演示 + 端到端集成 + README（commits `0d563ac`–`2234ba4`） |
| Phase 9 | ✅ | TUI 交互界面 16 commits（`50efb26`–`5cf5021`） |
| Phase 10 | ✅ | 工具调用链/上下文/TUI 体验修复 19 commits（`90ce81d`–`0102ffb`） |
| 最终会话 | ✅ | 观察跨轮累积 + 解码规范化 + 会话历史（`38dd1f4`、`fe71a6f`、`84f68b9`） |

**总计**：87 commits，362 测试全绿。各阶段详细 commit 说明见 `进展汇总.md`。

---

## 学到的教训

- **SPEC 命名要与目标语言运行时冲突检查**：`TypeError` 与 Python 内置异常同名，实现时被迫重命名（`TypeCheckError`），波及模型层、类型注解、测试类名
- **"环境事实"必须写进上下文，否则 LLM 会幻觉**：workdir 不注入 → LLM 编造 `D:\project\llm_agent\demo` 目录；不声明 Windows cmd 环境 → 反复发 PowerShell 命令失败
- **完成判定必须收敛**：空 JSON、纯文本意图、XML 工具调用、解析失败都要有确定兜底，否则循环空转 12 轮
- **真实使用是最高效的测试**：Phase 10 的问题（多步链失忆、^M 乱码、结果不配对）几乎全部是"跑起来才发现"，单元测试覆盖不到的集成层面要靠真实运行反馈
- **平台差异要在 PLAN 里显式写出**：Windows 无 make、getpass 无法输入，都是冷启动/实现期才暴露的

---

## 人工干预记录

| 时间 | 干预内容 | 原因 |
|------|---------|------|
| 2026-07-08 | 将 `TypeError` 重命名为 `TypeCheckError` 并同步 SPEC | 与 Python 内置异常同名（冷启动验证暴露） |
| 2026-07-08 | 修正 CHECKLIST/AGENT_LOG 状态标记与文件名（LOG.md → AGENT_LOG.md） | Claude 评审发现 4 处状态错误、1 处命名不符 |
| 2026-07-08 | 放弃 LangChain AgentExecutor，改为自写 AgentLoop | §A.4-A 禁止寄生成型 agent 框架 |
| 2026-08-06 | key set 改用 `click.prompt` 明文输入 | Windows CMD 下 getpass 无法输入（commit `c2b2b25`） |
| 2026-08-06 | 删除 CLI run() 中的重复代码段 | 一次 run 执行两遍（commit `133a2b1`） |
| 2026-08-09 | 按真实使用反馈重写上下文策略：观察跨轮累积、workdir/cmd 注入、纯文本 3 轮硬兜底 | 多步工具链失忆、目录幻觉、循环空转（commit `a7a7524`、`fe71a6f`） |
| 2026-08-10 | 补全交付文档：SPEC_PROCESS / REFLECTION / README 分发与安全章节 / CHECKLIST 状态 | 期末交付前对照《通用要求 §五》自查 |