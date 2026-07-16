from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from .http import post_json

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER = "https://auth.openai.com"
CALLBACK_PORT = 1455
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/auth/callback"
SCOPES = "openid profile email offline_access"

HttpPost = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class PkceAuthorization:
    verifier: str
    state: str
    authorize_url: str


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    id_token: str | None
    expires_at: int
    account_id: str
    scope: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "id_token": self.id_token,
            "expires_at": self.expires_at,
            "account_id": self.account_id,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TokenBundle:
        access_token = _required_string(value, "access_token")
        refresh_token = _required_string(value, "refresh_token")
        account_id = _required_string(value, "account_id")
        expires_at = value.get("expires_at")
        if not isinstance(expires_at, int) or expires_at <= 0:
            raise ValueError("Token file has an invalid expires_at")
        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=_optional_string(value, "id_token"),
            expires_at=expires_at,
            account_id=account_id,
            scope=_optional_string(value, "scope"),
        )


def create_authorization() -> PkceAuthorization:
    verifier = secrets.token_urlsafe(64)[:64]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "state": state,
            "originator": "opencode",
        }
    )
    return PkceAuthorization(verifier, state, f"{ISSUER}/oauth/authorize?{query}")


def login(
    *,
    open_browser: bool = True,
    timeout_seconds: int = 300,
    announce: Callable[[str], None] | None = None,
    browser_open: Callable[[str], object] = webbrowser.open,
    http_post: HttpPost = post_json,
    now: Callable[[], float] = time.time,
) -> TokenBundle:
    authorization = create_authorization()
    result: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            callback = urlparse(self.path)
            if callback.path != "/auth/callback":
                self._respond(404, "Not found")
                return
            query = parse_qs(callback.query)
            oauth_error = _first(query, "error_description") or _first(query, "error")
            code = _first(query, "code")
            state = _first(query, "state")
            if not state or not hmac.compare_digest(state, authorization.state):
                self._respond(400, "授权失败：OAuth state 无效。")
                return
            if oauth_error:
                result["error"] = oauth_error
                self._respond(400, f"授权失败：{html.escape(oauth_error)}")
                return
            if not code:
                result["error"] = "Missing authorization code"
                self._respond(400, "授权失败：callback 缺少 code。")
                return
            result["code"] = code
            self._respond(200, "授权完成。可以关闭这个页面并返回终端。")

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _respond(self, status: int, message: str) -> None:
            body = (
                "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
                f"<title>ChatGPT OAuth</title><body><main><h1>{message}</h1></main></body></html>"
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler) as server:
        if announce:
            announce(authorization.authorize_url)
        if open_browser:
            browser_open(authorization.authorize_url)
        deadline = time.monotonic() + timeout_seconds
        while "code" not in result and "error" not in result and time.monotonic() < deadline:
            server.timeout = min(0.5, max(deadline - time.monotonic(), 0.01))
            server.handle_request()

    if "error" in result:
        raise RuntimeError(result["error"])
    if "code" not in result:
        raise TimeoutError(f"OAuth callback did not arrive within {timeout_seconds} seconds")
    payload = exchange_code(result["code"], authorization.verifier, http_post=http_post)
    return token_bundle(payload, now=now)


def exchange_code(code: str, verifier: str, *, http_post: HttpPost = post_json) -> dict[str, Any]:
    return http_post(
        f"{ISSUER}/oauth/token",
        body=urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def refresh(refresh_token: str, *, http_post: HttpPost = post_json) -> dict[str, Any]:
    return http_post(
        f"{ISSUER}/oauth/token",
        body=urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CLIENT_ID,
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def token_bundle(
    payload: Mapping[str, Any],
    *,
    previous: TokenBundle | None = None,
    now: Callable[[], float] = time.time,
) -> TokenBundle:
    access_token = _required_string(payload, "access_token")
    refresh_token = _optional_string(payload, "refresh_token") or (
        previous.refresh_token if previous else ""
    )
    if not refresh_token:
        raise ValueError("OAuth response did not include a refresh_token")
    id_token = _optional_string(payload, "id_token") or (previous.id_token if previous else None)
    account_id = extract_account_id(id_token) or extract_account_id(access_token)
    if not account_id and previous:
        account_id = previous.account_id
    if not account_id:
        raise ValueError("OAuth tokens did not include a ChatGPT account identifier")
    expires_in = payload.get("expires_in", 3600)
    if not isinstance(expires_in, (int, float)) or expires_in <= 0:
        raise ValueError("OAuth response has an invalid expires_in")
    return TokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token,
        expires_at=int(now() + expires_in),
        account_id=account_id,
        scope=_optional_string(payload, "scope") or (previous.scope if previous else None),
    )


def extract_account_id(token: str | None) -> str | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    nested = claims.get("https://api.openai.com/auth")
    organizations = claims.get("organizations")
    candidates = [
        claims.get("chatgpt_account_id"),
        nested.get("chatgpt_account_id") if isinstance(nested, dict) else None,
        organizations[0].get("id")
        if isinstance(organizations, list) and organizations and isinstance(organizations[0], dict)
        else None,
    ]
    return next((value for value in candidates if isinstance(value, str) and value), None)


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"Missing or invalid {key}")
    return result


def _optional_string(value: Mapping[str, Any], key: str) -> str | None:
    result = value.get(key)
    return result if isinstance(result, str) and result else None


def _first(query: Mapping[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None
