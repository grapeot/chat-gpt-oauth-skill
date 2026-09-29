from __future__ import annotations

import json

from chat_gpt_oauth.cli import main
from chat_gpt_oauth.oauth import TokenBundle
from chat_gpt_oauth.storage import save_token


def test_status_json_never_prints_token_values(tmp_path, capsys) -> None:
    token_path = tmp_path / "token.json"
    save_token(
        TokenBundle(
            access_token="must-not-print-access",
            refresh_token="must-not-print-refresh",
            id_token="must-not-print-id",
            expires_at=2_000_000_000,
            account_id="acct-example",
            scope="openid offline_access",
        ),
        token_path,
    )

    assert main(["--token-path", str(token_path), "--json", "status"]) == 0
    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert parsed["account_id_present"] is True
    assert "must-not-print" not in output


def test_request_file_and_speed_json(tmp_path, monkeypatch, capsys):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("translate this")
    captured = {}

    def request(**kwargs):
        captured.update(kwargs)
        return {"answer": "translated", "service_tier": "priority", "usage": {"output_tokens": 3}}

    monkeypatch.setattr("chat_gpt_oauth.cli.request_result", request)
    assert (
        main(
            [
                "--json",
                "request",
                "--prompt-file",
                str(prompt_file),
                "--service-tier",
                "fast",
                "--reasoning-effort",
                "xhigh",
            ]
        )
        == 0
    )
    assert captured["prompt"] == "translate this"
    assert captured["service_tier"] == "fast"
    assert captured["reasoning_effort"] == "xhigh"
    assert json.loads(capsys.readouterr().out)["usage"] == {"output_tokens": 3}


def test_request_defaults_to_standard(monkeypatch, capsys):
    def request(**kwargs):
        assert kwargs["service_tier"] == "default"
        return {"answer": "OK"}

    monkeypatch.setattr("chat_gpt_oauth.cli.request_result", request)
    assert main(["request"]) == 0
    assert capsys.readouterr().out.strip() == "OK"
