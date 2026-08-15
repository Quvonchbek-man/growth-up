"""Admin paneli — butun bot bo'yicha ko'rsatkichlar.

Har bir yo'l `current_admin` bog'liqligini oladi: oddiy foydalanuvchi 403
qaytadi. Ommaviy xabar bu yerda ATAYLAB yo'q — u faqat botda (`/xabar`),
chunki tasdiqlash va natijani kuzatish o'sha yerda tabiiyroq va tasodifan
bosib yuborish qiyinroq.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_admin, get_session
from services import admin as admin_service
from shared.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
async def overview(
    days: int = Query(default=30, ge=7, le=365),
    user: User = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        **await admin_service.overview(session, user.tz),
        "days": days,
        "members": await admin_service.members_series(session, days, user.tz),
        "recent": await admin_service.recent_users(session, limit=10, tz=user.tz),
    }
