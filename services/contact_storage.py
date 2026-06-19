"""Unified contact storage — backend selection via CONTACT_STORAGE env."""
from typing import Any

from utils.storage_config import get_contact_storage_mode, is_client_side_storage


class ContactStorageError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def storage_label() -> str:
    return get_contact_storage_mode()


def check_storage() -> dict[str, Any]:
    mode = get_contact_storage_mode()
    if mode == "indexeddb":
        return {
            "ok": True,
            "storage": "indexeddb",
            "note": "Contacts are stored in the browser (IndexedDB). API persistence is disabled.",
        }
    if mode == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.check_firebase()
    from services.local_db_service import check_database

    result = check_database()
    result["storage"] = "postgresql"
    return result


def list_contacts() -> list[dict[str, Any]]:
    if is_client_side_storage():
        return []
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.list_contacts()
    from services import local_db_service as local_db

    return local_db.list_contacts()


def get_contact(contact_id: str) -> dict[str, Any] | None:
    if is_client_side_storage():
        return None
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.get_contact(contact_id)
    from services import local_db_service as local_db

    return local_db.get_contact(contact_id)


def create_contact(contact_data: dict[str, Any], image_path: str | None = None) -> dict[str, Any]:
    if is_client_side_storage():
        raise ContactStorageError(
            "CONTACT_STORAGE=indexeddb — save contacts in the browser (IndexedDB), not via this API.",
            status_code=501,
        )
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.create_contact(contact_data, image_path=image_path)
    from services import local_db_service as local_db

    return local_db.create_contact(contact_data, image_path=image_path)


def update_contact(contact_id: str, contact_data: dict[str, Any]) -> dict[str, Any]:
    if is_client_side_storage():
        raise ContactStorageError("CONTACT_STORAGE=indexeddb — update contacts in the browser.", status_code=501)
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.update_contact(contact_id, contact_data)
    from services import local_db_service as local_db

    return local_db.update_contact(contact_id, contact_data)


def delete_contact(contact_id: str) -> dict[str, Any]:
    if is_client_side_storage():
        raise ContactStorageError("CONTACT_STORAGE=indexeddb — delete contacts in the browser.", status_code=501)
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.delete_contact(contact_id)
    from services import local_db_service as local_db

    return local_db.delete_contact(contact_id)


def delete_all_contacts() -> dict[str, Any]:
    if is_client_side_storage():
        return {"deleted": 0, "note": "indexeddb mode — clear browser data from Settings"}
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        return firebase.delete_all_contacts()
    from services import local_db_service as local_db

    return local_db.delete_all_local_db_contacts()


def patch_sync_status(
    contact_id: str,
    sync_status: str,
    zoho_lead_id: str | None = None,
) -> None:
    if is_client_side_storage():
        return
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        firebase.patch_sync_status(contact_id, sync_status, zoho_lead_id)
        return
    from services import local_db_service as local_db

    local_db.patch_sync_status(contact_id, sync_status, zoho_lead_id)


def mark_whatsapp_sent(contact_id: str) -> None:
    if is_client_side_storage():
        return
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        firebase.append_note_marker(contact_id, "[whatsapp:sent]")
        return
    from services import local_db_service as local_db

    local_db.mark_whatsapp_sent(contact_id)


def mark_email_sent(contact_id: str) -> None:
    if is_client_side_storage():
        return
    if get_contact_storage_mode() == "firebase":
        from services import firebase_storage_service as firebase

        firebase.append_note_marker(contact_id, "[email:sent]")
        return
    from services import local_db_service as local_db

    local_db.mark_email_sent(contact_id)


def has_whatsapp_sent(contact: dict[str, Any]) -> bool:
    if get_contact_storage_mode() == "firebase":
        return "[whatsapp:sent]" in str(contact.get("notes") or "")
    from services import local_db_service as local_db

    return local_db.has_whatsapp_sent(contact)


def has_email_sent(contact: dict[str, Any]) -> bool:
    if get_contact_storage_mode() == "firebase":
        return "[email:sent]" in str(contact.get("notes") or "")
    from services import local_db_service as local_db

    return local_db.has_email_sent(contact)
