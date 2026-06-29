from fastapi import APIRouter

from app.api.v1 import activity, auth, audit, dashboard, invoices, reconciliation, vendors

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(invoices.router)
api_router.include_router(vendors.router)
api_router.include_router(reconciliation.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
api_router.include_router(activity.router)
