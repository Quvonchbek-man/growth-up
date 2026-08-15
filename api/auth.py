"""Telegram Mini App autentifikatsiyasi.

Mini App har so'rovda `initData` satrini yuboradi — Telegram uni bot tokeni
bilan imzolagan. Server imzoni qayta hisoblab tekshiradi: shu tekshiruvsiz
har kim `?user_id=123` yozib boshqa odamning ma'lumotini o'qiy olardi.

JWT ataylab yo'q: initData'ning o'zi imzolangan va muddatli. Token qatlamini
qo'shish yangi kod, yangi sirlar va yangi xato yuzasi degani, foyda esa yo'q.

Algoritm (Telegram hujjatlari):
    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    hash       = HMAC_SHA256(key=secret_key, msg=data_check_string)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from services import planning
from shared.config import settings
from shared.db import session_factory
from shared.models import User

logger = logging.getLogger(__name__)

# initData shu muddatdan eski bo'lsa rad etiladi. Telegram tavsiyasi — 1 kun.
MAX_AGE_SECONDS = 24 * 60 * 60


class InitDataError(Exception):
    pass


def parse_init_data(raw: str, bot_token: str, *, max_age: int = MAX_AGE_SECONDS) -> dict:
    """`initData` ni tekshiradi va ichidagi maydonlarni qaytaradi."""
    if not raw:
        raise InitDataError("initData bo'sh")
    if not bot_token:
        raise InitDataError("BOT_TOKEN sozlanmagan — imzoni tekshirib bo'lmaydi")

    # `parse_qsl` bo'sh qiymatlarni ham saqlashi kerak: ular imzoga kiradi
    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise InitDataError("hash yo'q")

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # Doimiy vaqtli solishtirish — imzoni bit-bit topishning oldini oladi
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("imzo mos kelmadi")

    auth_date = int(pairs.get("auth_date", "0") or 0)
    if max_age and (time.time() - auth_date) > max_age:
        raise InitDataError("initData muddati o'tgan — ilovani qayta oching")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InitDataError("foydalanuvchi ma'lumoti yo'q")

    try:
        pairs["user"] = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise InitDataError("foydalanuvchi ma'lumotini o'qib bo'lmadi") from exc

    return pairs


async def get_session() -> AsyncSession:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _extract_init_data(authorization: str | None, x_init_data: str | None) -> str:
    """`Authorization: tma <initData>` yoki `X-Init-Data: <initData>`."""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "tma" and value:
            return value
    return x_init_data or ""


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
) -> User:
    """Har himoyalangan endpoint shu bog'liqlikni oladi."""

    # --- Ishlab chiqish rejimi ---
    if not settings.check_init_data:
        if not settings.dev_mock_user_id:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "CHECK_INIT_DATA=false, lekin DEV_MOCK_USER_ID berilmagan",
            )
        return await planning.get_or_create_user(
            session,
            settings.dev_mock_user_id,
            username="dev",
            full_name="Dev Foydalanuvchi",
        )

    raw = _extract_init_data(authorization, x_init_data)
    try:
        data = parse_init_data(raw, settings.bot_token)
    except InitDataError as exc:
        logger.warning("initData rad etildi (%s): %s", request.url.path, exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    tg = data["user"]
    full_name = " ".join(
        part for part in (tg.get("first_name"), tg.get("last_name")) if part
    )
    return await planning.get_or_create_user(
        session,
        int(tg["id"]),
        username=tg.get("username"),
        full_name=full_name,
    )


def is_admin(user_id: int) -> bool:
    """Botning umumiy admini — `.env` dagi `SUPER_ADMIN_IDS` ro'yxatidan.

    **Bo'sh ro'yxat hech kimga ruxsat bermaydi.** Uni "tekshiruv o'chirilgan"
    deb talqin qilish klassik xato: `.env` to'ldirilmagan yoki noto'g'ri
    yozilgan serverda admin paneli hamma foydalanuvchiga ochilib qolardi.
    """
    return user_id in settings.super_admin_ids


async def current_admin(user: User = Depends(current_user)) -> User:
    """Admin endpointlari uchun. Admin bo'lmasa 403."""
    if not is_admin(user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Bu bo'lim faqat bot admini uchun"
        )
    return user
