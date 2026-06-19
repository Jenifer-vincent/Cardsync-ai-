"""Probe which Zoho Lead field accepts event text."""
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
from services.zoho_service import (
    ZOHO_API_DOMAIN,
    create_lead,
    extract_lead_id_from_response,
    get_valid_access_token,
)

TEST_VALUE = f"CardSync Event Probe {uuid.uuid4().hex[:6]}"
CANDIDATES = [
    "Event_Name",
    "EventName",
    "Twitter",
    "Skype_ID",
    "Description",
]

for api_name in CANDIDATES:
    payload = {
        "Last_Name": f"Probe {api_name}",
        "Company": "CardSync QA",
        api_name: TEST_VALUE,
    }
    print(f"\n=== Try field {api_name} ===")
    try:
        response = create_lead(payload)
        lead_id = extract_lead_id_from_response(response)
        print("created lead", lead_id)
    except Exception as exc:
        print("CREATE FAILED:", exc)
        continue

    token = get_valid_access_token()
    fetch = httpx.get(
        f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
        params={"fields": f"id,Last_Name,{api_name}"},
        timeout=30,
    )
    row = (fetch.json().get("data") or [{}])[0]
    stored = row.get(api_name)
    print("stored value:", repr(stored))
    if stored == TEST_VALUE:
        print(f"PASS: use ZOHO_LEAD_EVENT_FIELD={api_name}")
