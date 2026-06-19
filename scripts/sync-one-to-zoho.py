#!/usr/bin/env python3
"""Sync one pending local contact to Zoho CRM. Usage: python scripts/sync-one-to-zoho.py [contact_id]"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

from services.contact_service import sync_contact_to_zoho  # noqa: E402
from services.local_db_service import list_contacts  # noqa: E402
from services.zoho_service import ZohoError, format_zoho_error_message  # noqa: E402


def main() -> int:
    contact_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not contact_id:
        pending = [
            c
            for c in list_contacts()
            if c.get("syncStatus") != "synced_zoho" and not c.get("zohoLeadId")
        ]
        if not pending:
            print("No contacts pending Zoho sync.")
            return 0
        contact_id = pending[0]["id"]
        print(f"Using first pending contact: {pending[0].get('fullName')} ({contact_id})")

    try:
        result = sync_contact_to_zoho(contact_id)
        print("Synced to Zoho:", result)
        return 0
    except ZohoError as exc:
        print("Zoho sync failed:", format_zoho_error_message(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
