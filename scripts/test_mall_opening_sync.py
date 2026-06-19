"""Verify Mall Opening sync + readback after cooldown."""
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
from services.contact_service import sync_payload_to_zoho
from services.zoho_service import ZOHO_API_DOMAIN, get_leads, get_valid_access_token

TEST_EVENT = "Mall Opening"


def main() -> int:
    payload = {
        "fullName": "Mall Opening Test Lead",
        "company": "CardSync QA",
        "designation": "Manager",
        "phone": "+919876543210",
        "email": f"mall.test.{uuid.uuid4().hex[:6]}@example.com",
        "eventName": TEST_EVENT,
    }

    print("=== Sync via contact_service ===")
    result = sync_payload_to_zoho(payload)
    print(json.dumps(result, indent=2, default=str)[:800])

    print("\n=== Fetch leads (Mall Opening) ===")
    leads = get_leads()
    mall = [l for l in leads if TEST_EVENT.lower() in (l.get("eventName") or "").lower()]
    print(f"Total leads: {len(leads)}, Mall Opening matches: {len(mall)}")
    for row in mall[:3]:
        print("-", row.get("name"), "| eventName:", repr(row.get("eventName")))

    lead_id = result.get("zohoLeadId") or (mall[0]["id"] if mall else None)
    if lead_id:
        token = get_valid_access_token()
        response = httpx.get(
            f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
            headers={"Authorization": f"Zoho-oauthtoken {token}"},
            params={"fields": "id,Last_Name,Event_Name,Description"},
            timeout=30,
        )
        print(f"\n=== Raw Zoho fields for lead {lead_id} ===")
        print(json.dumps(response.json(), indent=2))

    ok = bool(mall) and mall[0].get("eventName") == TEST_EVENT
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
