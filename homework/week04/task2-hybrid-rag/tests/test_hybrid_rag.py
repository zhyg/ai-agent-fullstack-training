"""Task 2 自动化测试：统一分块、双路持久化、真实 BGE Embedding、三路对比、增量同步更新清理旧块、引用校验与 LLM 适配。"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from query import run_query
from rag.answer import build_prompt, check_citations
from rag.config import DEFAULT_CORPUS_DIR, DEFAULT_QUESTION
from rag.embed import BGESmallZhEmbedding
from rag.hybrid import BM25Retriever, hybrid_retrieve, rrf_fuse, vector_retrieve
from rag.llm import LLMConfig, call_llm, resolve_llm_config
from rag.store import build_and_save, load_stores, sync_update
from update_verify import apply_ttl_update, verify_no_stale_chunks


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """使用真实本地 BAAI/bge-small-zh-v1.5 建库一次供模块内多个只读测试复用。"""
    tmp = tmp_path_factory.mktemp("rag_base")
    corpus_copy = tmp / "corpus"
    store_dir = tmp / "storage"
    shutil.copytree(DEFAULT_CORPUS_DIR, corpus_copy)
    docs, nodes, index = build_and_save(corpus_copy, store_dir, overwrite=True)
    return corpus_copy, store_dir, docs, nodes, index


def test_real_bge_embedding_dimension_and_semantics() -> None:
    embed = BGESmallZhEmbedding()
    q_vec = embed.get_query_embedding("登录会话的有效期是多少分钟？")
    p_rel = embed.get_text_embedding("管理后台的登录会话有效期为 30 分钟。")
    p_irr = embed.get_text_embedding("今天天气不错，适合去公园散步。")
    assert len(q_vec) == 512
    assert len(p_rel) == 512
    # 余弦点积（BGE 向量已归一化）相关文本必须显著高于无关文本
    dot_rel = sum(a * b for a, b in zip(q_vec, p_rel))
    dot_irr = sum(a * b for a, b in zip(q_vec, p_irr))
    assert dot_rel > dot_irr + 0.15


def test_same_batch_nodes_persisted_and_aligned(built_store) -> None:
    _, store_dir, docs, nodes, index = built_store
    assert len(docs) >= 10
    assert len(nodes) > len(docs)

    loaded_index, bm25, loaded_nodes = load_stores(store_dir)
    vector_ids = set(loaded_index.docstore.docs.keys())
    bm25_ids = {n.node_id for n in loaded_nodes}
    assert vector_ids == bm25_ids
    assert len(bm25.nodes) == len(nodes)
    # 每个节点都带有 file_path 与 heading 来源元数据
    assert all(n.metadata.get("file_path") and n.metadata.get("heading") for n in loaded_nodes)


def test_three_way_retrieval_comparison_returns_top5_with_30min_evidence(built_store) -> None:
    _, store_dir, _, _, _ = built_store
    index, bm25, _ = load_stores(store_dir)

    vec_hits = vector_retrieve(index, DEFAULT_QUESTION, top_k=5)
    bm25_hits = bm25.retrieve(DEFAULT_QUESTION, top_k=5)
    rrf_hits = hybrid_retrieve(index, bm25, DEFAULT_QUESTION, top_k=5)

    assert len(vec_hits) == 5
    assert len(bm25_hits) == 5
    assert len(rrf_hits) == 5

    # 三路检索均应召回登录会话 30 分钟核心规则
    assert any("docs/session-rules.md" == h.node.metadata["file_path"] and "30 分钟" in h.node.text for h in vec_hits)
    assert any("30 分钟" in h.node.text for h in bm25_hits)
    assert rrf_hits[0].node.metadata["file_path"] == "docs/session-rules.md"
    assert "30 分钟" in rrf_hits[0].node.text


def test_sync_update_replaces_old_chunks_in_both_indexes(built_store, tmp_path: Path) -> None:
    base_corpus, base_storage, _, _, _ = built_store
    corpus_copy = tmp_path / "corpus_updated"
    store_copy = tmp_path / "storage_updated"
    shutil.copytree(base_corpus, corpus_copy)
    shutil.copytree(base_storage, store_copy)

    changed_files = apply_ttl_update(corpus_copy)
    assert len(changed_files) == 6
    assert "docs/session-rules.md" in changed_files
    assert "app/session.py" in changed_files

    report = sync_update(corpus_copy, store_copy)
    assert report.aligned is True
    assert set(report.modified_files) == set(changed_files)
    assert len(report.removed_node_ids) > 0
    assert len(report.inserted_node_ids) > 0

    stale = verify_no_stale_chunks(store_copy, changed_files)
    assert stale["passed"] is True
    assert stale["stale_in_vector"] == []
    assert stale["stale_in_bm25"] == []

    # 重新查询同一问题：三路 Top-5 中核心规则已全部变为 20 分钟
    out = run_query(store_copy, DEFAULT_QUESTION, mode="compare", top_k=5, no_llm=True)
    top_hybrid = out["retrieval"]["hybrid"][0]
    assert top_hybrid["file_path"] == "docs/session-rules.md"
    assert "20 分钟" in top_hybrid["excerpt"]
    assert "30 分钟" not in top_hybrid["excerpt"]


def test_citation_consistency_and_llm_adapter(monkeypatch) -> None:
    chk_ok = check_citations("登录会话有效期为 20 分钟 [1]，源码常量同步为 20 * 60 秒 [3]。", evidence_count=5)
    assert chk_ok.valid is True
    assert chk_ok.cited_indices == [1, 3]

    chk_bad = check_citations("有效期 20 分钟 [9]。", evidence_count=5)
    assert chk_bad.valid is False
    assert chk_bad.invalid_indices == [9]

    # 验证环境变量优先级解析
    for var in ("LLM_API_KEY", "DEEPSEEK_API_KEY", "MINIMAX_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
    cfg = resolve_llm_config()
    assert cfg is not None
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-chat"

    # Mock OpenAI client 验证 call_llm 完整调用链
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="登录会话有效期为 30 分钟 [1]。"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("openai.OpenAI", return_value=fake_client):
        ans, used = call_llm("测试提示词", config=LLMConfig("deepseek", "sk-test", "https://api.deepseek.com/v1", "deepseek-chat"))
    assert ans == "登录会话有效期为 30 分钟 [1]。"
    assert used.provider == "deepseek"
