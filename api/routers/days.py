"""Kun va vazifalar: bugun, ertaga, belgilash, qo'shish, ko'chirish."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, get_session
from api.schemas import TaskCreate, TaskMove, TaskStatusUpdate
from services import planning, stats, streak
from shared import clock
from shared.models import User

router = APIRouter(tags=["days"])


async def _day_payload(session: AsyncSession, user: User, d: date_type) -> dict:
    await planning.open_day(session, user, d)
    view = await stats.day_view(session, user, d, owner=True)
    state = await streak.recalc(session, user)
    view["streak"] = state.current_len
    view["best_streak"] = state.best_len
    return view


@router.get("/day/{day}")
async def get_day(
    day: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """`day` — ISO sana, yoki `today` / `tomorrow`."""
    if day == "today":
        d = clock.today_local(user.tz)
    elif day == "tomorrow":
        d = clock.tomorrow_local(user.tz)
    else:
        try:
            d = clock.parse_date(day)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sana formati noto'g'ri")
    return await _day_payload(session, user, d)


@router.post("/day/{day}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    day: str,
    payload: TaskCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    d = _resolve(day, user)
    try:
        await planning.add_task(
            session,
            user,
            d,
            payload.title,
            points=payload.points,
            visibility=payload.visibility,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return await _day_payload(session, user, d)


@router.post("/day/{day}/submit")
async def submit(
    day: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Rejani tasdiqlash.

    Aynan shu fakt bo'yicha sherikka "hali reja kiritmadi" xabari ketadi —
    vazifa qo'shishning o'zi tasdiq hisoblanmaydi.
    """
    d = _resolve(day, user)
    await planning.submit_plan(session, user, d)
    return await _day_payload(session, user, d)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    payload: TaskStatusUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    task = await planning.set_status(
        session,
        user.id,
        task_id,
        payload.status,
        reason=payload.reason,
        note=payload.note,
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vazifa topilmadi")
    return await _day_payload(session, user, task.date)


@router.post("/tasks/{task_id}/move")
async def move_task(
    task_id: int,
    payload: TaskMove,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    task = await planning.move_task(session, user.id, task_id, payload.date)
    if task is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bu vazifani ko'chirib bo'lmaydi (odat nusxasi ertaga baribir yaratiladi)",
        )
    return await _day_payload(session, user, payload.date)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ok = await planning.delete_task(session, user.id, task_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vazifa topilmadi")
    return {"ok": True}


def _resolve(day: str, user: User) -> date_type:
    if day == "today":
        return clock.today_local(user.tz)
    if day == "tomorrow":
        return clock.tomorrow_local(user.tz)
    try:
        return clock.parse_date(day)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sana formati noto'g'ri")
