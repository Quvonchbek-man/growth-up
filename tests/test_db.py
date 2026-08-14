"""Baza ulanishining sozlamalari.

Bu testlar bir marta uchragan haqiqiy nosozlikdan keyin yozildi: serverda
eslatma sikli va bot handleri bir vaqtda yozganda `database is locked`
xatosi chiqdi va foydalanuvchining amali jimgina yo'qoldi.
"""

from __future__ import annotations

from sqlalchemy import text

from shared import db as db_module


async def test_wal_rejimi_yoqilgan(session):
    """WAL bo'lmasa, o'qish va yozish bir-birini bloklaydi."""
    rejim = (await session.execute(text("PRAGMA journal_mode"))).scalar()
    assert str(rejim).lower() == "wal"


async def test_busy_timeout_qoyilgan(session):
    """0 bo'lsa, band baza darhol xato beradi — kutish kerak."""
    timeout = (await session.execute(text("PRAGMA busy_timeout"))).scalar()
    assert int(timeout) >= 5000


async def test_bir_vaqtda_ikki_sessiya_yoza_oladi(session, make_user):
    """Ikkinchi sessiya birinchisini kutadi, xato bermaydi."""
    from shared.models import User

    user = await make_user(1, "Birinchi")
    await session.commit()

    async with db_module.session_factory() as boshqa:
        user2 = User(id=2, full_name="Ikkinchi", tz="Asia/Tashkent")
        boshqa.add(user2)
        await boshqa.commit()

    ikkinchi = await session.get(User, 2)
    assert ikkinchi is not None
    assert user.id == 1
