from __future__ import annotations

import json

import pytest

from chat_gpt_oauth.client import (
    CODEX_RESPONSES_ENDPOINT,
    extract_output_text,
    extract_stream_text,
    request_text,
)
from chat_gpt_oauth.oauth import ISSUER, TokenBundle
from chat_gpt_oauth.storage import load_token, save_token


def test_request_uses_only_access_token_and_account_header(tmp_path) -> None:
    token_path = tmp_path / "token.json"
    save_token(
        TokenBundle(
            access_token="fake-access",
            refresh_token="fake-refresh",
            id_token="fake-id",
            expires_at=2_000_000_000,
            account_id="acct-example",
            scope="openid offline_access",
        ),
        token_path,
    )
    captured = {}

    def fake_stream(url, *, body, headers, timeout=30):
        captured.update(url=url, body=json.loads(body), headers=headers, timeout=timeout)
        return [
            {"type": "response.output_text.delta", "delta": "O"},
            {"type": "response.output_text.delta", "delta": "K"},
            {"type": "response.completed", "response": {}},
        ]

    answer = request_text(
        "Return OK",
        model="gpt-example",
        token_path=token_path,
        http_stream=fake_stream,
        now=lambda: 1_000,
    )

    assert answer == "OK"
    assert captured["url"] == CODEX_RESPONSES_ENDPOINT
    assert captured["headers"]["Authorization"] == "Bearer fake-access"
    assert captured["headers"]["ChatGPT-Account-Id"] == "acct-example"
    assert "fake-refresh" not in json.dumps(captured)
    assert "fake-id" not in json.dumps(captured)
    assert captured["body"]["store"] is False
    assert captured["body"]["stream"] is True
    assert captured["body"]["include"] == ["reasoning.encrypted_content"]


def test_expired_token_refreshes_and_persists_rotation(tmp_path) -> None:
    token_path = tmp_path / "token.json"
    save_token(
        TokenBundle(
            access_token="old-access",
            refresh_token="old-refresh",
            id_token=None,
            expires_at=900,
            account_id="acct-example",
            scope="openid offline_access",
        ),
        token_path,
    )
    calls = []

    def fake_post(url, *, body, headers, timeout=30):
        calls.append((url, body, headers, timeout))
        assert url == f"{ISSUER}/oauth/token"
        assert b"refresh_token=old-refresh" in body
        return {
            "access_token": "new-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
        }

    def fake_stream(url, *, body, headers, timeout=30):
        calls.append((url, body, headers, timeout))
        assert headers["Authorization"] == "Bearer new-access"
        return [
            {"type": "response.output_text.delta", "delta": "OK"},
            {"type": "response.completed", "response": {}},
        ]

    assert (
        request_text(
            token_path=token_path,
            http_post=fake_post,
            http_stream=fake_stream,
            now=lambda: 1_000,
        )
        == "OK"
    )
    stored = load_token(token_path)
    assert stored.access_token == "new-access"
    assert stored.refresh_token == "rotated-refresh"
    assert len(calls) == 2


def test_extract_output_text_ignores_reasoning_items() -> None:
    assert (
        extract_output_text(
            {
                "output": [
                    {"type": "reasoning", "summary": []},
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "first"},
                            {"type": "output_text", "text": "second"},
                        ],
                    },
                ]
            }
        )
        == "first\nsecond"
    )


def test_extract_stream_text_falls_back_to_completed_response() -> None:
    assert (
        extract_stream_text(
            [
                {
                    "type": "response.completed",
                    "response": {
                        "output": [
                            {
                                "type": "message",
                                "content": [{"type": "output_text", "text": "OK"}],
                            }
                        ]
                    },
                }
            ]
        )
        == "OK"
    )


def test_extract_stream_text_rejects_failure_after_partial_delta() -> None:
    with pytest.raises(RuntimeError, match="Codex stream failed"):
        extract_stream_text(
            [
                {"type": "response.output_text.delta", "delta": "PARTIAL"},
                {"type": "response.failed", "response": {"error": "upstream failed"}},
            ]
        )


def test_extract_stream_text_rejects_incomplete_stream() -> None:
    with pytest.raises(RuntimeError, match="before response.completed"):
        extract_stream_text([{"type": "response.output_text.delta", "delta": "PARTIAL"}])
