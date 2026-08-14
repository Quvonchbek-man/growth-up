"""Turtki — sherikka bir bosishda eslatma."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import NudgeCb
from bot.locales import uz as T
from services import notify
from shared.models import User

router = Router(name="nudge")


@router.callback_query(NudgeCb.filter())
async def nudge(
    call: CallbackQuery,
    callback_data: NudgeCb,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    if callback_data.to_user_id == user.id:
        await call.answer(T.NUDGE_SELF, show_alert=True)
        return

    target = await session.get(User, callback_data.to_user_id)
    if target is None:
        await call.answer(T.GENERIC_ERROR, show_alert=True)
        return

    ok = await notify.send_nudge(bot, session, user, target)
    await call.answer(T.NUDGE_SENT if ok else T.NUDGE_LIMIT, show_alert=not ok)
