"""Hamma narsani bitta processda ishga tushiradi.

    python run.py

Uchta vazifa parallel ishlaydi:
  1. Telegram bot (long polling)
  2. FastAPI serveri (Mini App + API)
  3. Eslatma sikli

Nega bitta process: bu kompyuterda Docker yo'q, Windows'da uchta xizmatni
alohida boshqarish — uchta oyna va uchta unutilgan restart degani.
Faza 3 da VPS'ga ko'chganda ham shu fayl o'zgarmaydi.

Faqat API kerak bo'lsa (masalan frontend ustida ishlaganda):
    python run.py --api-only
"""

from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn

from shared.config import settings
from shared.db import create_all

logger = logging.getLogger(__name__)


def force_utf8_output() -> None:
    """Windows konsolini UTF-8 ga o'tkazadi.

    Chiqish faylga yo'naltirilganda Python Windows'da tizim kodlashini
    (cp1251) tanlaydi. Log xabarlarimizda emoji va o'zbekcha belgilar bor —
    natijada ilova birinchi `print` dayoq `UnicodeEncodeError` bilan qulaydi.
    Buni ishga tushishning eng boshida hal qilamiz.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def setup_logging() -> None:
    force_utf8_output()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _banner(api_only: bool) -> None:
    print("─" * 62)
    print("  Duo Growth")
    print(f"  API:        http://{settings.api_host}:{settings.api_port}")
    print(f"  Mini App:   {settings.webapp_url or '(WEBAPP_URL sozlanmagan)'}")
    print(f"  Baza:       {settings.database_url}")
    print(f"  Vaqt:       {settings.timezone}", end="")
    if settings.dev_time_shift_minutes:
        print(f"  ⚠ {settings.dev_time_shift_minutes} daqiqa siljitilgan", end="")
    print()
    if not settings.check_init_data:
        print("  ⚠ CHECK_INIT_DATA=false — imzo TEKSHIRILMAYDI (faqat ishlab chiqish)")
    if api_only:
        print("  ⚠ Faqat API rejimi — bot va eslatmalar ishlamaydi")
    print("─" * 62)


async def main() -> None:
    api_only = "--api-only" in sys.argv
    setup_logging()
    await create_all()

    from api.main import app

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)

    if api_only or not settings.bot_token:
        if not api_only:
            logger.error(
                "BOT_TOKEN bo'sh — bot ishga tushmaydi. "
                "BotFather'dan token olib .env ga yozing."
            )
        _banner(api_only=True)
        await server.serve()
        return

    # Bot faqat token bor bo'lganda yig'iladi
    from bot.main import build_bot, build_dispatcher, setup_bot_profile
    from services import scheduler

    bot = build_bot()
    dp = build_dispatcher()
    app.state.bot = bot  # Mini App'dan turtki yuborish uchun kerak

    await setup_bot_profile(bot)
    me = await bot.get_me()
    _banner(api_only=False)
    print(f"  Bot:        @{me.username}")
    print("─" * 62)

    tasks = [
        asyncio.create_task(server.serve(), name="api"),
        asyncio.create_task(dp.start_polling(bot), name="bot"),
        asyncio.create_task(scheduler.run_forever(bot), name="scheduler"),
    ]

    try:
        # Biri yiqilsa — hammasini to'xtatamiz, "yarim ishlayotgan" holat
        # eng yomon variant: eslatma kelmaydi, lekin buni hech kim sezmaydi
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception() is not None:
                logger.error("«%s» to'xtadi", task.get_name(), exc_info=task.exception())
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")
