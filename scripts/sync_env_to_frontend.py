#!/usr/bin/env python3
"""Copy VITE_* and related frontend vars from main/ into frontend/.env."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_ENV = REPO_ROOT / "frontend" / ".env"
SOURCES = [
    REPO_ROOT / "main" / ".env",
    REPO_ROOT / "main" / ".env.development",
    REPO_ROOT / "main" / ".env.production",
]
FRONTEND_KEYS_PREFIX = ("VITE_",)
EXTRA_KEYS = ("PRODUCTION_API_URL", "NETLIFY_SITE_URL")
SKIP = frozenset({"VITE_LOCAL_DB_URL"})


def parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key in SKIP:
            continue
        if key.startswith(FRONTEND_KEYS_PREFIX) or key in EXTRA_KEYS:
            out[key] = value
    return out


def main() -> int:
    merged: dict[str, str] = {}
    for src in SOURCES:
        merged.update(parse_env(src))

    merged.setdefault("VITE_CONTACT_STORAGE", "indexeddb")

    lines = [
        "# Synced from main/ — frontend build + dev proxy",
        "",
    ]
    for key in sorted(merged):
        lines.append(f"{key}={merged[key]}")
    lines.append("")

    FRONTEND_ENV.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(merged)} variables to {FRONTEND_ENV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
