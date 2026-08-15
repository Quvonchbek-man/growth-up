"""Admin buyruqlari — faqat `SUPER_ADMIN_IDS` uchun.

Uchta guruh:
  • `/sinov`, `/vaqt` — o'z hisobingizda eslatmalarni tekshirish
  • `/admin` — butun bot bo'yicha ko'rsatkichlar
  • `/xabar` — barcha foydalanuvchiga ommaviy xabar

Bu buyruqlar `bot/main.py` dagi `COMMANDS` ro'yxatiga ATAYLAB
qo'shilmagan: menyu hammaga ko'rinadi, admin buyruqlari esa ko'rinmasligi
kerak. Qo'riqchi — har handlerdagi `is_admin` (u `UserMiddleware` dan
keladi); ro'yxatda yo'qligi qo'riqchi emas, shunchaki ko'zga tashlanmaslik.
"""

from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.callbacks import BroadcastCb
from bot.locales import uz as T
from services import admin as admin_service, groups, notify, scheduler
from shared import clock
from shared.config import settings
from shared.models import User

logger = logging.getLogger(__name__)

router = Router(name="dev")


class Broadcast(StatesGroup):
    """Ommaviy xabar oqimi: matn kutilyapti → tasdiq kutilyapti."""

    matn = State()
    tasdiq = State()


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
        f"Do'stga: {settings.nag_time}\n"
        f"Kun yopilishi: {settings.day_close_time}\n"
        f"Vazifadan oldin: {user.task_lead_min} daqiqa"
        + (" (o'chirilgan)" if user.task_lead_min <= 0 else "")
    )


# ─── Butun bot bo'yicha ko'rsatkichlar ───────────────────────────────────────


@router.message(Command("admin"))
async def admin_report(
    message: Message, session: AsyncSession, user: User, is_admin: bool
) -> None:
    if not is_admin:
        return

    data = await admin_service.overview(session, user.tz)
    odamlar, jamoa = data["users"], data["teams"]
    faollik, natija = data["activity"], data["results"]

    # Kalitlar ATAYLAB ochiq yozilgan, `**odamlar` emas: `tests/
    # test_integrity.py` shablon kalitlarini AST orqali tekshiradi va
    # `**` bilan uzatilganini ko'ra olmaydi. Ya'ni matnga yangi `{kalit}`
    # qo'shilsa, xato faqat admin buyruqni bosganda — jim qolgan bot
    # ko'rinishida — bilinardi.
    text = T.ADMIN_REPORT.format(
        date=data["date"],
        total=odamlar["total"],
        blocked=odamlar["blocked"],
        new_today=odamlar["new_today"],
        new_7d=odamlar["new_7d"],
        new_30d=odamlar["new_30d"],
        with_partner=jamoa["with_partner"],
        alone=jamoa["alone"],
        groups=jamoa["groups"],
        paired_groups=jamoa["paired_groups"],
        submitted_today=faollik["submitted_today"],
        active_7d=faollik["active_7d"],
        done_7d=faollik["done_7d"],
        avg_pct_7d=natija["avg_pct_7d"],
        tasks_done_7d=natija["tasks_done_7d"],
        best_streak=natija["best_streak"],
        reminders_today=data["reminders_today"],
    )

    # Oxirgi qo'shilganlar — kim kelayotganini ko'rish uchun. Ismlar
    # foydalanuvchi kiritgan matn, HTML rejimida qalqon kerak.
    recent = await admin_service.recent_users(session, limit=8, tz=user.tz)
    if recent:
        lines = [T.ADMIN_RECENT_TITLE]
        for row in recent:
            nom = html.escape(row["name"])
            belgi = "🤝" if row["has_partner"] else "👤"
            if row["is_blocked"]:
                belgi = "🚫"
            sana = (row["joined"] or "")[:10]
            lines.append(f"{belgi} {nom} — {sana}")
        text += "\n".join(lines)

    await message.answer(text)


# ─── Ommaviy xabar ───────────────────────────────────────────────────────────


@router.message(Command("xabar", "broadcast"))
async def broadcast_start(message: Message, state: FSMContext, is_admin: bool) -> None:
    if not is_admin:
        return
    await state.set_state(Broadcast.matn)
    await message.answer(T.BROADCAST_ASK)


@router.message(Command("bekor"), StateFilter(Broadcast.matn, Broadcast.tasdiq))
async def broadcast_cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(T.BROADCAST_CANCELLED)


@router.message(Broadcast.matn, F.text)
async def broadcast_preview(
    message: Message, state: FSMContext, session: AsyncSession, is_admin: bool
) -> None:
    if not is_admin:
        await state.clear()
        return

    text = (message.html_text or "").strip()
    if not text:
        await message.answer(T.BROADCAST_EMPTY)
        return

    count = len(await admin_service.broadcast_audience(session))

    # Ko'rinishni xuddi oluvchilar ko'radigan holatda yuboramiz. Yon foydasi:
    # xabar rad etilsa (masalan 4096 belgidan uzun) AYNAN SHU YERDA bilinadi —
    # hammaga ketishdan oldin.
    try:
        await message.answer(text)
    except Exception as exc:
        logger.info("Ommaviy xabar matni rad etildi: %s", exc)
        await message.answer(T.BROADCAST_BAD_TEXT.format(error=html.escape(str(exc))))
        return

    await state.update_data(text=text)
    await state.set_state(Broadcast.tasdiq)
    await message.answer(
        T.BROADCAST_PREVIEW.format(count=count), reply_markup=kb.broadcast_confirm()
    )


@router.callback_query(BroadcastCb.filter(), Broadcast.tasdiq)
async def broadcast_confirm(
    call: CallbackQuery,
    callback_data: BroadcastCb,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    is_admin: bool,
) -> None:
    if not is_admin:
        await call.answer()
        return

    if callback_data.action == "cancel":
        await state.clear()
        await call.message.edit_text(T.BROADCAST_CANCELLED)
        await call.answer()
        return

    data = await state.get_data()
    text = (data.get("text") or "").strip()
    await state.clear()
    if not text:
        await call.answer()
        return

    audience = await admin_service.broadcast_audience(session)
    await call.message.edit_text(T.BROADCAST_SENDING.format(count=len(audience)))
    await call.answer()

    result = await admin_service.broadcast(bot, session, text)
    await call.message.answer(
        T.BROADCAST_DONE.format(
            sent=result["sent"], blocked=result["blocked"], failed=result["failed"]
        )
    )
