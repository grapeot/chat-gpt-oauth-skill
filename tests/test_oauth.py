from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlparse

import pytest

from chat_gpt_oauth.oauth import (
    CLIENT_ID,
    REDIRECT_URI,
    TokenBundle,
    create_authorization,
    extract_account_id,
    token_bundle,
)


def jwt(claims: dict[str, object]) -> str:
    def encode(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{encode({'alg': 'none'})}.{encode(claims)}.signature"


def test_authorization_uses_pkce_s256_and_state() -> None:
    authorization = create_authorization()
    url = urlparse(authorization.authorize_url)
    query = parse_qs(url.query)
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(authorization.verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://auth.openai.com/oauth/authorize"
    assert query["client_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [REDIRECT_URI]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [expected_challenge]
    assert query["state"] == [authorization.state]
    assert len(authorization.verifier) >= 43


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"chatgpt_account_id": "acct-direct"}, "acct-direct"),
        ({"https://api.openai.com/auth": {"chatgpt_account_id": "acct-nested"}}, "acct-nested"),
        ({"organizations": [{"id": "acct-org"}]}, "acct-org"),
    ],
)
def test_extract_account_id_claim_locations(claims: dict[str, object], expected: str) -> None:
    assert extract_account_id(jwt(claims)) == expected


def test_token_bundle_validates_and_calculates_expiry() -> None:
    bundle = token_bundle(
        {
            "access_token": "access-value",
            "refresh_token": "refresh-value",
            "id_token": jwt({"chatgpt_account_id": "acct-1"}),
            "expires_in": 120,
            "scope": "openid offline_access",
        },
        now=lambda: 1_000,
    )

    assert bundle.account_id == "acct-1"
    assert bundle.expires_at == 1_120
    assert bundle.scope == "openid offline_access"


def test_refresh_response_preserves_metadata_and_accepts_rotation() -> None:
    previous = TokenBundle(
        access_token="old-access",
        refresh_token="old-refresh",
        id_token=jwt({"chatgpt_account_id": "acct-1"}),
        expires_at=1_000,
        account_id="acct-1",
        scope="openid offline_access",
    )
    refreshed = token_bundle(
        {
            "access_token": "new-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
        },
        previous=previous,
        now=lambda: 2_000,
    )

    assert refreshed.refresh_token == "rotated-refresh"
    assert refreshed.id_token == previous.id_token
    assert refreshed.account_id == "acct-1"
    assert refreshed.scope == previous.scope


def test_token_bundle_rejects_missing_account_identifier() -> None:
    with pytest.raises(ValueError, match="account identifier"):
        token_bundle(
            {"access_token": "opaque", "refresh_token": "refresh", "expires_in": 60},
            now=lambda: 1_000,
        )
