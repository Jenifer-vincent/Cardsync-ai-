"""POST example extracted contact JSON to /api/leads/sync-from-local (Zoho + optional email)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:5000").rstrip("/")
EXAMPLE_PATH = ROOT / "docs" / "EXTRACTED_CONTACT_API_EXAMPLE.json"


def main() -> int:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload.pop("_comment", None)

    print(f"POST {API_BASE}/api/leads/sync-from-local")
    print(json.dumps(payload, indent=2))

    with httpx.Client(timeout=60.0) as client:
        response = client.post(f"{API_BASE}/api/leads/sync-from-local", json=payload)

    print(f"\nStatus: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)

    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
