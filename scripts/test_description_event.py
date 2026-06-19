"""End-to-end test: eventName via Zoho Description (Events feature)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

import httpx
from services.contact_service import _contact_to_zoho_payload
from services.zoho_service import (
    ZOHO_API_DOMAIN,
    create_lead,
    extract_event_name_from_lead,
    extract_lead_id_from_response,
    get_leads,
    get_valid_access_token,
    zoho_lead_event_field,
)

TEST_EVENT = "Mall Opening"


def main() -> int:
    field = zoho_lead_event_field()
    print("=== Config ===")
    print(f"  ZOHO_LEAD_EVENT_FIELD = {field!r}")

    payload = _contact_to_zoho_payload(
        {
            "fullName": "Description Event Test",
            "company": "CardSync QA",
            "eventName": TEST_EVENT,
        }
    )
    print("\n=== Payload ===")
    print(f"  Description = {payload.get('Description')!r}")
    print(f"  Salutation in payload = {'Salutation' in payload}")

    response = create_lead(payload)
    lead_id = extract_lead_id_from_response(response)
    print(f"\n=== Created lead {lead_id} ===")

    token = get_valid_access_token()
    fetch = httpx.get(
        f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
        params={"fields": "id,Last_Name,Description,Salutation"},
        timeout=30,
    )
    row = (fetch.json().get("data") or [{}])[0]
    print(json.dumps(row, indent=2))

    match = next((lead for lead in get_leads() if lead.get("id") == lead_id), None)
    parsed = extract_event_name_from_lead(row)

    ok = (
        row.get("Description") == f"Event: {TEST_EVENT}"
        and row.get("Salutation") in (None, "")
        and parsed == TEST_EVENT
        and match
        and match.get("eventName") == TEST_EVENT
    )
    print("\n=== RESULT:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
