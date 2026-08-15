from fastapi import APIRouter

from api.routers import admin, days, habits, stats, team, user_settings

api_router = APIRouter(prefix="/api")
api_router.include_router(days.router)
api_router.include_router(habits.router)
api_router.include_router(team.router)
api_router.include_router(stats.router)
api_router.include_router(user_settings.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
