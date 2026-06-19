"""Scan the MetroAxis test card and queue WhatsApp to the extracted primary phone."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "tests" / "fixtures" / "metroaxis-test-card.png"
API = "http://127.0.0.1:5000"


def main() -> int:
    if not CARD.is_file():
        print(f"Missing test card: {CARD}", file=sys.stderr)
        return 1

    with CARD.open("rb") as handle:
        response = requests.post(
            f"{API}/scan-card",
            files={"card": ("metroaxis-test-card.png", handle, "image/png")},
            data={"connection_mode": "online"},
            timeout=120,
        )

    print("status", response.status_code)
    try:
        payload = response.json()
    except ValueError:
        print(response.text[:800], file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    contact = payload.get("contact") or {}
    phone = contact.get("phone") or (contact.get("phones") or [None])[0]
    print("\nExtracted phone:", phone or "NONE")
    print("WhatsApp to:", payload.get("whatsapp_to"))
    print("Recipient:", payload.get("whatsapp_recipient_name"))
    print("Message:", payload.get("whatsapp_message"))
    print("WhatsApp sent:", payload.get("whatsapp_sent"))
    print("WhatsApp error:", payload.get("whatsapp_error"))
    return 0 if response.ok and payload.get("success") and payload.get("whatsapp_sent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
