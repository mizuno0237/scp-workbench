#!/usr/bin/env python3
"""Fail if the public slice still contains internal hosts or secret-shaped values."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", "dist", ".venv", "venv", "__pycache__"}
FORBIDDEN = [
    "harbor.youhualin.com",
    "gitlab.youhualin.com",
    "youhualin.com",
    "悠桦林",
    "docker-compose.server.yml",
    "docker-compose.production.yml",
]
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret[_-]?key|password)\s*[:=]\s*['\"]?(?!change-me|REPLACE_WITH)[A-Za-z0-9_\-]{20,}"
)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
            continue
        files.append(path)
    return files


def main() -> int:
    hits: list[str] = []
    for path in iter_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT).as_posix()
        if rel == "scripts/scan-secrets.py":
            continue
        for token in FORBIDDEN:
            if token in text:
                hits.append(f"{rel}: forbidden token {token}")
        if SECRET_RE.search(text) and path.name not in {".env.example"}:
            hits.append(f"{rel}: secret-shaped assignment")
    if hits:
        print("secret scan failed:")
        for hit in hits:
            print(f"  {hit}")
        return 1
    print(f"secret scan passed ({len(iter_files())} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
