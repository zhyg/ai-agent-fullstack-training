# AI Agent 全栈工程师训练营课程代码

## Navigation

- [Week 01](./course_code/week01/)：从 Agent 全栈工程师能力与首个 Loop 出发，系统学习模型 API、Streaming、Prompt Engineering、Structured Output，并完成可治理的 LLM Gateway。
- [Week 02](./course_code/week02/)：从 Function Calling 与 Tool Use 出发，逐步完成工具协议与安全执行、MCP 接入、Runtime 治理，以及可审计的 Agent 工具基础设施。
- [Week 03](./course_code/week03/)：将 Tool Runtime 接入 pi Agent Loop，实现最大轮数、重复动作与完成条件等循环保护，叠加 Planning 计划层与证据校验；再补齐任务状态机、Checkpoint 与人工审批恢复，划定 pi-sandbox 与 OpenSandbox 执行边界，用 Agent Harness 把准备、修改、验证、异常处理、恢复与交付串成完整闭环；进而以 LangGraph 编排发布审批流水线（分支、并行、中断恢复、带预算循环），并以阶段三项目 project3 组合全部能力，交付可运行、可验证、可恢复的 Codebase Agent。
- [Week 04](./course_code/week04/)：Context Engineering（装配、优先级、预算、压缩与调试报告）与 Working Memory 组织每轮输入，用 OKF 建立可核对来源的跨会话长期记忆，用 LlamaIndex + Milvus 完成 RAG 五步实践（解析分块、混合检索、重排压缩、统一评估），再以 LLM Wiki 治理知识资产；项目四给 Codebase Agent 装上受治理的长期记忆与 RAG 检索。
- [Week 05](./course_code/week05/)：从 Multi-Agent 与 Subagent 的适用边界出发，把子任务写成可验收契约并处理聚合、冲突、串行交接与预算隔离；用 Skill 将审查方法沉淀为可复用能力包，完成订单接口审查、自动选择验证与权限边界设计；以 Agent 评测为主线，建立 Rubric、评测集、隔离运行与证据、程序/模型/人工评分、Trace 归因、版本对比和发布门禁；最终以 Skills + 多 Agent 交付可运行的 Eval Web 平台。
- [Week 06](./course_code/week06/)：从内网模型服务与推理部署出发，用 vLLM、量化、KV Cache 与压测建立容量基线；再以缓存、批处理/有界并发和 LiteLLM 路由降级优化性能与成本，用结构化日志、Langfuse Trace 与 Replay 排查 Agent 偏差，用 Prometheus/Grafana 分层监控业务、Agent、模型与安全指标；最后以发布清单、灰度、回滚和成本治理把能力组合成可部署、可监控、可审计的 Agent 平台。

## Amp Orbs

`.agents/setup` installs the course demos' dependencies for the reusable orb snapshot.
It uses the orb's Node.js (>=22.19) and uv, creates Python 3.11 `.venv` environments
beside each `requirements.txt` or `pyproject.toml` application, and includes available
development requirements. The gateway uses its `uv.lock`; npm projects use their
lockfiles, except the two bug-fix fixtures which have none. Unchanged locked npm
installs are reused when setup runs again on a stale snapshot.

Use each Python demo's `.venv/bin/python` (or activate that environment), and run
npm scripts from the relevant demo directory. The HITL services have their own
`v2/hitl/.venv`. `.agents/resume` does not reinstall dependencies.

Setup does not start demo servers, seed databases, download embedding models, or
configure API credentials. Supply credentials and runtime configuration as described
in each demo's README; do not commit secrets. No external database is required for
installation: the examples use local files, SQLite, or Milvus Lite.

## 作业批改 Skill

仓库内置 Amp skill [`grading-homework`](./.agents/skills/grading-homework/SKILL.md)，用于获取全部未批改作业，并按各周评分标准逐份批改、归档。

### 使用前准备

- 在 Amp 个人 Secrets & Env Vars 中配置 `GEEKBANG_COOKIE`（极客时间登录 Cookie）。不要把 Cookie 发到对话里，也不要提交 `.env`。
- 如需调用真实大模型，在个人 Secrets 中配置 `DEEPSEEK_API_KEY`。离线即可验收的作业不调用模型。
- `hw-guide/<周次>/` 下已有本周评分标准（如 `第二周作业评分标准.md`）及题目附件；反馈格式遵循 `hw-guide/学员作业反馈报告模板与要求.md`。

### 使用方法

在 Amp 线程中说“批改作业”，即批改全部已有评分标准的未批改作业。只批改一周时再给出周次或 article ID，例如：

```text
获取 week02 的作业列表并批改，article=1025885
```

只获取列表、暂不批改时，也可以直接运行脚本。省略参数会按文章拆到对应周目录：

```bash
python .agents/skills/grading-homework/scripts/save_list.py
python .agents/skills/grading-homework/scripts/save_list.py --article-id 1025885
```

### 处理流程

1. **获取列表**：调用 `scripts/get_homework_user_list.py`（默认 `status=0`，排除已批改的 8）。不指定文章时一次取全部作业，再按文章拆成 `homework/<周次>/homework-list<NN>-pending-<时间戳>.{json,md}`。已有列表不会被修改。作业五、作业六尚无评分标准，只列出不批改。
2. **独立批改**：每份提交新开一个 orb，克隆学员 Git 仓库，基于学员代码批改；同时最多运行 5 个。
3. **统一复核**：主线程复核每份评分，保证同类问题在不同学员间扣分一致；必要时要求对应线程修订。
4. **归档**：运行 `scripts/archive.py` 将结果写入 `homework/<周次>/`。
5. **报告**：列出学员、学号、记录号、分数、等级和验收结论。

### 归档规则

同一学员可能多次提交作业，新的批改记录不会覆盖已有记录：

| 情况 | 学员反馈 | 评分附件与证据包 |
| --- | --- | --- |
| 该学号本周首次批改 | `homework/<周次>/<学号>.md` | `attachments/<学号>.md`、`attachments/<学号>-evidence.tar.gz` |
| 该学号本周已有批改 | `homework/<周次>/<学号>-submission<记录号>.md` | `attachments/<学号>-submission<记录号>.md`、`attachments/<学号>-submission<记录号>-evidence.tar.gz` |

- 反馈首行记录 `<!-- submission:<记录号> -->`，已归档的记录号会自动跳过。
- 所有文件以独占方式创建，目标已存在时直接报错，不修改任何已有文件。
- 批改完成后**不会自动提交**；确认结果后，在线程中说“提交并推送”即可。
