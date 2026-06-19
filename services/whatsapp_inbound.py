"""User-initiated WhatsApp chat flow: register pending contacts and auto-reply in Chats."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from services.whatsapp_verify_store import load_all, persist_snapshot
from services.whatsapp_service import (
    build_scan_thank_you_text,
    extract_address,
    extract_company_name,
    extract_contact_name,
    extract_designation,
    extract_primary_email,
    extract_website,
    is_whatsapp_configured,
    normalize_whatsapp_phone,
    send_whatsapp_text,
)

logger = logging.getLogger(__name__)

_PENDING_TTL_SECONDS = 48 * 60 * 60
_VERIFIED_TTL_SECONDS = 24 * 60 * 60
_PENDING: dict[str, dict[str, Any]] = {}
_VERIFIED: dict[str, float] = {}
_REPLIED: dict[str, float] = {}
_REPLY_DEDUPE_SECONDS = 300


def _hydrate_from_disk() -> None:
    snapshot = load_all()
    _PENDING.update(snapshot.get("pending") or {})
    _VERIFIED.update({k: float(v) for k, v in (snapshot.get("verified") or {}).items()})
    _REPLIED.update({k: float(v) for k, v in (snapshot.get("replied") or {}).items()})


def _persist() -> None:
    persist_snapshot(_PENDING, _VERIFIED, _REPLIED)


_hydrate_from_disk()


def build_verify_ack_text(contact_name: str = "") -> str:
    greeting = f"Hi {(contact_name or 'there').strip().split()[0]}! " if contact_name else ""
    return (
        f"{greeting}Thank you - your WhatsApp number is verified with CardSync. "
        "Your business card details will be sent here shortly."
    )


def _purge_expired() -> None:
    now = time.time()
    expired = [key for key, entry in _PENDING.items() if entry.get("expires_at", 0) <= now]
    for key in expired:
        _PENDING.pop(key, None)
    stale_verified = [key for key, ts in _VERIFIED.items() if now - ts > _VERIFIED_TTL_SECONDS]
    for key in stale_verified:
        _VERIFIED.pop(key, None)
    stale_replies = [key for key, ts in _REPLIED.items() if now - ts > _REPLY_DEDUPE_SECONDS]
    for key in stale_replies:
        _REPLIED.pop(key, None)
    if expired or stale_verified or stale_replies:
        _persist()


def is_phone_whatsapp_verified(phone: str) -> bool:
    _purge_expired()
    try:
        normalized = normalize_whatsapp_phone(phone)
    except ValueError:
        return False
    return normalized in _VERIFIED


def get_phone_verify_status(phone: str) -> dict[str, Any]:
    _purge_expired()
    try:
        normalized = normalize_whatsapp_phone(phone)
    except ValueError as exc:
        return {"verified": False, "error": str(exc)}
    verified_at = _VERIFIED.get(normalized)
    return {
        "verified": bool(verified_at),
        "normalized_phone": normalized,
        "verified_at": verified_at,
    }


def _mark_verified(normalized_phone: str) -> None:
    _VERIFIED[normalized_phone] = time.time()
    _persist()


def _is_verify_intent_message(message: dict[str, Any]) -> bool:
    text = extract_inbound_message_text(message).lower().strip()
    return "verify" in text


def build_chat_reply_text(contact: dict[str, Any]) -> str:
    """Session reply sent after the contact messages us first (appears in Chats)."""
    contact_name = extract_contact_name(contact) or "there"
    first_name = contact_name.strip().split()[0]
    company = extract_company_name(contact)
    title = extract_designation(contact)
    email = extract_primary_email(contact)
    website = extract_website(contact)
    address = extract_address(contact)

    lines = [
        f"Hi {first_name}, thank you for connecting on WhatsApp!",
        "",
        "We saved your business card in CardSync:",
        f"Name: {contact_name}",
    ]
    if company:
        lines.append(f"Company: {company}")
    if title:
        lines.append(f"Title: {title}")
    if email:
        lines.append(f"Email: {email}")
    if website:
        lines.append(f"Website: {website}")
    if address:
        lines.append(f"Address: {address}")
    lines.extend(["", "Reply here anytime if you need to update your details."])
    return "\n".join(lines)


def register_pending_chat_reply(
    contact: dict[str, Any],
    *,
    verify_only: bool = False,
) -> dict[str, Any]:
    """Store contact details keyed by phone; auto-reply when that number messages us."""
    _purge_expired()
    phone = extract_primary_phone_from_contact(contact)
    if not phone:
        raise ValueError("No primary phone number on the contact.")

    normalized = normalize_whatsapp_phone(phone)
    _PENDING[normalized] = {
        "contact": dict(contact),
        "expires_at": time.time() + _PENDING_TTL_SECONDS,
        "registered_at": time.time(),
        "verify_only": verify_only,
    }
    _persist()
    logger.info(
        "Registered WhatsApp chat-reply pending for %s (verify_only=%s)",
        normalized,
        verify_only,
    )
    return {
        "registered": True,
        "recipient_phone": phone,
        "normalized_phone": normalized,
        "preview_message": (
            build_verify_ack_text(extract_contact_name(contact))
            if verify_only
            else build_chat_reply_text(contact)
        ),
        "verify_only": verify_only,
    }


def extract_primary_phone_from_contact(contact: dict[str, Any]) -> str:
    for key in ("phone", "phoneNumber", "primaryPhone"):
        value = str(contact.get(key) or "").strip()
        if value:
            return value
    phones = contact.get("phones") or []
    if isinstance(phones, list):
        for value in phones:
            text = str(value or "").strip()
            if text:
                return text
    return ""


def _should_auto_reply(normalized_phone: str) -> bool:
    last = _REPLIED.get(normalized_phone, 0)
    return time.time() - last >= _REPLY_DEDUPE_SECONDS


def _mark_replied(normalized_phone: str) -> None:
    _REPLIED[normalized_phone] = time.time()
    _persist()


async def handle_inbound_whatsapp_message(from_phone: str, message: dict[str, Any]) -> None:
    """Auto-reply in the open customer service window when a pending contact messages us."""
    if not is_whatsapp_configured():
        return

    try:
        normalized = normalize_whatsapp_phone(from_phone)
    except ValueError:
        logger.warning("Inbound WhatsApp from invalid phone: %s", from_phone)
        return

    _purge_expired()
    pending = _PENDING.get(normalized)
    verify_intent = _is_verify_intent_message(message)
    if not pending:
        if verify_intent:
            _mark_verified(normalized)
            logger.info(
                "Inbound WhatsApp from %s — verified via message intent (no pending registration).",
                normalized,
            )
        else:
            logger.info("Inbound WhatsApp from %s — no pending chat-reply registration.", normalized)
        return

    _mark_verified(normalized)

    if not _should_auto_reply(normalized):
        logger.info("Inbound WhatsApp from %s — auto-reply skipped (dedupe).", normalized)
        return

    contact = pending.get("contact") or {}
    contact_name = extract_contact_name(contact)
    if pending.get("verify_only"):
        body = build_verify_ack_text(contact_name)
    else:
        body = build_chat_reply_text(contact)
    fallback = build_scan_thank_you_text(
        contact_name,
        extract_company_name(contact),
        extract_designation(contact),
    )

    try:
        await asyncio.to_thread(send_whatsapp_text, from_phone, body or fallback)
        _mark_replied(normalized)
        logger.info(
            "WhatsApp chat-reply sent to %s (user-initiated thread, verify_only=%s).",
            normalized,
            pending.get("verify_only"),
        )
    except Exception as exc:
        logger.error("WhatsApp chat-reply failed for %s: %s", normalized, exc, exc_info=True)


def extract_inbound_message_text(message: dict[str, Any]) -> str:
    msg_type = message.get("type")
    if msg_type == "text":
        return str(message.get("text", {}).get("body") or "")
    if msg_type == "button":
        return str(message.get("button", {}).get("text") or "")
    interactive = message.get("interactive") or {}
    if interactive.get("type") == "button_reply":
        return str(interactive.get("button_reply", {}).get("title") or "")
    if interactive.get("type") == "list_reply":
        return str(interactive.get("list_reply", {}).get("title") or "")
    return ""
