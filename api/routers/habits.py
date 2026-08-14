"""Odatlar (shablonlar) CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, get_session
from api.schemas import HabitPayload
from services import planning
from shared import clock
from shared.models import Habit, Task, TaskStatus, User

router = APIRouter(prefix="/habits", tags=["habits"])


def _serialize(h: Habit) -> dict:
    return {
        "id": h.id,
        "title": h.title,
        "icon": h.icon,
        "schedule_kind": h.schedule_kind.value,
        "weekdays_mask": h.weekdays_mask,
        "points": h.points,
        "visibility": h.visibility.value,
        "is_archived": h.is_archived,
        "sort_order": h.sort_order,
    }


@router.get("")
async def list_habits(
    include_archived: bool = False,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = select(Habit).where(Habit.user_id == user.id)
    if not include_archived:
        query = query.where(Habit.is_archived.is_(False))
    rows = await session.scalars(query.order_by(Habit.sort_order, Habit.id))
    return [_serialize(h) for h in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_habit(
    payload: HabitPayload,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    last = await session.scalar(
        select(Habit.sort_order)
        .where(Habit.user_id == user.id)
        .order_by(Habit.sort_order.desc())
        .limit(1)
    )
    habit = Habit(
        user_id=user.id,
        title=payload.title.strip(),
        icon=payload.icon,
        schedule_kind=payload.schedule_kind,
        weekdays_mask=payload.weekdays_mask,
        points=payload.points,
        visibility=payload.visibility,
        sort_order=(last or 0) + 1,
    )
    session.add(habit)
    await session.flush()

    # Yangi odat ertangi rejada darhol ko'rinsin
    await planning.open_day(session, user, clock.tomorrow_local(user.tz))
    return _serialize(habit)


@router.put("/{habit_id}")
async def update_habit(
    habit_id: int,
    payload: HabitPayload,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    habit = await session.get(Habit, habit_id)
    if habit is None or habit.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Odat topilmadi")

    habit.title = payload.title.strip()
    habit.icon = payload.icon
    habit.schedule_kind = payload.schedule_kind
    habit.weekdays_mask = payload.weekdays_mask
    habit.points = payload.points
    habit.visibility = payload.visibility
    await session.flush()

    # O'tmishdagi vazifalar ATAYLAB o'zgarmaydi — tarix o'zgarmas bo'lishi kerak.
    # Faqat hali bajarilmagan kelajakdagi nusxalar yangilanadi.
    today = clock.today_local(user.tz)
    future = await session.scalars(
        select(Task).where(
            Task.user_id == user.id,
            Task.habit_id == habit.id,
            Task.date >= today,
            Task.status == TaskStatus.PLANNED,
        )
    )
    for task in future:
        task.title = habit.title
        task.points = habit.points
        task.visibility = habit.visibility
        await planning.recalc_day(session, user.id, task.date)

    return _serialize(habit)


@router.delete("/{habit_id}")
async def archive_habit(
    habit_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Odat o'chirilmaydi — arxivlanadi.

    O'chirilsa, o'tgan oy statistikasida "nima qilgan edim" degan savolga
    javob yo'qolardi. Kelajakdagi rejalashtirilgan nusxalar esa olib tashlanadi.
    """
    habit = await session.get(Habit, habit_id)
    if habit is None or habit.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Odat topilmadi")

    habit.is_archived = True
    today = clock.today_local(user.tz)

    future_dates = list(
        await session.scalars(
            select(Task.date).where(
                Task.user_id == user.id,
                Task.habit_id == habit.id,
                Task.date >= today,
                Task.status == TaskStatus.PLANNED,
            )
        )
    )
    await session.execute(
        delete(Task).where(
            Task.user_id == user.id,
            Task.habit_id == habit.id,
            Task.date >= today,
            Task.status == TaskStatus.PLANNED,
        )
    )
    await session.flush()
    for d in set(future_dates):
        await planning.recalc_day(session, user.id, d)

    return {"ok": True, "archived": True}
