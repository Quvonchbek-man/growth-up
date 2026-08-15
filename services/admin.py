"""Botning umumiy admini uchun ko'rsatkichlar va ommaviy xabar.

Bu modul **butun bot bo'yicha** ishlaydi — qolgan `services/` modullaridan
farqi shu. Shuning uchun undagi har bir so'rov barcha foydalanuvchilarni
qamraydi va hech qanday maxfiylik filtri qo'llanmaydi: bu yerdagi raqamlar
faqat `SUPER_ADMIN_IDS` ga ko'rsatiladi (tekshiruv `api/auth.py` va
`bot/handlers/dev.py` da).

**Eng muhim ko'rsatkich — «sherigi bor / yolg'iz».** Ilovaning butun qiymati
sherikda: yolg'iz foydalanuvchi ertami-kechmi tashlab ketadi. Jami
foydalanuvchi soni o'sib, yolg'izlar ulushi ham o'sayotgan bo'lsa — muammo
jalb qilishda emas, sherik topishda.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date as date_type, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services import planning
from shared import clock
from shared.models import (
    DailyPlan,
    Group,
    Membership,
    ReminderLog,
    StreakState,
    Task,
    TaskStatus,
    User,
)

logger = logging.getLogger(__name__)


async def _count(session: AsyncSession, stmt) -> int:
    return int(await session.scalar(stmt) or 0)


# ─── Ko'rsatkichlar ──────────────────────────────────────────────────────────


async def overview(session: AsyncSession, tz: str | None = None) -> dict:
    """Bir qarashda butun bot holati."""
    today = clock.today_local(tz)
    week_ago = today - timedelta(days=6)      # bugun ham kiradi → 7 kun
    month_ago = today - timedelta(days=29)

    total = await _count(session, select(func.count(User.id)))
    blocked = await _count(
        session, select(func.count(User.id)).where(User.is_blocked.is_(True))
    )

    # `created_at` — UTC, `today` — mahalliy sana. Chegarani mahalliy
    # yarim tundan hisoblaymiz, aks holda "bugun qo'shilganlar" 5 soatga
    # siljib ketadi (Asia/Tashkent = UTC+5).
    async def qoshilgan(since: date_type) -> int:
        boundary = clock.day_start_utc(since, tz)
        return await _count(
            session, select(func.count(User.id)).where(User.created_at >= boundary)
        )

    # Sherigi bor = a'zosi 2 va undan ko'p bo'lgan jamoada turibdi
    juft_jamoalar = (
        select(Membership.group_id)
        .group_by(Membership.group_id)
        .having(func.count(Membership.id) >= 2)
        .scalar_subquery()
    )
    sherikli = await _count(
        session,
        select(func.count(distinct(Membership.user_id))).where(
            Membership.group_id.in_(juft_jamoalar)
        ),
    )

    async def rejasi_bor(since: date_type) -> int:
        return await _count(
            session,
            select(func.count(distinct(DailyPlan.user_id))).where(
                DailyPlan.date >= since,
                DailyPlan.date <= today,
                DailyPlan.submitted_at.is_not(None),
            ),
        )

    bajargan_7 = await _count(
        session,
        select(func.count(distinct(Task.user_id))).where(
            Task.date >= week_ago,
            Task.date <= today,
            Task.status == TaskStatus.DONE,
        ),
    )

    # O'rtacha foiz — faqat rejasi bo'lgan kunlardan (bo'sh kunlar natijani
    # sun'iy pastga tortmasin; `services/scoring.py` dagi qoida bilan bir xil)
    ortacha = await session.scalar(
        select(func.avg(DailyPlan.completion_pct)).where(
            DailyPlan.date >= week_ago,
            DailyPlan.date <= today,
            DailyPlan.planned_count > 0,
        )
    )

    return {
        "date": today.isoformat(),
        "users": {
            "total": total,
            "blocked": blocked,
            "new_today": await qoshilgan(today),
            "new_7d": await qoshilgan(week_ago),
            "new_30d": await qoshilgan(month_ago),
        },
        "teams": {
            "with_partner": sherikli,
            "alone": total - sherikli,
            "groups": await _count(session, select(func.count(Group.id))),
            "paired_groups": await _count(
                session, select(func.count()).select_from(juft_jamoalar.subquery())
            ),
        },
        "activity": {
            "submitted_today": await rejasi_bor(today),
            "active_7d": await rejasi_bor(week_ago),
            "done_7d": bajargan_7,
        },
        "results": {
            "avg_pct_7d": round(float(ortacha or 0)),
            "tasks_done_7d": await _count(
                session,
                select(func.count(Task.id)).where(
                    Task.date >= week_ago,
                    Task.date <= today,
                    Task.status == TaskStatus.DONE,
                ),
            ),
            "best_streak": await _count(
                session, select(func.max(StreakState.best_len))
            ),
        },
        "reminders_today": await _count(
            session, select(func.count(ReminderLog.id)).where(ReminderLog.date == today)
        ),
    }


async def members_series(
    session: AsyncSession, days: int = 30, tz: str | None = None
) -> list[dict]:
    """A'zolar dinamikasi — har kun uchun to'rt raqam.

        total   — o'sha kun oxiriga qadar ro'yxatdan o'tganlar (o'sib boradi)
        active  — total minus o'sha kunga qadar botni bloklaganlar
        joined  — shu kuni qo'shilganlar
        left    — shu kuni bloklaganlar

    `total` va `active` orasidagi masofa — yo'qotish. Faqat kunlik
    qo'shilishni ko'rsatadigan ustunli grafik buni yashiradi: 10 kishi
    kelib 9 tasi ketgan kun ham, 10 kishi kelib hech kim ketmagan kun ham
    bir xil ko'rinadi.

    **Butun tarix o'qiladi**, faqat oyna emas: `total` — jamg'arma raqam,
    oynadan oldingi odamlar ham unga kiradi. Bir necha ming foydalanuvchida
    bu hali arzon; undan oshsa kunlik jamg'armani alohida jadvalda saqlash
    kerak bo'ladi.
    """
    today = clock.today_local(tz)
    since = today - timedelta(days=days - 1)

    rows = await session.execute(select(User.created_at, User.blocked_at))
    qoshilgan: dict[str, int] = {}
    ketgan: dict[str, int] = {}
    for created, blocked in rows:
        if created is not None:
            kun = clock.local_date_of(created, tz).isoformat()
            qoshilgan[kun] = qoshilgan.get(kun, 0) + 1
        if blocked is not None:
            kun = clock.local_date_of(blocked, tz).isoformat()
            ketgan[kun] = ketgan.get(kun, 0) + 1

    # Oyna boshigacha bo'lgan holatni jamlab olamiz
    total = sum(n for k, n in qoshilgan.items() if k < since.isoformat())
    yoqotish = sum(n for k, n in ketgan.items() if k < since.isoformat())

    natija = []
    d = since
    while d <= today:
        key = d.isoformat()
        kun_qoshildi = qoshilgan.get(key, 0)
        kun_ketdi = ketgan.get(key, 0)
        total += kun_qoshildi
        yoqotish += kun_ketdi
        natija.append(
            {
                "date": key,
                "total": total,
                "active": total - yoqotish,
                "joined": kun_qoshildi,
                "left": kun_ketdi,
            }
        )
        d += timedelta(days=1)
    return natija


async def recent_users(
    session: AsyncSession, limit: int = 10, tz: str | None = None
) -> list[dict]:
    """Oxirgi qo'shilganlar — kim kelgani va sherik topganini ko'rish uchun.

    Sana MAHALLIY qilib qaytariladi. `created_at` UTC'da saqlanadi va uni
    o'sha holicha ko'rsatish paneldagi qolgan raqamlarga zid ko'rinadi:
    "bugun qo'shildi: 6" yozilib turganda ro'yxatda kechagi sana chiqadi
    (Asia/Tashkent uchun kechqurun kelgan har bir odam shunday ko'rinadi).
    """
    rows = list(
        await session.scalars(
            select(User).order_by(User.created_at.desc()).limit(limit)
        )
    )
    if not rows:
        return []

    juft = set(
        await session.scalars(
            select(Membership.user_id)
            .where(Membership.user_id.in_([u.id for u in rows]))
            .where(
                Membership.group_id.in_(
                    select(Membership.group_id)
                    .group_by(Membership.group_id)
                    .having(func.count(Membership.id) >= 2)
                )
            )
        )
    )

    return [
        {
            "user_id": u.id,
            "name": u.display_name,
            "username": u.username,
            "joined": (
                clock.local_date_of(u.created_at, tz).isoformat()
                if u.created_at
                else None
            ),
            "has_partner": u.id in juft,
            "is_blocked": u.is_blocked,
        }
        for u in rows
    ]


# ─── Ommaviy xabar ───────────────────────────────────────────────────────────

# Telegram sekundiga ~30 ta xabarga ruxsat beradi. 20 — xavfsiz chegara:
# flood limitga tushsak butun yuborish sekinlashadi.
SEND_DELAY = 0.05


async def broadcast_audience(session: AsyncSession) -> list[User]:
    """Xabar ketadigan foydalanuvchilar — bloklaganlardan tashqari."""
    rows = await session.scalars(
        select(User).where(User.is_blocked.is_(False)).order_by(User.id)
    )
    return list(rows)


async def broadcast(bot: Bot, session: AsyncSession, text: str) -> dict[str, int]:
    """Barcha foydalanuvchiga xabar yuboradi.

    `notify.safe_send` ATAYLAB ishlatilmaydi: u `TelegramRetryAfter` da
    darhol `False` qaytaradi, ya'ni flood limitga tushilganda xabar jimgina
    yo'qolardi — 100 kishilik ro'yxatning yarmi xabarsiz qolishi mumkin.
    Bu yerda kutib, bir marta qayta uriniladi.

    Qaytaradi: yuborilgan / bloklagan / xato sonlari.
    """
    natija = {"sent": 0, "blocked": 0, "failed": 0}

    for user in await broadcast_audience(session):
        try:
            await bot.send_message(user.id, text)
            natija["sent"] += 1
        except TelegramForbiddenError:
            planning.mark_blocked(user)
            natija["blocked"] += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
            try:
                await bot.send_message(user.id, text)
                natija["sent"] += 1
            except Exception:
                logger.exception("Ommaviy xabar yuborilmadi: user=%s", user.id)
                natija["failed"] += 1
        except Exception:
            logger.exception("Ommaviy xabar yuborilmadi: user=%s", user.id)
            natija["failed"] += 1

        await asyncio.sleep(SEND_DELAY)

    await session.flush()
    logger.info("Ommaviy xabar: %s", natija)
    return natija


__all__ = [
    "overview",
    "members_series",
    "recent_users",
    "broadcast",
    "broadcast_audience",
]
