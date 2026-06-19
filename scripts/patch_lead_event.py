"""Set Event on an existing Zoho lead (Features / Description column)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

from services.zoho_service import get_leads, upsert_event_fields_on_lead


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch event name on a Zoho lead")
    parser.add_argument("--event", required=True, help='Event name, e.g. "Mall Opening"')
    parser.add_argument("--email", help="Match lead by email")
    parser.add_argument("--lead-id", help="Zoho lead id")
    args = parser.parse_args()

    lead_id = (args.lead_id or "").strip()
    email = (args.email or "").strip().lower()

    if not lead_id:
        if not email:
            print("Provide --lead-id or --email")
            return 1
        match = next(
            (row for row in get_leads() if str(row.get("email") or "").lower() == email),
            None,
        )
        if not match:
            print(f"No lead found for email {email!r}")
            return 1
        lead_id = str(match["id"])

    upsert_event_fields_on_lead(lead_id, {"eventName": args.event})
    print(f"Updated lead {lead_id} -> Event: {args.event}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
