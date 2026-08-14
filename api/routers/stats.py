"""Statistika — grafiklar uchun."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, get_session
from services import groups, stats as stats_service, streak
from shared import clock
from shared.models import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def overview(
    days: int = Query(default=30, ge=7, le=365),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    state = await streak.recalc(session, user)
    series = await stats_service.daily_series(session, user.id, days, user.tz)

    # Sheriklarning qatorlari — taqqoslash grafigi uchun.
    # Bu yerda faqat kunlik foiz uzatiladi, vazifa nomlari emas.
    partners = await groups.partners(session, user)
    partner_series = [
        {
            "user_id": p.id,
            "name": p.display_name,
            "series": await stats_service.daily_series(session, p.id, days, p.tz),
        }
        for p in partners
    ]

    return {
        "days": days,
        "streak": state.current_len,
        "best_streak": state.best_len,
        "series": series,
        "partners": partner_series,
        "reasons": await stats_service.reason_breakdown(session, user.id, days, user.tz),
        "habit_matrix": await stats_service.habit_matrix(session, user.id, days, user.tz),
        "week": {
            "start": clock.week_start(clock.today_local(user.tz)).isoformat(),
            "leaderboard": await stats_service.week_leaderboard(
                session,
                await _group_members(session, user),
                user.tz,
            ),
        },
    }


async def _group_members(session: AsyncSession, user: User) -> list[User]:
    group = await groups.get_user_group(session, user.id)
    if group is None:
        return [user]
    return await groups.members(session, group.id)
