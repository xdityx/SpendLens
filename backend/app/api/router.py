from fastapi import APIRouter, Depends

from app.api.routes import accounts, categories, commitments, dashboard, emi_plans, financial_profile, transactions
from app.core.security import require_api_token


api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_token)])
api_router.include_router(accounts.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(commitments.router)
api_router.include_router(emi_plans.router)
api_router.include_router(financial_profile.router)
api_router.include_router(dashboard.router)
