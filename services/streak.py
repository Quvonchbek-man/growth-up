"""Streak — ketma-ket muvaffaqiyatli kunlar soni.

Kun "muvaffaqiyatli" hisoblanadi, agar:
  1. o'sha kunga reja bo'lsa (`planned_count > 0`), va
  2. bajarilish foizi `STREAK_SUCCESS_PCT` (standart 60) dan kam bo'lmasa.

Rejasiz kun streak'ni uzadi — bu ataylab: ilovaning maqsadi rejani yozdirish.
Kasal yoki safar kunlari uchun vazifalarni `SKIPPED` qilish yo'li bor, u
foizga ta'sir qilmaydi.

**Bugungi kun streak'ni uzmaydi** — u hali tugamagan. Uzilish faqat kun
yopilgandan keyin ko'rinadi.

Har safar to'liq qayta hisoblanadi (oxirgi ~400 kun). 10 foydalanuvchi uchun
bu arzon, va "aqlli" inkremental hisoblashdan ko'ra ishonchliroq: bir marta
xato yozilsa, keyingi hisob ham noto'g'ri bo'lib qolardi.
"""

from __future__ import annotations

from datetime import date as date_type, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared import clock
from shared.config import settings
from shared.models import DailyPlan, StreakState, User

LOOKBACK_DAYS = 400


def _is_success(plan: DailyPlan | None) -> bool:
    if plan is None or plan.planned_count == 0:
        return False
    return plan.completion_pct >= settings.streak_success_pct


async def recalc(session: AsyncSession, user: User) -> StreakState:
    today = clock.today_local(user.tz)
    since = today - timedelta(days=LOOKBACK_DAYS)

    rows = await session.scalars(
        select(DailyPlan)
        .where(
            DailyPlan.user_id == user.id,
            DailyPlan.date >= since,
            DailyPlan.date <= today,
        )
        .order_by(DailyPlan.date)
    )
    plans = {p.date: p for p in rows}

    state = await session.get(StreakState, user.id)
    if state is None:
        state = StreakState(user_id=user.id)
        session.add(state)

    if not plans:
        state.current_len = 0
        state.best_len = max(state.best_len or 0, 0)
        state.last_success_date = None
        await session.flush()
        return state

    # --- Joriy streak: bugundan orqaga qarab ---
    cursor = today
    if not _is_success(plans.get(today)):
        # Bugun hali tugamagan — hisobni kechadan boshlaymiz
        cursor = today - timedelta(days=1)

    current = 0
    last_success: date_type | None = None
    while cursor >= since:
        if not _is_success(plans.get(cursor)):
            break
        if last_success is None:
            last_success = cursor
        current += 1
        cursor -= timedelta(days=1)

    # --- Eng uzun streak: butun tarix bo'ylab ---
    best = 0
    run = 0
    day = min(plans)
    while day <= today:
        if _is_success(plans.get(day)):
            run += 1
            best = max(best, run)
        else:
            run = 0
        day += timedelta(days=1)

    state.current_len = current
    state.best_len = max(best, current, state.best_len or 0)
    state.last_success_date = last_success
    await session.flush()
    return state


async def get(session: AsyncSession, user_id: int) -> StreakState | None:
    return await session.get(StreakState, user_id)


async def get_or_zero(session: AsyncSession, user_id: int) -> StreakState:
    state = await session.get(StreakState, user_id)
    if state is None:
        state = StreakState(user_id=user_id, current_len=0, best_len=0)
    return state
