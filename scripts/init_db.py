"""Jadvallarni yaratadi va ro'yxatini chiqaradi.

    python -m scripts.init_db

Alembic'gacha vaqtinchalik yechim. Model o'zgarsa mavjud jadval O'ZGARMAYDI —
ishlab chiqish paytida `data/growth.db` ni o'chirib qayta yaratish eng oson yo'l.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import inspect

from shared.db import create_all, engine


async def main() -> None:
    await create_all()

    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: inspect(c).get_table_names())

    print(f"{len(names)} ta jadval tayyor:")
    for name in sorted(names):
        print(f"  - {name}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
