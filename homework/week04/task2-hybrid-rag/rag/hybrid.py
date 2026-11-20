"""混合检索模块：BM25 关键词检索（jieba + BM25Okapi）+ 向量检索 + RRF 倒数排名融合。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Sequence

import jieba
from llama_index.core.schema import NodeWithScore, TextNode
from rank_bm25 import BM25Okapi

from .config import DEFAULT_CANDIDATE_K, DEFAULT_TOP_K, RRF_K

jieba.setLogLevel(60)


def tokenize(text: str) -> List[str]:
    """中文使用 jieba 分词，英文与代码符号保留小写 token。"""
    return [tok for tok in jieba.lcut(text.lower()) if tok.strip()]


class BM25Retriever:
    """基于同一批 LlamaIndex TextNode 构建的 BM25 关键词检索器。"""

    def __init__(self, nodes: Sequence[TextNode]):
        self.nodes = list(nodes)
        self.corpus = [tokenize(f"{n.metadata.get('file_path', '')} {n.metadata.get('heading', '')}\n{n.text}") for n in self.nodes]
        self.bm25 = BM25Okapi(self.corpus) if self.corpus else None

    def retrieve(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[NodeWithScore]:
        if not self.nodes or self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: (scores[i], -i), reverse=True)[:top_k]
        return [NodeWithScore(node=self.nodes[i], score=float(scores[i])) for i in order]


def save_bm25_nodes(nodes: Sequence[TextNode], path: Path) -> None:
    """以可读 JSON 格式落盘 BM25 节点，确保与向量索引共享相同 node_id 与元数据。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "node_id": n.node_id,
            "ref_doc_id": n.ref_doc_id,
            "text": n.text,
            "metadata": n.metadata,
        }
        for n in nodes
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_bm25_nodes(path: Path) -> List[TextNode]:
    """从 JSON 读取 BM25 节点并还原为 TextNode 列表。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes: List[TextNode] = []
    for item in raw:
        node = TextNode(
            id_=item["node_id"],
            text=item["text"],
            metadata=item.get("metadata", {}),
        )
        nodes.append(node)
    return nodes


def rrf_fuse(
    result_lists: Iterable[Sequence[NodeWithScore]],
    top_k: int = DEFAULT_TOP_K,
    k: int = RRF_K,
    weights: Sequence[float] | None = None,
) -> List[NodeWithScore]:
    """Reciprocal Rank Fusion：score = Σ weight / (k + rank)，rank 从 1 开始。"""
    lists = list(result_lists)
    if weights is None:
        weights = [1.0] * len(lists)
    fused: dict[str, float] = {}
    keep: dict[str, TextNode] = {}
    for weight, results in zip(weights, lists):
        for rank, item in enumerate(results, 1):
            nid = item.node.node_id
            fused[nid] = fused.get(nid, 0.0) + weight / (k + rank)
            keep.setdefault(nid, item.node)
    order = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [NodeWithScore(node=keep[nid], score=score) for nid, score in order]


def vector_retrieve(index, query: str, top_k: int = DEFAULT_TOP_K) -> List[NodeWithScore]:
    return index.as_retriever(similarity_top_k=top_k).retrieve(query)


def hybrid_retrieve(
    index,
    bm25: BM25Retriever,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    rrf_k: int = RRF_K,
    weights: Sequence[float] | None = None,
) -> List[NodeWithScore]:
    """向量检索 + BM25 检索分别召回 candidate_k 条，经 RRF 融合输出 top_k。"""
    vec_hits = vector_retrieve(index, query, top_k=candidate_k)
    bm25_hits = bm25.retrieve(query, top_k=candidate_k)
    return rrf_fuse([vec_hits, bm25_hits], top_k=top_k, k=rrf_k, weights=weights)
