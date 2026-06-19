"""List Zoho Leads fields (search for Event)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

import httpx
from services.zoho_service import ZOHO_API_DOMAIN, get_valid_access_token

token = get_valid_access_token()
url = f"{ZOHO_API_DOMAIN}/crm/v2/settings/fields"
response = httpx.get(
    url,
    headers={"Authorization": f"Zoho-oauthtoken {token}"},
    params={"module": "Leads"},
    timeout=30,
)
print("status", response.status_code)
if response.status_code != 200:
    print(response.text[:800])
    raise SystemExit(1)

fields = response.json().get("fields", [])
hits = [
    f
    for f in fields
    if "event" in f"{f.get('field_label', '')}{f.get('api_name', '')}".lower()
]
print("\nEvent-related fields:")
for field in hits:
    print(
        f"  label={field.get('field_label')} "
        f"api_name={field.get('api_name')} "
        f"type={field.get('data_type')}"
    )

if not hits:
    print("  (none)")
    print("\nCustom fields sample:")
    for field in [f for f in fields if f.get("custom_field")][:20]:
        print(f"  label={field.get('field_label')} api_name={field.get('api_name')}")
