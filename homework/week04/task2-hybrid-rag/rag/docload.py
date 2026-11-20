"""多格式文档加载器：Markdown / Python / HTML / CSV / PDF -> LlamaIndex Document。"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path
from typing import Dict, List

from llama_index.core import Document

EXT_TO_TYPE = {
    ".md": "doc",
    ".py": "code",
    ".html": "web",
    ".csv": "table",
    ".pdf": "pdf",
}


def rel_path(path: Path, corpus_dir: Path) -> str:
    """统一以相对 corpus 目录的 POSIX 路径作为来源标识。"""
    return path.relative_to(corpus_dir).as_posix()


def file_sha256(path: Path) -> str:
    """计算文件内容的 SHA-256，用于同步更新时精准检测变更文件。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_text(text: str) -> str:
    """清理页码注释、全角空格、行尾空格与连续空行。"""
    text = re.sub(r"<!--\s*page\s*\d+\s*-->", "", text)
    text = text.replace("\u3000", " ")
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_front_matter(text: str) -> tuple[dict, str]:
    """提取 Markdown 顶部的 YAML 头信息，正文不再重复保留。"""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return {}, text
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return meta, body


def load_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    lines: List[str] = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if tag.name.startswith("h"):
            lines.append(f"{'#' * int(tag.name[1])} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def load_csv(path: Path) -> str:
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    out: List[str] = []
    for row in rows:
        cells = "；".join(f"{k}是{v}" for k, v in row.items() if v)
        if cells:
            out.append(cells + "。")
    return "\n".join(out)


def load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: List[str] = []
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        pages.append(f"<!-- page {i} -->\n{text}")
    return "\n\n".join(pages)


def load_one(path: Path, corpus_dir: Path) -> Document:
    """加载单个支持的文件并构造带来源元数据与内容哈希的 LlamaIndex Document。"""
    rp = rel_path(path, corpus_dir)
    base = {
        "file_path": rp,
        "doc_type": EXT_TO_TYPE[path.suffix],
        "source": path.suffix.lstrip("."),
        "content_hash": file_sha256(path),
    }
    if path.suffix in {".md", ".py"}:
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        return Document(text=clean_text(body), metadata={**base, **meta}, id_=rp)
    if path.suffix == ".html":
        return Document(text=clean_text(load_html(path)), metadata=base, id_=rp)
    if path.suffix == ".csv":
        return Document(text=clean_text(load_csv(path)), metadata=base, id_=rp)
    if path.suffix == ".pdf":
        return Document(text=clean_text(load_pdf(path)), metadata=base, id_=rp)
    raise ValueError(f"Unsupported file extension: {path}")


def scan_corpus(corpus_dir: Path) -> Dict[str, Path]:
    """扫描语料目录，返回 {相对路径: Path} 映射。"""
    files: Dict[str, Path] = {}
    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix not in EXT_TO_TYPE:
            continue
        files[rel_path(path, corpus_dir)] = path
    return files


def load_all(corpus_dir: Path) -> List[Document]:
    """递归加载 corpus_dir 下全部支持的文档。"""
    return [load_one(path, corpus_dir) for path in scan_corpus(corpus_dir).values()]
