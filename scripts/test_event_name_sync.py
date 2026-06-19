"""Verify eventName maps to Zoho Lead Event_Name field on sync."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:5000").rstrip("/")
EVENT_FIELD = os.getenv("ZOHO_LEAD_EVENT_FIELD", "").strip() or "Event_Name"
TEST_EVENT = f"CardSync Test Event {uuid.uuid4().hex[:8]}"


def main() -> int:
    from services.contact_service import _contact_to_zoho_payload

    sample = {
        "fullName": "Event Sync Test",
        "company": "CardSync QA",
        "email": "event-sync-test@example.com",
        "phone": "+919999999999",
        "eventName": TEST_EVENT,
    }
    payload = _contact_to_zoho_payload(sample)
    print("=== Local payload mapping ===")
    print(f"ZOHO_LEAD_EVENT_FIELD={EVENT_FIELD}")
    print(f"eventName in payload: {payload.get(EVENT_FIELD)!r}")
    if payload.get(EVENT_FIELD) != TEST_EVENT:
        print("FAIL: event name not mapped into Zoho payload")
        return 1

    body = {
        **sample,
        "skipWhatsApp": True,
        "skipEmail": True,
        "connectionMode": "online",
    }
    print(f"\nPOST {API_BASE}/api/leads/sync-from-local")
    with httpx.Client(timeout=60.0) as client:
        health = client.get(f"{API_BASE}/health")
        if health.status_code != 200:
            print(f"Backend not healthy: {health.status_code}")
            return 1

        sync = client.post(f"{API_BASE}/api/leads/sync-from-local", json=body)
        print(f"Sync status: {sync.status_code}")
        sync_data = sync.json() if sync.content else {}
        print(json.dumps(sync_data, indent=2))
        if not sync.is_success:
            return 1

        lead_id = sync_data.get("zohoLeadId")
        if not lead_id:
            print("FAIL: no zohoLeadId returned")
            return 1

        leads = client.get(f"{API_BASE}/api/leads")
        if not leads.is_success:
            print(f"FAIL: could not list leads ({leads.status_code})")
            return 1

        rows = leads.json()
        match = next((r for r in rows if str(r.get("id")) == str(lead_id)), None)
        if not match:
            print(f"WARN: lead {lead_id} not in list yet; checking latest row with event filter")
            match = next((r for r in rows if r.get("eventName") == TEST_EVENT), None)

        print("\n=== Lead from Zoho (via API) ===")
        print(json.dumps(match, indent=2) if match else "No matching lead row")
        stored = (match or {}).get("eventName") if match else None
        if stored == TEST_EVENT:
            print(f"\nPASS: Event Name stored in Zoho as {stored!r}")
            return 0

        print(f"\nFAIL: expected eventName {TEST_EVENT!r}, got {stored!r}")
        print("Tip: confirm Zoho field API name matches ZOHO_LEAD_EVENT_FIELD in backend/.env")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
