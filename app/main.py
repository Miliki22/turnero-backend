from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(title=settings.app_name)

# Health público (sin versionar)
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name}

# API versionada
app.include_router(api_router, prefix="/api/v1")