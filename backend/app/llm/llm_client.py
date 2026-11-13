"""The ONLY place the app talks to a language model or embedding model.

Uses the standard OpenAI SDK pointed at our own Ollama server (OpenAI-compatible API).
Switching providers = changing LLM_BASE_URL / LLM_MODEL in .env.
"""
from __future__ import annotations

import json
import time
import re
from functools import lru_cache
from typing import Any, Iterator

from openai import OpenAI

from app.config import get_settings


@lru_cache
def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key, timeout=300)


_THINK = re.compile(r"<think>.*?</think>", re.S)


def _strip_think(text: str) -> str:
    """Qwen3 may emit <think>…</think> reasoning; users only see the final answer."""
    return _THINK.sub("", text or "").strip()


def chat(messages: list[dict], *, thinking: bool = False, temperature: float = 0.2,
         max_tokens: int = 1500, model: str | None = None) -> str:
    """One-shot completion. thinking=False appends Qwen3's /no_think switch (faster)."""
    s = get_settings()
    msgs = list(messages)
    if not thinking and msgs and msgs[-1]["role"] == "user":
        msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + "\n/no_think"}
    r = _client().chat.completions.create(model=model or s.llm_model, messages=msgs,
                                          temperature=temperature, max_tokens=max_tokens)
    return _strip_think(r.choices[0].message.content)


def chat_stream(messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 1500) -> Iterator[str]:
    """Streams tokens for the chat UI, hiding any <think> section."""
    s = get_settings()
    msgs = list(messages)
    if msgs and msgs[-1]["role"] == "user":
        msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + "\n/no_think"}
    stream = _client().chat.completions.create(model=s.llm_model, messages=msgs, temperature=temperature,
                                               max_tokens=max_tokens, stream=True)
    in_think = False
    for ev in stream:
        tok = ev.choices[0].delta.content or "" if ev.choices else ""
        if "<think>" in tok:
            in_think = True
        if not in_think and tok:
            yield tok
        if "</think>" in tok:
            in_think = False


def chat_json(messages: list[dict], schema_hint: str, **kw) -> dict[str, Any]:
    """Ask for JSON and parse it robustly. Used for intent classification, slot extraction, verification."""
    sys = {"role": "system", "content": "Reply with ONLY a valid JSON object, no prose, no code fences. "
                                        f"Schema: {schema_hint}"}
    out = chat([sys, *messages], temperature=0.0, **kw)
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        raise ValueError(f"Model did not return JSON: {out[:200]}")
    return json.loads(m.group(0))


@lru_cache
def _embed_client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.embed_base_url or s.llm_base_url, api_key=s.llm_api_key, timeout=300)


def embed(texts: list[str], batch: int = 32) -> list[list[float]]:
    """bge-m3 embeddings (1024-d). Batched to keep requests small. May run on a different GPU than the LLM."""
    s = get_settings()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        for attempt in range(6):  # survive SSH-tunnel blips: retry with backoff (2, 4, 8, 16, 32 s)
            try:
                r = _embed_client().embeddings.create(model=s.embed_model, input=texts[i:i + batch])
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(2 ** (attempt + 1))
        out.extend(d.embedding for d in r.data)
    return out
