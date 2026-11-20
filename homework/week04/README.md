# 第四周作业：项目长期记忆（pi 扩展）与混合检索 RAG（LlamaIndex）

- 作业原题：[AI Agent 全栈工程师训练营-作业四.md](../../hw-guide/week04/AI%20Agent%20%E5%85%A8%E6%A0%88%E5%B7%A5%E7%A8%8B%E5%B8%88%E8%AE%AD%E7%BB%83%E8%90%A5-%E4%BD%9C%E4%B8%9A%E5%9B%9B.md)
- 分支：`agent-week04`（基于 `main` 创建）

## 目录结构

```text
homework/week04/
├── README.md                          # 本说明
├── scripts/
│   └── render_terminal_png.py         # 终端日志 -> 高清 PNG 截图渲染工具
├── task1-pi-memory/                   # 第一题：为 pi 增加项目长期记忆
│   ├── extensions/project-memory.ts   # pi coding agent 扩展（5 个工具 + 2 个命令 + 跨会话提示注入）
│   ├── src/
│   │   ├── types.ts                   # 领域类型定义
│   │   ├── frontmatter.ts             # OKF YAML Frontmatter 编解码
│   │   ├── search.ts                  # 2-gram 检索打分、来源核对与格式化
│   │   ├── memory-store.ts            # OKF v0.2 项目隔离持久化存储（写 / 查读 / 改 / 删 / 校验）
│   │   └── cli.ts                     # 离线跨进程 CLI 入口
│   ├── login_demo/                    # 课程 login_demo 会话源码、测试说明与 pytest 单元测试
│   ├── scripts/run_pi_live.ts         # 真实 pi + 大模型独立会话三步 + 删除动作实跑脚本
│   ├── scripts/run_pi_with_llm.sh     # 一键跑真实 pi（默认 deepseek-v4-flash）并渲染 3 张截图
│   ├── scripts/verify_e2e.ts          # 无 Key 时的离线 CLI 跨进程验证（输出到 runs/cli_offline/）
│   ├── scripts/run_all.sh             # 有 Key 时走真实 pi；无 Key 时走离线 CLI（不覆盖真实 pi 截图）
│   ├── tests/memory-store.test.ts     # 单元与 pi 原生扩展加载集成测试
│   ├── runs/                          # 真实 pi 实测文本日志与 OKF 落盘快照
│   └── screenshots/                   # 3 张终端截图
└── task2-hybrid-rag/                  # 第二题：基于 LlamaIndex 实现向量 + BM25 + RRF 混合检索 RAG
    ├── corpus/                        # 原始 login_demo 资料副本（12 个多格式文件，不被修改）
    ├── rag/                           # docload / embed(BGE) / store(双路同步更新) / hybrid(BM25 持久化+RRF) / answer / llm
    ├── ingest.py                      # 步骤 1：建库（同批节点写向量索引与持久化 BM25 索引 bm25_index.json）
    ├── query.py                       # 步骤 2：三路检索对比 Top-5 + 真实模型带来源回答
    ├── update_verify.py               # 步骤 3：资料副本改 20 分钟 + 同步更新两路索引 + 旧块清零核验与重查
    ├── scripts/run_all.sh             # 一键跑全流程并生成 3 张截图
    ├── tests/test_hybrid_rag.py       # pytest 全量自动化测试
    ├── runs/                          # 实测文本日志
    └── screenshots/                   # 3 张终端截图
```

## 快速验证

### 第一题（Node.js >= 22 + Python pytest）

```bash
cd homework/week04/task1-pi-memory
npm install
npm run typecheck
npm test

# 配置大模型 API Key（默认 deepseek / deepseek-v4-flash），使用真实 pi 跑完独立会话并刷新截图：
export DEEPSEEK_API_KEY="sk-..."
export PI_PROVIDER="deepseek"
export PI_MODEL="deepseek-v4-flash"
bash scripts/run_all.sh

# 无 Key 时执行离线 CLI 验证（输出到 runs/cli_offline/，不会覆盖已提交的真实 pi 截图）：
# bash scripts/run_all.sh --offline-cli
```

### 第二题（Python 3.11 + uv）

```bash
cd homework/week04/task2-hybrid-rag
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest -v

# 配置真实大模型 Key 实跑全流程并刷新截图（强制调用真实模型生成带 [n] 引用回答）：
export DEEPSEEK_API_KEY="sk-..."
export DEEPSEEK_MODEL="deepseek-v4-flash"
bash scripts/run_all.sh --require-llm
```
