"""Verify eventName stores via Description fallback when no custom field is set."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

import httpx
from services.zoho_service import ZOHO_API_DOMAIN, get_valid_access_token

API_BASE = "http://127.0.0.1:5000"
TEST_EVENT = f"CardSync Desc Test {uuid.uuid4().hex[:6]}"
body = {
    "fullName": "Description Event Test",
    "company": "CardSync QA",
    "email": f"desc-event-{uuid.uuid4().hex[:8]}@example.com",
    "phone": "+919999999998",
    "eventName": TEST_EVENT,
    "skipWhatsApp": True,
    "skipEmail": True,
}

with httpx.Client(timeout=60.0) as client:
    sync = client.post(f"{API_BASE}/api/leads/sync-from-local", json=body)
    print("sync", sync.status_code, sync.json())
    lead_id = sync.json().get("zohoLeadId")

token = get_valid_access_token()
fetch = httpx.get(
    f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
    headers={"Authorization": f"Zoho-oauthtoken {token}"},
    params={"fields": "id,Last_Name,Description"},
    timeout=30,
)
row = (fetch.json().get("data") or [{}])[0]
desc = row.get("Description") or ""
print("Description:", repr(desc))
expected = f"Event: {TEST_EVENT}"
if expected in desc:
    print("PASS: event stored in Description")
else:
    print("FAIL: expected", expected)
