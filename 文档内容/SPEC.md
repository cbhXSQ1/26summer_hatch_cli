# SPEC: Hatch — 一个面向 Python 开发的 Coding Agent Harness

> **项目代号**：Hatch（孵化）  
> **类型**：A · Coding Agent Harness  
> **作者**：[你的姓名]  
> **日期**：2026-07-08

---

## 1. 问题陈述

### 1.1 要解决的问题

当前市面上的 Coding Agent（如 GitHub Copilot、Cursor、Claude Code）已经能完成相当比例的代码生成工作，但它们的"自我修正"能力严重依赖 LLM 自身的推理——即"让 LLM 自己检查自己的代码"。这种方式的缺陷是：

- LLM 可能"自信地犯错"：生成的代码有问题，但 LLM 认为没问题
- 缺乏客观判据：没有外部信号告诉 agent "你到底对不对"
- 修正不可预测：同一段错误代码，两次运行可能产生不同的修正结果

**Hatch 要解决的核心问题**：构建一个 harness，用**客观、确定性的反馈信号**（测试结果、lint 输出、类型检查报错）驱动 agent 的自我修正循环，使修正过程不再依赖 LLM 的"自觉"，而是依赖可验证的外部事实。

### 1.2 目标用户

- **Python 开发者**：希望有一个能自动修复代码问题的助手
- **学习 AI4SE 的学生**：通过本项目理解 harness 的工程本质

### 1.3 为什么值得做

当前 AI 编码工具的价值集中在"首次生成"，而"修正"环节仍是薄弱点。Hatch 通过将反馈闭环工程化，证明了工程师的价值不在于"写提示词"，而在于**构建让 LLM 无法逃避的客观验证体系**。

---

## 2. 用户故事

| # | 用户故事 | 验收标准 |
|---|---------|---------|
| US1 | 作为开发者，我希望 Hatch 能读取我指定的代码文件，理解其内容，并根据我的自然语言指令修改代码 | 给定一个 Python 文件和修改指令，Hatch 生成修改后的代码 |
| US2 | 作为开发者，我希望 Hatch 修改代码后自动运行测试，如果测试失败能自动分析失败原因并重新修改 | 注入一个带 bug 的修改，Hatch 检测到测试失败，解析错误，并重新尝试修正 |
| US3 | 作为开发者，我希望 Hatch 在尝试修正多次仍失败后能报告失败并保留上下文，而不是无限循环 | 设定最大修正轮次（如 3 轮），超出后 Hatch 停止并报告 |
| US4 | 作为开发者，我希望 Hatch 在执行危险命令（如 `rm -rf`、`git push --force`）前暂停并请求我确认 | 触发危险命令时，Hatch 拦截并等待人工输入 `yes/no` |
| US5 | 作为开发者，我希望 Hatch 能记住我在本次会话中的偏好和项目约定，供后续任务参考 | 在一个会话中设定"使用 pytest 而非 unittest"后，后续任务默认使用 pytest |
| US6 | 作为开发者，我希望 Hatch 能通过配置文件定制行为（如最大修正轮次、允许的工具、LLM 参数） | 提供 YAML 配置文件，修改后重启 Hatch 生效 |
| US7 | 作为开发者，我希望 Hatch 的安全凭据（API Key）不暴露在代码或日志中，且首次运行时有引导式录入 | 首次运行引导输入 key，存储到系统凭据管理器，日志中不出现明文 |

---

## 3. 功能规约

### 3.1 模块总览

```
hatch/
├── core/           # 主循环与 LLM 抽象
├── tools/          # 工具系统（文件读写、Shell、测试、lint、类型检查）
├── guardrails/     # 治理护栏
├── feedback/       # 反馈闭环引擎（★ 深入维度）
├── memory/         # 会话记忆
├── config/         # 配置管理
└── security/       # 凭据安全
```

### 3.2 模块详细规约

---

#### 3.2.1 core — 主循环与 LLM 抽象

**Agent 主循环**

```
输入：用户任务描述、工作目录
输出：任务完成或失败

循环：
  1. 组装上下文（系统提示 + 记忆 + 当前任务 + 上轮反馈）
  2. 调用 LLM 获取决策（自然语言描述要执行的动作）
  3. 解析 LLM 输出 → 提取动作（tool_name + parameters）
  4. 治理检查：guardrail(action) → 通过/拦截/需审批
  5. 分发执行：dispatch(action) → 执行结果
  6. 反馈引擎处理：feedback_engine.process(action, result) → 反馈信号
  7. 停机判断：任务完成？达到最大轮次？反馈信号指示成功？
  8. 若未停机，将反馈信号回灌到下一轮上下文
```

**LLM 抽象层**

```python
class LLMBackend(ABC):
    """LLM 后端抽象基类"""
    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        """发送消息列表，返回 LLM 响应"""
        ...

class MockLLM(LLMBackend):
    """Mock LLM：返回预编程的响应序列，用于确定性测试"""
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0

    def complete(self, messages: list[dict]) -> str:
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response

class OpenAICompatLLM(LLMBackend):
    """OpenAI 兼容 API 后端（DeepSeek、GLM 等国产模型通用）"""
    def __init__(self, api_key: str, base_url: str, model: str):
        ...

class DeepSeekLLM(OpenAICompatLLM):
    """DeepSeek API 后端"""
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key, "https://api.deepseek.com/v1", model)

class GLMLLM(OpenAICompatLLM):
    """智谱 GLM API 后端"""
    def __init__(self, api_key: str, model: str = "glm-4-flash"):
        super().__init__(api_key, "https://open.bigmodel.cn/api/paas/v4", model)

class ClaudeLLM(LLMBackend):
    """Anthropic Claude API 后端"""
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        ...
```

**边界条件**：
- LLM 返回无法解析的输出 → 记录错误，将错误信息作为反馈回灌，重试
- API 超时/网络错误 → 重试最多 3 次，指数退避
- 连续 3 次解析失败 → 停机，报告失败

---

#### 3.2.2 tools — 工具系统

Hatch 提供以下工具，每个工具实现统一的 `Tool` 接口：

```python
class Tool(ABC):
    name: str
    description: str
    parameters_schema: dict  # JSON Schema

    @abstractmethod
    def execute(self, params: dict) -> ToolResult:
        ...
```

**T1: FileReader** — 读取文件
- 输入：文件路径
- 输出：文件内容（带行号）或错误信息
- 边界：限制文件大小上限（默认 1MB），拒绝读取二进制文件

**T2: FileWriter** — 写入/修改文件
- 输入：文件路径、新内容（或 diff）
- 输出：写入成功/失败
- 边界：写入前自动备份原文件（`.hatch_backup/`），拒绝写入系统目录

**T3: ShellExecutor** — 执行 Shell 命令
- 输入：命令字符串、工作目录、超时时间
- 输出：stdout、stderr、退出码
- 边界：超时 30s 默认上限，工作目录限定在项目根目录内

**T4: TestRunner** — 运行测试
- 输入：测试命令（默认 `pytest`）、目标路径
- 输出：测试结果摘要（通过/失败数）、失败详情
- 边界：超时 120s

**T5: Linter** — 代码风格检查
- 输入：目标文件路径
- 输出：lint 问题列表（文件、行号、问题描述）
- 默认使用 `flake8`

**T6: TypeChecker** — 类型检查
- 输入：目标文件路径
- 输出：类型错误列表（文件、行号、错误描述）
- 默认使用 `mypy`

---

#### 3.2.3 guardrails — 治理护栏

**护栏规则引擎**

```python
class GuardrailRule(ABC):
    """单条护栏规则"""
    severity: str  # "block" | "approve" | "warn"

    @abstractmethod
    def check(self, action: Action) -> GuardrailResult:
        """返回：allowed / denied / needs_approval"""
        ...
```

**内置规则**：

| 规则 | 严重级别 | 触发条件 |
|------|---------|---------|
| 危险 Shell 命令 | block | 命令匹配 `rm -rf /`、`dd if=`、`:(){:|:&};:` 等 |
| 需审批命令 | approve | `git push --force`、`pip uninstall`、`chmod 777`、删除非临时文件 |
| 外部网络请求 | approve | 任何 `curl`、`wget` 调用 |
| 路径越界 | block | 读写工作目录之外的文件 |

**HITL 审批流程**：
1. 护栏检测到需审批动作
2. 暂停执行，向用户展示动作详情
3. 用户输入 `y/yes` 或 `n/no`
4. 超时（60s）无响应 → 视为拒绝

**边界条件**：
- 规则链按优先级排序，block 级优先于 approve 级
- 同一动作可能触发多条规则 → 取最高严重级别

---

#### 3.2.4 feedback — 反馈闭环引擎（★ 深入维度）

这是 Hatch 的核心深度模块。设计目标：**用确定性代码解析外部工具的输出，将其转化为结构化反馈信号，驱动 agent 的自我修正**。

**架构**：

```
                    ┌─────────────────┐
                    │  FeedbackEngine │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │TestParser  │ │LintParser  │ │TypeParser  │
     └────────────┘ └────────────┘ └────────────┘
              │              │              │
              ▼              ▼              ▼
     ┌─────────────────────────────────────────┐
     │         FailureClassifier               │
     │  syntax | type | logic | style | other  │
     └─────────────────────────────────────────┘
                             │
                             ▼
     ┌─────────────────────────────────────────┐
     │         CorrectionStrategySelector      │
     │  根据失败类别选择修正策略               │
     └─────────────────────────────────────────┘
                             │
                             ▼
     ┌─────────────────────────────────────────┐
     │         FeedbackAggregator               │
     │  合并多源反馈，生成结构化反馈摘要         │
     └─────────────────────────────────────────┘
```

**F1: TestResultParser** — pytest 输出解析器

```
输入：pytest 的 stdout 文本
输出：TestResult 结构体
  - total: int
  - passed: int
  - failed: int
  - errors: list[TestError]
    - test_name: str
    - error_type: str  # AssertionError | ImportError | NameError | ...
    - message: str
    - file_path: str
    - line_number: int | None
    - expected: str | None
    - actual: str | None
```

解析策略：正则匹配 pytest 的标准输出格式。关键匹配模式：
- `FAILED test_file.py::test_name` → 识别失败测试
- `AssertionError: assert X == Y` → 提取期望值和实际值
- `E   ...` → 捕获错误上下文

**F2: LintResultParser** — flake8 输出解析器

```
输入：flake8 的 stdout 文本
输出：LintResult 结构体
  - issues: list[LintIssue]
    - file_path: str
    - line: int
    - column: int
    - code: str  # E501, F401, W291 ...
    - message: str
```

flake8 输出格式固定：`path:line:col: code message`，解析完全确定性。

**F3: TypeCheckParser** — mypy 输出解析器

```
输入：mypy 的 stdout 文本
输出：TypeCheckResult 结构体
  - errors: list[TypeCheckError]
    - file_path: str
    - line: int
    - column: int
    - severity: str  # error | note
    - message: str
```

**F4: FailureClassifier** — 失败分类器

```
输入：TestResult + LintResult + TypeCheckResult（合并后）
输出：ClassifiedFailure 列表
  - category: FailureCategory
  - failures: 该类别下的所有失败项
  - priority: int  # 修正优先级 1-5

FailureCategory 枚举：
  - SYNTAX_ERROR:    语法错误（无法 import、SyntaxError）
  - TYPE_ERROR:      类型不匹配
  - LOGIC_ERROR:     测试断言失败（逻辑错误）
  - STYLE_ISSUE:     代码风格问题
  - RUNTIME_ERROR:   运行时异常（非语法/类型/逻辑）
  - UNKNOWN:         无法归类
```

分类逻辑（确定性算法）：
1. 检查是否有 `SyntaxError` / `IndentationError` → SYNTAX_ERROR
2. 检查 mypy 是否报错 → TYPE_ERROR
3. 检查 flake8 是否报错 → STYLE_ISSUE
4. 检查 pytest 是否有 `AssertionError` → LOGIC_ERROR
5. 检查 pytest 是否有其他异常 → RUNTIME_ERROR
6. 其余 → UNKNOWN

优先级规则：
- SYNTAX_ERROR = 1（最高，必须先修）
- TYPE_ERROR = 2
- LOGIC_ERROR = 3
- RUNTIME_ERROR = 4
- STYLE_ISSUE = 5（最低）

**F5: CorrectionStrategySelector** — 修正策略选择

```
输入：ClassifiedFailure 列表
输出：CorrectionStrategy

策略映射：
  SYNTAX_ERROR   → 返回语法错误位置和错误信息，指示 LLM 修正语法
  TYPE_ERROR     → 返回类型不匹配的变量/函数签名和期望类型
  LOGIC_ERROR    → 返回断言失败的测试名、期望值 vs 实际值
  STYLE_ISSUE    → 返回 lint 规则编号和说明
  RUNTIME_ERROR  → 返回异常类型和 traceback 摘要
```

每种策略会生成一段**结构化的反馈文本**，注入到下一轮 LLM 调用的上下文中。

**F6: FeedbackAggregator** — 多源反馈聚合

```
输入：各解析器的解析结果
输出：FeedbackSummary
  - success: bool  # 是否全部通过
  - total_issues: int
  - by_category: dict[FailureCategory, int]
  - top_issues: list[ClassifiedFailure]  # 前 5 个最高优先级问题
  - context_for_llm: str  # 注入 LLM 上下文的格式化文本
```

**F7: 多轮修正循环**

```
输入：初始任务、最大轮次 N（默认 3）
输出：最终结果

for round in 1..N:
    llm_response = llm.complete(context_with_feedback)
    actions = parse(llm_response)
    for action in actions:
        result = execute(action)
        feedback = feedback_engine.process(action, result)
    if feedback.success:
        return SUCCESS
    context_with_feedback = inject_feedback(context, feedback)

return FAILURE(max_rounds_reached)
```

**F8: 反馈历史追踪**

记录每一轮的反馈摘要，用于：
- 检测是否陷入"死循环"（连续 2 轮相同的反馈 → 尝试不同的修正策略）
- 生成最终报告（向用户展示修正过程）

**边界条件与错误处理**：
- 解析器遇到无法解析的输出格式 → 标记为 UNKNOWN 类别，将原始输出作为反馈回灌
- 反馈引擎本身异常 → 不崩溃，记录错误日志，降级为"将原始输出回灌 LLM"
- 连续 2 轮反馈完全相同 → 触发"策略切换"：在反馈中增加"请尝试不同的方法"提示

---

#### 3.2.5 memory — 会话记忆

**设计原则**：简单但完整。存储键值对形式的会话信息，按需注入 LLM 上下文。

```python
class SessionMemory:
    def set(self, key: str, value: str) -> None: ...
    def get(self, key: str) -> str | None: ...
    def get_all(self) -> dict[str, str]: ...
    def get_relevant_context(self, query: str) -> str: ...
```

**存储内容**：
- 项目约定（如 `test_framework: pytest`）
- 用户偏好（如 `code_style: pep8`）
- 历史决策记录（如上次某文件为何被修改）
- 当前会话的反馈历史摘要

**存储方式**：会话内使用内存字典；跨会话持久化到 `~/.hatch/memory.json`。

**边界条件**：
- 最大条目数限制（默认 100 条）
- 单条 value 最大 4096 字符
- 加载时验证 JSON 完整性

---

#### 3.2.6 config — 配置管理

**配置文件**：`hatch.yaml`（项目根目录，YAML 格式）

```yaml
llm:
  provider: deepseek        # deepseek | glm | claude
  model: deepseek-chat      # 模型名，可按 provider 选默认值
  api_base: https://api.deepseek.com/v1  # API 端点（仅 OpenAI 兼容格式需要）
  max_tokens: 4096
  temperature: 0.1

loop:
  max_rounds: 3
  max_total_tokens: 100000

tools:
  enabled:
    - file_reader
    - file_writer
    - shell_executor
    - test_runner
    - linter
    - type_checker
  shell_timeout: 30
  test_timeout: 120

guardrails:
  require_approval_for:
    - git_push_force
    - pip_uninstall
    - network_requests
  blocked_commands:
    - "rm -rf /"
    - "dd if="

feedback:
  max_rounds: 3          # 最大修正轮次
  loop_detection: true    # 死循环检测
  auto_apply_style: false # 自动应用风格修复

memory:
  max_entries: 100
  persist_path: ~/.hatch/memory.json
```

**配置加载**：
- 启动时读取 `hatch.yaml`
- 缺失时使用内置默认值
- 格式错误时报告具体行号和错误原因

---

#### 3.2.7 security — 凭据安全

**API Key 管理**：

Hatch 支持多个 LLM 供应商，每个供应商的 key 独立管理：

```
首次运行 → 检测当前 provider 的 key 是否存在 → 不存在 → 引导录入
                                                        ↓
                                              隐藏输入（getpass）
                                                        ↓
                                              存储到系统凭据管理器
                                              （service_name = "hatch/<provider>"）
                                                        ↓
                                              验证 key 有效性（一次轻量 API 调用）
                                                        ↓
                                              成功 → 正常运行
                                              失败 → 提示重新录入

后续运行 → 从凭据管理器读取当前 provider 的 key → 正常运行
切换 provider → hatch key set --provider glm → 录入新 key
```

**安全措施**：
- Key 绝不写入日志、绝不打印到终端、绝不存入配置文件
- 查看凭据状态时只显示 `****` + 最后 4 位
- 支持 `hatch key set --provider <name>` 为不同供应商录入 key
- 支持 `hatch key rotate` 替换当前 provider 的 key
- 支持 `hatch key clear` 清除 key
- `.env` 文件在 `.gitignore` 中，仅作为后备方案（文档说明其明文风险）

**威胁模型**：
- 攻击者获取日志文件 → 无凭据泄露
- 攻击者获取源码仓库 → 无凭据泄露
- 攻击者获取本机访问权限 → 凭据受操作系统凭据管理器保护（需用户登录会话）
- `.env` 文件若被误提交 → 明文泄露风险（文档告警 + `.gitignore` 防护）
- 多供应商场景：每个 provider 的 key 独立存储，一个泄露不影响其他

---

## 4. 非功能性需求

### 4.1 性能

| 指标 | 目标 |
|------|------|
| 工具执行（文件读写） | < 100ms |
| 工具执行（Shell 命令） | 取决于命令本身，超时上限 30s |
| 测试运行 | 取决于测试数量，超时上限 120s |
| LLM 调用 | 取决于 API 响应，超时上限 60s |
| 完整一轮修正循环 | < 3 分钟（单轮） |

### 4.2 安全

- 见 §3.2.7 凭据安全与威胁模型
- 见 §3.2.3 治理护栏

### 4.3 可用性

- CLI 界面，命令清晰明确
- 错误信息包含上下文，指出问题所在和可能的解决方案
- 首次运行引导式配置

### 4.4 可观测性

- 每轮循环输出当前状态（轮次、反馈摘要）
- 所有 LLM 调用记录 token 消耗
- 关键操作记录日志（可配置日志级别）
- 最终生成修正报告（几轮修正、每轮变化）

### 4.5 可测试性

- 核心机制可替换为 mock LLM 进行确定性单元测试（硬要求）
- 每个模块独立可测
- 测试覆盖核心路径和边界条件
- 一键测试命令：`pytest` 或 `make test`

### 4.6 CI/CD

- **测试 job**：`unit-test`，每次 push 自动运行 `pytest`
- **构建 job**：`build`，产出 `.whl` 包作为构建产物，验证包可安装
- 最后一次 CI 执行必须为 pass 状态

---

## 5. 系统架构

### 5.1 组件图

```
┌──────────────────────────────────────────────────────────┐
│                        CLI (click)                        │
│                 hatch run / hatch key / hatch config       │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                      AgentLoop                             │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  ContextBuilder  →  LLM Backend  →  ActionParser    │ │
│  │       ↑                                    │         │ │
│  │       │                                    ▼         │ │
│  │  Feedback ◄── FeedbackEngine ◄── ToolDispatcher     │ │
│  │  Summary        (★ Deep)          │                 │ │
│  │                                    ▼                 │ │
│  │                            GuardrailChain            │ │
│  │                                    │                 │ │
│  │                              ┌─────┴─────┐          │ │
│  │                              ▼           ▼          │ │
│  │                         Approved    HITL Prompt      │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Tools       │  │  Memory      │  │  Config       │
│  FileReader   │  │  SessionMem  │  │  hatch.yaml   │
│  FileWriter   │  │  PersistJSON │  │  Validator    │
│  ShellExec    │  └──────────────┘  └──────────────┘
│  TestRunner   │
│  Linter       │
│  TypeChecker  │
└──────────────┘
```

### 5.2 数据流（一轮循环）

```
User Input
    │
    ▼
ContextBuilder ──► [System Prompt + Memory + Task + Last Feedback]
    │
    ▼
LLM Backend ──► "I will: 1. read app.py, 2. modify function foo, 3. run tests"
    │
    ▼
ActionParser ──► [Action(read, "app.py"), Action(write, "app.py", new_content), Action(shell, "pytest")]
    │
    ▼
GuardrailChain ──► Check each action → 1 pass, 1 pass, 1 pass
    │
    ▼
ToolDispatcher ──► Execute each action, collect results
    │
    ▼
FeedbackEngine ──► Parse test output: 2 passed, 1 failed (AssertionError)
    │                Classify: LOGIC_ERROR, priority 3
    │                Generate: feedback summary for next round
    │
    ▼
StopCheck ──► Not all tests pass, round 1/3 → continue
    │
    ▼
ContextBuilder (next round) ← Feedback injected as context
```

### 5.3 外部依赖

| 依赖 | 用途 | 版本 |
|------|------|------|
| Python | 运行环境 | >= 3.10 |
| httpx | HTTP 客户端（调用 LLM API） | >= 0.27 |
| click | CLI 框架 | >= 8.0 |
| pyyaml | 配置文件解析 | >= 6.0 |
| keyring | 跨平台凭据管理 | >= 24.0 |
| pytest | 测试框架（开发依赖） | >= 7.0 |
| flake8 | 代码风格检查（运行依赖） | >= 6.0 |
| mypy | 类型检查（运行依赖） | >= 1.0 |

---

## 6. 数据模型

### 6.1 核心实体

```
Action
  - tool_name: str
  - parameters: dict
  - raw_llm_output: str  # LLM 原始输出（用于调试）

ToolResult
  - success: bool
  - output: str
  - error: str | None
  - exit_code: int | None

TestResult
  - total: int
  - passed: int
  - failed: int
  - errors: list[TestError]

TestError
  - test_name: str
  - error_type: str
  - message: str
  - file_path: str
  - line_number: int | None
  - expected: str | None
  - actual: str | None

LintResult
  - issues: list[LintIssue]

LintIssue
  - file_path: str
  - line: int
  - column: int
  - code: str
  - message: str

TypeCheckResult
  - errors: list[TypeCheckError]

TypeCheckError
  - file_path: str
  - line: int
  - column: int
  - severity: str
  - message: str

ClassifiedFailure
  - category: FailureCategory
  - failures: list[TestError | LintIssue | TypeCheckError]
  - priority: int

FailureCategory (Enum)
  - SYNTAX_ERROR
  - TYPE_ERROR
  - LOGIC_ERROR
  - STYLE_ISSUE
  - RUNTIME_ERROR
  - UNKNOWN

FeedbackSummary
  - success: bool
  - total_issues: int
  - by_category: dict[FailureCategory, int]
  - top_issues: list[ClassifiedFailure]
  - context_for_llm: str
  - round_number: int

GuardrailResult
  - allowed: bool
  - reason: str
  - requires_approval: bool

MemoryEntry
  - key: str
  - value: str
  - timestamp: datetime

LoopState
  - round: int
  - max_rounds: int
  - history: list[FeedbackSummary]
  - status: "running" | "success" | "failed" | "stopped"
```

### 6.2 关系

```
AgentLoop 1 ──── * Round
Round    1 ──── 1 FeedbackSummary
Round    1 ──── * Action
Action   1 ──── 1 ToolResult
FeedbackSummary 1 ──── * ClassifiedFailure
```

---

## 7. 凭据与分发设计

### 7.1 凭据存储方案

- **主方案**：使用 `keyring` 库，自动适配操作系统凭据管理器
  - Windows: Windows Credential Manager
  - macOS: Keychain
  - Linux: Secret Service / kwallet
  - 每个供应商的 key 以 `hatch/<provider>` 为 service_name 独立存储
- **后备方案**：`~/.hatch/.env` 文件（文档说明其明文风险）
- **录入流程**：`hatch key set [--provider <name>]` → 隐藏输入 → 验证 → 存储
- **查看状态**：`hatch key status` → 显示各 provider 状态和 `****-xxxx`（最后 4 位）
- **更新**：`hatch key rotate` → 重新录入
- **清除**：`hatch key clear [--provider <name>]` → 从凭据管理器删除

### 7.2 分发形态

**主选：PyPI 包分发**

```bash
pip install hatch-agent
hatch key set                 # 引导录入 API Key
hatch run "修复 app.py 中的类型错误"
```

**次选：GitHub 直接安装（无需 PyPI 发布）**

```bash
pip install git+https://github.com/<username>/hatch.git
hatch key set
hatch run "修复测试"
```

**本地开发安装**

```bash
git clone https://github.com/<username>/hatch.git
cd hatch
pip install -e .
hatch key set
```

### 7.3 目标平台

- 操作系统：Windows 10+、macOS 12+、Linux（Ubuntu 20.04+）
- Python：>= 3.10
- CPU 架构：x86_64、ARM64（Apple Silicon）

---

## 8. 技术选型与理由

| 技术 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 最熟悉的语言；丰富的生态（httpx、click、keyring）；类型注解支持 |
| LLM 供应商 | DeepSeek / GLM / Claude | 国产模型性价比高、获取方便；Claude 编码能力强；均支持统一的消息格式抽象 |
| LLM 调用方式 | httpx 直接 HTTP 调用 | 各供应商 API 协议统一为 OpenAI 兼容格式，用 httpx 统一调用，避免依赖各供应商 SDK |
| CLI 框架 | Click | 轻量、装饰器式 API、Python 社区标准 |
| 配置格式 | YAML | 可读性好、支持注释、Python 生态成熟 |
| 凭据管理 | keyring | 跨平台、自动适配系统凭据管理器 |
| 测试框架 | pytest | Python 标准测试框架 |
| 代码检查 | flake8 + mypy | Python 社区标准工具 |
| 分发 | PyPI + Git 安装 | PyPI 覆盖标准 Python 用户；Git 安装无需注册 PyPI 账号 |
| 构建工具 | setuptools / hatchling | Python 标准打包 |

---

## 9. 验收标准

### 9.1 核心功能验收

| # | 验收项 | 判定标准 |
|---|--------|---------|
| AC1 | Agent 主循环能运行 | 给定任务，Hatch 能完成至少一轮"读取 → 修改 → 执行"循环 |
| AC2 | Mock LLM 可替换 | 将真实 LLM 后端替换为 `MockLLM`，所有测试仍能通过 |
| AC3 | 反馈闭环工作 | 注入一个会失败的修改，Hatch 检测到测试失败并重新尝试修正 |
| AC4 | 多轮修正 | 设定 `max_rounds=3`，Hatch 在 3 轮内成功修正或正确报告失败 |
| AC5 | 护栏拦截危险命令 | 任务中要求执行 `rm -rf /`，Hatch 拦截并拒绝执行 |
| AC6 | HITL 审批 | 任务中要求执行 `git push --force`，Hatch 暂停等待用户确认 |
| AC7 | 凭据安全 | 日志和终端输出中不出现明文 API Key |
| AC8 | 配置文件生效 | 修改 `hatch.yaml` 中的 `max_rounds`，重启后生效 |
| AC9 | 一键测试 | `pytest` 命令全部通过（或 `make test`），包含 mock LLM 测试 |
| AC10 | CI 通过 | GitHub Actions 中 `unit-test` job 通过，`build` job 成功产出 `.whl` 包 |

### 9.2 机制演示验收（Mock LLM 确定性测试）

| # | 演示项 | 判定标准 |
|---|--------|---------|
| MD1 | 护栏拦截演示 | `GuardrailChain.check(dangerous_action)` 返回 `allowed=False`，无需真实 LLM |
| MD2 | 反馈闭环演示 | 注入一次测试失败，断言 FeedbackEngine 正确解析、分类、生成修正策略 |
| MD3 | 重点维度演示 | 多轮修正循环中，反馈信号正确回灌，第二轮 LLM 收到的上下文中包含第一轮的反馈摘要 |

---

## 10. 领域与机制设计（§A.5 要求）

### 10.1 领域分析：Coding

| 机制 | Coding 领域的具体形态 |
|------|----------------------|
| **动作/工具** | 读写文件、执行 Shell 命令、运行 pytest、运行 flake8、运行 mypy |
| **客观反馈信号** | 测试结果（pytest 输出）、代码风格问题（flake8 输出）、类型错误（mypy 输出） |
| **危险动作** | 删除系统文件（`rm -rf /`）、强制推送（`git push --force`）、卸载包、越界读写 |
| **记忆** | 项目约定（测试框架、代码风格偏好）、历史决策（哪些修改已被尝试并失败） |

### 10.2 重点维度：反馈闭环

**选择理由**：
1. 在 Coding 领域，反馈信号天然客观、确定、可编码——测试通过/失败是二值的，lint 规则是固定的，类型检查是算法可判定的
2. 反馈闭环是 harness 区别于"单纯的 LLM 调用"的关键——没有反馈，agent 就是盲目的
3. 作为大一学生，反馈闭环的实现最为直观：解析测试输出 → 分类错误 → 指导修正，每一步都有清晰的输入输出
4. 测试反馈闭环只需 mock LLM 返回预设的响应序列，不依赖网络和真实 LLM，完全符合 §A.4-C 的判定标准

**深入实现要点**：
- 三个解析器（pytest / flake8 / mypy）各自实现完整的输出解析，处理边界格式
- 失败分类器用确定性算法（非 LLM）完成分类和优先级排序
- 修正策略选择器为每种失败类别生成不同的反馈提示
- 死循环检测：连续 2 轮反馈相同时切换策略
- 多轮修正追踪：每轮反馈摘要可追溯

### 10.3 机制编码实现方式

| 机制 | 如何编码（非提示词） |
|------|---------------------|
| 反馈信号 | 正则解析器 + 分类算法，纯 Python 代码，输入字符串 → 输出结构化数据 |
| 危险动作拦截 | 规则引擎，匹配命令模式 → 返回拦截决策，不依赖 LLM 判断 |
| HITL | 状态机：`pending → waiting_for_user → approved/denied → timeout`，纯代码逻辑 |
| 死循环检测 | 比较连续轮次的 FeedbackSummary，相同则触发策略切换 |

---

## 11. 风险与未决问题

| # | 风险 | 影响 | 缓解措施 |
|---|------|------|---------|
| R1 | LLM 输出格式不稳定，ActionParser 无法解析 | 循环中断 | 解析失败时把错误信息回灌 LLM 要求重试；最多 3 次 |
| R2 | pytest/flake8/mypy 输出格式随版本变化 | 解析器失效 | 解析器支持多版本格式；兜底：无法解析时标记为 UNKNOWN 类别 |
| R3 | LLM API 调用成本 | 开发期间费用高 | Mock LLM 模式下开发核心逻辑；真实 LLM 仅用于集成测试；DeepSeek/GLM 国产模型价格低，适合开发调试 |
| R4 | 大一水平对异步编程不熟悉 | 开发进度慢 | 使用 httpx 同步调用 + 简单循环，避免 async/await 复杂性 |
| R5 | 凭据管理器在不同 Linux 发行版行为不一致 | keyring 存储失败 | 提供 `.env` 后备方案，文档说明风险 |
| R6 | 多轮修正陷入无限循环 | 消耗 token 和时间 | `max_rounds` 硬限制 + 死循环检测 |
| R7 | 不同 LLM 供应商响应格式差异 | ActionParser 解析不稳定 | 统一要求 LLM 输出特定格式（如 JSON 包裹的工具调用）；解析失败时回灌错误信息重试 |

---

## 附录 A：项目目录结构

```
hatch/
├── hatch/
│   ├── __init__.py
│   ├── cli.py                  # CLI 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── loop.py             # AgentLoop 主循环
│   │   ├── llm.py              # LLMBackend 抽象 + MockLLM + DeepSeekLLM + GLMLLM + ClaudeLLM
│   │   ├── parser.py           # ActionParser（LLM 输出 → Action 列表）
│   │   └── context.py          # ContextBuilder（组装上下文）
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py             # Tool 抽象基类 + ToolResult
│   │   ├── file_reader.py
│   │   ├── file_writer.py
│   │   ├── shell_executor.py
│   │   ├── test_runner.py
│   │   ├── linter.py
│   │   ├── type_checker.py
│   │   └── registry.py         # ToolRegistry（工具注册与分发）
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── chain.py            # GuardrailChain
│   │   ├── rules.py            # 内置规则
│   │   └── hitl.py             # HITL 审批交互
│   ├── feedback/
│   │   ├── __init__.py
│   │   ├── engine.py           # FeedbackEngine 主入口
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── test_parser.py      # pytest 输出解析
│   │   │   ├── lint_parser.py      # flake8 输出解析
│   │   │   └── type_parser.py      # mypy 输出解析
│   │   ├── classifier.py       # FailureClassifier
│   │   ├── strategies.py       # CorrectionStrategySelector
│   │   └── aggregator.py       # FeedbackAggregator
│   ├── memory/
│   │   ├── __init__.py
│   │   └── session.py          # SessionMemory
│   ├── config/
│   │   ├── __init__.py
│   │   └── loader.py           # 配置加载与校验
│   └── security/
│       ├── __init__.py
│       └── key_manager.py      # 凭据管理（keyring + .env 后备）
├── tests/
│   ├── __init__.py
│   ├── test_loop.py            # 主循环测试（mock LLM）
│   ├── test_llm.py             # LLM 抽象层测试
│   ├── test_parser.py          # ActionParser 测试
│   ├── test_tools.py           # 工具系统测试
│   ├── test_guardrails.py      # 护栏测试（mock LLM）
│   ├── test_feedback_parser.py # 反馈解析器测试（确定性）
│   ├── test_feedback_classifier.py  # 失败分类器测试
│   ├── test_feedback_loop.py   # 反馈闭环集成测试（mock LLM）
│   ├── test_memory.py
│   ├── test_config.py
│   ├── test_security.py
│   └── fixtures/               # 测试 fixtures
│       ├── sample_pytest_output.txt
│       ├── sample_flake8_output.txt
│       ├── sample_mypy_output.txt
│       └── sample_project/     # 用于集成测试的迷你项目
├── hatch.yaml                  # 默认配置文件
├── pyproject.toml              # 项目元数据与依赖
├── Makefile                    # 一键命令（make test / make build）
├── .gitlab-ci.yml
├── .gitignore
├── README.md
└── LICENSE
```

---

## 附录 B：CLI 命令设计

```bash
# 核心命令
hatch run "<任务描述>"              # 运行 agent 执行任务
hatch run -f task.txt              # 从文件读取任务

# 凭据管理
hatch key set                        # 录入/更新当前 provider 的 API Key
hatch key set --provider glm         # 为指定供应商录入 key
hatch key status                     # 查看凭据状态
hatch key clear                      # 清除凭据
hatch key clear --provider deepseek  # 清除指定供应商的凭据

# 配置
hatch config show                  # 显示当前配置
hatch config validate              # 验证配置文件

# 工具
hatch --version                    # 显示版本
hatch --help                       # 帮助
```