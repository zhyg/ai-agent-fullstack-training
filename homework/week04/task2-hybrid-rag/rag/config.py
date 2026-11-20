"""Task 2 RAG 配置：目录、分块参数、本地 Embedding 模型、RRF 融合参数与网络环境工具。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = BASE_DIR / "corpus"
DEFAULT_STORAGE_DIR = BASE_DIR / "storage"
DEFAULT_UPDATED_CORPUS_DIR = BASE_DIR / "corpus_updated"
DEFAULT_UPDATED_STORAGE_DIR = BASE_DIR / "storage_updated"

# 本地真实 Embedding 模型（fastembed ONNX，512 维，无需 API Key）
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "BAAI/bge-small-zh-v1.5")

# 分块参数（Markdown 按标题分块 + 过长二次切分，代码整文件单节点）
CHUNK_SIZE = 384
CHUNK_OVERLAP = 32

# RRF 融合参数
RRF_K = 60
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_K = 20

# 作业默认验证问题
DEFAULT_QUESTION = "登录会话的有效期是多少分钟？"


def sanitize_no_proxy() -> None:
    """移除 NO_PROXY 中会导致部分 httpx/urllib3 版本解析异常的裸 ::1 条目。"""
    for var in ("NO_PROXY", "no_proxy"):
        val = os.environ.get(var)
        if val and "::1" in val:
            parts = [p.strip() for p in val.split(",") if p.strip() and p.strip() not in {"::1", "[::1]"}]
            os.environ[var] = ",".join(dict.fromkeys(parts))
