"""混合检索模块：BM25 关键词索引（jieba + BM25Okapi 持久化）+ 向量检索 + RRF 倒数排名融合。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import jieba
from llama_index.core.schema import NodeWithScore, TextNode
from rank_bm25 import BM25Okapi

from .config import DEFAULT_CANDIDATE_K, DEFAULT_TOP_K, RRF_K

jieba.setLogLevel(60)


def tokenize(text: str) -> List[str]:
    """中文使用 jieba 分词，英文与代码符号保留小写 token。"""
    return [tok for tok in jieba.lcut(text.lower()) if tok.strip()]


class BM25Retriever:
    """基于同一批 LlamaIndex TextNode 构建并可完整持久化的 BM25 关键词索引。"""

    def __init__(self, nodes: Sequence[TextNode], *, _bm25: Optional[BM25Okapi] = None):
        self.nodes = list(nodes)
        if _bm25 is not None:
            self.bm25: Optional[BM25Okapi] = _bm25
        else:
            corpus = [
                tokenize(f"{n.metadata.get('file_path', '')} {n.metadata.get('heading', '')}\n{n.text}")
                for n in self.nodes
            ]
            self.bm25 = BM25Okapi(corpus) if corpus else None

    def retrieve(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[NodeWithScore]:
        if not self.nodes or self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: (scores[i], -i), reverse=True)[:top_k]
        return [NodeWithScore(node=self.nodes[i], score=float(scores[i])) for i in order]

    def save(self, path: Path) -> None:
        """将已构建的 BM25 倒排词频统计（idf / doc_freqs / doc_len / avgdl）与节点一并持久化。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        index_state = None
        if self.bm25 is not None:
            index_state = {
                "k1": self.bm25.k1,
                "b": self.bm25.b,
                "epsilon": self.bm25.epsilon,
                "corpus_size": self.bm25.corpus_size,
                "avgdl": self.bm25.avgdl,
                "average_idf": self.bm25.average_idf,
                "doc_len": list(self.bm25.doc_len),
                "idf": dict(self.bm25.idf),
                "doc_freqs": [dict(freq) for freq in self.bm25.doc_freqs],
            }
        payload = {
            "version": 1,
            "bm25_index": index_state,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "ref_doc_id": n.ref_doc_id,
                    "text": n.text,
                    "metadata": n.metadata,
                }
                for n in self.nodes
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BM25Retriever":
        """从持久化文件直接恢复 BM25Okapi 索引状态，无需加载时重新分词建库。"""
        raw = json.loads(path.read_text(encoding="utf-8"))
        nodes = [
            TextNode(
                id_=item["node_id"],
                text=item["text"],
                metadata=item.get("metadata", {}),
            )
            for item in raw.get("nodes", [])
        ]
        state = raw.get("bm25_index")
        if not nodes or state is None:
            return cls(nodes)

        bm25 = BM25Okapi.__new__(BM25Okapi)
        bm25.k1 = float(state["k1"])
        bm25.b = float(state["b"])
        bm25.epsilon = float(state["epsilon"])
        bm25.tokenizer = None
        bm25.corpus_size = int(state["corpus_size"])
        bm25.avgdl = float(state["avgdl"])
        bm25.average_idf = float(state["average_idf"])
        bm25.doc_len = [int(x) for x in state["doc_len"]]
        bm25.idf = {str(k): float(v) for k, v in state["idf"].items()}
        bm25.doc_freqs = [{str(k): int(v) for k, v in doc.items()} for doc in state["doc_freqs"]]
        return cls(nodes, _bm25=bm25)


def rrf_fuse(
    result_lists: Iterable[Sequence[NodeWithScore]],
    top_k: int = DEFAULT_TOP_K,
    k: int = RRF_K,
) -> List[NodeWithScore]:
    """Reciprocal Rank Fusion：score = Σ 1 / (k + rank)，rank 从 1 开始。"""
    fused: dict[str, float] = {}
    keep: dict[str, TextNode] = {}
    for results in result_lists:
        for rank, item in enumerate(results, 1):
            nid = item.node.node_id
            fused[nid] = fused.get(nid, 0.0) + 1.0 / (k + rank)
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
) -> List[NodeWithScore]:
    """向量检索 + BM25 检索分别召回 candidate_k 条，经 RRF 融合输出 top_k。"""
    vec_hits = vector_retrieve(index, query, top_k=candidate_k)
    bm25_hits = bm25.retrieve(query, top_k=candidate_k)
    return rrf_fuse([vec_hits, bm25_hits], top_k=top_k, k=rrf_k)
