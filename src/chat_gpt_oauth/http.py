from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(
    url: str,
    *,
    body: bytes,
    headers: Mapping[str, str],
    timeout: float = 30,
) -> dict[str, Any]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS endpoints
            payload = response.read()
    except HTTPError as error:
        snippet = error.read(2_000).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {url}: {snippet}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot reach {url}: {error.reason}") from error

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{url} returned invalid JSON") from error
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{url} returned a non-object JSON response")
    return decoded


def post_sse(
    url: str,
    *,
    body: bytes,
    headers: Mapping[str, str],
    timeout: float = 120,
) -> list[dict[str, Any]]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS endpoint
            payload = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        snippet = error.read(2_000).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {url}: {snippet}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot reach {url}: {error.reason}") from error

    events: list[dict[str, Any]] = []
    for line in payload.splitlines():
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{url} returned invalid SSE JSON") from error
        if isinstance(event, dict):
            events.append(event)
    if not events:
        raise RuntimeError(f"{url} returned no SSE events")
    return events
