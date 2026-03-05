from fastapi import APIRouter

from app.api.routes import agents, analytics, auth, calls, forms, health, tenant_config, tenants, webhooks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(tenant_config.router)
api_router.include_router(agents.router)
api_router.include_router(calls.router)
api_router.include_router(forms.router)
api_router.include_router(analytics.router)
api_router.include_router(webhooks.router)
