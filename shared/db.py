"""Bazaga ulanish. Bot va API ikkalasi shu moduldan foydalanadi.

`shop-bot\\shared\\db.py` dan ko'chirilgan — naqsh o'zini oqlagan.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.config import BASE_DIR, settings


def _prepare_sqlite_dir() -> None:
    """SQLite ishlatilsa, fayl uchun papkani oldindan yaratamiz."""
    if not settings.is_sqlite:
        return
    # sqlite+aiosqlite:///data/growth.db  ->  data/growth.db
    raw_path = settings.database_url.split("///", 1)[-1]
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


_prepare_sqlite_dir()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Skript va servislar uchun sessiya konteksti.

    Bot handlerlari sessiyani middleware orqali, API esa Depends orqali oladi —
    ular bu yerdan foydalanmaydi.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """Jadvallarni yaratadi (Alembic'gacha, ishlab chiqish uchun)."""
    from shared import models  # noqa: F401  — modellar ro'yxatga olinishi uchun

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
