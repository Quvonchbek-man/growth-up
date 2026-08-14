"""Vaqt oralig'i va qo'shimcha vazifalar uchun bir martalik migratsiya.

    python -m scripts.migrate_002_time

Nega kerak: `scripts/init_db.py` faqat YO'Q jadvalni yaratadi, mavjudiga
yangi ustun qo'shmaydi. Server 2026-08-14 dan beri real ishlaydi — bazani
o'chirib qayta yaratish tarixni yo'q qilardi.

**Idempotent:** har qadam avval "bu allaqachon qilinganmi" deb tekshiradi,
shuning uchun ikkinchi marta ishga tushirilsa hech narsa o'zgarmaydi.

Ishga tushirishdan oldin zaxira nusxa oling:

    cp data/growth.db data/backups/growth-$(date +%F).db
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from shared.db import engine

# jadval -> (ustun nomi, SQL turi va standarti)
YANGI_USTUNLAR: dict[str, list[tuple[str, str]]] = {
    "habits": [
        ("start_time", "TIME"),
        ("end_time", "TIME"),
    ],
    "tasks": [
        ("start_time", "TIME"),
        ("end_time", "TIME"),
        ("is_extra", "BOOLEAN NOT NULL DEFAULT 0"),
    ],
    "users": [
        ("task_lead_min", "INTEGER NOT NULL DEFAULT 10"),
    ],
    "daily_plans": [
        ("extra_count", "INTEGER NOT NULL DEFAULT 0"),
        ("extra_done_count", "INTEGER NOT NULL DEFAULT 0"),
    ],
}


async def _ustunlar(conn, jadval: str) -> set[str]:
    rows = await conn.execute(text(f"PRAGMA table_info({jadval})"))
    return {row[1] for row in rows}


async def _ustun_qoshish(conn) -> int:
    qoshildi = 0
    for jadval, ustunlar in YANGI_USTUNLAR.items():
        mavjud = await _ustunlar(conn, jadval)
        if not mavjud:
            print(f"  ! {jadval} jadvali yo'q — tashlab ketildi")
            continue
        for nom, tur in ustunlar:
            if nom in mavjud:
                continue
            await conn.execute(text(f"ALTER TABLE {jadval} ADD COLUMN {nom} {tur}"))
            print(f"  + {jadval}.{nom}")
            qoshildi += 1
    return qoshildi


async def _reminder_log_qayta_qurish(conn) -> bool:
    """`reminder_log` ga `task_id` qo'shadi va UNIQUE cheklovini almashtiradi.

    Bu yerda oddiy `ADD COLUMN` yetmaydi: cheklov `(user_id, kind, date)` dan
    `(user_id, kind, date, task_id)` ga o'zgarishi kerak, SQLite esa mavjud
    cheklovni o'zgartira olmaydi — jadvalni qayta qurish yagona yo'l.

    Yozuvlar `task_id = 0` bilan ko'chiriladi. Ularni tashlab yuborish
    mumkin emas: o'shanda bugungi eslatmalar ikkinchi marta yuborilardi.
    """
    mavjud = await _ustunlar(conn, "reminder_log")
    if not mavjud:
        print("  ! reminder_log jadvali yo'q — tashlab ketildi")
        return False
    if "task_id" in mavjud:
        return False

    await conn.execute(
        text(
            """
            CREATE TABLE reminder_log_new (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind VARCHAR(32) NOT NULL,
                date DATE NOT NULL,
                task_id INTEGER NOT NULL DEFAULT 0,
                sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_reminder_once UNIQUE (user_id, kind, date, task_id)
            )
            """
        )
    )
    await conn.execute(
        text(
            """
            INSERT INTO reminder_log_new (id, user_id, kind, date, task_id, sent_at)
            SELECT id, user_id, kind, date, 0, sent_at FROM reminder_log
            """
        )
    )
    await conn.execute(text("DROP TABLE reminder_log"))
    await conn.execute(text("ALTER TABLE reminder_log_new RENAME TO reminder_log"))
    print("  ~ reminder_log qayta qurildi (task_id qo'shildi)")
    return True


async def _hisoblagichlarni_toldirish() -> int:
    """Mavjud kunlarning `extra_*` hisoblagichlarini qayta hisoblaydi.

    Eski vazifalarda `is_extra = 0`, ya'ni raqamlar nolga teng bo'lishi
    kerak — lekin buni taxmin qilib qo'ymay, `recalc_day` ning o'zi
    hisoblasin: formulaning yagona manbayi shu.
    """
    from sqlalchemy import select

    from services import planning
    from shared.db import session_factory
    from shared.models import DailyPlan

    async with session_factory() as session:
        rows = await session.execute(select(DailyPlan.user_id, DailyPlan.date))
        kunlar = list(rows)
        for user_id, d in kunlar:
            await planning.recalc_day(session, user_id, d)
        await session.commit()
    return len(kunlar)


async def main() -> None:
    print("Migratsiya 002 — vaqt oralig'i va qo'shimcha vazifalar\n")

    async with engine.begin() as conn:
        qoshildi = await _ustun_qoshish(conn)
        qayta_qurildi = await _reminder_log_qayta_qurish(conn)

    if not qoshildi and not qayta_qurildi:
        print("  Hammasi allaqachon joyida — o'zgarish yo'q.")
    else:
        kunlar = await _hisoblagichlarni_toldirish()
        print(f"  OK: {kunlar} ta kun qayta hisoblandi")

    await engine.dispose()
    print("\nTayyor.")


if __name__ == "__main__":
    asyncio.run(main())
