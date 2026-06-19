#!/usr/bin/env python3
"""Wipe Firebase/PostgreSQL contacts and optionally all Zoho CRM leads.

Requires the Python API running (default http://127.0.0.1:5000).

Usage:
  python scripts/wipe_all_data.py
  SKIP_ZOHO=1 python scripts/wipe_all_data.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env  # noqa: E402

load_env()

DEFAULT_API = "http://127.0.0.1:5000"


def main() -> int:
    api_base = os.getenv("VITE_API_URL", DEFAULT_API).rstrip("/")
    include_zoho = os.getenv("SKIP_ZOHO", "").strip() != "1"

    payload = json.dumps({"confirm": True, "include_zoho": include_zoho}).encode("utf-8")
    req = urllib.request.Request(
        f"{api_base}/admin/wipe-all-data",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"Wiping backend data via {api_base}/admin/wipe-all-data …")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print("Backend wipe failed:", detail or exc.reason, file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Backend not reachable at {api_base}: {exc.reason}", file=sys.stderr)
        print("Start the Python API: cd backend && python run.py", file=sys.stderr)
        return 1

    print(json.dumps(body, indent=2))
    contacts = body.get("contacts") or {}
    if contacts.get("error"):
        print("Contacts:", contacts["error"], file=sys.stderr)
    elif "deleted" in contacts:
        print(f"Contacts deleted: {contacts.get('deleted', 0)}")

    print(
        "\nDone. Use Settings → Delete all data in the app to clear the browser queue/cache.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
