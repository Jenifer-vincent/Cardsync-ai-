"""Find Zoho Lead fields that accept plain text event names."""
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

CANDIDATES = [
    "Skype_ID",
    "Fax",
    "Secondary_Email",
    "Salutation",
    "Tag",
    "Test",
    "Twitter",
    "Website",
    "Designation",
    "Description",
]
TEST = "Mall Opening"


def main() -> None:
    token = get_valid_access_token()
    print("Testing which fields store plain text:", TEST)
    print("-" * 50)
    working: list[str] = []

    for api in CANDIDATES:
        name = f"Probe {api} {uuid.uuid4().hex[:3]}"
        body = {"data": [{"Last_Name": name, "Company": "CardSync QA", api: TEST}]}
        try:
            create = httpx.post(
                f"{ZOHO_API_DOMAIN}/crm/v2/Leads",
                headers={
                    "Authorization": f"Zoho-oauthtoken {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30,
            )
            row = (create.json().get("data") or [{}])[0]
            if row.get("status") != "success":
                code = row.get("code")
                message = row.get("message")
                print(f"{api:20} BLOCKED  {code} {message}")
                continue

            lead_id = (row.get("details") or {}).get("id")
            fetch = httpx.get(
                f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                params={"fields": f"id,{api}"},
                timeout=30,
            )
            data = (fetch.json().get("data") or [{}])[0]
            stored = data.get(api)
            if stored == TEST:
                print(f"{api:20} WORKS    stores event text OK")
                working.append(api)
            elif api in data and stored:
                print(f"{api:20} PARTIAL  stored={stored!r}")
            elif api in data:
                print(f"{api:20} EMPTY    field exists but null")
            else:
                print(f"{api:20} NO API   field not exposed")
        except Exception as exc:
            print(f"{api:20} ERROR    {exc}")

    print("-" * 50)
    if working:
        print("Use one of these API names in ZOHO_LEAD_EVENT_FIELD:", ", ".join(working))
    else:
        print("Only Description is reliable on this Zoho plan.")


if __name__ == "__main__":
    main()
