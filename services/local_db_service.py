import base64
import logging
import mimetypes
import os
import uuid
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

def _postgres_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        return ""
    # Prisma adds ?schema=public — psycopg2 does not accept that query string.
    return raw.split("?", 1)[0]


class LocalDbError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def check_database() -> dict:
    if not _postgres_url():
        return {
            "ok": False,
            "error": "DATABASE_URL is missing in .env (PostgreSQL connection string).",
        }
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"ok": True, "database": "postgresql"}
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def _connect():
    url = _postgres_url()
    if not url:
        raise LocalDbError(
            "PostgreSQL is not configured. Set DATABASE_URL in .env and run npm run db:push once.",
            status_code=503,
        )
    return psycopg2.connect(url)


WHATSAPP_SENT_MARKER = "[whatsapp:sent]"
EMAIL_SENT_MARKER = "[email:sent]"


def has_whatsapp_sent(contact: dict[str, Any]) -> bool:
    return WHATSAPP_SENT_MARKER in str(contact.get("notes") or "")


def has_email_sent(contact: dict[str, Any]) -> bool:
    return EMAIL_SENT_MARKER in str(contact.get("notes") or "")


def mark_whatsapp_sent(contact_id: str) -> None:
    contact = get_contact(contact_id)
    if not contact or has_whatsapp_sent(contact):
        return

    new_notes = f"{str(contact.get('notes') or '').strip()}\n{WHATSAPP_SENT_MARKER}".strip()
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'UPDATE contacts SET notes = %s, "updatedAt" = %s WHERE id = %s',
                    (new_notes, datetime.utcnow(), contact_id),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to mark WhatsApp sent for %s: %s", contact_id, exc)


def mark_email_sent(contact_id: str) -> None:
    contact = get_contact(contact_id)
    if not contact or has_email_sent(contact):
        return

    new_notes = f"{str(contact.get('notes') or '').strip()}\n{EMAIL_SENT_MARKER}".strip()
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'UPDATE contacts SET notes = %s, "updatedAt" = %s WHERE id = %s',
                    (new_notes, datetime.utcnow(), contact_id),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to mark email sent for %s: %s", contact_id, exc)


def _row_to_contact(row: dict[str, Any]) -> dict[str, Any]:
    sync_status = str(row.get("syncStatus") or "local_only")
    zoho_lead_id = row.get("zohoLeadId")
    if sync_status == "synced_zoho" or zoho_lead_id:
        status = "synced"
        zoho_synced = True
    elif sync_status == "failed":
        status = "failed"
        zoho_synced = False
    else:
        status = "pending"
        zoho_synced = False

    name = row.get("fullName") or ""
    created = row.get("createdAt")
    updated = row.get("updatedAt")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    if hasattr(updated, "isoformat"):
        updated = updated.isoformat()

    return {
        "id": str(row["id"]),
        "name": name,
        "fullName": name,
        "firstName": row.get("firstName") or "",
        "lastName": row.get("lastName") or "",
        "designation": row.get("designation") or "",
        "title": row.get("designation") or "",
        "company": row.get("company") or "",
        "phone": row.get("phone") or "",
        "secondaryPhone": row.get("secondaryPhone") or "",
        "email": row.get("email") or "",
        "secondaryEmail": row.get("secondaryEmail") or "",
        "website": row.get("website") or "",
        "secondaryWebsite": row.get("secondaryWebsite") or "",
        "address": row.get("address") or "",
        "secondaryAddress": row.get("secondaryAddress") or "",
        "socialLinks": row.get("socialLinks") or "",
        "gstNumber": row.get("gstNumber") or "",
        "notes": row.get("notes") or "",
        "cardImageBase64": row.get("cardImageBase64"),
        "syncStatus": sync_status,
        "firebaseId": row.get("firebaseId"),
        "zohoLeadId": zoho_lead_id,
        "source": "localdb",
        "status": status,
        "zohoSynced": zoho_synced,
        "created_at": created or "",
        "lastSync": (
            "Synced to Zoho"
            if status == "synced"
            else "Local PostgreSQL · pending Zoho"
            if sync_status == "local_only"
            else str(updated or "Pending Zoho sync")
        ),
        "channels": {"whatsapp": bool(row.get("phone")), "email": bool(row.get("email"))},
        "whatsappSent": has_whatsapp_sent({"notes": row.get("notes") or ""}),
        "emailSent": has_email_sent({"notes": row.get("notes") or ""}),
    }


def _payload_to_local_body(
    contact_data: dict[str, Any],
    card_image_base64: str | None = None,
) -> dict[str, Any]:
    name = contact_data.get("fullName") or contact_data.get("name") or ""
    first = contact_data.get("firstName") or ""
    last = contact_data.get("lastName") or ""
    if not last and name:
        parts = str(name).strip().split(None, 1)
        first = first or (parts[0] if parts else "")
        last = parts[1] if len(parts) > 1 else (parts[0] if parts else "")

    sync_status = contact_data.get("syncStatus") or "local_only"
    if contact_data.get("zohoLeadId") or contact_data.get("zohoSynced"):
        sync_status = "synced_zoho"

    return {
        "fullName": str(name).strip() or "Contact",
        "firstName": str(first).strip(),
        "lastName": str(last).strip(),
        "designation": str(
            contact_data.get("designation") or contact_data.get("title") or ""
        ).strip(),
        "company": str(contact_data.get("company") or "").strip(),
        "phone": str(contact_data.get("phone") or contact_data.get("phoneNumber") or "").strip(),
        "secondaryPhone": str(contact_data.get("secondaryPhone") or "").strip(),
        "email": str(
            contact_data.get("email") or contact_data.get("emailAddress") or ""
        ).strip(),
        "secondaryEmail": str(contact_data.get("secondaryEmail") or "").strip(),
        "website": str(contact_data.get("website") or "").strip(),
        "secondaryWebsite": str(contact_data.get("secondaryWebsite") or "").strip(),
        "address": str(contact_data.get("address") or "").strip(),
        "secondaryAddress": str(contact_data.get("secondaryAddress") or "").strip(),
        "socialLinks": str(contact_data.get("socialLinks") or "").strip(),
        "gstNumber": str(contact_data.get("gstNumber") or "").strip(),
        "notes": str(contact_data.get("notes") or "").strip(),
        "cardImageBase64": card_image_base64 or contact_data.get("cardImageBase64"),
        "syncStatus": sync_status,
        "zohoLeadId": contact_data.get("zohoLeadId"),
    }


def image_path_to_base64(image_path: str | None) -> str | None:
    if not image_path or not os.path.isfile(image_path):
        return None
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def list_contacts() -> list[dict[str, Any]]:
    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    'SELECT * FROM contacts ORDER BY "createdAt" DESC',
                )
                rows = cur.fetchall()
        return [_row_to_contact(dict(row)) for row in rows]
    except LocalDbError:
        raise
    except Exception as exc:
        logger.error("PostgreSQL list failed: %s", exc)
        return []


def get_contact(contact_id: str) -> dict[str, Any] | None:
    try:
        with _connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_contact(dict(row))
    except LocalDbError:
        raise
    except Exception as exc:
        raise LocalDbError(str(exc)) from exc


def create_contact(
    contact_data: dict[str, Any],
    image_path: str | None = None,
) -> dict[str, Any]:
    body = _payload_to_local_body(
        contact_data,
        image_path_to_base64(image_path),
    )
    contact_id = str(uuid.uuid4())
    now = datetime.utcnow()

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO contacts (
                        id, "fullName", "firstName", "lastName", designation, company,
                        phone, "secondaryPhone", email, "secondaryEmail", website,
                        "secondaryWebsite", address, "secondaryAddress", "socialLinks",
                        "gstNumber", notes, "cardImageBase64", "syncStatus", "zohoLeadId",
                        "createdAt", "updatedAt"
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        contact_id,
                        body["fullName"],
                        body["firstName"],
                        body["lastName"],
                        body["designation"],
                        body["company"],
                        body["phone"],
                        body["secondaryPhone"],
                        body["email"],
                        body["secondaryEmail"],
                        body["website"],
                        body["secondaryWebsite"],
                        body["address"],
                        body["secondaryAddress"],
                        body["socialLinks"],
                        body["gstNumber"],
                        body["notes"],
                        body["cardImageBase64"],
                        body["syncStatus"],
                        body.get("zohoLeadId"),
                        now,
                        now,
                    ),
                )
            conn.commit()
    except LocalDbError:
        raise
    except Exception as exc:
        raise LocalDbError(f"Failed to save contact: {exc}") from exc

    return {"success": True, "id": contact_id, "database": "postgresql"}


def update_contact(contact_id: str, contact_data: dict[str, Any]) -> dict[str, Any]:
    body = _payload_to_local_body(contact_data)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE contacts SET
                        "fullName" = %s, "firstName" = %s, "lastName" = %s,
                        designation = %s, company = %s, phone = %s, "secondaryPhone" = %s,
                        email = %s, "secondaryEmail" = %s, website = %s, "secondaryWebsite" = %s,
                        address = %s, "secondaryAddress" = %s, "socialLinks" = %s,
                        "gstNumber" = %s, notes = %s, "cardImageBase64" = COALESCE(%s, "cardImageBase64"),
                        "syncStatus" = %s, "zohoLeadId" = COALESCE(%s, "zohoLeadId"),
                        "updatedAt" = %s
                    WHERE id = %s
                    """,
                    (
                        body["fullName"],
                        body["firstName"],
                        body["lastName"],
                        body["designation"],
                        body["company"],
                        body["phone"],
                        body["secondaryPhone"],
                        body["email"],
                        body["secondaryEmail"],
                        body["website"],
                        body["secondaryWebsite"],
                        body["address"],
                        body["secondaryAddress"],
                        body["socialLinks"],
                        body["gstNumber"],
                        body["notes"],
                        body["cardImageBase64"],
                        body["syncStatus"],
                        body.get("zohoLeadId"),
                        datetime.utcnow(),
                        contact_id,
                    ),
                )
                if cur.rowcount == 0:
                    return {"success": False, "error": "Contact not found"}
            conn.commit()
    except LocalDbError:
        raise
    except Exception as exc:
        raise LocalDbError(str(exc)) from exc
    return {"success": True, "id": contact_id}


def delete_contact(contact_id: str) -> dict[str, Any]:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
                if cur.rowcount == 0:
                    return {"success": False, "message": "Contact not found"}
            conn.commit()
    except LocalDbError:
        raise
    except Exception as exc:
        raise LocalDbError(str(exc)) from exc
    return {
        "success": True,
        "message": f"Contact {contact_id} deleted from PostgreSQL",
    }


def delete_contact_by_zoho_lead_id(zoho_lead_id: str) -> dict[str, Any]:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM contacts WHERE \"zohoLeadId\" = %s", (zoho_lead_id,))
                deleted = cur.rowcount
            conn.commit()
        return {"success": True, "deleted": deleted}
    except LocalDbError:
        raise
    except Exception as exc:
        raise LocalDbError(str(exc)) from exc


def patch_sync_status(
    contact_id: str,
    *,
    sync_status: str,
    zoho_lead_id: str | None = None,
) -> None:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE contacts
                    SET "syncStatus" = %s, "zohoLeadId" = COALESCE(%s, "zohoLeadId"), "updatedAt" = %s
                    WHERE id = %s
                    """,
                    (sync_status, zoho_lead_id, datetime.utcnow(), contact_id),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to patch sync status for %s: %s", contact_id, exc)


def delete_all_local_db_contacts() -> dict:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM contacts")
                deleted = cur.rowcount
            conn.commit()
        return {"success": True, "deleted": deleted}
    except LocalDbError as exc:
        return {"deleted": 0, "error": str(exc)}
    except Exception as exc:
        logger.warning("PostgreSQL wipe failed: %s", exc)
        return {"deleted": 0, "error": str(exc)}
