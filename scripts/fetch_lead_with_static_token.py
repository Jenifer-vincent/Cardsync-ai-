"""Fetch one lead using ZOHO_ACCESS_TOKEN fallback (no refresh)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

import httpx

lead_id = sys.argv[1] if len(sys.argv) > 1 else "1326662000000684003"
token = os.getenv("ZOHO_ACCESS_TOKEN", "").strip()
domain = os.getenv("ZOHO_API_DOMAIN", "https://www.zohoapis.in").rstrip("/")
response = httpx.get(
    f"{domain}/crm/v2/Leads/{lead_id}",
    headers={"Authorization": f"Zoho-oauthtoken {token}"},
    params={"fields": "id,Last_Name,Description,Event_Name,Twitter"},
    timeout=30,
)
print("status", response.status_code)
print(json.dumps(response.json(), indent=2))
