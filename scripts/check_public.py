from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"}
CHECKS = {
    "machine-specific home path": re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/"),
    "private vault reference": re.compile(r"op://", re.IGNORECASE),
    "OpenAI-style secret key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "JWT-like token": re.compile(
        r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b"
    ),
}


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.is_file() or any(
            part in IGNORED_PARTS or part.endswith(".egg-info") for part in path.parts
        ):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in CHECKS.items():
            if pattern.search(content):
                failures.append(f"{path.relative_to(ROOT)}: {label}")
    if failures:
        print("Public scan failed:")
        print("\n".join(failures))
        return 1
    print("Public content scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
