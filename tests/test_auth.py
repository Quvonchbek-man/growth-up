"""initData imzosi — ilovaning yagona qulfi.

Bu tekshiruv buzilsa, har kim `user_id` ni o'zgartirib boshqa odamning
rejalari, statistikasi va jamoasiga kira oladi. Shuning uchun bu yerda
"ishlaydimi" emas, "buzib bo'ladimi" tekshiriladi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from api.auth import InitDataError, parse_init_data

TOKEN = "123456:TEST-TOKEN"


def make_init_data(
    *,
    token: str = TOKEN,
    user_id: int = 42,
    auth_date: int | None = None,
    extra: dict | None = None,
) -> str:
    """Telegram yuboradigan `initData` ning haqiqiy nusxasi."""
    pairs = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(
            {"id": user_id, "first_name": "Sinov", "username": "test"},
            separators=(",", ":"),
        ),
    }
    pairs.update(extra or {})

    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_togri_imzo_otadi():
    data = parse_init_data(make_init_data(user_id=777), TOKEN)
    assert data["user"]["id"] == 777
    assert data["user"]["username"] == "test"


def test_bosh_initdata():
    with pytest.raises(InitDataError):
        parse_init_data("", TOKEN)


def test_hash_yoq():
    with pytest.raises(InitDataError):
        parse_init_data("auth_date=1&user=%7B%22id%22%3A1%7D", TOKEN)


def test_boshqa_token_bilan_imzolangan():
    """Boshqa botning initData'si bizning botga o'tmasligi kerak."""
    begona = make_init_data(token="999999:BEGONA-TOKEN")
    with pytest.raises(InitDataError):
        parse_init_data(begona, TOKEN)


def test_user_id_ozgartirilsa_rad_etiladi():
    """Eng muhim hujum: imzoni qoldirib, foydalanuvchi id sini almashtirish."""
    raw = make_init_data(user_id=42)
    # urlencode'da `{"id":42,` shunday ko'rinadi: `%7B%22id%22%3A42%2C`
    buzilgan = raw.replace("%22id%22%3A42", "%22id%22%3A99")
    assert buzilgan != raw, "sinov satri haqiqatan o'zgargan bo'lishi kerak"

    with pytest.raises(InitDataError):
        parse_init_data(buzilgan, TOKEN)


def test_hash_ozgartirilsa_rad_etiladi():
    raw = make_init_data()
    buzilgan = raw[:-1] + ("0" if raw[-1] != "0" else "1")
    with pytest.raises(InitDataError):
        parse_init_data(buzilgan, TOKEN)


def test_muddati_otgan():
    eski = int(time.time()) - 60 * 60 * 48  # 2 kun oldin
    with pytest.raises(InitDataError):
        parse_init_data(make_init_data(auth_date=eski), TOKEN)


def test_muddat_tekshiruvini_ochirish_mumkin():
    """Sinov va nosozlikni tuzatish uchun — ishlab chiqarishda ishlatilmaydi."""
    eski = int(time.time()) - 60 * 60 * 48
    data = parse_init_data(make_init_data(auth_date=eski), TOKEN, max_age=0)
    assert data["user"]["id"] == 42


def test_tokensiz_tekshirib_bolmaydi():
    with pytest.raises(InitDataError):
        parse_init_data(make_init_data(), "")


def test_foydalanuvchi_malumoti_yoq():
    pairs = {"auth_date": str(int(time.time()))}
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()

    with pytest.raises(InitDataError):
        parse_init_data(urlencode(pairs), TOKEN)


def test_bosh_qiymatli_maydon_imzoni_buzmaydi():
    """`start_param=` kabi bo'sh maydonlar ham imzoga kiradi."""
    data = parse_init_data(make_init_data(extra={"start_param": ""}), TOKEN)
    assert data["start_param"] == ""
