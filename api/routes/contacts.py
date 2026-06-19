import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.outreach import (
    email_response,
    fire_post_zoho_outreach,
    is_online_mode,
    run_post_zoho_outreach,
    schedule_outreach_for_contact,
    whatsapp_response,
)
from api.schemas import (
    ContactUpdateRequest,
    DuplicateCheckRequest,
    LocalContactBody,
    SyncOutreachOptions,
    SyncStatusBody,
)
from services import contact_storage as storage
from services.contact_service import (
    delete_contact,
    find_duplicate_contacts,
    get_all_contacts,
    save_contact,
    seed_offline_sample_if_empty,
    sync_all_pending_to_zoho,
    sync_contact_to_zoho,
    update_contact,
)
from services.contact_storage import ContactStorageError
from services.local_db_service import LocalDbError
from services.zoho_service import ZohoError, delete_lead, format_zoho_error_message
from utils.file_utils import cleanup_temp_file, save_temp_file, validate_file

router = APIRouter(tags=["Contacts"])
logger = logging.getLogger(__name__)


@router.post("/contacts/check-duplicates")
async def check_duplicates(request: DuplicateCheckRequest):
    return {"duplicates": find_duplicate_contacts(request.model_dump())}


@router.put("/contacts/{contact_id}")
async def update_existing_contact(contact_id: str, request: ContactUpdateRequest):
    result = update_contact(contact_id, request.contact)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Contact not found"))
    return result


@router.post("/contacts")
async def create_contact(
    contact: str = Form(...),
    card: Optional[UploadFile] = File(None),
):
    try:
        contact_data = json.loads(contact)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid contact JSON") from exc

    temp_path = None
    try:
        if card and card.filename:
            if not validate_file(card):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid card image. Supported types: JPG, JPEG, PNG.",
                )
            temp_path = await save_temp_file(card)

        try:
            result = save_contact(contact_data, image_path=temp_path)
        except LocalDbError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to save contact")

        whatsapp_result, email_result = await schedule_outreach_for_contact(
            contact_data,
            online_mode=is_online_mode(contact_data.get("connectionMode")),
            contact_id=result.get("id"),
            skip_whatsapp=bool(contact_data.get("skipWhatsApp")),
            skip_email=bool(contact_data.get("skipEmail")),
        )
        return {
            **result,
            **whatsapp_response(whatsapp_result),
            **email_response(email_result),
        }
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)


@router.get("/contacts", summary="List all local database contacts")
async def fetch_contacts():
    return get_all_contacts()


@router.get("/api/storage/config")
async def storage_config():
    from utils.storage_config import get_contact_storage_mode

    return {
        "storage": get_contact_storage_mode(),
        "database": storage.check_storage(),
    }


@router.get("/api/contacts", summary="List contacts (UI shape)")
async def list_contacts_api():
    return storage.list_contacts()


@router.get("/api/contacts/{contact_id}")
async def get_contact_api(contact_id: str):
    contact = storage.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("/api/contacts", summary="Save contact")
async def create_contact_json(body: LocalContactBody):
    try:
        payload = body.model_dump()
        result = storage.create_contact(payload)
        contact_id = result["id"]
        response: dict[str, Any] = {
            "success": True,
            "id": contact_id,
            "contact": storage.get_contact(contact_id),
        }

        if is_online_mode(body.connectionMode):
            try:
                zoho = sync_contact_to_zoho(contact_id)
                response["zohoLeadId"] = zoho.get("zohoLeadId")
                response["zohoSynced"] = True
                response["alreadySynced"] = zoho.get("alreadySynced", False)
                whatsapp_result, email_result = await run_post_zoho_outreach(
                    contact_id=contact_id,
                    skip_whatsapp=body.skipWhatsApp,
                    skip_email=body.skipEmail,
                    log_context="create-contact",
                )
                response.update(whatsapp_response(whatsapp_result))
                response.update(email_response(email_result))
            except ZohoError as exc:
                response["zohoError"] = format_zoho_error_message(exc)
            except Exception as exc:
                logger.error("Zoho sync on save failed for %s: %s", contact_id, exc, exc_info=True)
                response["zohoError"] = str(exc)

        return response
    except ContactStorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except LocalDbError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/api/contacts/{contact_id}")
async def update_contact_json(contact_id: str, body: LocalContactBody):
    try:
        result = storage.update_contact(contact_id, body.model_dump())
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Contact not found"))
        return {"success": True, "id": contact_id, "contact": storage.get_contact(contact_id)}
    except ContactStorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except LocalDbError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch("/api/contacts/{contact_id}/sync-status")
async def patch_contact_sync_status(contact_id: str, body: SyncStatusBody):
    storage.patch_sync_status(
        contact_id,
        sync_status=body.syncStatus,
        zoho_lead_id=body.zohoLeadId,
    )
    contact = storage.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"success": True, "contact": contact}


@router.delete("/api/contacts/{contact_id}")
async def delete_contact_api(contact_id: str, deleteZoho: bool = False):
    contact = storage.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if deleteZoho and contact.get("zohoLeadId"):
        zoho_lead_id = str(contact.get("zohoLeadId"))
        try:
            delete_lead(zoho_lead_id)
        except ZohoError as exc:
            if exc.status_code == 404:
                logger.warning("Zoho lead %s already deleted when deleting local contact.", zoho_lead_id)
            else:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail=format_zoho_error_message(exc),
                ) from exc

    result = storage.delete_contact(contact_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Contact not found"))
    return result


@router.post("/contacts/seed-sample")
async def seed_offline_sample():
    return seed_offline_sample_if_empty()


@router.post("/contacts/sync-pending-to-zoho")
async def sync_pending_contacts_to_zoho():
    try:
        result = sync_all_pending_to_zoho()
        for item in result.get("results", []):
            contact_id = item.get("id")
            if not item.get("success") or not contact_id:
                continue
            fire_post_zoho_outreach(contact_id=str(contact_id))
            item["outreach_queued"] = True
        return result
    except ZohoError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=format_zoho_error_message(exc),
        ) from exc
    except Exception as exc:
        logger.error("Bulk Zoho sync failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/contacts/{contact_id}/sync-to-zoho")
async def sync_single_contact_to_zoho(
    contact_id: str,
    body: SyncOutreachOptions | None = None,
):
    opts = body or SyncOutreachOptions()
    try:
        result = sync_contact_to_zoho(contact_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Contact not found"))
        whatsapp_result, email_result = await run_post_zoho_outreach(
            contact_id=contact_id,
            skip_whatsapp=opts.skipWhatsApp,
            skip_email=opts.skipEmail,
            log_context="sync-contact",
        )
        result.update(whatsapp_response(whatsapp_result))
        result.update(email_response(email_result))
        return result
    except HTTPException:
        raise
    except ZohoError as exc:
        logger.warning("Zoho sync failed for %s: %s", contact_id, format_zoho_error_message(exc))
        raise HTTPException(
            status_code=exc.status_code,
            detail=format_zoho_error_message(exc),
        ) from exc
    except Exception as exc:
        logger.error("Zoho sync failed for %s: %s", contact_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/contacts/{contact_id}")
async def remove_contact(contact_id: str):
    return delete_contact(contact_id)
