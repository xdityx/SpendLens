from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.api_title, version=settings.api_version)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
