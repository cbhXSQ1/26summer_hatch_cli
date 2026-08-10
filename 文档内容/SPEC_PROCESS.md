# SPEC_PROCESS: Hatch 规约与计划生成过程记录

---

## 1. 协作工具与工作流概览

| 阶段 | 工具 | 说明 |
|------|------|------|
| 规约（brainstorming → writing-plans） | opencode + Superpowers 插件 | 使用 `brainstorming`、`writing-plans` 技能 |
| 冷启动验证（§4.5） | Claude Code | 有意不安装 Superpowers 插件，纯靠 SPEC + PLAN 实现 T0.1–T1.1 |
| 正式实现 | opencode + Superpowers | subagent-driven-development + TDD + code-review |

**时间线**：2026-07-08 选定项目类型 A → SPEC 初稿 → PLAN（31 tasks / 8 Phases）→ Claude 冷启动验证 → SPEC/PLAN 修订 → 正式实现（87 commits，362 测试全绿）→ Phase 9–10 按真实使用反馈迭代（TUI + 工具调用链修复）。

---

## 2. 从模糊想法到 SPEC：brainstorming 关键节点

**最初想法**（一句话）："做一个能自动写代码、还能自己发现自己写错的 agent。"

brainstorming 智能体是 opencode 上的 Superpowers `brainstorming` 技能。它先从"你究竟想做什么"切入，以下是关键问答节选（复刻整理，与最终设计一致）：

> **AI**：那按命题文件你应该选 A 类。六个维度里你想深入哪一个？我的建议是反馈闭环：在 coding 领域，测试通过/失败是二值的，lint 规则是固定的，类型检查是算法可判定的——这些信号天然客观、确定、可编码，是最适合"把机制做成代码"的维度。
>
> **我**：同意，反馈闭环。但我要确认它的判据是机制。
>
> **AI**：对，§A.4-C 的硬标准是：把真实 LLM 换成 mock LLM，机制还能不能跑确定性单测。反馈闭环完全满足：喂一段 pytest 输出，断言解析出的 TestResult 字段正确，每次都成立。

这个追问直接决定了项目形态：**A 类 harness + 反馈闭环深度维度**。SPEC §10.2 记录了选择反馈闭环的四条理由，其中第 3 条（"每一步都有清晰的输入输出，作为大一学生最直观"）正来自这段对话。

brainstorming 继续用"分块呈现 + 逐步签字"的方式确认了各设计块：

| 设计块 | 智能体追问 | 我的决策 | 理由 |
|--------|-----------|---------|------|
| 用户故事 | "开发者到底在哪些场景用你的产品？" | 7 个故事（US1–US7）覆盖核心闭环、多轮停机、护栏、HITL、记忆、配置、凭据七条主线 | 每个故事带可判定验收标准，避免"按回车"式不可测故事 |
| 反馈引擎架构 | "解析器输出怎么变成 LLM 看得懂的修正指令？" | 四段流水线：TestParser/LintParser/TypeParser → FailureClassifier → CorrectionStrategySelector → FeedbackAggregator | 每段有清晰输入输出、可独立单测；分类用确定性算法而非 LLM（§3.2.4 F4） |
| 护栏 | "什么操作必须交人工？什么直接拦？" | 危险命令 block、需审批命令 approve、网络请求 approve、路径越界 block（§3.2.3） | 优先级 block > approve > allowed；规则可正则匹配，纯代码 |
| 凭据 | "API Key 放哪？" | keyring 主方案 + `~/.hatch/.env` 后备 | 自动适配系统凭据管理器；.env 明文风险在文档显式告警（§3.2.7 威胁模型） |
| 分发 | "别人怎么拿到你的项目并跑起来？" | PyPI 主选 + GitHub 直接安装次选 | CLI 项目无 WebUI 需求；包分发是"全新机器从零运行"的最短路径 |
| LLM 调用 | "用三家 SDK 还是统一 HTTP？" | httpx 直接调用，OpenAI 兼容协议统一 | DeepSeek/GLM 均兼容 OpenAI 格式，Claude 单独适配；少两个 SDK 依赖（SPEC §8） |
| 技术栈 | "语言、框架、测试工具？" | Python 3.10+ / click / pyyaml / pytest + flake8 + mypy | 生态成熟、类型注解友好、与课程环境一致 |

---

## 3. 三轮关键迭代节选与处理决策

> 以下三轮迭代覆盖 brainstorming → writing-plans 全程。对话为复刻整理，处理决策与最终 SPEC/PLAN 完全一致。

### 迭代 1：问题陈述聚焦（"修不好"的问题到底出在哪）

> **AI**：现在的 Coding Agent 为什么修不好自己的代码？
>
> **我**：让 LLM 自己检查自己，它可能自信地犯错。
>
> **AI**：这是"缺乏客观判据"。那你的核心命题就是——用客观、确定性信号取代 LLM 的"自觉"。落到 SPEC 里应该是一个可验证的问题陈述，而不是一句口号。
>
> **我**：写清楚：pytest 输出、flake8 输出、mypy 输出就是外部信号；修正过程不依赖 LLM 自觉，依赖可验证事实。

**处理**：SPEC §1.1 按此定型，并明确写出 LLM 三缺陷（自信地犯错 / 缺乏客观判据 / 修正不可预测）。

### 迭代 2：反馈引擎架构细化（机制怎么编码）

> **AI**：pytest 输出是一大段文本，你怎么把"哪个测试挂了、期望值 vs 实际值"变成 LLM 能直接用的信息？
>
> **我**：正则解析出结构化 TestResult，再分类、再生成修正策略文本。
>
> **AI**：分类用什么？如果让 LLM 分类，这机制就算提示词。应该写死一个确定性算法：语法错误优先级最高，必须最先修。
>
> **我**：分类算法写成 6 级 ，SyntaxError → mypy → flake8 → AssertionError → 其他异常 → UNKNOWN，优先级 1–5，全是代码。
>
> **AI**：再加一个兜底：解析不了的输出标记 UNKNOWN，把原文回灌，别让引擎崩溃。

**处理**：全部接受，固化到 SPEC §3.2.4 F1–F8（解析器 → 分类器 6 步算法 → 策略映射 → 聚合器 → 多轮循环 → 历史追踪），边界条件含"反馈引擎自身异常降级为原文回灌"和"连续 2 轮相同反馈触发策略切换"。

### 迭代 3：可测性与验收设计（§A.4-C 的落实）

> **AI**：§A.6 要求提交机制演示：护栏拦截、反馈闭环改变 agent 行为、重点维度确定性行为。这些能不能在 mock LLM 下离线复现？
>
> **我**：能。MockLLM 返回预设响应序列，护栏直接喂构造的 Action("rm -rf /")，反馈引擎喂样本输出文本。
>
> **AI**：那把它们写成可重复运行的脚本，不要只留在测试里。
>
> **我**：三个 demo 脚本 + MD1–MD3 验收项进 SPEC §9.2，任务进 PLAN T8.1–T8.3。
>
> **AI**：还有无限循环风险——多轮修正最多跑几轮？
>
> **我**：max_rounds 硬限制（默认 3，配置可调）+ 死循环检测。

**处理**：SPEC §9.2 增加 MD1–MD3 验收表；PLAN 增加 T8.1–T8.3；风险表加 R6（无限循环缓解：max_rounds + 死循环检测）。

---

## 4. 采纳与推翻的 AI 建议

### 采纳的建议

| 建议 | 采纳理由 |
|------|---------|
| 反馈分类用确定性算法而非 LLM 判断（§3.2.4 F4） | 分类算法可单测、结果可复现，符合 §A.4-C 硬标准 |
| 用户故事全部带验收标准（US1–US7） | 后续实现时每个故事都有客观完成判据 |
| 多轮修正加硬限制 `max_rounds` + 死循环检测（§3.2.4 F8） | 防止 token 无限消耗，对应风险 R6 |
| 凭据状态只显示 `****` + 最后 4 位（§3.2.7） | 可查看状态又不泄露明文 |
| 用 mock LLM 覆盖全部核心机制测试 | 362 个测试全部离线确定性运行 |
| 流式输出用 SSE 而非 WebSocket（实现期，commit `53c71e8`） | OpenAI 兼容的 SSE 更简单，httpx 原生支持，避免引入 websocket 依赖 |
| 解析不了的回灌原文而非崩溃（§3.2.4 F8 边界） | 反馈引擎自身异常降级，保证循环不中断 |

### 推翻或修正的建议

| 建议 | 我的决定 | 为什么 |
|------|---------|--------|
| 用 LangChain/AutoGen 高层循环搭建 agent | 推翻 | §A.4-A 明令禁止寄生成型 agent 框架，主循环必须自己写（`hatch/core/loop.py`） |
| key 输入用 `getpass` 隐藏输入 | 实现期推翻（commit `c2b2b25`） | Windows CMD 下 getpass 无法输入，改用 `click.prompt` 明文显示（API Key 场景无回显需求） |
| 模型默认 `deepseek-reasoner` | 实现期修正（commit `cf5d996`） | 真实使用后更新模型列表，`v4-flash` 替换 reasoner 提升响应质量 |
| SPEC 中 `TypeError` 命名 | 冷启动实现时推翻 | 与 Python 内置异常同名，重命名为 `TypeCheckError`（详见 §5） |

---

## 5. 冷启动验证（§4.5）——关键客观证据

- **验证 agent**：Claude Code（与主开发 opencode 类型不同；全新 session，无任何先前对话与 memory）
- **输入**：仅 `SPEC.md` + `PLAN.md`，不补充口头解释；指定实现 T0.1–T1.1（约 1–2 小时），并要求"遇到不确定即暂停询问，不凭猜测继续"
- **结果**：T0.1、T0.2、T1.1 完成，41 tests passed，与预期基本一致；`response_claude.md` 记录了实现反馈

### 暴露的问题与修订（修订前后关键 diff）

**问题 1：`TypeError` 命名冲突**

- 现象：SPEC §6 定义 `TypeError`，与 Python 内置异常同名，shadowing 导致 `except TypeError` 失效、linter 报 Redeclared
- 判定：SPEC 命名缺陷（不是 agent 读错）
- 修订：数据模型重命名为 `TypeCheckError`；SPEC §3.2.4-F3 与 §6.1 同步更新；影响 `models.py`、类型注解、`ClassifiedFailure.failures` 联合类型、测试类名

**问题 2：`git init` 与初始 commit 步骤遗漏**

- 现象：PLAN T0.1 只写创建目录/文件，未提 `git init`，Claude 在此暂停询问仓库是否已初始化
- 判定：PLAN 缺失步骤
- 修订：PLAN T0.1 补充 `git init` 与验证项 `git log` 有初始 commit

**问题 3：Windows 无 `make` 命令**

- 现象：PLAN T0.2 验证步骤只写 `make test` / `make build`
- 判定：PLAN 未覆盖平台差异
- 修订：PLAN 补充 Windows 替代命令 `python -m pytest` / `python -m build`

**附带发现**：`TestError`/`TestResult` 以 `Test` 开头被 pytest 收集为测试类，产生 PytestCollectionWarning——在 `pyproject.toml` 加 `filterwarnings` 忽略（response_claude.md §5.2）。

### 无歧义、未受阻的部分

项目目录结构（附录 A）、hatch.yaml 配置格式（§3.2.6）、数据模型字段（§6）、依赖版本（§5.3）、CLI 入口命名（附录 B）——这些部分 spec 足够清晰，agent 一次通过，说明 SPEC 整体质量达标。

### 后续对 SPEC/PLAN 的持续修订

- 冷启动后所有 task 验证步骤统一写成"Windows + Linux 双平台可执行"格式
- Phase 9 新增 TUI 交互界面（`hatch chat`）——不在原 PLAN 内，属真实使用需求的扩展，写入 PLAN 的 Phase 9 表（TU.1–TU.12）

---

## 6. 实现期暴露的机制缺陷与修订（测试与真实使用反馈）

> PLAN 之外的持续迭代。Phase 9–10 共 35 个 commit 来自"真实使用 + 测试暴露问题"，这是 spec 流程之外的宝贵反馈源。以下按根因归类（详细 commit 说明见 `进展汇总.md`）。

### 6.1 上下文与记忆缺陷（真实使用暴露）

| Commit | 问题 | 修订 |
|--------|------|------|
| `fe71a6f` | 多步工具调用链"失忆"：每轮只记得上一轮结果，LLM 说"结果未展示"并重复探索 | 观察结果跨轮累积（`observations_text` 每轮拼接而非覆盖） |
| `7066b2a` | 新终端默认继续最新会话逻辑不清，`run` 两次后 LLM 把两条用户消息当成一条 | 重写 SessionManager（去 active_session 文件，用 `get_latest()`）+ 会话历史拼接 |
| `38dd1f4` | run 命令没把 workdir 传给 AgentLoop，LLM 从历史猜目录（曾编造 `D:\project\llm_agent\demo`） | `--cwd` 传递到 AgentLoop + workdir 注入 system prompt |
| `cf5d996` | 对话历史上限 10 影响缓存命中 | 上限 10→50 |

### 6.2 解析器与完成判定缺陷（测试 + 使用暴露）

| Commit | 问题 | 修订 |
|--------|------|------|
| `a7a7524` | Anthropic 风格 `<tool_calls>` 无法解析，整轮作废 | XML 工具调用兜底解析 |
| `651e849` | LLM 返回空 `[]` 时不输出文本 | system prompt 重写：先写文本再放空 JSON |
| `a7ae492` | JSON 解析失败静默成功；纯文本计划（"我先…"）被当成完成 | 解析失败提醒重试；纯文本意图不视为完成 |
| `a7a7524` | 连续 12 轮纯文本空转 | 纯文本 3 轮硬兜底直接 failed |
| `fe71a6f` | 解释性回复（"我接下来会…"）被误判为动作意图，重复解释 | 意图关键词移除弱承诺词 |
| `cf5d996`/`a7a7524` | 长输出截断成半截 JSON | max_tokens=4096 请求体对齐 |

### 6.3 工具与输出质量缺陷（真实使用暴露）

| Commit | 问题 | 修订 |
|--------|------|------|
| `fe71a6f` | shell 输出乱码、^M 行尾 | UTF-8→GBK→latin-1 依次解码 + CRLF→LF 规范化 |
| `a7a7524` | BOM 导致文件读取异常 | file_reader 用 utf-8-sig |
| `a7a7524` | LLM 幻觉工具参数（`working_dir` 就是编出来的） | 工具描述带参数 JSON Schema |
| `a7a7524` | 用户输入 PowerShell 命令（Get-ChildItem）反复失败 | system prompt 声明 Windows cmd.exe 环境 |
| `133a2b1` | `run` 执行两遍 | 删除 CLI 重复代码段 |
| `0102ffb` | 相同命令重复执行 | 重复检测去重提示 |

### 6.4 TUI 交互缺陷（真实使用暴露）

| Commit | 问题 | 修订 |
|--------|------|------|
| `04f6222` | 下拉菜单从未显示 | FloatContainer 包装 |
| `c58aa4a`/`a3a1dea` | 日志滚动方向切换有死区、惰性算法卡住 | scroll_top 锚定 + 切片渲染 |
| `02644aa` | 下拉浮层与文本混排；Esc 响应慢；切窗后滚轮失效 | 全宽不透明背景 + Esc eager + 鼠标模式保活 |
| `90ce81d` | 不可见下拉遮盖可见下拉 | 隐藏时高度归零 |
| `2243ccd` | 工具轮次助手回复丢失，连续 user 消息 | 工具轮也保存 assistant 消息到对话历史 |

### 6.5 教训总结

1. **"机制是代码"要贯彻到运行时细节**：工作目录、shell 环境、输出编码这类"环境事实"不写进上下文，LLM 就会幻觉——workdir 注入、cmd 声明、解码规范化都是同一教训。
2. **完成判定必须收敛**：纯文本意图、空 JSON、XML 格式、解析失败都要有确定的兜底行为，否则循环空转或静默误报成功。
3. **真实使用是最高效的测试**：Phase 10 的问题几乎全部是"跑起来才发现"，它们暴露的是单元测试覆盖不到的集成层面（跨轮状态、平台差异、真实 LLM 行为）。
4. **spec 之外要有反馈渠道**：SPEC/PLAN 覆盖了规约期已知问题，但实现期的反馈源（demo 脚本、真实 run、HATCH_DEBUG 日志）才是 Phase 9–10 修复的依据。

---

## 7. 对 brainstorming 技能的反思

### 做得好的地方

- "你究竟想做什么"的追问迫使我先回答"自我修正为什么不依赖 LLM 自觉"，否则反馈引擎会做成一堆提示词，无法通过 §A.4-C 的 mock 单测判据。
- "分块呈现 + 逐步签字"避免了从头一次性写大文档：每个设计块（故事/机制/凭据/分发）单独确认，7 个用户故事和 7 个设计块都是逐块签字的结果。
- 主动把 §A.4-C 的硬标准翻译成可操作问题（"换成 mock LLM 还能不能跑确定性单测"），这让 SPEC §9.2 的验收项从一开始就可执行。

### 让我不满的地方

- 对话节选冗长：大量问答对是重复确认同一个点，关键决策淹没在长文里，后期回看效率低（本文件整理时不得不做大量裁剪并且使用agent代理完成）。
- brainstorming 对"实现期会出什么问题"帮助有限：Phase 9–10 暴露的 35 个问题（工具链失忆、编码乱码、完成判定不收敛）几乎没有在规约期被预见到——它擅长结构设计，不擅长预测运行时集成问题。

---

## 8. 结论

SPEC/PLAN 决定初步实现质量：冷启动验证暴露的 3 个问题（命名冲突、git 遗漏、make 平台差异）都在早期修复，避免了 8 个 Phase 的返工；"反馈闭环"这一深度维度的规约（§3.2.4）在实现阶段几乎未再改动，证明 brainstorming 阶段的细化投入是值得的。但项目后半程（TUI、工具调用链）的价值几乎全部来自真实使用反馈而非规约——这印证了命题文件的判断：spec 是地图，但地图之外的路（运行时集成问题）只能靠跑起来才知道。
