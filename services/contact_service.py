import logging
import os
import re
from datetime import datetime

from services import contact_storage as storage
from services.contact_storage import ContactStorageError
from services.zoho_service import apply_event_and_notes_to_zoho_payload

logger = logging.getLogger(__name__)


def seed_offline_sample_if_empty():
    existing = get_all_contacts()
    return {
        "seeded": False,
        "message": "Sample seeding disabled — no hardcoded contacts",
        "count": len(existing),
    }


def save_contact(contact_data, image_path=None):
    contact_data = dict(contact_data)
    contact_data.setdefault("created_at", datetime.utcnow().isoformat())
    contact_data.setdefault("source", "localdb")
    contact_data.setdefault("status", "pending")
    contact_data.setdefault("zohoSynced", False)
    contact_data.setdefault("syncStatus", "local_only")

    try:
        return storage.create_contact(contact_data, image_path=image_path)
    except ContactStorageError as exc:
        logger.error("Error saving contact: %s", exc)
        raise


def get_all_contacts():
    try:
        return storage.list_contacts()
    except Exception as exc:
        logger.error("Error reading contacts: %s", exc)
        return []


def delete_all_contacts():
    return storage.delete_all_contacts()


def delete_contact(contact_id: str):
    return storage.delete_contact(contact_id)


def get_contact_by_id(contact_id: str):
    try:
        return storage.get_contact(contact_id)
    except Exception as exc:
        logger.error("Error reading contact: %s", exc)
        return None


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in str(phone or "") if c.isdigit())


def find_duplicate_contacts(contact_data: dict) -> list:
    email = str(contact_data.get("email") or contact_data.get("emailAddress") or "").strip().lower()
    phone = _normalize_phone(contact_data.get("phone") or contact_data.get("phoneNumber") or "")
    name = str(contact_data.get("fullName") or contact_data.get("name") or "").strip().lower()
    company = str(contact_data.get("company") or contact_data.get("companyName") or "").strip().lower()

    duplicates = []
    seen_ids = set()

    for contact in get_all_contacts():
        cid = contact.get("id")
        if not cid or cid in seen_ids:
            continue

        matched_by = []
        c_email = str(contact.get("email") or "").strip().lower()
        c_phone = _normalize_phone(contact.get("phone") or "")
        c_name = str(contact.get("fullName") or contact.get("name") or "").strip().lower()
        c_company = str(contact.get("company") or "").strip().lower()

        if email and c_email and email == c_email:
            matched_by.append("email")
        if phone and c_phone and (phone == c_phone or phone.endswith(c_phone) or c_phone.endswith(phone)):
            matched_by.append("phone")
        if name and company and c_name == name and c_company == company:
            matched_by.append("name_company")

        if matched_by:
            seen_ids.add(cid)
            duplicates.append({"contact": contact, "matchedBy": matched_by})

    return duplicates


def update_contact(contact_id: str, contact_data: dict):
    contact_data = dict(contact_data)
    contact_data["updated_at"] = datetime.utcnow().isoformat()
    result = storage.update_contact(contact_id, contact_data)
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Contact not found")}
    return result


def _clean_company(value: str) -> str:
    """Match legacy Firebase/Node flow; fix common OCR glitches."""
    company = str(value or "").strip()
    if company.startswith("@"):
        company = company[1:].strip()
    return company or "Unknown"


def _normalize_website(value: str) -> str:
    """Add https:// when missing; keep legacy behavior of passing website through."""
    url = str(value or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return "https://" + url.lstrip("/")
    return url


def _contact_to_zoho_payload(contact_data: dict) -> dict:
    """
    Zoho lead fields — same shape as the pre-Firebase Node controller:
    full name in Last_Name, Company required, other fields passed through.
    """
    full_name = str(
        contact_data.get("fullName") or contact_data.get("name") or ""
    ).strip()

    payload = {
        "Last_Name": full_name or "Contact",
        "Company": _clean_company(str(contact_data.get("company") or "")),
        "Designation": str(
            contact_data.get("designation") or contact_data.get("title") or ""
        ).strip(),
        "Street": str(contact_data.get("address") or "").strip(),
        "Phone": str(
            contact_data.get("phone") or contact_data.get("phoneNumber") or ""
        ).strip(),
        "Email": str(
            contact_data.get("email") or contact_data.get("emailAddress") or ""
        ).strip(),
        "Website": _normalize_website(
            str(contact_data.get("website") or "")
        ),
    }
    apply_event_and_notes_to_zoho_payload(
        payload,
        str(contact_data.get("eventName") or ""),
        str(contact_data.get("notes") or ""),
    )
    return payload


def is_zoho_lead_id(value: object) -> bool:
    """Zoho CRM lead ids are long numeric strings (not local UUIDs)."""
    text = str(value or "").strip()
    return text.isdigit() and len(text) >= 10


def sync_payload_to_zoho(contact_data: dict) -> dict:
    """Create a Zoho lead from local PostgreSQL contact fields."""
    from services.zoho_service import (
        ZohoError,
        create_lead,
        extract_lead_id_from_response,
        find_existing_lead_ids,
        resolve_duplicate_lead_id,
        upsert_event_fields_on_lead,
        upsert_event_on_matching_leads,
    )

    existing_id = str(contact_data.get("zohoLeadId") or "").strip()
    if is_zoho_lead_id(existing_id):
        payload = _contact_to_zoho_payload(contact_data)
        upsert_event_on_matching_leads(contact_data, payload)
        upsert_event_fields_on_lead(existing_id, contact_data)
        return {
            "success": True,
            "already_synced": True,
            "zohoLeadId": existing_id,
        }

    payload = _contact_to_zoho_payload(contact_data)
    event_name = str(contact_data.get("eventName") or "").strip()
    if not event_name:
        logger.warning(
            "sync_payload_to_zoho: eventName missing for %s",
            payload.get("Email") or payload.get("Last_Name") or "lead",
        )

    matching_ids = find_existing_lead_ids(payload)
    if matching_ids:
        upsert_event_on_matching_leads(contact_data, payload)
        return {
            "success": True,
            "zohoLeadId": matching_ids[0],
            "already_synced": True,
        }

    try:
        zoho_response = create_lead(payload)
    except ZohoError as exc:
        details = exc.details if isinstance(exc.details, dict) else {}
        if details.get("code") == "DUPLICATE_DATA" or exc.status_code == 409:
            existing_id = resolve_duplicate_lead_id(details, payload)
            if existing_id:
                upsert_event_on_matching_leads(contact_data, payload)
                upsert_event_fields_on_lead(existing_id, contact_data)
                return {
                    "success": True,
                    "zohoLeadId": existing_id,
                    "already_synced": True,
                }
        raise

    zoho_lead_id = extract_lead_id_from_response(zoho_response)
    if not zoho_lead_id:
        raise ZohoError(502, "Zoho did not return a lead id after create.", zoho_response)
    upsert_event_fields_on_lead(zoho_lead_id, contact_data)
    upsert_event_on_matching_leads(contact_data, payload)
    return {
        "success": True,
        "zohoLeadId": zoho_lead_id,
    }


def sync_contact_to_zoho(contact_id: str):
    from services.zoho_service import ZohoError

    contact = get_contact_by_id(contact_id)
    if not contact:
        return {"success": False, "error": "Contact not found"}

    if contact.get("zohoLeadId") or contact.get("zohoSynced"):
        return {
            "success": True,
            "already_synced": True,
            "alreadySynced": True,
            "id": contact_id,
            "zohoLeadId": contact.get("zohoLeadId"),
        }

    try:
        result = sync_payload_to_zoho(contact)
        zoho_lead_id = result.get("zohoLeadId")
    except ZohoError as exc:
        # Rate limits / temporary Zoho outages — keep pending so user can retry
        if exc.status_code not in (429, 503):
            try:
                storage.patch_sync_status(contact_id, sync_status="failed")
            except Exception as update_err:
                logger.error("Failed to mark contact as failed: %s", update_err)
        raise

    storage.patch_sync_status(
        contact_id,
        sync_status="synced_zoho",
        zoho_lead_id=str(zoho_lead_id) if zoho_lead_id else None,
    )

    return {
        "success": True,
        "id": contact_id,
        "zohoLeadId": zoho_lead_id,
        "alreadySynced": False,
    }


def sync_all_pending_to_zoho():
    contacts = get_all_contacts()
    pending = [
        c
        for c in contacts
        if not c.get("zohoLeadId")
        and not c.get("zohoSynced")
        and c.get("status") != "failed"
    ]
    results = []
    synced_count = 0

    for contact in pending:
        contact_id = contact.get("id")
        if not contact_id:
            continue
        try:
            result = sync_contact_to_zoho(contact_id)
            results.append(result)
            if result.get("success"):
                synced_count += 1
        except Exception as exc:
            logger.error("Failed to sync contact %s to Zoho: %s", contact_id, exc)
            results.append({"success": False, "id": contact_id, "error": str(exc)})

    return {
        "success": True,
        "synced": synced_count,
        "total": len(pending),
        "results": results,
    }
