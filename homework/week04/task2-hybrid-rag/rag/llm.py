"""真实模型调用适配器：支持 DeepSeek / MiniMax / 任意 OpenAI 兼容接口。

优先级：
1. 显式指定的 LLM_API_KEY + LLM_BASE_URL + LLM_MODEL
2. DEEPSEEK_API_KEY（默认 https://api.deepseek.com/v1，模型 deepseek-chat）
3. MINIMAX_API_KEY（默认 https://api.minimaxi.com/v1，模型 MiniMax-Text-01）
4. OPENAI_API_KEY（默认 https://api.openai.com/v1，模型 gpt-4o-mini）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from .config import BASE_DIR, sanitize_no_proxy

sanitize_no_proxy()


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str


def resolve_llm_config() -> Optional[LLMConfig]:
    """从环境变量（以及项目根 .env）解析真实大模型配置；未配置时返回 None。"""
    load_dotenv(BASE_DIR / ".env", override=False)

    if os.environ.get("LLM_API_KEY", "").strip():
        return LLMConfig(
            provider=os.environ.get("LLM_PROVIDER", "custom"),
            api_key=os.environ["LLM_API_KEY"].strip(),
            base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1").strip(),
            model=os.environ.get("LLM_MODEL", "deepseek-chat").strip(),
        )
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return LLMConfig(
            provider="deepseek",
            api_key=os.environ["DEEPSEEK_API_KEY"].strip(),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip(),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip(),
        )
    if os.environ.get("MINIMAX_API_KEY", "").strip():
        return LLMConfig(
            provider="minimax",
            api_key=os.environ["MINIMAX_API_KEY"].strip(),
            base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1").strip(),
            model=os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01").strip(),
        )
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return LLMConfig(
            provider="openai",
            api_key=os.environ["OPENAI_API_KEY"].strip(),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip(),
        )
    return None


def call_llm(prompt: str, config: Optional[LLMConfig] = None, temperature: float = 0.0) -> tuple[str, LLMConfig]:
    """调用真实大模型生成带来源引用的回答。"""
    cfg = config or resolve_llm_config()
    if cfg is None:
        raise RuntimeError(
            "未检测到真实大模型 API Key。请在环境变量或 .env 中配置以下任一项："
            "DEEPSEEK_API_KEY / MINIMAX_API_KEY / OPENAI_API_KEY / LLM_API_KEY。"
        )
    from openai import OpenAI

    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=60.0)
    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    content = (resp.choices[0].message.content or "").strip()
    return content, cfg
