from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .client import DEFAULT_MODEL, DEFAULT_PROMPT, request_text
from .oauth import login
from .storage import delete_token, load_token, resolve_token_path, save_token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chatgpt-oauth",
        description="ChatGPT/Codex OAuth 非官方 compatibility reference",
    )
    parser.add_argument("--token-path", help="明文 token JSON 路径")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    login_parser = commands.add_parser("login", help="打开浏览器完成 PKCE 登录并保存 token")
    login_parser.add_argument("--no-open", action="store_true", help="只打印 URL，不自动打开浏览器")

    commands.add_parser("status", help="显示 token 文件位置和过期状态，不输出 token")

    request_parser = commands.add_parser("request", help="使用已保存 token 调用 Codex Responses")
    request_parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    request_parser.add_argument("--model", default=DEFAULT_MODEL)

    demo_parser = commands.add_parser("demo", help="登录、明文落盘，然后请求模型只返回 OK")
    demo_parser.add_argument("--no-open", action="store_true")
    demo_parser.add_argument("--model", default=DEFAULT_MODEL)

    commands.add_parser("logout", help="删除本地明文 token 文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token_path = resolve_token_path(args.token_path)
    try:
        if args.command in {"login", "demo"}:
            _warn_plaintext(token_path)
            tokens = login(
                open_browser=not args.no_open,
                announce=lambda url: _announce_authorization(url, args.no_open),
            )
            save_token(tokens, token_path)
            _emit(
                {
                    "status": "authenticated",
                    "token_path": str(token_path),
                    "storage": "plaintext-json",
                    "expires_at": tokens.expires_at,
                    "account_id_present": True,
                },
                as_json=args.json,
            )
            if args.command == "demo":
                answer = request_text(model=args.model, token_path=token_path)
                _emit({"answer": answer, "expected": "OK"}, as_json=args.json)
                return 0 if answer.strip() == "OK" else 2
            return 0

        if args.command == "status":
            tokens = load_token(token_path)
            _emit(
                {
                    "token_path": str(token_path),
                    "storage": "plaintext-json",
                    "expires_at": tokens.expires_at,
                    "expired": tokens.expires_at <= int(time.time()),
                    "account_id_present": bool(tokens.account_id),
                    "scope": tokens.scope,
                },
                as_json=args.json,
            )
            return 0

        if args.command == "request":
            _warn_plaintext(token_path)
            answer = request_text(
                prompt=args.prompt,
                model=args.model,
                token_path=token_path,
            )
            _emit({"answer": answer}, as_json=args.json)
            return 0

        if args.command == "logout":
            deleted = delete_token(token_path)
            _emit({"status": "deleted", "token_path": str(deleted)}, as_json=args.json)
            return 0
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    return 1


def _warn_plaintext(path: Path) -> None:
    print(
        f"警告：本 reference implementation 会把 access/refresh/id token 明文写入 {path}。"
        "该文件权限设为 0600，但任何能读取你本地账户的进程仍可读取它。",
        file=sys.stderr,
    )


def _announce_authorization(url: str, no_open: bool) -> None:
    if no_open:
        print(f"请在浏览器打开：{url}", file=sys.stderr)
        return
    print("正在打开系统浏览器完成 ChatGPT/Codex 授权……", file=sys.stderr)


def _emit(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if "answer" in payload:
        print(payload["answer"])
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
