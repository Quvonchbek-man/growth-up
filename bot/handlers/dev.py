"""Sinov buyruqlari — faqat `SUPER_ADMIN_IDS` uchun.

Eslatmalarni tekshirish uchun kechgacha kutish kerak emas: `/sinov`
hamma eslatmani darhol yuboradi.
"""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from services import groups, notify, scheduler
from shared import clock
from shared.config import settings
from shared.models import User

router = Router(name="dev")


@router.message(Command("sinov", "test"))
async def test_reminders(
    message: Message, session: AsyncSession, user: User, bot: Bot, is_admin: bool
) -> None:
    if not is_admin:
        return

    await scheduler.reset_today_log(user.id)
    await message.answer("⏳ Barcha eslatmalar yuborilmoqda…")
    await scheduler.tick(bot, force_user_id=user.id)

    # "Sherigingiz reja kiritmadi" xabari sherik nomidan keladi, shuning uchun
    # o'z eslatmalarimizni majburlash uni ko'rsatmaydi — alohida chaqiramiz.
    for partner in await groups.partners(session, user):
        await scheduler.reset_today_log(partner.id)
        await notify.nag_partners_about(bot, session, partner)

    await message.answer("✅ Tugadi. Yuqoridagi xabarlarni tekshiring.")


@router.message(Command("vaqt", "time"))
async def show_time(message: Message, user: User, is_admin: bool) -> None:
    if not is_admin:
        return

    await message.answer(
        "<b>Vaqt holati</b>\n"
        f"UTC: <code>{clock.now_utc():%Y-%m-%d %H:%M}</code>\n"
        f"Mahalliy ({user.tz}): <code>{clock.now_local(user.tz):%Y-%m-%d %H:%M}</code>\n"
        f"Bugun: <code>{clock.today_local(user.tz)}</code>\n"
        f"Sun'iy siljish: <code>{settings.dev_time_shift_minutes} daqiqa</code>\n\n"
        f"Kechki eslatma: {user.plan_reminder_at or settings.plan_reminder_time}\n"
        f"Ertalabki: {user.digest_at or settings.digest_time}\n"
        f"Sherikka: {settings.nag_time}\n"
        f"Kun yopilishi: {settings.day_close_time}"
    )
