import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.env_loader import load_env

load_env()
token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
v = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0")
h = {"Authorization": f"Bearer {token}"}
waba = sys.argv[1] if len(sys.argv) > 1 else "3295273757438898"

phones = requests.get(
    f"https://graph.facebook.com/{v}/{waba}/phone_numbers?fields=id,display_phone_number,verified_name,status",
    headers=h,
    timeout=30,
).json()
print("PHONES:")
print(json.dumps(phones, indent=2))

templates = requests.get(
    f"https://graph.facebook.com/{v}/{waba}/message_templates?limit=50",
    headers=h,
    timeout=30,
).json()
print("TEMPLATES:")
for t in templates.get("data", []):
    body = next((c.get("text", "") for c in t.get("components", []) if c.get("type") == "BODY"), "")
    print(t.get("name"), t.get("language"), t.get("status"), body[:80])
