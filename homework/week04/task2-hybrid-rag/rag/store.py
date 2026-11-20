"""统一分块、双路持久化（VectorStoreIndex + BM25）与增量同步更新。"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.vector_stores import SimpleVectorStore

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .docload import file_sha256, load_all, load_one, scan_corpus
from .embed import BGESmallZhEmbedding
from .hybrid import BM25Retriever, load_bm25_nodes, save_bm25_nodes

BM25_FILE = "bm25_nodes.json"
MANIFEST_FILE = "manifest.json"


def bm25_path(store_dir: Path) -> Path:
    return store_dir / BM25_FILE


def manifest_path(store_dir: Path) -> Path:
    return store_dir / MANIFEST_FILE


def get_embedding(embed_model: BaseEmbedding | None = None) -> BaseEmbedding:
    return embed_model if embed_model is not None else BGESmallZhEmbedding()


def _heading_of(text: str, header_path: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else ""
    m = re.match(r"^#{1,6}\s+(.*)$", first)
    own = m.group(1).strip() if m else ""
    parents = header_path.strip("/").replace("/", " > ")
    if parents and own:
        return f"{parents} > {own}"
    return own or parents or "(正文)"


def _split_sentences(text: str) -> List[str]:
    """中英文友好的分句器，避免依赖外部 NLTK 数据目录。"""
    parts = re.split(r"(?<=[。！？!?;\n])", text)
    return [p for p in parts if p]


def chunk_document(
    doc: Document,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[TextNode]:
    """将单个 Document 分块为带来源元数据与稳定 node_id 的 TextNode 列表。"""
    fp = doc.metadata["file_path"]
    raw_chunks: List[tuple[str, str, str]] = []

    if doc.metadata.get("doc_type") == "code":
        raw_chunks.append((doc.text, "(整文件)", ""))
    else:
        md_parser = MarkdownNodeParser()
        splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_tokenizer_fn=_split_sentences,
        )
        for md_node in md_parser.get_nodes_from_documents([doc]):
            header = md_node.metadata.get("header_path", "") or ""
            sub_nodes = splitter.get_nodes_from_documents([md_node]) or [md_node]
            for sub in sub_nodes:
                text = sub.text.strip()
                if not text:
                    continue
                raw_chunks.append((text, _heading_of(text, header), header))

    nodes: List[TextNode] = []
    for idx, (text, heading, header_path) in enumerate(raw_chunks):
        node_id = f"{fp}::chunk_{idx}"
        node = TextNode(
            id_=node_id,
            text=text,
            metadata={
                **doc.metadata,
                "heading": heading,
                "header_path": header_path,
                "chunk_index": idx,
            },
        )
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=fp)
        nodes.append(node)
    return nodes


def chunk_documents(
    docs: Sequence[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[TextNode]:
    """基于同一批文档生成同一批 TextNode，同时供向量索引与 BM25 使用。"""
    all_nodes: List[TextNode] = []
    for doc in docs:
        all_nodes.extend(chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return all_nodes


def _build_manifest(nodes: Sequence[TextNode]) -> Dict[str, dict]:
    manifest: Dict[str, dict] = {}
    for node in nodes:
        fp = node.metadata["file_path"]
        entry = manifest.setdefault(
            fp,
            {
                "content_hash": node.metadata.get("content_hash", ""),
                "doc_type": node.metadata.get("doc_type", ""),
                "node_ids": [],
            },
        )
        entry["node_ids"].append(node.node_id)
    return manifest


def _save_manifest(manifest: Dict[str, dict], store_dir: Path) -> None:
    manifest_path(store_dir).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_manifest(store_dir: Path) -> Dict[str, dict]:
    path = manifest_path(store_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_and_save(
    corpus_dir: Path,
    store_dir: Path,
    overwrite: bool = True,
    embed_model: BaseEmbedding | None = None,
) -> tuple[List[Document], List[TextNode], VectorStoreIndex]:
    """从语料目录全量构建向量索引与 BM25 索引（基于同一批节点）并落盘。"""
    if store_dir.exists():
        if not overwrite:
            raise RuntimeError(f"索引目录已存在：{store_dir}（可传 --overwrite 重建）")
        shutil.rmtree(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)

    docs = load_all(corpus_dir)
    nodes = chunk_documents(docs)

    model = get_embedding(embed_model)
    Settings.embed_model = model
    vector_store = SimpleVectorStore()
    storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(
        nodes,
        storage_context=storage_ctx,
        embed_model=model,
        show_progress=False,
    )
    index.storage_context.persist(str(store_dir))
    save_bm25_nodes(nodes, bm25_path(store_dir))
    _save_manifest(_build_manifest(nodes), store_dir)
    return docs, nodes, index


def load_stores(
    store_dir: Path,
    embed_model: BaseEmbedding | None = None,
) -> tuple[VectorStoreIndex, BM25Retriever, List[TextNode]]:
    """从落盘目录加载向量索引与 BM25 检索器。"""
    model = get_embedding(embed_model)
    Settings.embed_model = model
    ctx = StorageContext.from_defaults(persist_dir=str(store_dir))
    index = load_index_from_storage(ctx, embed_model=model)
    nodes = load_bm25_nodes(bm25_path(store_dir))
    return index, BM25Retriever(nodes), nodes


@dataclass
class SyncUpdateReport:
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    removed_node_ids: List[str]
    inserted_node_ids: List[str]
    total_vector_nodes: int
    total_bm25_nodes: int
    aligned: bool


def sync_update(
    corpus_dir: Path,
    store_dir: Path,
    embed_model: BaseEmbedding | None = None,
) -> SyncUpdateReport:
    """基于文件 SHA-256 清单增量同步更新向量索引与 BM25 索引，确保旧分块完全退出。"""
    manifest = load_manifest(store_dir)
    current_files = scan_corpus(corpus_dir)

    added: List[str] = []
    modified: List[str] = []
    deleted: List[str] = []

    for fp, path in current_files.items():
        digest = file_sha256(path)
        if fp not in manifest:
            added.append(fp)
        elif manifest[fp].get("content_hash") != digest:
            modified.append(fp)

    for fp in sorted(manifest.keys()):
        if fp not in current_files:
            deleted.append(fp)

    index, _, bm25_nodes = load_stores(store_dir, embed_model=embed_model)
    to_remove_files = set(deleted) | set(modified)
    removed_node_ids: List[str] = []

    for fp in sorted(to_remove_files):
        old_ids = list(manifest.get(fp, {}).get("node_ids", []))
        removed_node_ids.extend(old_ids)
        try:
            index.delete_ref_doc(fp, delete_from_docstore=True)
        except Exception:
            pass
        remaining = [nid for nid in old_ids if nid in index.docstore.docs]
        if remaining:
            index.delete_nodes(remaining, delete_from_docstore=True)
        for nid in old_ids:
            try:
                index.vector_store.delete_nodes(node_ids=[nid])
            except Exception:
                pass
            if nid in index.docstore.docs:
                index.docstore.delete_document(nid, raise_error=False)
        manifest.pop(fp, None)

    bm25_nodes = [n for n in bm25_nodes if n.metadata.get("file_path") not in to_remove_files]

    inserted_node_ids: List[str] = []
    for fp in sorted(set(added) | set(modified)):
        doc = load_one(current_files[fp], corpus_dir)
        new_nodes = chunk_document(doc)
        index.insert_nodes(new_nodes)
        bm25_nodes.extend(new_nodes)
        inserted_node_ids.extend(n.node_id for n in new_nodes)
        manifest[fp] = {
            "content_hash": doc.metadata["content_hash"],
            "doc_type": doc.metadata["doc_type"],
            "node_ids": [n.node_id for n in new_nodes],
        }

    bm25_nodes.sort(key=lambda n: n.node_id)
    index.storage_context.persist(str(store_dir))
    save_bm25_nodes(bm25_nodes, bm25_path(store_dir))
    _save_manifest(manifest, store_dir)

    vector_ids = set(index.docstore.docs.keys())
    bm25_ids = {n.node_id for n in bm25_nodes}
    return SyncUpdateReport(
        added_files=sorted(added),
        modified_files=sorted(modified),
        deleted_files=sorted(deleted),
        removed_node_ids=removed_node_ids,
        inserted_node_ids=inserted_node_ids,
        total_vector_nodes=len(vector_ids),
        total_bm25_nodes=len(bm25_ids),
        aligned=(vector_ids == bm25_ids),
    )
