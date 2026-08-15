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
        "start_time": h.start_time.isoformat("minutes") if h.start_time else None,
        "end_time": h.end_time.isoformat("minutes") if h.end_time else None,
        "is_archived": h.is_archived,
        "sort_order": h.sort_order,
    }


def _check_span(payload: HabitPayload) -> None:
    """Oraliq tekshiruvi — `services/planning.py` dagi qoida bilan bir xil."""
    if payload.end_time is not None and payload.start_time is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Tugash vaqti uchun boshlanish vaqti ham kerak",
        )
    if (
        payload.start_time is not None
        and payload.end_time is not None
        and payload.end_time <= payload.start_time
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Tugash vaqti boshlanishidan keyin bo'lishi kerak",
        )


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
    _check_span(payload)
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
        start_time=payload.start_time,
        end_time=payload.end_time,
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
    _check_span(payload)
    habit = await session.get(Habit, habit_id)
    if habit is None or habit.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Odat topilmadi")

    habit.title = payload.title.strip()
    habit.icon = payload.icon
    habit.schedule_kind = payload.schedule_kind
    habit.weekdays_mask = payload.weekdays_mask
    habit.points = payload.points
    habit.visibility = payload.visibility
    habit.start_time = payload.start_time
    habit.end_time = payload.end_time
    await session.flush()

    # O'tmishdagi vazifalar ATAYLAB o'zgarmaydi — tarix o'zgarmas bo'lishi kerak.
    # Faqat hali bajarilmagan kelajakdagi nusxalar yangilanadi. Jadval
    # o'zgargani (kun qo'shilishi yoki chiqib qolishi) shu yerda emas,
    # `planning._sync_habit_tasks` da hal bo'ladi — quyidagi `open_day` uni
    # ertangi kun uchun darhol ishga tushiradi.
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
        task.start_time = habit.start_time
        task.end_time = habit.end_time
        await planning.recalc_day(session, user.id, task.date)

    # Jadval o'zgarishi ertangi rejada darhol ko'rinsin: kun qo'shilgan
    # bo'lsa nusxa yaratiladi, chiqib qolgan bo'lsa olib tashlanadi.
    await planning.open_day(session, user, clock.tomorrow_local(user.tz))
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
