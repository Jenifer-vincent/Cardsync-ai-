from fastapi import APIRouter

from api.routes.admin import router as admin_router
from api.routes.contacts import router as contacts_router
from api.routes.integrations import router as integrations_router
from api.routes.leads import router as leads_router


def build_api_router() -> APIRouter:
    root = APIRouter()
    root.include_router(integrations_router)
    root.include_router(contacts_router)
    root.include_router(leads_router)
    root.include_router(admin_router)
    return root
