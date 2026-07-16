from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .http import post_json, post_sse
from .oauth import HttpPost, TokenBundle, refresh, token_bundle
from .storage import load_token, save_token

CODEX_RESPONSES_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_PROMPT = "请只回复 OK，不要添加其他文字。"
HttpStream = Callable[..., list[dict[str, Any]]]


def ensure_fresh_token(
    path: str | Path | None = None,
    *,
    refresh_margin_seconds: int = 60,
    now: Callable[[], float] = time.time,
    http_post: HttpPost = post_json,
) -> TokenBundle:
    current = load_token(path)
    if current.expires_at > now() + refresh_margin_seconds:
        return current
    updated = token_bundle(
        refresh(current.refresh_token, http_post=http_post),
        previous=current,
        now=now,
    )
    save_token(updated, path)
    return updated


def request_text(
    prompt: str = DEFAULT_PROMPT,
    *,
    model: str | None = None,
    token_path: str | Path | None = None,
    http_post: HttpPost = post_json,
    http_stream: HttpStream = post_sse,
    now: Callable[[], float] = time.time,
) -> str:
    tokens = ensure_fresh_token(token_path, now=now, http_post=http_post)
    payload = {
        "model": model or os.environ.get("CHATGPT_OAUTH_MODEL") or DEFAULT_MODEL,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "store": False,
        "stream": True,
        "include": ["reasoning.encrypted_content"],
    }
    events = http_stream(
        CODEX_RESPONSES_ENDPOINT,
        body=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {tokens.access_token}",
            "ChatGPT-Account-Id": tokens.account_id,
            "Content-Type": "application/json",
            "User-Agent": "chat-gpt-oauth-skill/0.1",
            "originator": "opencode",
        },
        timeout=120,
    )
    text = extract_stream_text(events)
    if not text:
        raise RuntimeError("Codex response did not contain output_text")
    return text


def extract_stream_text(events: list[dict[str, Any]]) -> str:
    for event in events:
        if event.get("type") in {"error", "response.failed"}:
            detail = event.get("error") or event.get("response") or event
            snippet = json.dumps(detail, ensure_ascii=False)[:2_000]
            raise RuntimeError(f"Codex stream failed: {snippet}")
    completed = next(
        (event for event in reversed(events) if event.get("type") == "response.completed"),
        None,
    )
    if completed is None:
        raise RuntimeError("Codex stream ended before response.completed")
    deltas = [
        event["delta"]
        for event in events
        if event.get("type") == "response.output_text.delta"
        and isinstance(event.get("delta"), str)
    ]
    if deltas:
        return "".join(deltas)
    response = completed.get("response")
    if isinstance(response, dict):
        return extract_output_text(response)
    return ""


def extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        texts.extend(
            part["text"]
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "output_text"
            and isinstance(part.get("text"), str)
        )
    return "\n".join(texts)
