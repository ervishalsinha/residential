from fastapi import APIRouter

from app.api.v1.endpoints import (
	admin_db,
	auth,
	complaints,
	dashboard,
	emergency,
	expenses,
	meta,
	notices,
	notifications,
	payments,
	properties,
	residents,
	staff,
	units,
	visitors,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
api_router.include_router(admin_db.router, prefix="/admin/db", tags=["admin-db"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(residents.router, prefix="/residents", tags=["residents"])
api_router.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
api_router.include_router(visitors.router, prefix="/visitors", tags=["visitors"])
api_router.include_router(notices.router, prefix="/notices", tags=["notices"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(staff.router, prefix="/staff", tags=["staff"])
api_router.include_router(units.router, prefix="/units", tags=["units"])
api_router.include_router(emergency.router, prefix="/emergency", tags=["emergency"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
