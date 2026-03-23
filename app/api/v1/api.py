from fastapi import APIRouter
from app.api.v1.routers import system

api_router = APIRouter()
api_router.include_router(system.router)