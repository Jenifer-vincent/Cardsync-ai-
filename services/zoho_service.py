import logging
import os
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "")
ZOHO_REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI", "")
ZOHO_ACCOUNTS_URL = os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in")
ZOHO_API_DOMAIN = os.getenv("ZOHO_API_DOMAIN") or os.getenv(
    "ZOHO_API_URL", "https://www.zohoapis.in"
)
ZOHO_ACCESS_TOKEN_FALLBACK = os.getenv("ZOHO_ACCESS_TOKEN", "")

# Map UI / label names to Zoho API field names.
ZOHO_EVENT_FIELD_API_ALIASES: dict[str, str] = {
    "features": "Description",
    "feature": "Description",
    "description": "Description",
}


def zoho_lead_event_field() -> str:
    """Configured event field (label or API name) from live env."""
    return os.getenv("ZOHO_LEAD_EVENT_FIELD", "Features").strip() or "Features"


def zoho_lead_event_api_name() -> str:
    """Resolved Zoho API field name used in CRM requests."""
    field = zoho_lead_event_field()
    return ZOHO_EVENT_FIELD_API_ALIASES.get(field.lower(), field)


def _parse_event_field_value(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("event:"):
            parsed = line.split(":", 1)[1].strip()
            if parsed:
                return parsed
    return text


def zoho_lead_event_fields_to_fetch() -> list[str]:
    """Lead fields requested when listing contacts from Zoho."""
    fields = [
        "id",
        "Last_Name",
        "Company",
        "Designation",
        "Email",
        "Phone",
        "Website",
        "Street",
        "Description",
        "Salutation",
        "Modified_Time",
        "Created_Time",
    ]
    event_field = zoho_lead_event_api_name()
    if event_field not in fields:
        fields.append(event_field)
    return fields


NOTES_LINE_PREFIX = "Notes: "
ZOHO_FEATURES_NOTES_MAX_LENGTH = 2000


def apply_event_and_notes_to_zoho_payload(
    payload: dict,
    event_name: str,
    notes: str = "",
) -> None:
    api_field = zoho_lead_event_api_name()
    existing = str(payload.get(api_field) or "").strip()
    if event_name.strip():
        apply_event_name_to_zoho_payload(payload, event_name)
        existing = str(payload.get(api_field) or "").strip()
    if notes.strip():
        apply_notes_to_zoho_payload(payload, notes)
    elif not event_name.strip() and not existing:
        return


def _parse_notes_from_description(value: object) -> str:
    for line in str(value or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("notes:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def _description_note_lines(existing: str) -> list[str]:
    return [
        line.strip()
        for line in str(existing or "").splitlines()
        if line.strip().lower().startswith("notes:")
    ]


def apply_event_name_to_zoho_payload(payload: dict, event_name: str) -> None:
    """Write event to Zoho Features column (API: Description) as Event: {name}."""
    name = str(event_name or "").strip()
    if not name:
        return

    api_field = zoho_lead_event_api_name()
    existing = str(payload.get(api_field) or "").strip()
    note_lines = _description_note_lines(existing)
    body = f"Event: {name}"
    if note_lines:
        body = f"{body}\n" + "\n".join(note_lines)
    payload[api_field] = body


def apply_notes_to_zoho_payload(payload: dict, notes: str) -> None:
    """Write notes to Zoho Features column (API: Description) as Notes: {text}."""
    text = str(notes or "").strip()
    if not text:
        return

    api_field = zoho_lead_event_api_name()
    existing = str(payload.get(api_field) or "").strip()
    event_name = _parse_event_field_value(existing)
    full = text[:ZOHO_FEATURES_NOTES_MAX_LENGTH]

    event_lines = [
        line.strip()
        for line in existing.splitlines()
        if line.strip().lower().startswith("event:")
    ]
    body_parts = event_lines if event_lines else ([f"Event: {event_name}"] if event_name else [])
    body_parts.append(f"{NOTES_LINE_PREFIX}{full}")
    payload[api_field] = "\n".join(part for part in body_parts if part).strip()


def extract_event_name_from_lead(lead: dict) -> str:
    """Read event from Features (Description) only."""
    api_field = zoho_lead_event_api_name()

    for field_name in (api_field, "Description"):
        parsed = _parse_event_field_value(lead.get(field_name))
        if parsed:
            return parsed
    return ""


def extract_notes_from_lead(lead: dict) -> str:
    """Read notes from Features/Description Notes: line."""
    api_field = zoho_lead_event_api_name()
    for source in (lead.get(api_field), lead.get("Description")):
        parsed = _parse_notes_from_description(source)
        if parsed:
            return parsed
    return ""


_token_cache: dict[str, Any] = {"access_token": "", "expires_at_ms": 0}
_refresh_blocked_until_ms: int = 0


class ZohoError(Exception):
    def __init__(self, status_code: int, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def format_zoho_error_message(exc: "ZohoError") -> str:
    """Human-readable message for API responses and toasts."""
    record = exc.details if isinstance(exc.details, dict) else {}
    oauth_desc = record.get("error_description") or record.get("error")
    if oauth_desc and str(oauth_desc) not in str(exc):
        base = str(oauth_desc).strip()
    else:
        base = str(exc).strip()

    parts = [base or "Zoho request failed."]
    code = record.get("code")
    if code and code not in parts[0]:
        parts.append(f"({code})")
    inner = record.get("details")
    if isinstance(inner, dict):
        api_name = inner.get("api_name")
        if api_name:
            parts.append(f"Check field: {api_name}.")
    if exc.status_code == 429:
        parts.append("Wait 2–3 minutes and try again.")
    if record.get("code") == "INVALID_TOKEN" or exc.status_code == 401:
        parts.append(
            "Check ZOHO_REFRESH_TOKEN in backend/.env or regenerate tokens in Zoho API Console."
        )
    return " ".join(p for p in parts if p)


def _oauth_error_status(detail: Any, http_status: int) -> int:
    desc = ""
    if isinstance(detail, dict):
        desc = str(detail.get("error_description") or detail.get("error") or "")
    if http_status == 429 or "too many requests" in desc.lower():
        return 429
    if http_status in (401, 403):
        return 401
    if http_status >= 500:
        return 503
    return http_status if http_status >= 400 else 502


def _has_refresh_credentials() -> bool:
    return bool(ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN)


def refresh_access_token() -> dict:
    global _refresh_blocked_until_ms

    if not _has_refresh_credentials():
        if ZOHO_ACCESS_TOKEN_FALLBACK:
            return {"access_token": ZOHO_ACCESS_TOKEN_FALLBACK, "expires_in": 3600}
        raise ZohoError(
            500,
            "Zoho credentials are missing. Set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN.",
        )

    now_ms = int(time.time() * 1000)
    if now_ms < _refresh_blocked_until_ms:
        if _token_cache.get("access_token"):
            return {
                "access_token": _token_cache["access_token"],
                "expires_in": max(60, int((_token_cache["expires_at_ms"] - now_ms) / 1000)),
            }
        raise ZohoError(
            429,
            "Zoho token refresh is temporarily rate-limited. Wait 2–3 minutes and try again.",
            None,
        )

    url = f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    if ZOHO_REDIRECT_URI:
        params["redirect_uri"] = ZOHO_REDIRECT_URI

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json() if exc.response.content else str(exc)
        status = _oauth_error_status(detail, exc.response.status_code)
        desc = ""
        if isinstance(detail, dict):
            desc = str(detail.get("error_description") or detail.get("error") or "")
        message = desc.strip() or "Failed to refresh Zoho access token."
        if status == 429:
            _refresh_blocked_until_ms = int(time.time() * 1000) + 180_000
        raise ZohoError(status, message, detail) from exc
    except httpx.RequestError as exc:
        raise ZohoError(502, "Failed to refresh Zoho access token.", str(exc)) from exc

    access_token = data.get("access_token")
    expires_in = int(data.get("expires_in") or 3600)
    if not access_token:
        raise ZohoError(502, "Zoho token refresh failed: access_token missing.")

    _token_cache["access_token"] = access_token
    _token_cache["expires_at_ms"] = int(time.time() * 1000) + max(60, expires_in - 30) * 1000
    return data


def get_valid_access_token() -> str:
    if _token_cache["access_token"] and time.time() * 1000 < _token_cache["expires_at_ms"]:
        return _token_cache["access_token"]
    try:
        data = refresh_access_token()
        return data["access_token"]
    except ZohoError as exc:
        if exc.status_code == 429 and _token_cache.get("access_token"):
            return _token_cache["access_token"]
        raise


def _auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }


def _duplicate_lead_id(record: dict) -> str | None:
    """When Zoho returns DUPLICATE_DATA, reuse the existing CRM record id."""
    inner = record.get("details") or {}
    if not isinstance(inner, dict):
        return None
    duplicate = inner.get("duplicate_record") or {}
    if isinstance(duplicate, dict) and duplicate.get("id"):
        return str(duplicate["id"])
    if inner.get("id"):
        return str(inner["id"])
    return None


def _ensure_zoho_record_success(payload: dict) -> dict:
    """Zoho often returns HTTP 200 with per-record status error in data[]."""
    records = payload.get("data") or []
    if not records:
        raise ZohoError(502, "Zoho returned an empty response.", payload)

    first = records[0]
    if first.get("status") == "error":
        code = first.get("code") or ""
        if code == "DUPLICATE_DATA":
            raise ZohoError(
                409,
                first.get("message") or "Lead already exists in Zoho.",
                first,
            )
        message = first.get("message") or code or "Zoho rejected the lead."
        raise ZohoError(400, str(message), first)

    return payload


def _search_leads_rows(params: dict[str, str]) -> list[dict]:
    """Return all Zoho leads matching search params (email / phone)."""
    if not params:
        return []

    endpoint = f"{ZOHO_API_DOMAIN}/crm/v2/Leads/search"

    def send(token: str) -> httpx.Response:
        with httpx.Client(timeout=20.0) as client:
            return client.get(
                endpoint,
                params=params,
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
            )

    try:
        token = get_valid_access_token()
        response = send(token)
        if response.status_code == 204:
            return []
        if response.status_code >= 400:
            if response.status_code == 401 and _has_refresh_credentials():
                refresh_access_token()
                response = send(get_valid_access_token())
            if response.status_code >= 400:
                return []
        payload = response.json()
        return payload.get("data") or []
    except Exception as exc:
        logger.warning("Zoho lead search failed: %s", exc)
        return []


def _search_leads(params: dict[str, str]) -> str | None:
    """Find an existing lead id via Zoho CRM search (email / phone params)."""
    rows = _search_leads_rows(params)
    if rows and rows[0].get("id"):
        return str(rows[0]["id"])
    return None


def search_lead_ids_by_email(email: str) -> list[str]:
    safe = str(email or "").strip()
    if not safe:
        return []
    return [
        str(row["id"])
        for row in _search_leads_rows({"email": safe})
        if row.get("id")
    ]


def search_lead_ids_by_phone(phone: str) -> list[str]:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) < 7:
        return []
    return [
        str(row["id"])
        for row in _search_leads_rows({"phone": digits})
        if row.get("id")
    ]


def find_existing_lead_ids(lead_payload: dict) -> list[str]:
    """All Zoho lead ids matching email or phone (handles duplicate leads)."""
    seen: set[str] = set()
    ordered: list[str] = []
    email = str(lead_payload.get("Email") or "").strip()
    phone = str(lead_payload.get("Phone") or "").strip()
    for lead_id in search_lead_ids_by_email(email):
        if lead_id not in seen:
            seen.add(lead_id)
            ordered.append(lead_id)
    for lead_id in search_lead_ids_by_phone(phone):
        if lead_id not in seen:
            seen.add(lead_id)
            ordered.append(lead_id)
    return ordered


def upsert_event_on_matching_leads(contact_data: dict, lead_payload: dict) -> list[str]:
    """Write event to every duplicate lead with the same email/phone."""
    event_name = str(contact_data.get("eventName") or "").strip()
    if not event_name:
        return []

    updated: list[str] = []
    for lead_id in find_existing_lead_ids(lead_payload):
        upsert_event_fields_on_lead(lead_id, contact_data)
        updated.append(lead_id)
    return updated


def search_lead_by_email(email: str) -> str | None:
    safe = str(email or "").strip()
    if not safe:
        return None
    return _search_leads({"email": safe})


def search_lead_by_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) < 7:
        return None
    return _search_leads({"phone": digits})


def resolve_duplicate_lead_id(record: dict, lead_payload: dict) -> str | None:
    existing = _duplicate_lead_id(record)
    if existing:
        return existing
    email = lead_payload.get("Email") or ""
    found = search_lead_by_email(email)
    if found:
        return found
    return search_lead_by_phone(lead_payload.get("Phone") or "")


def extract_lead_id_from_response(zoho_response: dict) -> str | None:
    for item in zoho_response.get("data") or []:
        if item.get("status") != "success":
            continue
        details = item.get("details") or {}
        lead_id = details.get("id")
        if lead_id:
            return str(lead_id)
    return None


def create_lead(lead_payload: dict) -> dict:
    endpoint = f"{ZOHO_API_DOMAIN}/crm/v2/Leads"

    def send(token: str) -> httpx.Response:
        with httpx.Client(timeout=20.0) as client:
            return client.post(
                endpoint,
                json={"data": [lead_payload]},
                headers=_auth_headers(token),
            )

    try:
        token = get_valid_access_token()
        response = send(token)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {"raw": response.text[:200]}
            code = str(body.get("code") or "") if isinstance(body, dict) else ""
            if code == "INVALID_TOKEN" and _has_refresh_credentials():
                _token_cache["access_token"] = ""
                _token_cache["expires_at_ms"] = 0
                refresh_access_token()
                response = send(get_valid_access_token())
                if response.status_code >= 400:
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"raw": response.text[:200]}
            if response.status_code >= 400:
                raise ZohoError(
                    response.status_code,
                    "Failed to create lead in Zoho.",
                    body,
                )
        result = _ensure_zoho_record_success(response.json())
        lead_id = extract_lead_id_from_response(result)
        event_field = zoho_lead_event_api_name()
        event_value = str(lead_payload.get(event_field) or "").strip()
        if not event_value and event_field != "Description":
            event_value = str(lead_payload.get("Description") or "").strip()
        if lead_id and event_value:
            # Zoho often drops Description on create; PUT persists Features column.
            update_lead(lead_id, {event_field: event_value})
        return result
    except ZohoError:
        raise
    except Exception as exc:
        raise ZohoError(502, "Failed to create lead in Zoho.", str(exc)) from exc


def update_lead(lead_id: str, lead_payload: dict) -> dict:
    """Update an existing Zoho lead (partial fields)."""
    lead_id = str(lead_id or "").strip()
    if not lead_id:
        raise ZohoError(400, "Lead id is required for update.")

    endpoint = f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}"

    def send(token: str) -> httpx.Response:
        with httpx.Client(timeout=20.0) as client:
            return client.put(
                endpoint,
                json={"data": [lead_payload]},
                headers=_auth_headers(token),
            )

    try:
        token = get_valid_access_token()
        response = send(token)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {"raw": response.text[:200]}
            if (
                isinstance(body, dict)
                and body.get("code") == "INVALID_TOKEN"
                and _has_refresh_credentials()
            ):
                _token_cache["access_token"] = ""
                _token_cache["expires_at_ms"] = 0
                refresh_access_token()
                response = send(get_valid_access_token())
                if response.status_code >= 400:
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"raw": response.text[:200]}
            if response.status_code >= 400:
                raise ZohoError(
                    response.status_code,
                    "Failed to update lead in Zoho.",
                    body,
                )
        if response.status_code == 204 or not (response.content or response.text.strip()):
            return {"data": [{"status": "success", "details": {"id": lead_id}}]}
        return _ensure_zoho_record_success(response.json())
    except ZohoError:
        raise
    except Exception as exc:
        raise ZohoError(502, "Failed to update lead in Zoho.", str(exc)) from exc


def upsert_event_fields_on_lead(lead_id: str | None, contact_data: dict) -> None:
    """Ensure Features/Description has Event: {name} and Notes: {text}."""
    if not lead_id:
        return

    event_name = str(contact_data.get("eventName") or "").strip()
    notes = str(contact_data.get("notes") or "").strip()
    if not event_name and not notes:
        return

    patch: dict = {}
    apply_event_and_notes_to_zoho_payload(patch, event_name, notes)
    if not patch:
        return

    try:
        update_lead(str(lead_id), patch)
    except ZohoError:
        raise
    except Exception as exc:
        raise ZohoError(502, "Failed to update event on Zoho lead.", str(exc)) from exc


def _extract_event_name_from_lead(lead: dict, event_field: str = "") -> str:
    del event_field  # kept for callers; config comes from zoho_lead_event_field()
    return extract_event_name_from_lead(lead)


def get_leads() -> list[dict]:
    endpoint = f"{ZOHO_API_DOMAIN}/crm/v2/Leads"
    params = {"fields": ",".join(zoho_lead_event_fields_to_fetch())}

    def send(token: str) -> httpx.Response:
        with httpx.Client(timeout=20.0) as client:
            return client.get(
                endpoint,
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
                params=params,
            )

    try:
        token = get_valid_access_token()
        response = send(token)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {"raw": response.text[:200]}
            if body.get("code") == "INVALID_TOKEN" and _has_refresh_credentials():
                refresh_access_token()
                response = send(get_valid_access_token())
                if response.status_code >= 400:
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"raw": response.text[:200]}
                    raise ZohoError(response.status_code, "Failed to fetch leads from Zoho.", body)
            elif response.status_code >= 400:
                raise ZohoError(response.status_code, "Failed to fetch leads from Zoho.", body)
        if response.status_code == 204 or not (response.content or response.text.strip()):
            return []
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZohoError(502, "Failed to fetch leads from Zoho.", response.text[:200]) from exc
        data = payload.get("data") or []
        return [
            {
                "id": lead.get("id"),
                "name": lead.get("Last_Name") or "",
                "designation": lead.get("Designation") or "",
                "title": lead.get("Designation") or "",
                "company": lead.get("Company") or "",
                "address": lead.get("Street") or "",
                "phone": lead.get("Phone") or "",
                "email": lead.get("Email") or "",
                "website": lead.get("Website") or "",
                "eventName": extract_event_name_from_lead(lead),
                "notes": extract_notes_from_lead(lead),
                "status": "synced",
                "lastSync": lead.get("Modified_Time") or lead.get("Created_Time") or "Just now",
                "channels": {
                    "whatsapp": bool(lead.get("Phone")),
                    "email": bool(lead.get("Email")),
                },
            }
            for lead in data
        ]
    except ZohoError:
        raise
    except Exception as exc:
        logger.warning("Zoho leads request failed: %s", exc)
        raise ZohoError(502, "Failed to fetch leads from Zoho.", str(exc)) from exc


def delete_all_leads() -> dict:
    """Delete every lead in Zoho CRM (paginated)."""
    deleted = 0
    errors: list[dict] = []
    page = 1
    per_page = 200

    while True:
        endpoint = f"{ZOHO_API_DOMAIN}/crm/v2/Leads"
        params = {
            "fields": "id",
            "page": page,
            "per_page": per_page,
        }

        def send(token: str) -> httpx.Response:
            with httpx.Client(timeout=30.0) as client:
                return client.get(
                    endpoint,
                    headers={"Authorization": f"Zoho-oauthtoken {token}"},
                    params=params,
                )

        token = get_valid_access_token()
        response = send(token)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {"raw": response.text[:200]}
            if body.get("code") == "INVALID_TOKEN" and _has_refresh_credentials():
                refresh_access_token()
                response = send(get_valid_access_token())
            if response.status_code >= 400:
                raise ZohoError(response.status_code, "Failed to list leads for wipe.", body)

        if response.status_code == 204 or not (response.content or response.text.strip()):
            break

        payload = response.json()
        leads = payload.get("data") or []
        if not leads:
            break

        for lead in leads:
            lead_id = lead.get("id")
            if not lead_id:
                continue
            try:
                delete_lead(str(lead_id))
                deleted += 1
            except ZohoError as exc:
                errors.append({"id": lead_id, "error": str(exc)})

        info = payload.get("info") or {}
        if not info.get("more_records"):
            break
        page += 1

    return {"deleted": deleted, "errors": errors}


def delete_lead(lead_id: str) -> dict:
    endpoint = f"{ZOHO_API_DOMAIN}/crm/v2/Leads/{lead_id}"
    try:
        token = get_valid_access_token()
        with httpx.Client(timeout=20.0) as client:
            response = client.delete(
                endpoint,
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
            )
        if response.status_code >= 400:
            raise ZohoError(response.status_code, "Failed to delete lead in Zoho.", response.json())
        return response.json()
    except ZohoError:
        raise
    except Exception as exc:
        raise ZohoError(502, "Failed to delete lead in Zoho.", str(exc)) from exc
