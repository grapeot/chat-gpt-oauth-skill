from __future__ import annotations

import stat

from chat_gpt_oauth.oauth import TokenBundle
from chat_gpt_oauth.storage import load_token, save_token


def test_plaintext_token_round_trip_and_permissions(tmp_path) -> None:
    bundle = TokenBundle(
        access_token="fake-access",
        refresh_token="fake-refresh",
        id_token="fake-id",
        expires_at=2_000_000_000,
        account_id="acct-example",
        scope="openid offline_access",
    )
    target = tmp_path / "private" / "token.json"

    saved = save_token(bundle, target)

    assert saved == target.resolve()
    assert load_token(target) == bundle
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700


def test_custom_path_does_not_change_existing_parent_permissions(tmp_path) -> None:
    parent = tmp_path / "shared"
    parent.mkdir(mode=0o755)
    target = parent / "token.json"
    bundle = TokenBundle(
        access_token="fake-access",
        refresh_token="fake-refresh",
        id_token=None,
        expires_at=2_000_000_000,
        account_id="acct-example",
        scope=None,
    )

    save_token(bundle, target)

    assert stat.S_IMODE(parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
