"""Test muhiti.

**Muhim:** bu yerdagi `os.environ` sozlamalari loyiha modullari import
qilinishidan OLDIN qo'yiladi. `shared/db.py` dvigatelni import paytida
yaratadi — kech qo'ysak, testlar haqiqiy `data/growth.db` ga tegib ketardi.
"""

from __future__ import annotations

import os
import pathlib
import sys

TESTS_DIR = pathlib.Path(__file__).parent
PROJECT_DIR = TESTS_DIR.parent
TEST_DB = TESTS_DIR / "_test.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["BOT_TOKEN"] = "123456:TEST-TOKEN"
os.environ["CHECK_INIT_DATA"] = "false"
os.environ["DEV_MOCK_USER_ID"] = "1001"
os.environ["TIMEZONE"] = "Asia/Tashkent"
os.environ["DEV_TIME_SHIFT_MINUTES"] = "0"
os.environ["SUPER_ADMIN_IDS"] = "1001"
os.environ["WEBAPP_URL"] = "https://example.test"

sys.path.insert(0, str(PROJECT_DIR))

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from shared import db as db_module  # noqa: E402
from shared.models import (  # noqa: E402
    Base,
    DailyPlan,
    Group,
    Habit,
    Membership,
    Nudge,
    Reaction,
    ReminderLog,
    ScheduleKind,
    StreakState,
    Task,
    User,
    Visibility,
)

# Har testdan keyin tozalanadigan jadvallar (bog'liqlik tartibida)
_TABLES = [
    ReminderLog,
    Nudge,
    Reaction,
    Task,
    DailyPlan,
    StreakState,
    Habit,
    Membership,
    Group,
    User,
]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    if TEST_DB.exists():
        TEST_DB.unlink()
    async with db_module.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await db_module.engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest_asyncio.fixture
async def session(_schema):
    """Toza bazali sessiya. Har test o'z ma'lumoti bilan boshlanadi."""
    async with db_module.session_factory() as s:
        for table in _TABLES:
            await s.execute(delete(table))
        await s.commit()
        yield s


# ─── Fabrikalar ──────────────────────────────────────────────────────────────


@pytest.fixture
def make_user(session):
    async def _make(user_id: int, name: str = "Sinov", **kwargs) -> User:
        user = User(id=user_id, full_name=name, tz="Asia/Tashkent", **kwargs)
        session.add(user)
        await session.flush()
        return user

    return _make


@pytest.fixture
def make_habit(session):
    async def _make(
        user: User,
        title: str = "Odat",
        *,
        points: int = 1,
        visibility: Visibility = Visibility.PUBLIC,
        schedule_kind: ScheduleKind = ScheduleKind.DAILY,
        weekdays_mask: int = 127,
        **kwargs,
    ) -> Habit:
        habit = Habit(
            user_id=user.id,
            title=title,
            points=points,
            visibility=visibility,
            schedule_kind=schedule_kind,
            weekdays_mask=weekdays_mask,
            **kwargs,
        )
        session.add(habit)
        await session.flush()
        return habit

    return _make


# ─── Soxta bot ───────────────────────────────────────────────────────────────


class FakeBot:
    """Telegramga chiqmaydigan bot. Yuborilgan xabarlarni yig'ib boradi.

    `fail_for` ichidagi foydalanuvchilarga yuborishda `TelegramForbiddenError`
    ko'tariladi — bloklangan odam holatini sinash uchun.
    """

    def __init__(self, fail_for: set[int] | None = None):
        self.sent: list[tuple[int, str]] = []
        self.fail_for = fail_for or set()

    async def send_message(self, chat_id: int, text: str, reply_markup=None, **kwargs):
        if chat_id in self.fail_for:
            from aiogram.exceptions import TelegramForbiddenError

            raise TelegramForbiddenError(method=None, message="blocked by user")
        self.sent.append((chat_id, text))
        return True

    def texts_for(self, user_id: int) -> list[str]:
        return [text for uid, text in self.sent if uid == user_id]


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()
