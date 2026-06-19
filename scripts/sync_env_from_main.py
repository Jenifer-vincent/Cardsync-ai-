#!/usr/bin/env python3
"""Copy backend-relevant variables from main/.env into backend/.env.

Also copies the Firebase service-account JSON when FIREBASE_CREDENTIALS_PATH is set.

Safe to re-run — overwrites backend/.env from main/.env (frontend-only keys skipped).

Usage (from repo root or backend/):
  python backend/scripts/sync_env_from_main.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
MAIN_ROOT = REPO_ROOT / "main"
MAIN_ENV = MAIN_ROOT / ".env"
BACKEND_ENV = BACKEND_ROOT / ".env"

# Frontend / deprecated Node local-db — not used by Python backend
SKIP_KEYS = frozenset(
    {
        "VITE_API_URL",
        "VITE_CONTACT_STORAGE",
        "VITE_LOCAL_DB_URL",
        "LOCAL_DB_PORT",
        "NETLIFY_SITE_URL",
        "PRODUCTION_API_URL",
    }
)

DEFAULTS = {
    "HOST": "127.0.0.1",
    "RELOAD": "true",
}


def parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        out[key.strip()] = value
    return out


def format_env(values: dict[str, str]) -> str:
    lines = [
        "# Auto-synced from main/.env — edit here or re-run scripts/sync_env_from_main.py",
        "",
    ]
    for key in sorted(values):
        lines.append(f"{key}={values[key]}")
    lines.append("")
    return "\n".join(lines)


def _resolve_source_path(raw: str) -> Path | None:
    cleaned = raw.strip().strip('"').strip("'")
    if not cleaned:
        return None
    path = Path(cleaned)
    if path.is_absolute() and path.is_file():
        return path
    for base in (MAIN_ROOT, REPO_ROOT, BACKEND_ROOT):
        candidate = base / cleaned
        if candidate.is_file():
            return candidate
    return None


def sync_firebase_credentials(merged: dict[str, str]) -> None:
    raw = merged.get("FIREBASE_CREDENTIALS_PATH", "")
    source = _resolve_source_path(raw)
    if not source:
        if raw.strip():
            print(f"Warning: Firebase JSON not found for FIREBASE_CREDENTIALS_PATH={raw.strip()!r}")
        return

    dest = BACKEND_ROOT / source.name
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
        print(f"Copied Firebase credentials: {source.name} -> backend/{source.name}")

    merged["FIREBASE_CREDENTIALS_PATH"] = source.name


def main() -> int:
    if not MAIN_ENV.is_file():
        print(f"Missing {MAIN_ENV} — nothing to sync.")
        return 1

    source = parse_env(MAIN_ENV)
    merged = {k: v for k, v in source.items() if k not in SKIP_KEYS}

    for key, value in DEFAULTS.items():
        merged.setdefault(key, value)

    sync_firebase_credentials(merged)

    BACKEND_ENV.write_text(format_env(merged), encoding="utf-8")
    print(f"Wrote {len(merged)} variables to {BACKEND_ENV}")
    skipped = sorted(SKIP_KEYS & source.keys())
    print(f"Skipped frontend-only keys: {', '.join(skipped) or '(none)'}")
    storage = merged.get("CONTACT_STORAGE", "")
    if storage == "indexeddb":
        print(
            "Note: CONTACT_STORAGE=indexeddb — Firebase env is present but storage uses browser IndexedDB. "
            "Set CONTACT_STORAGE=firebase in backend/.env to use Firebase."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
