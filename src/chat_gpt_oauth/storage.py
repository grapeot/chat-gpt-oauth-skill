from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .oauth import TokenBundle

DEFAULT_TOKEN_PATH = Path("~/.chatgpt_oauth/token.json")


def resolve_token_path(value: str | Path | None = None) -> Path:
    configured = value or os.environ.get("CHATGPT_OAUTH_TOKEN_PATH") or DEFAULT_TOKEN_PATH
    return Path(configured).expanduser().resolve()


def save_token(bundle: TokenBundle, path: str | Path | None = None) -> Path:
    uses_default_path = path is None and not os.environ.get("CHATGPT_OAUTH_TOKEN_PATH")
    target = resolve_token_path(path)
    parent_existed = target.parent.exists()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if uses_default_path or not parent_existed:
        os.chmod(target.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".token-", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(bundle.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        os.chmod(target, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def load_token(path: str | Path | None = None) -> TokenBundle:
    target = resolve_token_path(path)
    with target.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Token file must contain a JSON object")
    return TokenBundle.from_dict(payload)


def delete_token(path: str | Path | None = None) -> Path:
    target = resolve_token_path(path)
    target.unlink(missing_ok=True)
    return target
