#!/usr/bin/env python3
"""步骤 2：查询对比（Vector / BM25 / RRF 混合检索各自 Top-5 + 真实模型生成带来源引用回答）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from llama_index.core.schema import NodeWithScore

from rag.answer import build_prompt, check_citations, format_citations, source_label
from rag.config import DEFAULT_CANDIDATE_K, DEFAULT_QUESTION, DEFAULT_STORAGE_DIR, DEFAULT_TOP_K, RRF_K
from rag.hybrid import hybrid_retrieve, vector_retrieve
from rag.llm import call_llm, resolve_llm_config
from rag.store import load_stores


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
) -> dict:
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

    return {
        "question": question,
        "storage_dir": str(storage_dir.resolve()),
        "mode": mode,
        "top_k": top_k,
        "retrieval": {name: format_citations(hits) for name, hits in results.items()},
        "evidence_for_llm": format_citations(evidence_hits),
        "llm_status": llm_status,
        "llm": llm_info,
        "answer": answer_text,
        "citation_check": citation_check,
        "prompt": prompt,
        "_hits": results,
    }


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

    out = run_query(
        storage_dir=args.storage,
        question=args.question,
        mode=args.mode,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        no_llm=args.no_llm,
    )
    hits_map = out.pop("_hits")

    if args.require_llm and out["llm_status"] != "real_llm_called":
        print(
            "错误：--require-llm 已开启，但未配置大模型 API Key（支持 DEEPSEEK_API_KEY / MINIMAX_API_KEY / OPENAI_API_KEY / LLM_API_KEY）。",
            file=sys.stderr,
        )
        return 2

    if args.as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print(f"步骤 2：查询对比与带来源回答 | 问题：{args.question}")
    print("=" * 72)
    if "vector" in hits_map:
        print_hits("1) 向量检索 (BGE-small-zh-v1.5)", hits_map["vector"])
    if "bm25" in hits_map:
        print_hits("2) 关键词检索 (BM25 + jieba)", hits_map["bm25"])
    if "hybrid" in hits_map:
        print_hits(f"3) RRF 混合检索 (k={RRF_K})", hits_map["hybrid"])

    print("\n" + "=" * 72)
    print("基于 RRF 混合检索证据生成带来源引用的回答")
    print("=" * 72)
    if out["llm_status"] == "real_llm_called":
        print(f"调用模型: {out['llm']['provider']} / {out['llm']['model']}")
        print("\n【模型回答】")
        print(out["answer"])
        chk = out["citation_check"]
        print(
            f"\n【引用一致性校验】: {'PASS' if chk['valid'] else 'WARN'} "
            f"(引用编号={chk['cited_indices']}, 越界编号={chk['invalid_indices']})"
        )
    else:
        reason = "已指定 --no-llm" if out["llm_status"] == "skipped_by_flag" else "当前环境未配置大模型 API Key"
        print(f"提示：{reason}，跳过在线大模型调用。")
        print("配置 DEEPSEEK_API_KEY / MINIMAX_API_KEY / OPENAI_API_KEY 后重新执行即可调用真实模型生成回答。")

    print("\n【引用来源清单（与 [编号] 一一对应）】")
    for item in out["evidence_for_llm"]:
        print(f"  [{item['index']}] {item['source']} (score={item['score']:.6f})")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
