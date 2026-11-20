"""真实本地 Embedding：BAAI/bge-small-zh-v1.5（基于 fastembed ONNX，512 维）。

优先尝试官方 HuggingFace Hub，可通过 HF_ENDPOINT 覆盖镜像源。
"""

from __future__ import annotations

import os
import warnings
from typing import List

from .config import EMBED_MODEL, sanitize_no_proxy

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
sanitize_no_proxy()

warnings.filterwarnings("ignore", message="Cannot enable progress bars.*HF_HUB_DISABLE_PROGRESS_BARS")

from llama_index.core.base.embeddings.base import BaseEmbedding

_MODEL_CACHE: dict[str, object] = {}


def _load_fastembed(model_name: str):
    if model_name not in _MODEL_CACHE:
        from fastembed import TextEmbedding

        _MODEL_CACHE[model_name] = TextEmbedding(model_name=model_name)
    return _MODEL_CACHE[model_name]


class BGESmallZhEmbedding(BaseEmbedding):
    """封装 BAAI/bge-small-zh-v1.5 为 LlamaIndex BaseEmbedding。"""

    model_name: str = EMBED_MODEL

    def _get_query_embedding(self, query: str) -> List[float]:
        vec = next(_load_fastembed(self.model_name).query_embed([query]))
        return [float(x) for x in vec]

    def _get_text_embedding(self, text: str) -> List[float]:
        vec = next(_load_fastembed(self.model_name).passage_embed([text]))
        return [float(x) for x in vec]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return [[float(x) for x in vec] for vec in _load_fastembed(self.model_name).passage_embed(texts)]

    async def _aget_query_embedding(self, query: str) -> List[float]:  # pragma: no cover
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:  # pragma: no cover
        return self._get_text_embedding(text)
