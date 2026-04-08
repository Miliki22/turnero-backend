"""API router composition for v1."""

from fastapi import APIRouter

from app.api.v1.routers import auth, clients, services, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(services.router)
