"""Fetch a Zoho lead with candidate event field API names."""
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
from services.zoho_service import ZOHO_API_DOMAIN, get_valid_access_token

LEAD_ID = sys.argv[1] if len(sys.argv) > 1 else "1326662000000682002"
CANDIDATES = [
    "Event_Name",
    "EventName",
    "Twitter",
    "Skype_ID",
    "Secondary_Email",
    "Description",
]

token = get_valid_access_token()
fields = ",".join(["id", "Last_Name", "Company", *CANDIDATES])
response = httpx.get(
    f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{LEAD_ID}",
    headers={"Authorization": f"Zoho-oauthtoken {token}"},
    params={"fields": fields},
    timeout=30,
)
print("status", response.status_code)
print(json.dumps(response.json(), indent=2))
