"""A'zolar dinamikasi uchun: `users.blocked_at`.

    python -m scripts.migrate_003_blocked_at

Nega kerak: `is_blocked` faqat bayroq — kim bloklagani ko'rinadi, lekin
QACHON bloklagani emas. Admin paneldagi "a'zolar dinamikasi" grafigida
"shu kuni nechta odam ketdi" degan raqam aynan shu maydondan chiqadi.

**Idempotent** — ikkinchi marta ishga tushirilsa hech narsa qilmaydi.

Eski ma'lumot haqida: bloklash sanasi hech qachon saqlanmagan, ya'ni uni
tiklab bo'lmaydi. Migratsiya taxminiy qiymat qo'yadi — `updated_at`
(yozuvga oxirgi tegilgan payt). Bloklangan foydalanuvchiga bundan keyin
tegilmaydi, shuning uchun bu odatda aynan bloklash payti bo'ladi. Bu
qiymat **taxminiy**, migratsiyadan keyingi ma'lumot esa aniq.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from shared.db import engine


async def _ustunlar(conn, jadval: str) -> set[str]:
    rows = await conn.execute(text(f"PRAGMA table_info({jadval})"))
    return {row[1] for row in rows}


async def main() -> None:
    print("Migratsiya 003 - users.blocked_at\n")

    async with engine.begin() as conn:
        mavjud = await _ustunlar(conn, "users")
        if not mavjud:
            print("  ! users jadvali yo'q - tashlab ketildi")
        elif "blocked_at" in mavjud:
            print("  Hammasi allaqachon joyida - o'zgarish yo'q.")
        else:
            await conn.execute(text("ALTER TABLE users ADD COLUMN blocked_at DATETIME"))
            print("  + users.blocked_at")

            natija = await conn.execute(
                text(
                    "UPDATE users SET blocked_at = updated_at "
                    "WHERE is_blocked = 1 AND blocked_at IS NULL"
                )
            )
            print(
                f"  ~ {natija.rowcount} ta eski bloklangan foydalanuvchiga "
                "taxminiy sana qo'yildi (updated_at)"
            )

    await engine.dispose()
    print("\nTayyor.")


if __name__ == "__main__":
    asyncio.run(main())
