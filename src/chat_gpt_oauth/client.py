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


def request_result(
    prompt: str = DEFAULT_PROMPT,
    *,
    model: str | None = None,
    token_path: str | Path | None = None,
    tokens: TokenBundle | None = None,
    service_tier: str | None = "default",
    reasoning_effort: str | None = None,
    timeout: float = 600,
    http_post: HttpPost = post_json,
    http_stream: HttpStream = post_sse,
    now: Callable[[], float] = time.time,
) -> dict[str, Any]:
    tokens = tokens or ensure_fresh_token(token_path, now=now, http_post=http_post)
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
    if service_tier is not None:
        payload["service_tier"] = "priority" if service_tier == "fast" else service_tier
    if reasoning_effort is not None:
        payload["reasoning"] = {"effort": reasoning_effort}
    started = time.perf_counter()
    first_event_seconds = None
    first_text_seconds = None
    last_text_seconds = None
    completed_seconds = None

    def observe(event: dict[str, Any]) -> None:
        nonlocal first_event_seconds, first_text_seconds, last_text_seconds, completed_seconds
        elapsed = time.perf_counter() - started
        if first_event_seconds is None:
            first_event_seconds = elapsed
        if event.get("type") == "response.output_text.delta" and event.get("delta"):
            if first_text_seconds is None:
                first_text_seconds = elapsed
            last_text_seconds = elapsed
        if event.get("type") == "response.completed":
            completed_seconds = elapsed

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
        timeout=timeout,
        on_event=observe,
    )
    text = extract_stream_text(events)
    if not text:
        raise RuntimeError("Codex response did not contain output_text")
    response = next(
        e["response"] for e in reversed(events) if e.get("type") == "response.completed"
    )
    return {
        "answer": text,
        "requested_model": payload["model"],
        "requested_service_tier": payload.get("service_tier"),
        "reasoning_effort": reasoning_effort,
        "model": response.get("model"),
        "reasoning": response.get("reasoning"),
        "service_tier": response.get("service_tier"),
        "status": response.get("status"),
        "service_tier_events": [
            {"event": event.get("type"), "service_tier": event["response"].get("service_tier")}
            for event in events
            if isinstance(event.get("response"), dict)
            and "service_tier" in event["response"]
        ],
        "usage": response.get("usage"),
        "timing": {
            "total_seconds": time.perf_counter() - started,
            "first_event_seconds": first_event_seconds,
            "first_text_seconds": first_text_seconds,
            "last_text_seconds": last_text_seconds,
            "completed_seconds": completed_seconds,
        },
    }


def request_text(prompt: str = DEFAULT_PROMPT, **kwargs: Any) -> str:
    return request_result(prompt, **kwargs)["answer"]


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
        if event.get("type") == "response.output_text.delta" and isinstance(event.get("delta"), str)
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
