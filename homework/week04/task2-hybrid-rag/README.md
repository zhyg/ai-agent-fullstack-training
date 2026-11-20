# 第二题：基于 LlamaIndex 实现向量与关键词混合检索 RAG

基于 `login_demo` 多格式资料（Markdown / Python / HTML / CSV / PDF），使用 **LlamaIndex + 真实本地 BGE Embedding（`BAAI/bge-small-zh-v1.5`，512 维 ONNX）+ jieba BM25 + RRF 倒数排名融合** 实现双路混合检索、带来源引用回答与同步增量更新。

## 核心设计

1. **同批节点双路建库（[ingest.py](./ingest.py)）**：
   - Markdown 按标题层级分块（`MarkdownNodeParser` + 中英文友好的 `SentenceSplitter`），源码整文件单节点，每个节点分配稳定 `node_id`（`<file_path>::chunk_<i>`）并携带 `file_path`、`heading`、`doc_type`、`content_hash` 元数据。
   - 基于同一批 `TextNode` 同时构建 LlamaIndex `VectorStoreIndex`（`SimpleVectorStore`）与 `BM25Retriever`（`jieba` + `BM25Okapi`），统一落盘到 `storage/` 并生成 `manifest.json`。
2. **三路查询对比与带来源回答（[query.py](./query.py)）**：
   - 对“登录会话的有效期是多少分钟？”同时执行向量检索、BM25 检索与 RRF 混合检索（`k=60`），各输出 Top-5 结果、分数与来源（`file_path § heading`）。
   - 将 RRF 混合检索证据按 `[1]..[5]` 编号装配后交给真实大模型（支持 `DEEPSEEK_API_KEY` / `MINIMAX_API_KEY` / `OPENAI_API_KEY` / `LLM_API_KEY`），并对模型回答中的 `[n]` 引用做一致性校验。
3. **两路索引同步更新验证（[update_verify.py](./update_verify.py)）**：
   - 复制原始资料到 `corpus_updated/`、初始索引到 `storage_updated/`（不污染原始 `corpus/`）。
   - 将登录会话有效期由 `30 分钟` 修改为 `20 分钟`（同步修改 `docs/session-rules.md`、`app/session.py`、`tables/session-matrix.csv`、`docs/faq.md`、`docs/payment-session.md`、`docs/testing-guide.md`）。
   - 通过 `sync_update()` 基于 SHA-256 清单同时从向量库（`docstore` + `vector_store`）与 BM25 节点库中删除变更文件的全部旧节点、插入新节点并落盘，随后校验两路节点数对齐且已更新文件零 `30 分钟` 旧分块残留，最后重查确认结果与引用全部切至 20 分钟新资料。

## 安装与运行

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 运行全量自动化测试（含真实 BGE Embedding 语义、双路对齐、增量更新去旧块、引用校验与 LLM 适配）
.venv/bin/python -m pytest -v

# 一键运行步骤 1~3 并生成 3 张截图（未配置大模型 Key 时输出完整三路检索与证据清单）
bash scripts/run_all.sh

# 配置真实大模型 API Key 后重跑（自动调用真实模型生成带 [n] 引用的回答并更新截图）
cp .env.example .env   # 填入 DEEPSEEK_API_KEY（或 MINIMAX_API_KEY / OPENAI_API_KEY）
bash scripts/run_all.sh --require-llm
```

## 验证证据与截图

- [step1_ingest.png](./screenshots/step1_ingest.png)（步骤 1：建库结果、节点总数、双路同批对齐校验与带来源分块样例）
- [step2_compare_answer.png](./screenshots/step2_compare_answer.png)（步骤 2：向量 / BM25 / RRF 三路 Top-5 对比与引用来源清单）
- [step3_update_verify.png](./screenshots/step3_update_verify.png)（步骤 3：资料副本改为 20 分钟、移除 19 个旧节点并写入 19 个新节点、零旧分块残留校验与重查结果）
