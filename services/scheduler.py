"""Eslatma sikli.

Har `REMINDER_TICK_SECONDS` (standart 60) soniyada bir marta uyg'onadi va
"kimning vaqti keldi" deb tekshiradi. Har foydalanuvchi uchun alohida job
yaratmaydi — foydalanuvchi eslatma vaqtini o'zgartirganda jadvalni qayta
qurish shart bo'lmaydi, va bot restart bo'lganda tiklanadigan holat yo'q.

Kechikkan eslatma ham yuboriladi (`clock.is_due` oynasi 10 daqiqa): kompyuter
uxlab qolgan bo'lishi mumkin. Takrorlanmasligini `ReminderLog` kafolatlaydi.

Beshta eslatma kunning belgilangan vaqtlarida ishlaydi, oltinchisi —
vazifa eslatmasi — kun ichida, har vazifaning o'z vaqtida.

**Har foydalanuvchi alohida sessiyada** ishlanadi: bittasida xato chiqsa,
qolganlarning eslatmasi yo'qolmasin.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import delete, select

from services import notify
from shared import clock
from shared.config import settings
from shared.db import session_factory
from shared.models import ReminderKind, ReminderLog, User

logger = logging.getLogger(__name__)


async def fire_due_for(bot: Bot, user: User, session, *, force: bool = False) -> list[str]:
    """Shu foydalanuvchi uchun vaqti kelgan eslatmalarni yuboradi.

    `force=True` — vaqtga qaramay hammasini yuboradi (sinov uchun).
    Qaysi eslatmalar ketganini nomlar ro'yxati sifatida qaytaradi.
    """
    fired: list[str] = []
    tz = user.tz

    # Tartib muhim: avval kecha yopiladi, keyin bugungi xulosa yuboriladi.
    steps = (
        ("kun_yopish", settings.day_close_time, notify.close_and_summarize),
        ("sabab", settings.ask_reason_time, notify.ask_reasons),
        ("ertalabki", user.digest_at or settings.digest_time, notify.send_digest),
        (
            "kechki",
            user.plan_reminder_at or settings.plan_reminder_time,
            notify.send_plan_reminder,
        ),
        ("sherikka", settings.nag_time, notify.nag_partners_about),
    )

    for name, at, fn in steps:
        if not force and not clock.is_due(at, tz):
            continue
        result = await fn(bot, session, user)
        if result:
            fired.append(name)

    # Oltinchi qadam alohida turadi: yuqoridagilar kun chegarasidagi bitta
    # belgilangan vaqtda ishlaydi, bu esa kun ichida va har vazifa uchun
    # o'z vaqtida — tekshiruv `notify` ichida.
    if await notify.send_task_reminders(bot, session, user, force=force):
        fired.append("vazifa")

    return fired


async def tick(bot: Bot, *, force_user_id: int | None = None) -> None:
    async with session_factory() as session:
        rows = await session.scalars(
            select(User).where(User.is_blocked.is_(False)).order_by(User.id)
        )
        users = list(rows)

    for user in users:
        if force_user_id is not None and user.id != force_user_id:
            continue
        # Har foydalanuvchi — o'z sessiyasi, o'z tranzaksiyasi
        async with session_factory() as session:
            try:
                fresh = await session.get(User, user.id)
                if fresh is None:
                    continue
                fired = await fire_due_for(
                    bot, fresh, session, force=force_user_id is not None
                )
                await session.commit()
                if fired:
                    logger.info("Eslatma yuborildi: user=%s -> %s", fresh.id, fired)
            except Exception:
                await session.rollback()
                logger.exception("Eslatma xatosi: user=%s", user.id)


async def reset_today_log(user_id: int) -> None:
    """Sinov uchun: bugungi/kechagi eslatma yozuvlarini o'chiradi.

    Shundan keyin `force` bilan chaqirilgan eslatmalar qaytadan ketadi.
    """
    from datetime import timedelta

    async with session_factory() as session:
        today = clock.today_local()
        await session.execute(
            delete(ReminderLog).where(
                ReminderLog.user_id == user_id,
                ReminderLog.date >= today - timedelta(days=1),
            )
        )
        await session.commit()


async def run_forever(bot: Bot) -> None:
    interval = max(5, settings.reminder_tick_seconds)
    logger.info("Eslatma sikli ishga tushdi (har %s soniyada)", interval)
    while True:
        try:
            await tick(bot)
        except asyncio.CancelledError:
            logger.info("Eslatma sikli to'xtatildi")
            raise
        except Exception:
            # Sikl hech qachon o'lmasligi kerak — bu ilovaning yuragi
            logger.exception("Eslatma siklida kutilmagan xato")
        await asyncio.sleep(interval)


__all__ = ["fire_due_for", "tick", "run_forever", "reset_today_log", "ReminderKind"]
