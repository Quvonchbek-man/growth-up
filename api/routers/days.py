"""Kun va vazifalar: bugun, ertaga, belgilash, qo'shish, ko'chirish."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, get_session
from api.schemas import HabitTaskCreate, TaskCreate, TaskMove, TaskStatusUpdate, TaskTime
from services import planning, stats, streak
from shared import clock
from shared.models import Habit, Task, User

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
    """Kunga vazifa qo'shadi. **Qo'shimcha yoki reja ekani shu yerda hal bo'ladi.**

    Bugungi kunga qo'shilgan har qanday ish — qo'shimcha: reja kechqurun
    berilgan va'da, unga kun ichida ortdan qo'shib bo'lmaydi. Ertangi va
    undan keyingi kunlarga qo'shilgani — oddiy reja vazifasi.
    """
    d = _resolve(day, user)
    today = clock.today_local(user.tz)

    if d < today:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "O'tgan kunga vazifa qo'shib bo'lmaydi — bu soxta tarix bo'lardi",
        )

    is_extra = d == today
    if is_extra and payload.start_time is not None:
        # O'tgan vaqt qo'yilsa eslatmaning ma'nosi yo'q, ustiga —
        # "allaqachon qilib bo'lgan ishni orqadan yozib qo'yish" yo'li.
        if payload.start_time <= clock.now_local(user.tz).time():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "O'tgan vaqtni qo'yib bo'lmaydi — vaqtni keyinroqqa qo'ying "
                "yoki bo'sh qoldiring",
            )

    try:
        await planning.add_task(
            session,
            user,
            d,
            payload.title,
            points=payload.points,
            visibility=payload.visibility,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_extra=is_extra,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return await _day_payload(session, user, d)


@router.post("/day/{day}/habits", status_code=status.HTTP_201_CREATED)
async def create_habit_task(
    day: str,
    payload: HabitTaskCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Odatni jadvalida yo'q kunga qo'lda qo'shadi.

    Faqat KELAJAKDAGI kunga: bugungi reja kechqurun berilgan va'da, unga
    kun ichida odat qo'shish foizni ko'tarishning yo'li bo'lardi. Bugun
    uchun erkin matnli qo'shimcha bor (`POST /day/{day}/tasks`).
    """
    d = _resolve(day, user)
    if d <= clock.today_local(user.tz):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Odatni faqat kelajakdagi rejaga qo'shish mumkin. Bugunga "
            "qo'shmoqchi bo'lsangiz — qo'shimcha vazifa sifatida yozing",
        )

    habit = await session.get(Habit, payload.habit_id)
    if habit is None or habit.user_id != user.id or habit.is_archived:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Odat topilmadi")

    duplicate = await session.scalar(
        select(Task.id).where(
            Task.user_id == user.id,
            Task.date == d,
            Task.habit_id == habit.id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Bu odat allaqachon ro'yxatda"
        )

    await planning.add_habit_task(session, user, d, habit)
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
    task = await planning.move_task(session, user, task_id, payload.date)
    if task is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bu vazifani ko'chirib bo'lmaydi (odat nusxasi ertaga baribir yaratiladi)",
        )
    return await _day_payload(session, user, payload.date)


@router.post("/tasks/{task_id}/time")
async def set_task_time(
    task_id: int,
    payload: TaskTime,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Vazifa oralig'ini o'zgartiradi. Ikkalasi bo'sh bo'lsa — vaqtsiz qiladi."""
    try:
        task = await planning.set_task_time(
            session, user.id, task_id, payload.start_time, payload.end_time
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vazifa topilmadi")
    return await _day_payload(session, user, task.date)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Vazifani o'chiradi.

    Bugungi REJA vazifasi o'chirilmaydi: bajarilmagan ishni ro'yxatdan
    olib tashlash foizni ko'tarishning eng oson yo'li bo'lardi. Qo'shimcha
    esa va'da emas — uni istagan payt olib tashlash mumkin.
    """
    task = await planning.get_task(session, user.id, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vazifa topilmadi")
    if task.date <= clock.today_local(user.tz) and not task.is_extra:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bugungi rejani o'zgartirib bo'lmaydi. Bajara olmagan bo'lsangiz — "
            "kun yakunida sababini belgilaysiz",
        )

    await planning.delete_task(session, user.id, task_id)
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
