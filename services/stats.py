"""Statistika va maxfiylik filtri.

**Maxfiylik qoidasi bir joyda** — shu faylda. Sherikka ketadigan har qanday
ma'lumot `visible_to_partner()` yoki `serialize_task(..., owner=False)`
orqali o'tishi shart. Filtrni har joyda takrorlash — sizib chiqishning eng
keng tarqalgan sababi.

  PUBLIC     → sherik nomini ham, holatini ham ko'radi
  STATS_ONLY → nomi "Yashirin vazifa" ga almashadi, holati hisobga kiradi
  PRIVATE    → sherik umuman ko'rmaydi; uning ballari jamoa reytingiga
               ham KIRMAYDI (aks holda "ball qayerdan keldi?" degan savol
               orqali yashirin vazifa borligi fosh bo'lardi)

Sherikka ko'rinadigan foizlar `daily_plans` jadvalidagi hisoblagichlardan
emas, har safar `tasks` dan hisoblanadi: u hisoblagichlar egasining o'z
statistikasi uchun, ular yashirin vazifalarni ham o'z ichiga oladi.
10 foydalanuvchi uchun bu farq sezilmaydi.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date as date_type, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services import planning, scoring, streak
from shared import clock
from shared.models import (
    DailyPlan,
    Habit,
    MissReason,
    Task,
    TaskStatus,
    User,
    Visibility,
)

HIDDEN_TITLE = "Yashirin vazifa"

REASON_LABELS: dict[str, str] = {
    MissReason.TIRED.value: "Charchadim",
    MissReason.NO_TIME.value: "Vaqt yetmadi",
    MissReason.FORGOT.value: "Unutdim",
    MissReason.NOT_IMPORTANT.value: "Muhim emas edi",
    MissReason.OTHER.value: "Boshqa",
}


# ─── Maxfiylik ───────────────────────────────────────────────────────────────


def visible_to_partner(tasks: Iterable[Task]) -> list[Task]:
    return [t for t in tasks if t.effective_visibility != Visibility.PRIVATE]


def serialize_task(task: Task, *, owner: bool) -> dict:
    vis = task.effective_visibility
    hide_title = not owner and vis == Visibility.STATS_ONLY
    return {
        "id": task.id,
        "title": HIDDEN_TITLE if hide_title else task.title,
        "hidden": hide_title,
        "status": task.status.value,
        "source": task.source.value,
        "habit_id": task.habit_id,
        "points": task.points,
        "visibility": vis.value,
        "start_time": task.start_time.isoformat("minutes") if task.start_time else None,
        "end_time": task.end_time.isoformat("minutes") if task.end_time else None,
        "is_extra": task.is_extra,
        "miss_reason": task.miss_reason.value if task.miss_reason else None,
        "miss_note": task.miss_note if owner else None,
        "done_at": task.done_at.isoformat() if task.done_at else None,
    }


# ─── Kun ko'rinishi ──────────────────────────────────────────────────────────


async def day_view(
    session: AsyncSession, user: User, d: date_type, *, owner: bool = True
) -> dict:
    """Bitta kunning to'liq tasviri. `owner=False` bo'lsa maxfiylik qo'llanadi."""
    plan = await planning.get_plan(session, user.id, d)
    tasks = await planning.get_tasks(session, user.id, d)
    if not owner:
        tasks = visible_to_partner(tasks)

    stats = scoring.summarize(tasks)
    return {
        "date": d.isoformat(),
        "submitted": bool(plan and plan.submitted_at),
        "closed": bool(plan and plan.closed_at),
        "tasks": [serialize_task(t, owner=owner) for t in tasks],
        **stats,
    }


async def partner_cards(session: AsyncSession, viewer: User, partners: list[User]) -> list[dict]:
    """Jamoa sahifasidagi sherik kartochkalari."""
    today = clock.today_local(viewer.tz)
    tomorrow = today + timedelta(days=1)

    cards = []
    for p in partners:
        day = await day_view(session, p, today, owner=False)
        st = await streak.get_or_zero(session, p.id)
        tomorrow_plan = await planning.get_plan(session, p.id, tomorrow)
        cards.append(
            {
                "user_id": p.id,
                "name": p.display_name,
                "username": p.username,
                "today": day,
                "streak": st.current_len,
                "best_streak": st.best_len,
                "tomorrow_submitted": bool(tomorrow_plan and tomorrow_plan.submitted_at),
            }
        )
    return cards


# ─── Vaqt qatorlari ──────────────────────────────────────────────────────────


async def daily_series(
    session: AsyncSession, user_id: int, days: int = 30, tz: str | None = None
) -> list[dict]:
    """Oxirgi N kun: bajarilish foizi va ball. Bo'sh kunlar ham qatorda bo'ladi.

    Grafikda uzilish bo'lmasligi uchun mavjud bo'lmagan kunlar nol bilan
    to'ldiriladi — aks holda "3 kun ilovaga kirmadim" grafikda ko'rinmaydi.
    """
    today = clock.today_local(tz)
    since = today - timedelta(days=days - 1)

    rows = await session.scalars(
        select(DailyPlan)
        .where(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= since,
            DailyPlan.date <= today,
        )
        .order_by(DailyPlan.date)
    )
    by_date = {p.date: p for p in rows}

    series = []
    d = since
    while d <= today:
        p = by_date.get(d)
        series.append(
            {
                "date": d.isoformat(),
                "weekday": d.weekday(),
                "planned": p.planned_count if p else 0,
                "done": p.done_count if p else 0,
                "pct": p.completion_pct if p else 0,
                "score": p.score if p else 0,
                "submitted": bool(p and p.submitted_at),
            }
        )
        d += timedelta(days=1)
    return series


async def reason_breakdown(
    session: AsyncSession, user_id: int, days: int = 30, tz: str | None = None
) -> list[dict]:
    """Nega bajarilmadi — sabablar taqsimoti.

    Bu ilovaning eng qimmatli ma'lumoti: bir oydan keyin "vaqt yetmadi" 70%
    bo'lsa, muammo motivatsiyada emas, rejaning hajmida.
    """
    today = clock.today_local(tz)
    since = today - timedelta(days=days - 1)

    rows = await session.execute(
        select(Task.miss_reason, func.count(Task.id))
        .where(
            Task.user_id == user_id,
            Task.date >= since,
            Task.date <= today,
            Task.status == TaskStatus.MISSED,
            # Qo'shimchadan sabab so'ralmaydi — u yerda hammasi "noma'lum"
            # bo'lib chiqib, eng qimmatli grafikni ma'nosiz qilardi.
            Task.is_extra.is_(False),
        )
        .group_by(Task.miss_reason)
    )

    out = []
    for reason, count in rows:
        key = reason.value if reason is not None else "unknown"
        out.append(
            {
                "reason": key,
                "label": REASON_LABELS.get(key, "Sabab ko'rsatilmagan"),
                "count": count,
            }
        )
    out.sort(key=lambda r: r["count"], reverse=True)
    return out


async def habit_matrix(
    session: AsyncSession, user_id: int, days: int = 30, tz: str | None = None
) -> dict:
    """Odat × kun jadvali (heatmap uchun).

    Qaysi odat qaysi kunlarda uzilayotganini ko'rsatadi — masalan sport
    faqat dushanba kunlari bajarilmasligi.
    """
    today = clock.today_local(tz)
    since = today - timedelta(days=days - 1)

    habits = list(
        await session.scalars(
            select(Habit).where(Habit.user_id == user_id).order_by(Habit.sort_order, Habit.id)
        )
    )
    rows = await session.execute(
        select(Task.habit_id, Task.date, Task.status).where(
            Task.user_id == user_id,
            Task.date >= since,
            Task.date <= today,
            Task.habit_id.is_not(None),
        )
    )

    cells: dict[int, dict[str, str]] = {h.id: {} for h in habits}
    for habit_id, d, status in rows:
        if habit_id in cells:
            cells[habit_id][d.isoformat()] = status.value

    dates = []
    d = since
    while d <= today:
        dates.append(d.isoformat())
        d += timedelta(days=1)

    return {
        "dates": dates,
        "habits": [
            {
                "id": h.id,
                "title": h.title,
                "icon": h.icon,
                "cells": [cells[h.id].get(ds) for ds in dates],
            }
            for h in habits
        ],
    }


# ─── Jamoa reytingi ──────────────────────────────────────────────────────────


async def leaderboard(
    session: AsyncSession,
    users: list[User],
    since: date_type,
    until: date_type,
) -> list[dict]:
    """Davr bo'yicha ball reytingi.

    PRIVATE vazifalar hisobga KIRMAYDI — yashirin ish jamoa reytingida
    ball bermaydi. Bu maxfiylikning narxi va qoida oldindan aytiladi.

    Qo'shimchalar ham KIRMAYDI. Reyting `daily_plans` dan emas, `tasks` dan
    to'g'ridan-to'g'ri hisoblanadi — ya'ni `scoring.py` dagi ajratma bu
    yerga o'z-o'zidan yetib kelmaydi va filtr qo'lda yozilishi shart.
    Bo'lmasa qo'shimcha ball bermasa ham reytingga sizib o'tadi.
    """
    if not users:
        return []

    ids = [u.id for u in users]
    rows = await session.execute(
        select(
            Task.user_id,
            func.coalesce(func.sum(Task.points), 0),
            func.count(Task.id),
        )
        .where(
            Task.user_id.in_(ids),
            Task.date >= since,
            Task.date <= until,
            Task.status == TaskStatus.DONE,
            Task.is_extra.is_(False),
            # Habit'dan yaratilgan vazifada visibility har doim to'ldirilgan,
            # qo'l vazifasida NULL bo'lishi mumkin — u PUBLIC degani.
            (Task.visibility.is_(None)) | (Task.visibility != Visibility.PRIVATE),
        )
        .group_by(Task.user_id)
    )
    totals = {uid: (int(score), int(cnt)) for uid, score, cnt in rows}

    board = []
    for u in users:
        score, count = totals.get(u.id, (0, 0))
        st = await streak.get_or_zero(session, u.id)
        board.append(
            {
                "user_id": u.id,
                "name": u.display_name,
                "score": score,
                "done_count": count,
                "streak": st.current_len,
            }
        )

    board.sort(key=lambda r: (-r["score"], -r["streak"], r["name"]))
    for i, row in enumerate(board, start=1):
        row["rank"] = i
    return board


async def week_leaderboard(session: AsyncSession, users: list[User], tz: str | None = None):
    today = clock.today_local(tz)
    start = clock.week_start(today)
    return await leaderboard(session, users, start, today)
