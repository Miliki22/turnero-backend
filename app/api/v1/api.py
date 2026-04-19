"""API router composition for v1."""

from fastapi import APIRouter

from app.api.v1.routers import appointments, auth, clients, integrations_google, services, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(services.router)
api_router.include_router(appointments.router)
api_router.include_router(integrations_google.router)
