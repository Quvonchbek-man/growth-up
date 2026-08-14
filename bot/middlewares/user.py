"""Foydalanuvchini bazadan oladi yoki yaratadi."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from services import planning
from shared.config import settings


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")

        if tg_user is None or session is None or tg_user.is_bot:
            return await handler(event, data)

        user = await planning.get_or_create_user(
            session,
            tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )

        data["user"] = user
        data["is_admin"] = tg_user.id in settings.super_admin_ids
        return await handler(event, data)
