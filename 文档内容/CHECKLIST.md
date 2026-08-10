# CHECKLIST: Hatch 验收清单

> 对照 SPEC §9 和通用要求 §五，逐项打勾确认。

---

## 一、核心功能验收

| # | 验收项 | 判定标准 | 状态 |
|---|--------|---------|------|
| AC1 | Agent 主循环能运行 | 给定任务，Hatch 完成至少一轮"读取 → 修改 → 执行"循环 | ✅ |
| AC2 | Mock LLM 可替换 | 将真实 LLM 后端替换为 `MockLLM`，所有测试仍能通过 | ✅ |
| AC3 | 反馈闭环工作 | 注入一个会失败的修改，Hatch 检测到测试失败并重新尝试修正 | ✅ |
| AC4 | 多轮修正 | 设定 `max_rounds=3`，Hatch 在 3 轮内成功修正或正确报告失败 | ✅ |
| AC5 | 护栏拦截危险命令 | 任务中要求执行 `rm -rf /`，Hatch 拦截并拒绝执行 | ✅ |
| AC6 | HITL 审批 | 任务中要求执行 `git push --force`，Hatch 暂停等待用户确认 | ✅ |
| AC7 | 凭据安全 | 日志和终端输出中不出现明文 API Key | ✅ |
| AC8 | 配置文件生效 | 修改 `hatch.yaml` 中的 `max_rounds`，重启后生效 | ✅ |
| AC9 | 一键测试 | `pytest` 全部通过，包含 mock LLM 测试 | ✅ 362/362 |
| AC10 | CI 通过 | `unit-test` job 通过，`build` job 产出 `.whl` | ✅ 双平台全绿 |

---

## 二、机制演示验收（Mock LLM 确定性测试）

| # | 演示项 | 判定标准 | 状态 |
|---|--------|---------|------|
| MD1 | 护栏拦截演示 | `GuardrailChain.check(dangerous_action)` 返回 `allowed=False`，无需真实 LLM | ✅ `tests/demo_guardrail.py` |
| MD2 | 反馈闭环演示 | 注入一次测试失败，断言 FeedbackEngine 正确解析、分类、生成修正策略 | ✅ `tests/demo_feedback.py` |
| MD3 | 重点维度演示 | 多轮修正循环中，反馈信号正确回灌，第二轮 LLM 上下文包含第一轮反馈摘要 | ✅ `tests/demo_multiround.py` |

---

## 三、交付物清单（通用要求 §五）

| # | 交付物 | 要求 | 状态 |
|---|--------|------|------|
| D1 | `SPEC.md` | 含 10 个必选章节 + §10 领域与机制设计 | ✅ |
| D2 | `PLAN.md` | 任务粒度足够 subagent 单次完成，含 TDD 验证步骤 | ✅ |
| D3 | `SPEC_PROCESS.md` | 记录 brainstorming 关键节点、冷启动验证结果 | ✅ |
| D4 | 完整源代码 | 含 harness 内核 + mock-LLM 单元测试，规范的 commit/PR 历史 | ✅ 87 commits / 362 tests |
| D5 | 分发产物 | `pyproject.toml` + `Makefile`，README 写清获取/运行/key 配置/已知限制 | ✅ |
| D6 | `README.md` | 项目简介、安装、运行、分发命令、目录结构、安全边界说明 | ✅ |
| D7 | `AGENT_LOG.md` | 按时间顺序记录关键节点，含 subagent 输出片段和人工干预 | ✅ |
| D8 | `.gitlab-ci.yml` | 含 `unit-test` job | ✅ |
| D9 | CI/CD 执行记录 | 最后一次 CI 执行 pass | ✅ GitLab pipeline 双绿（unit-test + build）；GitHub Actions windows/ubuntu 双平台也通过。Pipeline: https://git.nju.edu.cn/cbhXSQ2/26summer/-/pipelines |
| D10 | `REFLECTION.md` | 1500–2500 字反思报告 | ✅ 1900+ 字，本人撰写 |
| D11 | 线上部署 URL（WebUI） | 纯 CLI harness 项目，无 WebUI 接口，此项不适用 | N/A |

---

## 四、额外硬性要求

| # | 要求 | 来源 | 状态 |
|---|------|------|------|
| H1 | 凭据绝不硬编码、不提交 Git | §3.1 | ✅ keyring 存储 + .gitignore |
| H2 | 首次运行引导录入 key | §3.1 | ✅ `hatch key set` 引导录入 |
| H3 | 至少 3 个功能模块 | §3.4 | ✅ 8 个模块（core/tools/guardrails/feedback/memory/tui/config/security） |
| H4 | 使用 Superpowers 框架 | §3.6 | ✅ — opencode 已配置 Superpowers 插件，正式开发全部使用 Superpowers 技能（Claude Code 冷启动验证时偏离，理由见 AGENT_LOG） |
| H5 | TDD 红→绿→重构 | §3.6 | ✅ 每个 task 先写失败测试再实现 |
| H6 | 仓库无真实凭据 | §4.7 | ✅ |
| H7 | 完整 commit 历史 + PR 工作流 | §4.7 | ✅ 87 commits 按 task 拆分 |
| H8 | `PLAN.md` 持续更新（每完成一个 task 标记 commit hash） | §4.7 | ✅ |
| H9 | Harness 主循环自己实现，不寄生框架 | §A.4-A | ✅ `hatch/core/loop.py` 自写 AgentLoop |
| H10 | 机制是代码，不是提示词 | §A.4-B | ✅ 反馈解析器/分类器/护栏均为确定性代码 |
| H11 | 移除真实 LLM 后机制仍可单测验证 | §A.4-C | ✅ 362 测试全部 mock LLM，离线可跑 |
| H12 | 六个维度都有最低实现 + 一个维度深入 | §A.4-D | ✅ 反馈闭环为深入维度（★） |

---

## 五、最终检查

- [x] `.gitignore` 排除 `.env`、`venv/`、`dist/`、`__pycache__/`
- [x] 仓库中不含任何真实 API Key
- [x] `pytest` 全绿（362/362，Windows + Linux）
- [x] CI 最后一次执行 pass（GitLab pipeline + GitHub Actions）
- [x] 所有文档文件已提交