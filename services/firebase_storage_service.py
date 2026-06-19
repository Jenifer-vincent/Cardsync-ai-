import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_firestore_client = None
_init_error: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _credentials_path() -> str:
    raw = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip().strip('"').strip("'")
    if not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        path = _project_root() / raw
    return str(path)


def _init_firestore():
    global _firestore_client, _init_error
    if _firestore_client is not None:
        return _firestore_client
    if _init_error:
        raise RuntimeError(_init_error)

    cred_path = _credentials_path()
    if not cred_path or not os.path.isfile(cred_path):
        _init_error = (
            "Firebase storage requires FIREBASE_CREDENTIALS_PATH pointing to a service-account JSON file."
        )
        raise RuntimeError(_init_error)

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        _init_error = "firebase-admin is not installed. Run: pip install firebase-admin"
        raise RuntimeError(_init_error) from exc

    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        options = {}
        bucket = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
        if bucket:
            options["storageBucket"] = bucket
        firebase_admin.initialize_app(cred, options or None)

    _firestore_client = firestore.client()
    return _firestore_client


def check_firebase() -> dict[str, Any]:
    try:
        db = _init_firestore()
        # Lightweight read — collection metadata
        _ = db.collection("contacts").limit(1)
        return {"ok": True, "storage": "firebase"}
    except Exception as exc:
        logger.warning("Firebase health check failed: %s", exc)
        return {"ok": False, "storage": "firebase", "error": str(exc)}


def _payload_to_doc(contact_data: dict[str, Any]) -> dict[str, Any]:
    name = contact_data.get("fullName") or contact_data.get("name") or "Contact"
    return {
        "fullName": str(name).strip(),
        "firstName": str(contact_data.get("firstName") or "").strip(),
        "lastName": str(contact_data.get("lastName") or "").strip(),
        "designation": str(contact_data.get("designation") or contact_data.get("title") or "").strip(),
        "company": str(contact_data.get("company") or "").strip(),
        "phone": str(contact_data.get("phone") or contact_data.get("phoneNumber") or "").strip(),
        "secondaryPhone": str(contact_data.get("secondaryPhone") or "").strip(),
        "email": str(contact_data.get("email") or contact_data.get("emailAddress") or "").strip(),
        "secondaryEmail": str(contact_data.get("secondaryEmail") or "").strip(),
        "website": str(contact_data.get("website") or "").strip(),
        "secondaryWebsite": str(contact_data.get("secondaryWebsite") or "").strip(),
        "address": str(contact_data.get("address") or "").strip(),
        "secondaryAddress": str(contact_data.get("secondaryAddress") or "").strip(),
        "socialLinks": str(contact_data.get("socialLinks") or "").strip(),
        "gstNumber": str(contact_data.get("gstNumber") or "").strip(),
        "notes": str(contact_data.get("notes") or "").strip(),
        "cardImageBase64": contact_data.get("cardImageBase64"),
        "syncStatus": contact_data.get("syncStatus") or "local_only",
        "zohoLeadId": contact_data.get("zohoLeadId"),
        "updatedAt": datetime.utcnow().isoformat(),
    }


def _doc_to_contact(doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
    sync_status = str(data.get("syncStatus") or "local_only")
    zoho_lead_id = data.get("zohoLeadId")
    if sync_status == "synced_zoho" or zoho_lead_id:
        status = "synced"
    elif sync_status == "failed":
        status = "failed"
    else:
        status = "pending"

    name = data.get("fullName") or ""
    created = data.get("createdAt") or ""
    updated = data.get("updatedAt") or ""

    return {
        "id": doc_id,
        "name": name,
        "fullName": name,
        "firstName": data.get("firstName") or "",
        "lastName": data.get("lastName") or "",
        "designation": data.get("designation") or "",
        "title": data.get("designation") or "",
        "company": data.get("company") or "",
        "phone": data.get("phone") or "",
        "secondaryPhone": data.get("secondaryPhone") or "",
        "email": data.get("email") or "",
        "secondaryEmail": data.get("secondaryEmail") or "",
        "website": data.get("website") or "",
        "secondaryWebsite": data.get("secondaryWebsite") or "",
        "address": data.get("address") or "",
        "secondaryAddress": data.get("secondaryAddress") or "",
        "socialLinks": data.get("socialLinks") or "",
        "gstNumber": data.get("gstNumber") or "",
        "notes": data.get("notes") or "",
        "cardImageBase64": data.get("cardImageBase64"),
        "syncStatus": sync_status,
        "firebaseId": doc_id,
        "zohoLeadId": zoho_lead_id,
        "source": "firebase",
        "status": status,
        "zohoSynced": status == "synced",
        "created_at": created,
        "lastSync": "Synced to Zoho" if status == "synced" else "Firebase · pending Zoho",
        "channels": {"whatsapp": bool(data.get("phone")), "email": bool(data.get("email"))},
        "whatsappSent": "[whatsapp:sent]" in str(data.get("notes") or ""),
        "emailSent": "[email:sent]" in str(data.get("notes") or ""),
    }


def list_contacts() -> list[dict[str, Any]]:
    db = _init_firestore()
    docs = db.collection("contacts").stream()
    contacts = []
    for doc in docs:
        data = doc.to_dict() or {}
        contacts.append(_doc_to_contact(doc.id, data))
    contacts.sort(key=lambda c: c.get("created_at") or "", reverse=True)
    return contacts


def get_contact(contact_id: str) -> dict[str, Any] | None:
    db = _init_firestore()
    snap = db.collection("contacts").document(contact_id).get()
    if not snap.exists:
        return None
    return _doc_to_contact(snap.id, snap.to_dict() or {})


def create_contact(contact_data: dict[str, Any], image_path: str | None = None) -> dict[str, Any]:
    del image_path  # card image is passed as base64 in contact_data
    db = _init_firestore()
    contact_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    body = _payload_to_doc(contact_data)
    body["createdAt"] = now
    db.collection("contacts").document(contact_id).set(body)
    return {"success": True, "id": contact_id, "database": "firebase"}


def update_contact(contact_id: str, contact_data: dict[str, Any]) -> dict[str, Any]:
    db = _init_firestore()
    ref = db.collection("contacts").document(contact_id)
    if not ref.get().exists:
        return {"success": False, "error": "Contact not found"}
    body = _payload_to_doc(contact_data)
    ref.set(body, merge=True)
    return {"success": True, "id": contact_id}


def delete_contact(contact_id: str) -> dict[str, Any]:
    db = _init_firestore()
    ref = db.collection("contacts").document(contact_id)
    if not ref.get().exists:
        return {"success": False, "message": "Contact not found"}
    ref.delete()
    return {"success": True, "message": f"Contact {contact_id} deleted from Firebase"}


def delete_all_contacts() -> dict[str, Any]:
    db = _init_firestore()
    batch = db.batch()
    count = 0
    for doc in db.collection("contacts").stream():
        batch.delete(doc.reference)
        count += 1
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
    if count % 400 != 0:
        batch.commit()
    return {"deleted": count}


def patch_sync_status(
    contact_id: str,
    sync_status: str,
    zoho_lead_id: str | None = None,
) -> None:
    db = _init_firestore()
    ref = db.collection("contacts").document(contact_id)
    payload: dict[str, Any] = {"syncStatus": sync_status, "updatedAt": datetime.utcnow().isoformat()}
    if zoho_lead_id:
        payload["zohoLeadId"] = zoho_lead_id
    ref.set(payload, merge=True)


def append_note_marker(contact_id: str, marker: str) -> None:
    contact = get_contact(contact_id)
    if not contact or marker in str(contact.get("notes") or ""):
        return
    notes = f"{str(contact.get('notes') or '').strip()}\n{marker}".strip()
    db = _init_firestore()
    db.collection("contacts").document(contact_id).set(
        {"notes": notes, "updatedAt": datetime.utcnow().isoformat()},
        merge=True,
    )
