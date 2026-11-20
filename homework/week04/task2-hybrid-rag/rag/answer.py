"""证据装配、提示词构造、引用一致性核验与统一终端输出格式化。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from llama_index.core.schema import NodeWithScore

PROMPT_TEMPLATE = """你是 login_demo 项目的知识库问答助手。
请严格遵守以下规则：
1. 只能依据下方【证据列表】中的事实回答问题，禁止编造证据之外的信息。
2. 每个关键结论后必须用 [编号] 标注来源，且编号必须与【证据列表】一一对应。
3. 若证据中出现历史文档（如旧版发布说明/历史记录）与当前最新规则或源码（如 docs/session-rules.md、app/session.py、tables/session-matrix.csv）不一致，请优先以当前规则与源码为准，并指出差异与对应来源编号。
4. 如果证据中没有提到，请直接回答“证据里没有写”。

【证据列表】
{context}

【问题】
{question}
"""


def source_label(hit_or_node) -> str:
    node = getattr(hit_or_node, "node", hit_or_node)
    fp = node.metadata.get("file_path", "?")
    heading = node.metadata.get("heading") or "(正文)"
    return f"{fp} § {heading}"


def assemble_context(hits: Sequence[NodeWithScore], max_chars: int = 4000) -> str:
    parts: List[str] = []
    for idx, hit in enumerate(hits, 1):
        snippet = hit.node.text.strip()
        parts.append(f"[{idx}] 来源：{source_label(hit)}\n{snippet}")
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...(截断)"
    return text


def build_prompt(question: str, hits: Sequence[NodeWithScore]) -> str:
    return PROMPT_TEMPLATE.format(context=assemble_context(hits), question=question)


def format_citations(hits: Sequence[NodeWithScore]) -> List[dict]:
    return [
        {
            "index": idx,
            "node_id": hit.node.node_id,
            "file_path": hit.node.metadata.get("file_path", ""),
            "heading": hit.node.metadata.get("heading", ""),
            "source": source_label(hit),
            "score": round(float(hit.score or 0.0), 6),
            "excerpt": hit.node.text.strip().replace("\n", " ")[:140],
        }
        for idx, hit in enumerate(hits, 1)
    ]


@dataclass
class CitationCheck:
    cited_indices: List[int]
    invalid_indices: List[int]
    valid: bool


def check_citations(answer_text: str, evidence_count: int) -> CitationCheck:
    """检查模型回答中出现的 [n] 是否全部落在 [1, evidence_count] 合法范围内。"""
    found = sorted({int(m) for m in re.findall(r"\[(\d+)\]", answer_text)})
    invalid = [n for n in found if n < 1 or n > evidence_count]
    return CitationCheck(
        cited_indices=found,
        invalid_indices=invalid,
        valid=bool(found) and not invalid,
    )


def print_llm_answer_section(
    *,
    section_title: str,
    list_title: str,
    llm_status: str,
    llm_info: Optional[dict],
    answer: Optional[str],
    citation_check: Optional[dict],
    evidence_for_llm: Sequence[dict],
    show_excerpt: bool = False,
) -> None:
    """统一打印大模型带来源引用回答、引用校验结果与引用来源清单。"""
    print("\n" + "=" * 72)
    print(section_title)
    print("=" * 72)
    if llm_status == "real_llm_called" and llm_info is not None and citation_check is not None:
        print(f"调用模型: {llm_info['provider']} / {llm_info['model']}")
        print("\n【模型回答】")
        print(answer or "")
        print(
            f"\n【引用一致性校验】: {'PASS' if citation_check['valid'] else 'WARN'} "
            f"(引用编号={citation_check['cited_indices']}, 越界编号={citation_check['invalid_indices']})"
        )
    else:
        reason = "已指定 --no-llm" if llm_status == "skipped_by_flag" else "当前环境未配置大模型 API Key"
        print(f"提示：{reason}，跳过在线大模型调用。")
        print("配置 DEEPSEEK_API_KEY / MINIMAX_API_KEY / OPENAI_API_KEY 后重新执行即可调用真实模型生成回答。")

    print(f"\n【{list_title}】")
    for item in evidence_for_llm:
        print(f"  [{item['index']}] {item['source']} (score={item['score']:.6f})")
        if show_excerpt:
            print(f"      摘录: {item['excerpt']}")
    print("=" * 72)
