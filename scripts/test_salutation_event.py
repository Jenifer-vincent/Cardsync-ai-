"""End-to-end test: eventName -> Zoho Salutation (Event Name column)."""
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
    print("=== 1. Config ===")
    print(f"  ZOHO_LEAD_EVENT_FIELD = {field!r}")

    print("\n=== 2. Build payload ===")
    payload = _contact_to_zoho_payload(
        {
            "fullName": "Salutation E2E Test",
            "company": "CardSync QA",
            "eventName": TEST_EVENT,
        }
    )
    print(f"  {field} = {payload.get(field)!r}")
    print(f"  Description = {payload.get('Description')!r}")

    print("\n=== 3. Create lead in Zoho ===")
    response = create_lead(payload)
    lead_id = extract_lead_id_from_response(response)
    print(f"  lead_id = {lead_id}")

    print("\n=== 4. Raw Zoho fetch ===")
    token = get_valid_access_token()
    fetch = httpx.get(
        f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
        params={"fields": f"id,Last_Name,{field},Description"},
        timeout=30,
    )
    row = (fetch.json().get("data") or [{}])[0]
    print(json.dumps(row, indent=2))

    print("\n=== 5. get_leads() readback ===")
    match = next((lead for lead in get_leads() if lead.get("id") == lead_id), None)
    if match:
        print(f"  eventName = {match.get('eventName')!r}")
    else:
        print("  lead not found in get_leads()")

    salutation_ok = row.get(field) == TEST_EVENT
    app_ok = bool(match) and match.get("eventName") == TEST_EVENT
    parsed_ok = extract_event_name_from_lead(row) == TEST_EVENT

    print("\n=== Results ===")
    print(f"  Zoho {field} column: {'PASS' if salutation_ok else 'FAIL'}")
    print(f"  App get_leads():      {'PASS' if app_ok else 'FAIL'}")
    print(f"  extract_event_name:   {'PASS' if parsed_ok else 'FAIL'}")

    if salutation_ok and app_ok and parsed_ok:
        print("\nOVERALL: PASS")
        return 0

    print("\nOVERALL: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
