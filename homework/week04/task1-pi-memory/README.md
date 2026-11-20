# 第一题：为 pi 增加项目长期记忆

基于 OKF v0.2（Markdown + YAML Frontmatter + `index.md` + `log.md`）为 `@mariozechner/pi-coding-agent` 实现按项目隔离的持久化长期记忆扩展，不依赖向量数据库。

## 核心能力

- **项目隔离持久化**：按项目规范路径生成 `projectKey`（可通过 `PI_MEMORY_PROJECT_ID` / `PI_MEMORY_ROOT` 覆盖），每个项目独立存储在 `<storageRoot>/<projectKey>/` 下，互不串扰。
- **完整四个动作（暴露为真实 `pi` 工具与 CLI）**：
  1. `project_memory_write`：写入 OKF 记忆文件并同步更新 `index.md` 与 `log.md`，返回真实磁盘路径。
  2. `project_memory_search` / `project_memory_read`：按当前项目查找并读取记忆，默认核对 `sources` 中文件路径在当前工作区是否存在（`EXISTS` / `MISSING`）。
  3. `project_memory_update`：项目变更并验证后更新原记录，递增 `revision` 并在 `log.md` 记录变更原因与证据。
  4. `project_memory_delete`：移除活动记忆、更新 `index.md` 并在 `log.md` 留痕。
- **跨会话自动感知**：通过 `pi.on("before_agent_start")` 在新会话启动时向系统提示词注入当前项目记忆目录与核对规则，并提供 `/memory-list` 与 `/memory-validate` 斜杠命令。
- **安全边界**：严格拒绝 `..`、绝对路径、保留名 `index` / `log` 等路径穿越输入。

## 安装与运行

```bash
npm install
npm run typecheck
npm test                  # 5 项测试（含真实 pi DefaultResourceLoader 原生加载校验）
bash scripts/run_all.sh   # 跨独立子进程执行步骤 1~3 并生成 3 张截图
```

### 在真实 `pi` 中加载并使用

```bash
# 方式 1：进入 login_demo 交互式启动 pi 并挂载扩展
cd login_demo
../node_modules/.bin/pi -e ../extensions/project-memory.ts

# 方式 2：配置大模型 Key 后一键跑完 3 个独立 pi 会话
export DEEPSEEK_API_KEY="sk-..."   # 或 OPENAI_API_KEY / ANTHROPIC_API_KEY
bash scripts/run_pi_with_llm.sh
```

## 验证证据与截图

- [step1_write.png](./screenshots/step1_write.png)（步骤 1：写入持久化存储并返回实际保存路径）
- [step2_new_session_read.png](./screenshots/step2_new_session_read.png)（步骤 2：全新进程跨会话查找并核对文件存在性）
- [step3_migrate_update.png](./screenshots/step3_migrate_update.png)（步骤 3：迁移测试至 `tests/auth/test_session.py`、同步修改 `docs/testing-guide.md`、实测 `pytest` 全绿并更新原记忆至 `rev 2` + 验证删除动作）
