from fastapi import APIRouter

from app.api.routes import accounts, categories, commitments, dashboard, financial_profile, transactions


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(accounts.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(commitments.router)
api_router.include_router(financial_profile.router)
api_router.include_router(dashboard.router)
