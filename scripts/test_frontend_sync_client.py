"""Debug sync-from-local eventName through FastAPI app."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

from fastapi.testclient import TestClient
from main import app
from services.contact_service import _contact_to_zoho_payload

client = TestClient(app)

payload = {
    "fullName": "App Client Test",
    "company": "CardSync QA",
    "phone": "+919876543266",
    "email": "appclient.test@example.com",
    "eventName": "Mall Opening",
    "connectionMode": "online",
    "skipWhatsApp": True,
    "skipEmail": True,
}

built = _contact_to_zoho_payload(payload)
print("Built payload Description:", repr(built.get("Description")))

response = client.post("/api/leads/sync-from-local", json=payload)
print("Status:", response.status_code)
print("Body:", response.json())

leads = client.get("/api/leads")
print("Leads status:", leads.status_code)
for row in leads.json():
    if row.get("name") == "App Client Test":
        print("eventName from API:", repr(row.get("eventName")))
