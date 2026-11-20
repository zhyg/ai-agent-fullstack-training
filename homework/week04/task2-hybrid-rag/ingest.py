#!/usr/bin/env python3
"""步骤 1：建立索引（读取 login_demo 资料 -> 统一分块 -> 真实 BGE 向量索引 + BM25 索引落盘）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag.answer import source_label
from rag.config import DEFAULT_CORPUS_DIR, DEFAULT_STORAGE_DIR, EMBED_MODEL
from rag.store import bm25_path, build_and_save, manifest_path


def pick_sample_node(nodes):
    """优先挑选登录会话规则的分块作为展示样例。"""
    for node in nodes:
        if node.metadata.get("file_path") == "docs/session-rules.md" and "30" in node.text:
            return node
    return nodes[0] if nodes else None


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 LlamaIndex 向量索引与 BM25 关键词索引")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_DIR, help="资料目录")
    parser.add_argument("--storage", type=Path, default=DEFAULT_STORAGE_DIR, help="索引持久化目录")
    parser.add_argument("--overwrite", action="store_true", default=True, help="覆盖已有索引目录")
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false")
    parser.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 格式输出")
    args = parser.parse_args()

    docs, nodes, index = build_and_save(
        corpus_dir=args.corpus,
        store_dir=args.storage,
        overwrite=args.overwrite,
    )
    vector_ids = set(index.docstore.docs.keys())
    bm25_ids = {n.node_id for n in nodes}
    sample = pick_sample_node(nodes)

    summary = {
        "corpus_dir": str(args.corpus.resolve()),
        "storage_dir": str(args.storage.resolve()),
        "embedding_model": EMBED_MODEL,
        "document_count": len(docs),
        "node_count": len(nodes),
        "vector_node_count": len(vector_ids),
        "bm25_node_count": len(bm25_ids),
        "same_node_batch_aligned": vector_ids == bm25_ids,
        "files_persisted": sorted(p.name for p in args.storage.iterdir()),
        "sample_node": (
            {
                "node_id": sample.node_id,
                "source": source_label(sample),
                "doc_type": sample.metadata.get("doc_type"),
                "file_path": sample.metadata.get("file_path"),
                "heading": sample.metadata.get("heading"),
                "content_hash": sample.metadata.get("content_hash", "")[:12],
                "text": sample.text,
            }
            if sample is not None
            else None
        ),
    }

    if args.as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("步骤 1：建立索引（LlamaIndex 向量索引 + BM25 关键词索引）")
    print("=" * 72)
    print(f"语料目录      : {summary['corpus_dir']}")
    print(f"索引存储目录  : {summary['storage_dir']}")
    print(f"Embedding 模型: {summary['embedding_model']} (真实本地 ONNX 向量)")
    print(f"文档数量      : {summary['document_count']}")
    print(f"分块节点总数  : {summary['node_count']}")
    print(f"向量索引节点数: {summary['vector_node_count']}")
    print(f"BM25 节点数   : {summary['bm25_node_count']}")
    print(f"双路同批对齐  : {'PASS (node_id 集合完全一致)' if summary['same_node_batch_aligned'] else 'FAIL'}")
    print(f"持久化文件    : {', '.join(summary['files_persisted'])}")
    print(f"BM25 索引路径 : {bm25_path(args.storage)}")
    print(f"清单文件路径  : {manifest_path(args.storage)}")
    if sample is not None:
        print("-" * 72)
        print("带来源的分块样例：")
        print(f"  node_id : {sample.node_id}")
        print(f"  来源    : {source_label(sample)}")
        print(f"  类型    : {sample.metadata.get('doc_type')} | hash: {sample.metadata.get('content_hash', '')[:12]}")
        print("  内容    :")
        for line in sample.text.splitlines():
            print(f"    {line}" if line else "")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
