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
