"""Botni yig'ish. Ishga tushirish `run.py` orqali."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from bot.handlers import get_router
from bot.locales import uz as T
from bot.middlewares import DbSessionMiddleware, ThrottleMiddleware, UserMiddleware
from shared.config import settings
from shared.db import session_factory

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Ilovani ochish"),
    BotCommand(command="bugun", description="Bugungi reja"),
    BotCommand(command="jamoa", description="Taklif kodi va sheriklar"),
    BotCommand(command="help", description="Qanday ishlaydi"),
]


def build_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Tartib muhim: avval sessiya ochilsin, keyin foydalanuvchi o'qilsin
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.update.outer_middleware(UserMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())

    dp.include_router(get_router())
    return dp


async def setup_bot_profile(bot: Bot) -> None:
    """Buyruqlar ro'yxati va Mini App menyu tugmasi.

    Menyu tugmasi ataylab kodda o'rnatiladi: tunnel manzili o'zgarganda
    BotFather'ga kirish shart bo'lmasin, `.env` + restart yetsin.
    """
    await bot.set_my_commands(COMMANDS)

    url = settings.webapp_url.strip()
    if not url:
        logger.warning(
            "WEBAPP_URL bo'sh — Mini App tugmasi ko'rinmaydi. "
            "Tunnelni ishga tushirib, manzilni .env ga yozing."
        )
        return

    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text=T.BTN_OPEN_APP, web_app=WebAppInfo(url=url))
        )
        logger.info("Mini App menyu tugmasi o'rnatildi: %s", url)
    except Exception:
        # HTTPS bo'lmasa Telegram rad etadi — bot baribir ishlashi kerak
        logger.exception("Menyu tugmasini o'rnatib bo'lmadi (URL HTTPS ekanini tekshiring)")
