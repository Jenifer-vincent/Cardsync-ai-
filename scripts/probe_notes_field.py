"""Find a Zoho Lead field that stores long notes text."""
from __future__ import annotations

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

LONG = "This is a long note over twenty five characters for testing field capacity."

CANDIDATES = [
    "Notes",
    "Note",
    "Contact_Notes",
    "Lead_Notes",
    "CardSync_Notes",
    "Card_Notes",
    "Event_Notes",
    "Remarks",
    "Comment",
    "Skype_ID",
    "Secondary_Email",
    "Twitter",
    "Fax",
    "Tag",
    "Test",
]


def main() -> int:
    token = get_valid_access_token()
    working: list[tuple[str, int, bool]] = []

    for api in CANDIDATES:
        body = {"data": [{"Last_Name": f"P{uuid.uuid4().hex[:3]}", "Company": "QA", api: LONG}]}
        response = httpx.post(
            f"{ZOHO_API_DOMAIN}/crm/v2/Leads",
            headers={"Authorization": f"Zoho-oauthtoken {token}"},
            json=body,
            timeout=30,
        )
        row = (response.json().get("data") or [{}])[0]
        if row.get("status") != "success":
            details = row.get("details") or {}
            print(f"{api:20} BLOCKED  {row.get('code')} max={details.get('maximum_length')}")
            continue

        lead_id = (row.get("details") or {}).get("id")
        fetch = httpx.get(
            f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
            headers={"Authorization": f"Zoho-oauthtoken {token}"},
            params={"fields": f"id,{api}"},
            timeout=30,
        )
        stored = str((fetch.json().get("data") or [{}])[0].get(api) or "")
        full = stored == LONG
        print(f"{api:20} WORKS    len={len(stored)} full={full}")
        if full:
            working.append((api, len(stored), full))

    print("-" * 50)
    if working:
        print("Recommended ZOHO_LEAD_NOTES_FIELD:", working[0][0])
    else:
        print("No long-text custom field found. Create one in Zoho CRM (Leads module).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
