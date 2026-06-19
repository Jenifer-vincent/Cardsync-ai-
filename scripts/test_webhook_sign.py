"""One-off: POST signed webhook to production (run locally)."""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

SECRET = os.getenv("WHATSAPP_APP_SECRET", "").strip().strip('"').strip("'")
BASE = os.getenv("TEST_WEBHOOK_URL", "https://businessscannercardbackend.onrender.com/webhook")
PHONE = os.getenv("TEST_PHONE", "916309248193")


def main() -> int:
    if not SECRET:
        print("Set WHATSAPP_APP_SECRET in env", file=sys.stderr)
        return 1

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": PHONE,
                                    "type": "text",
                                    "text": {"body": "Hi, verify my number"},
                                    "id": "local-test-msg",
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        BASE,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            print("webhook status:", resp.status)
    except urllib.error.HTTPError as exc:
        print("webhook status:", exc.code, exc.read().decode())

    time.sleep(2)
    status_url = BASE.replace("/webhook", "/integrations/whatsapp/verify-status")
    with urllib.request.urlopen(f"{status_url}?phone={PHONE}", timeout=30) as resp:
        print("verify-status:", resp.read().decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
