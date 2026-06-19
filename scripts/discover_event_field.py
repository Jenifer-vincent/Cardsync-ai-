"""Discover Zoho Lead field that stores event text (label may be 'Event Name')."""
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
from services.zoho_service import ZOHO_API_DOMAIN, get_leads, get_valid_access_token

# Common Leads fields + likely custom names for label "Event Name"
CANDIDATES = [
    "Event_Name",
    "EventName",
    "Event",
    "Event_name",
    "Custom_Event_Name",
    "Twitter",
    "Skype_ID",
    "Description",
    "Lead_Source",
    "Tag",
]

token = get_valid_access_token()
leads = get_leads()
if not leads:
    print("No leads found")
    raise SystemExit(1)

lead_id = leads[0]["id"]
fields = ",".join(["id", "Last_Name", *CANDIDATES])
response = httpx.get(
    f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}",
    headers={"Authorization": f"Zoho-oauthtoken {token}"},
    params={"fields": fields},
    timeout=30,
)
print("Lead id:", lead_id)
print("status:", response.status_code)
body = response.json()
print(json.dumps(body, indent=2))

row = (body.get("data") or [{}])[0]
print("\nNon-empty candidate fields:")
for name in CANDIDATES:
    value = row.get(name)
    if value not in (None, "", []):
        print(f"  {name} = {value!r}")

print("\nLeads with parsed eventName from get_leads():")
for lead in leads[:10]:
    if lead.get("eventName"):
        print(f"  {lead.get('name')!r} -> {lead.get('eventName')!r}")
