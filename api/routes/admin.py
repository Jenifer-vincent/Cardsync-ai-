import logging

from fastapi import APIRouter, HTTPException

from api.schemas import WipeAllDataBody
from services import contact_storage as storage
from services.contact_service import delete_all_contacts
from services.zoho_service import ZohoError, delete_all_leads

router = APIRouter(tags=["Admin"])
logger = logging.getLogger(__name__)


@router.post("/admin/wipe-all-data")
async def wipe_all_data(body: WipeAllDataBody):
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true in the request body to wipe local database and related data.",
        )

    result = {
        "contacts": delete_all_contacts(),
        "storage": storage.storage_label(),
        "zoho": None,
    }
    if body.include_zoho:
        try:
            result["zoho"] = delete_all_leads()
        except ZohoError as exc:
            logger.warning("Zoho wipe skipped or partial: %s", exc)
            result["zoho"] = {"deleted": 0, "error": str(exc)}

    return {"success": True, **result}
