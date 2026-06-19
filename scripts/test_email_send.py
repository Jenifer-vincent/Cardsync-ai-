"""Send a test business thank-you email using Gmail SMTP credentials from .env."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.env_loader import load_env

load_env()

from services.email_service import (  # noqa: E402
    extract_primary_email,
    is_email_configured,
    send_business_thank_you_email,
    send_thank_you_to_contact,
    validate_email_address,
)

DEFAULT_TEST_RECIPIENT = "saligantisandeepzzz6@gmail.com"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a business thank-you email via Gmail SMTP.")
    parser.add_argument(
        "--email",
        default=DEFAULT_TEST_RECIPIENT,
        help=f"Recipient email address (default: {DEFAULT_TEST_RECIPIENT}).",
    )
    parser.add_argument(
        "--from-contact",
        action="store_true",
        help="Treat --email as parsed contact data by wrapping it in a contact dict.",
    )
    parser.add_argument(
        "--override",
        default=DEFAULT_TEST_RECIPIENT,
        help="Force delivery to this address regardless of extracted email.",
    )
    args = parser.parse_args()

    if not is_email_configured():
        print(
            "Email not configured. Set BREVO_API_KEY + BREVO_SENDER_EMAIL, "
            "or BREVO_SMTP_*, or GMAIL_USER + GMAIL_APP_PASSWORD in .env",
            file=sys.stderr,
        )
        return 1

    try:
        if args.from_contact:
            contact = {"email": args.email, "name": "Test Contact", "company": "Test Co"}
            extracted = extract_primary_email(contact)
            ok, detail = validate_email_address(extracted)
            print(f"Extracted email: {extracted!r} (valid={ok}, detail={detail!r})")
            result = send_thank_you_to_contact(contact, test_override=args.override)
        else:
            ok, detail = validate_email_address(args.email)
            print(f"Recipient email: {args.email!r} (valid={ok}, detail={detail!r})")
            result = send_business_thank_you_email(args.email, test_override=args.override)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
