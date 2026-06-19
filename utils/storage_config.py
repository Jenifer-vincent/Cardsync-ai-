"""Offline contact storage is browser IndexedDB; online saves go to Zoho CRM."""

VALID_STORAGE_MODES = ("indexeddb",)


def get_contact_storage_mode() -> str:
    return "indexeddb"


def is_client_side_storage() -> bool:
    return True
