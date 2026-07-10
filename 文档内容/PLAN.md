# PLAN: Hatch — Coding Agent Harness 实现计划

> 基于 `SPEC.md` 生成，每个 task 可独立派发给 subagent 完成。
> 遵循 TDD：先写失败测试 → 最小实现 → 重构。

---

## 依赖关系图

```
Phase 0 (项目脚手架)
  └─► Phase 1 (核心层)
        ├─► Phase 2 (工具系统)
        ├─► Phase 3 (治理护栏)
        ├─► Phase 4 (动作解析与上下文)
        ├─► Phase 5 (反馈引擎 ★)
        └─► Phase 6 (记忆)
              └─► Phase 7 (主循环 + CLI)
                    └─► Phase 8 (机制演示 + 集成)
```

Phase 1 内的 T1.2~T1.5 可并行；Phase 2 内的 T2.2~T2.4c 可并行；Phase 5 内的 T5.2~T5.4 可并行。

---

## Phase 0: 项目脚手架

### T0.1 — 项目初始化

| 项 | 内容 |
|----|------|
| **目标** | 创建项目目录结构、`pyproject.toml`、`__init__.py` 文件 |
| **涉及文件** | `pyproject.toml`、`hatch/__init__.py`、`hatch/core/__init__.py`、`hatch/tools/__init__.py`、`hatch/guardrails/__init__.py`、`hatch/feedback/__init__.py`、`hatch/feedback/parsers/__init__.py`、`hatch/memory/__init__.py`、`hatch/config/__init__.py`、`hatch/security/__init__.py`、`tests/__init__.py`、`.gitignore` |
| **实现要点** | `git init` 初始化仓库；`pyproject.toml` 声明依赖：`httpx`、`click`、`pyyaml`、`keyring`；`[project.scripts]` 定义 `hatch` 入口；`.gitignore` 排除 `__pycache__`、`.env`、`.hatch_backup/`、`dist/`、`venv/`、`.venv/`；创建虚拟环境：`python -m venv venv`，激活后 `pip install -e .`；完成初始 commit |
| **验证** | `git log` 有初始 commit；`venv/` 目录存在；激活虚拟环境后 `pip install -e .` 成功，`import hatch` 不报错 |

### T0.2 — 配置文件与 Makefile

| 项 | 内容 |
|----|------|
| **目标** | 创建默认 `hatch.yaml`、`Makefile`、`.gitlab-ci.yml` |
| **涉及文件** | `hatch.yaml`、`Makefile`、`.gitlab-ci.yml` |
| **实现要点** | `hatch.yaml` 按 SPEC §3.2.6 格式；`Makefile` 提供 `make test`（pytest）、`make build`（python -m build）、`make clean`、`make install`、`make dev-install`；`.gitlab-ci.yml` 包含 `unit-test` 和 `build` 两个 job |
| **验证** | `make test` 能执行（即使 0 个测试）；`make build` 产出 `dist/*.whl`；Windows 本地无 `make` 时用 `python -m pytest` 和 `python -m build` 替代 |

---

## Phase 1: 核心层

### T1.1 — 数据模型

| 项 | 内容 |
|----|------|
| **目标** | 定义所有共享数据类（dataclass）和枚举 |
| **涉及文件** | `hatch/core/models.py`、`tests/test_models.py` |
| **实现要点** | 按 SPEC §6 定义：`Action`、`ToolResult`、`TestResult`、`TestError`、`LintResult`、`LintIssue`、`TypeCheckResult`、`TypeCheckError`、`ClassifiedFailure`、`FailureCategory`(Enum)、`FeedbackSummary`、`GuardrailResult`、`MemoryEntry`、`LoopState`；全部使用 `@dataclass` |
| **验证** | 测试：创建各实体实例，断言字段类型和默认值正确；`FailureCategory` 枚举值正确 |

### T1.2 — LLM 抽象层 + MockLLM

| 项 | 内容 |
|----|------|
| **目标** | 实现 `LLMBackend` 抽象基类和 `MockLLM` |
| **涉及文件** | `hatch/core/llm.py`、`tests/test_llm.py` |
| **依赖** | T1.1 |
| **实现要点** | `LLMBackend` 含 `complete(messages: list[dict]) -> str` 抽象方法；`MockLLM` 接受 `responses: list[str]`，每次调用返回序列中的下一个，`call_count` 自增 |
| **验证** | 测试：MockLLM 按序列返回；超出序列循环回开头；`call_count` 正确递增 |

### T1.3 — LLM 适配器（DeepSeek / GLM / Claude）

| 项 | 内容 |
|----|------|
| **目标** | 实现三个真实 LLM 后端 |
| **涉及文件** | `hatch/core/llm.py`（追加）、`tests/test_llm.py`（追加） |
| **依赖** | T1.2 |
| **实现要点** | `OpenAICompatLLM` 基类：用 `httpx` POST 到 `{base_url}/chat/completions`，构造 OpenAI 格式请求体；`DeepSeekLLM` 默认 `api.deepseek.com`；`GLMLLM` 默认 `open.bigmodel.cn/api/paas/v4`；`ClaudeLLM` 用 Anthropic Messages API。全部支持 `api_key` 参数和 `model` 参数 |
| **验证** | 测试：用 Mock 替换 httpx 响应，验证各适配器构造正确的 HTTP 请求（URL、headers、body 格式）；超时重试逻辑 |

### T1.4 — 配置加载器

| 项 | 内容 |
|----|------|
| **目标** | 读取并校验 `hatch.yaml` 配置 |
| **涉及文件** | `hatch/config/loader.py`、`tests/test_config.py` |
| **依赖** | T1.1 |
| **实现要点** | `ConfigLoader.load(path)` 读取 YAML → 校验必填字段 → 合并默认值 → 返回 `Config` 对象；缺失文件时使用内置默认值；格式错误时报告具体行号和错误原因 |
| **验证** | 测试：加载合法配置成功；缺失文件用默认值；非法 YAML 报错；缺少必填字段报错；默认值覆盖正确 |

### T1.5 — 凭据管理器

| 项 | 内容 |
|----|------|
| **目标** | 实现 API Key 的安全存储与读取 |
| **涉及文件** | `hatch/security/key_manager.py`、`tests/test_security.py` |
| **依赖** | T1.1 |
| **实现要点** | `KeyManager` 封装 `keyring`：`set_key(provider, key)` → 存储到 `hatch/<provider>`；`get_key(provider)` → 读取；`delete_key(provider)` → 删除；`list_providers()` → 列出已存储的 provider；后备方案：`~/.hatch/.env` 文件读取（文档标注风险） |
| **验证** | 测试：Mock keyring，验证 set/get/delete 流程；key 值不暴露在日志中；`get_key` 返回 `None` 时正确处理 |

---

## Phase 2: 工具系统

### T2.1 — Tool 基类 + ToolRegistry

| 项 | 内容 |
|----|------|
| **目标** | 定义工具接口和注册机制 |
| **涉及文件** | `hatch/tools/base.py`、`hatch/tools/registry.py`、`tests/test_tools.py` |
| **依赖** | T1.1 |
| **实现要点** | `Tool` ABC：`name`、`description`、`parameters_schema`、`execute(params) -> ToolResult`；`ToolRegistry`：`register(tool)`、`get(name)`、`list_tools()`、`dispatch(action) -> ToolResult` |
| **验证** | 测试：注册工具后能获取；未注册工具名返回错误；dispatch 正确调用对应工具 |

### T2.2 — FileReader + FileWriter

| 项 | 内容 |
|----|------|
| **目标** | 实现文件读写工具 |
| **涉及文件** | `hatch/tools/file_reader.py`、`hatch/tools/file_writer.py`、`tests/test_tools.py`（追加） |
| **依赖** | T2.1 |
| **实现要点** | FileReader：读取文件，返回带行号内容；限制 1MB；拒绝二进制文件（检测 null 字节）；FileWriter：写入文件，自动备份到 `.hatch_backup/`；拒绝写入系统目录（`/etc`、`C:\Windows` 等） |
| **验证** | 测试：读取正常文件；超过 1MB 拒绝；二进制文件拒绝；文件不存在报错；写入后内容正确；备份文件存在；拒绝写入系统路径 |

### T2.3 — ShellExecutor

| 项 | 内容 |
|----|------|
| **目标** | 实现 Shell 命令执行工具 |
| **涉及文件** | `hatch/tools/shell_executor.py`、`tests/test_tools.py`（追加） |
| **依赖** | T2.1 |
| **实现要点** | `subprocess.run` 执行命令；捕获 stdout/stderr；超时 30s 默认；工作目录限定在项目根内；返回 `ToolResult(success, output, error, exit_code)` |
| **验证** | 测试：执行 `echo hello` 返回正确输出；超时命令被终止；退出码非零时 success=False；stderr 捕获正确 |

### T2.4a — TestRunner

| 项 | 内容 |
|----|------|
| **目标** | 实现测试运行工具 |
| **涉及文件** | `hatch/tools/test_runner.py`、`tests/test_tools.py`（追加） |
| **依赖** | T2.1 |
| **实现要点** | TestRunner：执行 `pytest`，超时 120s，返回 stdout+stderr |
| **验证** | 测试：对合法代码运行，验证返回 ToolResult；pytest 不存在时优雅报错 |

### T2.4b — Linter

| 项 | 内容 |
|----|------|
| **目标** | 实现代码风格检查工具 |
| **涉及文件** | `hatch/tools/linter.py`、`tests/test_tools.py`（追加） |
| **依赖** | T2.1 |
| **实现要点** | Linter：执行 `flake8 <path>`，返回 stdout |
| **验证** | 测试：flake8 未安装时给出安装提示 |

### T2.4c — TypeChecker

| 项 | 内容 |
|----|------|
| **目标** | 实现类型检查工具 |
| **涉及文件** | `hatch/tools/type_checker.py`、`tests/test_tools.py`（追加） |
| **依赖** | T2.1 |
| **实现要点** | TypeChecker：执行 `mypy <path>`，返回 stdout |
| **验证** | 测试：mypy 未安装时给出安装提示 |

---

## Phase 3: 治理护栏

### T3.1 — GuardrailRule 基类 + 内置规则

| 项 | 内容 |
|----|------|
| **目标** | 定义护栏规则接口和四条内置规则 |
| **涉及文件** | `hatch/guardrails/rules.py`、`tests/test_guardrails.py` |
| **依赖** | T1.1 |
| **实现要点** | `GuardrailRule` ABC：`severity`、`check(action) -> GuardrailResult`；`DangerousCommandRule`：正则匹配 `rm -rf /`、`dd if=`、fork bomb；`ApprovalCommandRule`：匹配 `git push --force`、`pip uninstall`、`chmod 777`；`NetworkRequestRule`：匹配 `curl`、`wget`；`PathTraversalRule`：检查文件路径是否越界 |
| **验证** | 测试：对每个规则传入匹配/不匹配的 action，断言结果正确；`DangerousCommandRule` 对 `rm -rf /` 返回 denied；普通 `ls` 返回 allowed |

### T3.2 — GuardrailChain

| 项 | 内容 |
|----|------|
| **目标** | 实现规则链，串联所有规则并取最高严重级别 |
| **涉及文件** | `hatch/guardrails/chain.py`、`tests/test_guardrails.py`（追加） |
| **依赖** | T3.1 |
| **实现要点** | `GuardrailChain`：`add_rule(rule)`、`check(action) -> GuardrailResult`；遍历所有规则，遇 block 立即返回；否则收集所有 approve 请求；block > approve > allowed |
| **验证** | 测试：一个动作触发 block+approve → 返回 block；无规则触发 → allowed；纯 approve 动作 → needs_approval=True |

### T3.3 — HITL 审批交互

| 项 | 内容 |
|----|------|
| **目标** | 实现人工审批暂停/恢复流程 |
| **涉及文件** | `hatch/guardrails/hitl.py`、`tests/test_guardrails.py`（追加） |
| **依赖** | T3.2 |
| **实现要点** | `HITLHandler`：`request_approval(action) -> bool`；展示动作详情；等待用户输入 `y/n`；超时 60s 返回 False；测试时注入 mock input 函数 |
| **验证** | 测试：Mock input 返回 `y` → 返回 True；返回 `n` → False；超时 → False；动作详情展示正确 |

---

## Phase 4: 动作解析与上下文

### T4.1 — ActionParser

| 项 | 内容 |
|----|------|
| **目标** | 将 LLM 输出解析为 Action 列表 |
| **涉及文件** | `hatch/core/parser.py`、`tests/test_parser.py` |
| **依赖** | T1.1 |
| **实现要点** | `ActionParser.parse(llm_output: str) -> list[Action]`；要求 LLM 输出 JSON 格式的工具调用列表；解析 JSON → 提取 tool_name + parameters；解析失败返回空列表 + 错误信息 |
| **验证** | 测试：合法 JSON 正确解析；非法 JSON 返回空列表；缺少 tool_name 的 JSON 被拒绝；多个 action 正确拆分 |

### T4.2 — ContextBuilder

| 项 | 内容 |
|----|------|
| **目标** | 组装发送给 LLM 的上下文消息 |
| **涉及文件** | `hatch/core/context.py`、`tests/test_loop.py`（追加） |
| **依赖** | T1.1、T1.4 |
| **实现要点** | `ContextBuilder.build(task, memory, feedback, tools) -> list[dict]`；系统提示词包含：角色定义、可用工具列表、输出格式要求；用户消息包含：任务描述；上轮反馈注入为 assistant 消息 |
| **验证** | 测试：验证消息列表格式正确；系统提示词包含工具描述；反馈注入到正确位置 |

---

## Phase 5: 反馈引擎（★ 深入维度）

### T5.1 — 测试 Fixtures

| 项 | 内容 |
|----|------|
| **目标** | 创建用于测试反馈解析器的样本输出文件 |
| **涉及文件** | `tests/fixtures/sample_pytest_output.txt`、`tests/fixtures/sample_flake8_output.txt`、`tests/fixtures/sample_mypy_output.txt`、`tests/fixtures/sample_project/` |
| **实现要点** | 各文件包含真实工具输出的典型样例：pytest 包含通过+失败+错误；flake8 包含 E501/F401/W291；mypy 包含类型错误+note；sample_project 包含一个简单的 Python 项目（含一个有 bug 的文件和对应测试） |
| **验证** | 手动检查文件内容格式正确 |

### T5.2 — TestResultParser（pytest 输出）

| 项 | 内容 |
|----|------|
| **目标** | 解析 pytest 输出为结构化 TestResult |
| **涉及文件** | `hatch/feedback/parsers/test_parser.py`、`tests/test_feedback_parser.py` |
| **依赖** | T1.1、T5.1 |
| **实现要点** | 正则匹配：`= test session starts =` 后的统计行提取 total/passed/failed；`FAILED test_file.py::test_name` 识别失败测试；`AssertionError` 提取 expected/actual；`E   ...` 捕获错误上下文 |
| **验证** | 测试：解析 sample_pytest_output.txt，断言 total/passed/failed 数量正确；每个 TestError 的字段与文件内容一致；全通过的输出解析后 failed=0 |

### T5.3 — LintResultParser（flake8 输出）

| 项 | 内容 |
|----|------|
| **目标** | 解析 flake8 输出为结构化 LintResult |
| **涉及文件** | `hatch/feedback/parsers/lint_parser.py`、`tests/test_feedback_parser.py`（追加） |
| **依赖** | T1.1、T5.1 |
| **实现要点** | flake8 输出格式固定：`path:line:col: code message`；正则 `(\S+):(\d+):(\d+): (\w+) (.+)` 提取各字段 |
| **验证** | 测试：解析 sample_flake8_output.txt；每个 LintIssue 的 file/line/col/code/message 正确；空输出返回空列表 |

### T5.4 — TypeCheckParser（mypy 输出）

| 项 | 内容 |
|----|------|
| **目标** | 解析 mypy 输出为结构化 TypeCheckResult |
| **涉及文件** | `hatch/feedback/parsers/type_parser.py`、`tests/test_feedback_parser.py`（追加） |
| **依赖** | T1.1、T5.1 |
| **实现要点** | mypy 格式：`path:line:col: severity: message`；`[note]` 行也需捕获；正则提取 path/line/col/severity/message |
| **验证** | 测试：解析 sample_mypy_output.txt；每个 TypeCheckError 字段正确；error 和 note 级别区分正确 |

### T5.5 — FailureClassifier

| 项 | 内容 |
|----|------|
| **目标** | 按类别和优先级分类失败项 |
| **涉及文件** | `hatch/feedback/classifier.py`、`tests/test_feedback_classifier.py` |
| **依赖** | T1.1、T5.2、T5.3、T5.4 |
| **实现要点** | 按 SPEC §3.2.4-F4 的分类算法：SyntaxError → SYNTAX_ERROR；mypy 报错 → TYPE_ERROR；flake8 报错 → STYLE_ISSUE；AssertionError → LOGIC_ERROR；其他异常 → RUNTIME_ERROR；优先级 1-5 |
| **验证** | 测试：传入含 SyntaxError 的 TestResult → 分类为 SYNTAX_ERROR, priority=1；混合多种错误 → 各类别正确分组；空输入 → 无分类 |

### T5.6 — CorrectionStrategySelector

| 项 | 内容 |
|----|------|
| **目标** | 根据失败类别选择修正策略 |
| **涉及文件** | `hatch/feedback/strategies.py`、`tests/test_feedback_classifier.py`（追加） |
| **依赖** | T5.5 |
| **实现要点** | 按 SPEC §3.2.4-F5 的策略映射，为每个类别生成结构化反馈文本；SYNTAX_ERROR → 返回错误位置+信息；LOGIC_ERROR → 返回 expected vs actual |
| **验证** | 测试：各类别生成不同策略文本；SYNTAX_ERROR 策略包含文件名和行号；LOGIC_ERROR 策略包含 expected/actual |

### T5.7 — FeedbackAggregator

| 项 | 内容 |
|----|------|
| **目标** | 合并多源反馈，生成 FeedbackSummary |
| **涉及文件** | `hatch/feedback/aggregator.py`、`tests/test_feedback_classifier.py`（追加） |
| **依赖** | T5.5、T5.6 |
| **实现要点** | `aggregate(test_result, lint_result, type_result, round_number) -> FeedbackSummary`；计算 success（全部通过）；top_issues 取前 5 个最高优先级；生成 `context_for_llm` 格式化文本 |
| **验证** | 测试：全部通过 → success=True；有失败 → success=False；top_issues 按优先级排序；context_for_llm 包含关键信息 |

### T5.8 — FeedbackEngine 集成

| 项 | 内容 |
|----|------|
| **目标** | 将解析器、分类器、聚合器集成为统一的反馈引擎 |
| **涉及文件** | `hatch/feedback/engine.py`、`tests/test_feedback_loop.py` |
| **依赖** | T5.2–T5.7 |
| **实现要点** | `FeedbackEngine.process(action, tool_result, round_number) -> FeedbackSummary`；根据 action 类型决定调用哪些解析器；死循环检测：比较连续 2 轮 FeedbackSummary |
| **验证** | 测试：对 TestRunner 的 action 触发 pytest 解析；对 Linter 的 action 触发 flake8 解析；连续 2 轮相同反馈触发死循环检测 |

---

## Phase 6: 记忆

### T6.1 — SessionMemory

| 项 | 内容 |
|----|------|
| **目标** | 实现会话记忆存储与检索 |
| **涉及文件** | `hatch/memory/session.py`、`tests/test_memory.py` |
| **依赖** | T1.1 |
| **实现要点** | `SessionMemory`：`set/get/get_all/get_relevant_context`；内存字典存储；最大 100 条；单条 value 最大 4096 字符；持久化到 `~/.hatch/memory.json`（加载时校验 JSON 完整性） |
| **验证** | 测试：set 后 get 正确；超限时拒绝新条目；超长 value 截断；持久化后重启可恢复；损坏 JSON 文件优雅降级 |

---

## Phase 7: 主循环 + CLI

### T7.1 — AgentLoop 主循环

| 项 | 内容 |
|----|------|
| **目标** | 实现完整的 agent 主循环 |
| **涉及文件** | `hatch/core/loop.py`、`tests/test_loop.py` |
| **依赖** | T1.2、T1.4、T2.1、T3.2、T3.3、T4.1、T4.2、T5.8、T6.1 |
| **实现要点** | 按 SPEC §3.2.1 主循环伪代码实现；`run(task, llm, tools, guardrails, feedback_engine, memory, config) -> LoopState`；组装上下文 → 调 LLM → 解析 → 护栏 → 执行 → 反馈 → 停机判断 |
| **验证** | 测试：用 MockLLM 返回预设响应序列，验证完整循环执行；达到 max_rounds 后停机；反馈为 success 时停机；护栏拦截后正确停止 |

### T7.2 — CLI 入口

| 项 | 内容 |
|----|------|
| **目标** | 实现命令行接口 |
| **涉及文件** | `hatch/cli.py` |
| **依赖** | T7.1、T1.5 |
| **实现要点** | 用 click 实现：`hatch run "<task>"`、`hatch run -f task.txt`、`hatch key set [--provider]`、`hatch key status`、`hatch key clear [--provider]`、`hatch key rotate`、`hatch config show`、`hatch config validate`、`hatch --version` |
| **验证** | 手动测试：`hatch --help` 显示所有命令；`hatch key set` 引导录入 |

---

## Phase 8: 机制演示与集成

### T8.1 — 机制演示 1：护栏拦截危险动作

| 项 | 内容 |
|----|------|
| **目标** | 在 mock LLM 下确定性演示护栏拦截 |
| **涉及文件** | `tests/demo_guardrail.py` |
| **依赖** | T3.2、T7.1 |
| **实现要点** | 创建 MockLLM 返回"执行 rm -rf /"的响应；运行 AgentLoop；断言 GuardrailChain 拦截该动作；输出清晰的演示日志 |
| **验证** | `python tests/demo_guardrail.py` 运行，输出显示 "DANGER BLOCKED" |

### T8.2 — 机制演示 2：反馈闭环修正

| 项 | 内容 |
|----|------|
| **目标** | 注入一次测试失败，演示反馈闭环使 agent 收到反馈并改变行为 |
| **涉及文件** | `tests/demo_feedback.py` |
| **依赖** | T5.8、T7.1 |
| **实现要点** | 第一轮 MockLLM 返回"写一个有 bug 的代码"；pytest 返回失败；FeedbackEngine 解析 → 分类为 LOGIC_ERROR；第二轮 MockLLM 验证上下文包含反馈摘要；第二轮 MockLLM 返回"根据反馈修正代码" |
| **验证** | `python tests/demo_feedback.py` 运行，输出显示第一轮反馈解析结果和第二轮修正行为 |

### T8.3 — 机制演示 3：多轮反馈闭环（重点维度）

| 项 | 内容 |
|----|------|
| **目标** | 演示完整的多轮修正循环，反馈信号正确回灌 |
| **涉及文件** | `tests/demo_multiround.py` |
| **依赖** | T5.8、T7.1 |
| **实现要点** | 3 轮循环：第 1 轮 → 语法错误（SYNTAX_ERROR）；第 2 轮 → 类型错误（TYPE_ERROR）；第 3 轮 → 全部通过；每轮验证 LLM 上下文包含上一轮的反馈摘要；验证死循环检测逻辑 |
| **验证** | `python tests/demo_multiround.py` 运行，输出显示 3 轮过程，第 3 轮 success=True |

### T8.4 — 端到端集成测试

| 项 | 内容 |
|----|------|
| **目标** | 用 sample_project 做完整集成测试 |
| **涉及文件** | `tests/test_feedback_loop.py`（完善） |
| **依赖** | T8.1、T8.2、T8.3 |
| **实现要点** | 使用 sample_project（含 bug 代码 + 测试）；MockLLM 模拟真实行为；验证完整流程：读文件 → 修改 → 运行测试 → 反馈 → 再修改 → 通过 |
| **验证** | `pytest tests/test_feedback_loop.py` 通过，不依赖网络和真实 LLM |

### T8.5 — README.md

| 项 | 内容 |
|----|------|
| **目标** | 编写项目文档 |
| **涉及文件** | `README.md`、`LICENSE` |
| **依赖** | T7.2 |
| **实现要点** | 按通用要求 §五.4 包含：项目简介、安装、运行、分发命令、目录结构、安全边界说明；LICENSE 使用 MIT |
| **验证** | 他人按 README 步骤能成功安装并运行 |

---

## 并行执行建议

```
worktree 1: T0.1 → T0.2 → T1.1 → T1.2 → T1.3
worktree 2:              T1.1 → T1.4
worktree 3:              T1.1 → T1.5

worktree 1: T2.1 → T2.2 → T2.3 → T2.4a → T2.4b → T2.4c
worktree 2: T3.1 → T3.2 → T3.3
worktree 3: T4.1 → T4.2

worktree 1: T5.1 → T5.2 → T5.3 → T5.4 → T5.5 → T5.6 → T5.7 → T5.8
worktree 2: T6.1

worktree 1: T7.1 → T7.2 → T8.1 → T8.2 → T8.3 → T8.4 → T8.5
```

---

## 任务完成状态

| Task | 状态 | Commit Hash | 备注 |
|------|------|-------------|------|
| T0.1 | ✅ | `ffc0210` | |
| T0.2 | ✅ | `ffc0210` | |
| T1.1 | ✅ | `ffc0210` | |
| T1.2 | ✅ | `70a539e` | |
| T1.3 | ✅ | `34d2696` | |
| T1.4 | ✅ | `77eab91` | |
| T1.5 | ✅ | `b3c62f8` | |
| T2.1 | ✅ | `ea10f23` | |
| T2.2 | ✅ | `b05f0e5` | |
| T2.3 | ✅ | `799cc82` | |
| T2.4a | ✅ | `986edf8` | |
| T2.4b | ✅ | `5e784e7` | |
| T2.4c | ✅ | `cede033` | |
| T3.1 | ✅ | `27658c2` | |
| T3.2 | ✅ | `f8b3a1f` | |
| T3.3 | ✅ | `e47752f` | |
| T4.1 | ✅ | `2a2a3c2` | |
| T4.2 | ✅ | `23c666a` | |
| T5.1 | ✅ | `19a663b` | |
| T5.2 | ✅ | `7a6c551` | |
| T5.3 | ✅ | `7a6c551` | |
| T5.4 | ✅ | `7a6c551` | |
| T5.5 | ✅ | `6d43be8` | |
| T5.6 | ✅ | `512382e` | |
| T5.7 | ✅ | `2bb505d` | |
| T5.8 | ✅ | `390c627` | |
| T6.1 | ✅ | `aad43a8` | |
| T7.1 | ✅ | `bb289e1` | |
| T7.2 | ✅ | `7983b7e` | |
| T8.1 | ✅ | `0d563ac` | |
| T8.2 | ✅ | `0d563ac` | |
| T8.3 | ✅ | `0d563ac` | |
| T8.4 | ✅ | `9437837` | |
| T8.5 | ✅ | `2234ba4` | |
| **总测试** | **233/233** | — | 含 CLI 17 + 工具 33 + 反馈 36 + 护栏 11 + LLM 5 + 循环 6 + 记忆 6 |