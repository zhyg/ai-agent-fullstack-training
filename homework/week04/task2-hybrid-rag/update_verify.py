#!/usr/bin/env python3
"""步骤 3：更新验证（在资料副本中将登录会话有效期改为 20 分钟 -> 同步更新向量与 BM25 索引 -> 验证旧分块退出并重查）。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

from query import print_hits, run_query
from rag.answer import print_llm_answer_section
from rag.config import (
    DEFAULT_CORPUS_DIR,
    DEFAULT_QUESTION,
    DEFAULT_STORAGE_DIR,
    DEFAULT_TOP_K,
    DEFAULT_UPDATED_CORPUS_DIR,
    DEFAULT_UPDATED_STORAGE_DIR,
    RRF_K,
)
from rag.store import build_and_save, check_stale_chunks, sync_update

# 将当前登录会话有效期由 30 分钟调整为 20 分钟的定点替换规则（保留记住我 30 天与历史文档原样）
REPLACEMENTS: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "docs/session-rules.md",
        [
            ("updated: 2026-10-01", "updated: 2026-11-20"),
            ("管理后台的登录会话有效期为 30 分钟。", "管理后台的登录会话有效期为 20 分钟。"),
            ("从签发时刻开始计算，30 分钟后到期。", "从签发时刻开始计算，20 分钟后到期。"),
            ("新的到期时间 = 请求到达时刻 + 30 分钟。", "新的到期时间 = 请求到达时刻 + 20 分钟。"),
        ],
    ),
    (
        "app/session.py",
        [
            ("SESSION_TTL_SECONDS = 30 * 60", "SESSION_TTL_SECONDS = 20 * 60"),
        ],
    ),
    (
        "tables/session-matrix.csv",
        [
            ("login_demo,登录会话,30 分钟,", "login_demo,登录会话,20 分钟,"),
        ],
    ),
    (
        "docs/faq.md",
        [
            ("先确认会话有效期配置是否被改过，默认 30 分钟。", "先确认会话有效期配置是否被改过，默认 20 分钟。"),
        ],
    ),
    (
        "docs/payment-session.md",
        [
            ("登录会话 30 分钟、可续期；", "登录会话 20 分钟、可续期；"),
        ],
    ),
    (
        "docs/testing-guide.md",
        [
            ("覆盖续期后到期时间被推后 30 分钟。", "覆盖续期后到期时间被推后 20 分钟。"),
        ],
    ),
]


def apply_ttl_update(corpus_copy: Path) -> List[str]:
    """在资料副本上将登录会话有效期改为 20 分钟，返回已修改的相对路径列表。"""
    changed: List[str] = []
    for rel, pairs in REPLACEMENTS:
        target = corpus_copy / rel
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        updated = text
        for old, new in pairs:
            if old not in updated:
                raise RuntimeError(f"未在 {rel} 中找到预期文本：{old!r}")
            updated = updated.replace(old, new)
        if updated != text:
            target.write_text(updated, encoding="utf-8")
            changed.append(rel)
    return changed


def verify_no_stale_chunks(storage_dir: Path, updated_files: List[str]) -> dict:
    """委托 rag.store 校验两路索引中已更新文件均已彻底清除旧的 30 分钟内容。"""
    return check_stale_chunks(storage_dir, updated_files, stale_terms=("30 分钟", "30 * 60"))


def main() -> int:
    parser = argparse.ArgumentParser(description="在资料副本中更新登录会话有效期至 20 分钟并验证两路索引同步更新")
    parser.add_argument("--source-corpus", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--source-storage", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--updated-corpus", type=Path, default=DEFAULT_UPDATED_CORPUS_DIR)
    parser.add_argument("--updated-storage", type=Path, default=DEFAULT_UPDATED_STORAGE_DIR)
    parser.add_argument("-q", "--question", default=DEFAULT_QUESTION)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--require-llm", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    # 若源索引尚未建立，先自动建库
    if not (args.source_storage / "manifest.json").exists():
        build_and_save(args.source_corpus, args.source_storage, overwrite=True)

    # 1. 复制原始资料与初始索引到副本目录（绝不污染原目录）
    if args.updated_corpus.exists():
        shutil.rmtree(args.updated_corpus)
    shutil.copytree(args.source_corpus, args.updated_corpus)

    if args.updated_storage.exists():
        shutil.rmtree(args.updated_storage)
    shutil.copytree(args.source_storage, args.updated_storage)

    # 2. 在资料副本中将登录会话有效期改为 20 分钟
    changed_files = apply_ttl_update(args.updated_corpus)

    # 3. 增量同步更新两路索引（删除旧块 + 插入新块 + 持久化）
    report = sync_update(args.updated_corpus, args.updated_storage)

    # 4. 校验两路索引均无残留旧分块且完全对齐
    stale_check = verify_no_stale_chunks(args.updated_storage, changed_files)

    # 5. 重新查询同一问题
    query_result = run_query(
        storage_dir=args.updated_storage,
        question=args.question,
        mode="compare",
        top_k=args.top_k,
        no_llm=args.no_llm,
    )

    if args.require_llm and query_result.llm_status != "real_llm_called":
        print(
            "错误：--require-llm 已开启，但未配置大模型 API Key。",
            file=sys.stderr,
        )
        return 2

    payload = {
        "updated_corpus_dir": str(args.updated_corpus.resolve()),
        "updated_storage_dir": str(args.updated_storage.resolve()),
        "changed_files": changed_files,
        "sync_report": {
            "added_files": report.added_files,
            "modified_files": report.modified_files,
            "deleted_files": report.deleted_files,
            "removed_node_count": len(report.removed_node_ids),
            "inserted_node_count": len(report.inserted_node_ids),
            "total_vector_nodes": report.total_vector_nodes,
            "total_bm25_nodes": report.total_bm25_nodes,
            "aligned": report.aligned,
        },
        "stale_check": stale_check,
        "query_result": query_result.to_dict(),
    }

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("步骤 3：更新验证（登录会话有效期 30 分钟 -> 20 分钟，同步更新两路索引）")
    print("=" * 72)
    print(f"资料副本目录  : {payload['updated_corpus_dir']}")
    print(f"更新后索引目录: {payload['updated_storage_dir']}")
    print(f"变更文件 ({len(changed_files)}): {', '.join(changed_files)}")
    print(f"移除旧节点数  : {len(report.removed_node_ids)}")
    print(f"写入新节点数  : {len(report.inserted_node_ids)}")
    print(
        f"索引节点对齐  : vector={report.total_vector_nodes}, bm25={report.total_bm25_nodes} "
        f"({'PASS' if report.aligned else 'FAIL'})"
    )
    print(
        f"旧分块清理核验: {'PASS (两路索引中已更新文件均无 30 分钟旧分块残留)' if stale_check['passed'] else 'FAIL'}"
    )

    print_hits("更新后 1) 向量检索 (BGE-small-zh-v1.5)", query_result.hits_by_mode["vector"])
    print_hits("更新后 2) 关键词检索 (BM25 + jieba)", query_result.hits_by_mode["bm25"])
    print_hits(f"更新后 3) RRF 混合检索 (k={RRF_K})", query_result.hits_by_mode["hybrid"])

    print_llm_answer_section(
        section_title="更新后的回答与引用核验",
        list_title="更新后引用来源清单（与 [编号] 一一对应）",
        llm_status=query_result.llm_status,
        llm_info=query_result.llm,
        answer=query_result.answer,
        citation_check=query_result.citation_check,
        evidence_for_llm=query_result.evidence_for_llm,
        show_excerpt=True,
    )
    return 0 if stale_check["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
