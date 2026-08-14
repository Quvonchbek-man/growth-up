"""Tugmani tez-tez bosishdan himoya.

Kichik jamoa uchun murakkab rate limiter kerak emas — foydalanuvchi
bo'yicha oxirgi bosish vaqtini xotirada saqlash yetadi.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, seconds: float = 0.4) -> None:
        self.seconds = seconds
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last.get(tg_user.id, 0.0)
        if now - last < self.seconds:
            # Callback'ga javob bermasak, Telegram tugmani "osilgan" ko'rsatadi
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None

        self._last[tg_user.id] = now
        return await handler(event, data)
