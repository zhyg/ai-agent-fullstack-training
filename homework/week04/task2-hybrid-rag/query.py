#!/usr/bin/env python3
"""步骤 2：查询对比（Vector / BM25 / RRF 混合检索各自 Top-5 + 真实模型生成带来源引用回答）。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from llama_index.core.schema import NodeWithScore

from rag.answer import (
    build_prompt,
    check_citations,
    format_citations,
    print_llm_answer_section,
    source_label,
)
from rag.config import DEFAULT_CANDIDATE_K, DEFAULT_QUESTION, DEFAULT_STORAGE_DIR, DEFAULT_TOP_K, RRF_K
from rag.hybrid import hybrid_retrieve, vector_retrieve
from rag.llm import call_llm, resolve_llm_config
from rag.store import load_stores


@dataclass
class QueryResult:
    """结构化检索与问答结果（显式区分可序列化字段与原始命中节点）。"""

    question: str
    storage_dir: str
    mode: str
    top_k: int
    retrieval: Dict[str, List[dict]]
    evidence_for_llm: List[dict]
    llm_status: str
    llm: Optional[dict]
    answer: Optional[str]
    citation_check: Optional[dict]
    prompt: str
    hits_by_mode: Dict[str, List[NodeWithScore]]

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "storage_dir": self.storage_dir,
            "mode": self.mode,
            "top_k": self.top_k,
            "retrieval": self.retrieval,
            "evidence_for_llm": self.evidence_for_llm,
            "llm_status": self.llm_status,
            "llm": self.llm,
            "answer": self.answer,
            "citation_check": self.citation_check,
            "prompt": self.prompt,
        }


def print_hits(title: str, hits: List[NodeWithScore]) -> None:
    print(f"\n--- {title} (Top-{len(hits)}) ---")
    for idx, hit in enumerate(hits, 1):
        excerpt = hit.node.text.strip().replace("\n", " ")
        if len(excerpt) > 100:
            excerpt = excerpt[:100] + "..."
        print(f"  [{idx}] score={hit.score:.6f} | 来源: {source_label(hit)}")
        print(f"      node_id={hit.node.node_id}")
        print(f"      摘录: {excerpt}")


def run_query(
    storage_dir: Path,
    question: str,
    mode: str = "compare",
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    no_llm: bool = False,
) -> QueryResult:
    index, bm25, _ = load_stores(storage_dir)

    results: Dict[str, List[NodeWithScore]] = {}
    if mode in ("vector", "compare"):
        results["vector"] = vector_retrieve(index, question, top_k=top_k)
    if mode in ("bm25", "compare"):
        results["bm25"] = bm25.retrieve(question, top_k=top_k)
    if mode in ("hybrid", "compare"):
        results["hybrid"] = hybrid_retrieve(
            index, bm25, question, top_k=top_k, candidate_k=candidate_k, rrf_k=RRF_K
        )

    evidence_hits = results.get("hybrid") or next(iter(results.values()))
    prompt = build_prompt(question, evidence_hits)
    llm_cfg = None if no_llm else resolve_llm_config()

    answer_text = None
    llm_info = None
    citation_check = None
    llm_status = "skipped_by_flag" if no_llm else "no_api_key"

    if llm_cfg is not None:
        answer_text, used_cfg = call_llm(prompt, config=llm_cfg)
        llm_status = "real_llm_called"
        llm_info = {
            "provider": used_cfg.provider,
            "model": used_cfg.model,
            "base_url": used_cfg.base_url,
        }
        chk = check_citations(answer_text, len(evidence_hits))
        citation_check = {
            "valid": chk.valid,
            "cited_indices": chk.cited_indices,
            "invalid_indices": chk.invalid_indices,
        }

    return QueryResult(
        question=question,
        storage_dir=str(storage_dir.resolve()),
        mode=mode,
        top_k=top_k,
        retrieval={name: format_citations(hits) for name, hits in results.items()},
        evidence_for_llm=format_citations(evidence_hits),
        llm_status=llm_status,
        llm=llm_info,
        answer=answer_text,
        citation_check=citation_check,
        prompt=prompt,
        hits_by_mode=results,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="三路检索对比与带来源引用的 RAG 回答")
    parser.add_argument("-q", "--question", default=DEFAULT_QUESTION, help="查询问题")
    parser.add_argument("--storage", type=Path, default=DEFAULT_STORAGE_DIR, help="索引目录")
    parser.add_argument(
        "--mode",
        choices=["compare", "vector", "bm25", "hybrid"],
        default="compare",
        help="检索模式（默认 compare 同时输出向量、BM25 与 RRF 混合检索）",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="每路返回条数（默认 5）")
    parser.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K, help="RRF 候选召回数")
    parser.add_argument("--no-llm", action="store_true", help="仅做检索与证据装配，不调用外部大模型")
    parser.add_argument("--require-llm", action="store_true", help="强制要求真实模型调用，缺 Key 时非零退出")
    parser.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 格式输出")
    args = parser.parse_args()

    result = run_query(
        storage_dir=args.storage,
        question=args.question,
        mode=args.mode,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        no_llm=args.no_llm,
    )

    if args.require_llm and result.llm_status != "real_llm_called":
        print(
            "错误：--require-llm 已开启，但未配置大模型 API Key（支持 DEEPSEEK_API_KEY / MINIMAX_API_KEY / OPENAI_API_KEY / LLM_API_KEY）。",
            file=sys.stderr,
        )
        return 2

    if args.as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print(f"步骤 2：查询对比与带来源回答 | 问题：{args.question}")
    print("=" * 72)
    if "vector" in result.hits_by_mode:
        print_hits("1) 向量检索 (BGE-small-zh-v1.5)", result.hits_by_mode["vector"])
    if "bm25" in result.hits_by_mode:
        print_hits("2) 关键词检索 (BM25 + jieba)", result.hits_by_mode["bm25"])
    if "hybrid" in result.hits_by_mode:
        print_hits(f"3) RRF 混合检索 (k={RRF_K})", result.hits_by_mode["hybrid"])

    print_llm_answer_section(
        section_title="基于 RRF 混合检索证据生成带来源引用的回答",
        list_title="引用来源清单（与 [编号] 一一对应）",
        llm_status=result.llm_status,
        llm_info=result.llm,
        answer=result.answer,
        citation_check=result.citation_check,
        evidence_for_llm=result.evidence_for_llm,
        show_excerpt=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
