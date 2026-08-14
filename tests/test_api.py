"""API — Mini App shu yerdan ma'lumot oladi.

`CHECK_INIT_DATA=false` (conftest'da) bo'lgani uchun har so'rov
`DEV_MOCK_USER_ID` nomidan bajariladi. Imzo tekshiruvining o'zi
`test_auth.py` da alohida sinaladi.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from shared.config import settings

MEN = 1001  # DEV_MOCK_USER_ID


@pytest_asyncio.fixture
async def client(session):
    """`session` fixture'i bazani tozalaydi, keyin ASGI mijozi beriladi."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ─── Asosiy ──────────────────────────────────────────────────────────────────


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_mini_app_kesh_sarlavhasi(client):
    """`index.html` keshdan olinmasligi kerak — aks holda eski versiya qoladi."""
    r = await client.get("/")
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")


async def test_me_va_jamoa_bloki(client):
    r = await client.get("/api/me")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == MEN
    assert data["streak_success_pct"] == settings.streak_success_pct
    # Jamoa hali yaratilmagan — `/team` ochilganda paydo bo'ladi
    assert "group" in data


async def test_sozlamani_ozgartirish(client):
    r = await client.patch(
        "/api/me",
        json={"plan_reminder_at": "22:30", "show_ranking": False},
    )
    assert r.status_code == 200
    assert r.json()["plan_reminder_at"] == "22:30"
    assert r.json()["show_ranking"] is False

    # Saqlanganini alohida so'rovda tasdiqlaymiz
    assert (await client.get("/api/me")).json()["plan_reminder_at"] == "22:30"


async def test_notogri_vaqt_mintaqasi_saqlanmaydi(client):
    oldingi = (await client.get("/api/me")).json()["tz"]
    r = await client.patch("/api/me", json={"tz": "Mars/Olympus"})
    assert r.status_code == 200
    assert r.json()["tz"] == oldingi


# ─── Kun va vazifalar ────────────────────────────────────────────────────────


async def test_kun_korinishi(client):
    for day in ("today", "tomorrow"):
        r = await client.get(f"/api/day/{day}")
        assert r.status_code == 200, day
        assert r.json()["tasks"] == []


async def test_notogri_sana(client):
    r = await client.get("/api/day/kecha-kunduz")
    assert r.status_code == 400


async def test_vazifa_hayoti(client):
    """Qo'shish → belgilash → o'chirish, har qadamda hisoblagichlar to'g'ri."""
    r = await client.post("/api/day/tomorrow/tasks", json={"title": "Hisobot", "points": 4})
    assert r.status_code == 201
    view = r.json()
    assert view["planned_count"] == 1
    task_id = view["tasks"][0]["id"]

    r = await client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert r.status_code == 200
    assert r.json()["done_count"] == 1
    assert r.json()["score"] == 4

    r = await client.delete(f"/api/tasks/{task_id}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert (await client.get("/api/day/tomorrow")).json()["planned_count"] == 0


async def test_bosh_nomli_vazifa_rad_etiladi(client):
    # Faqat bo'shliqdan iborat nom pydantic'dan o'tadi, `add_task` rad etadi
    r = await client.post("/api/day/tomorrow/tasks", json={"title": "   "})
    assert r.status_code == 400
    # Umuman bo'sh satrni esa pydantic ushlaydi
    r = await client.post("/api/day/tomorrow/tasks", json={"title": ""})
    assert r.status_code == 422


async def test_begona_vazifa_topilmaydi(client):
    r = await client.patch("/api/tasks/999999", json={"status": "done"})
    assert r.status_code == 404


async def test_rejani_tasdiqlash(client):
    await client.post("/api/day/tomorrow/tasks", json={"title": "Ish"})
    r = await client.post("/api/day/tomorrow/submit")
    assert r.status_code == 200
    assert r.json()["submitted"] is True


# ─── Odatlar ─────────────────────────────────────────────────────────────────


async def test_odat_crud(client):
    r = await client.post(
        "/api/habits",
        json={"title": "Yugurish", "points": 3, "visibility": "private"},
    )
    assert r.status_code == 201
    habit = r.json()
    assert habit["title"] == "Yugurish"
    assert habit["visibility"] == "private"

    r = await client.put(f"/api/habits/{habit['id']}", json={"title": "Sport", "points": 5})
    assert r.status_code == 200
    assert r.json()["title"] == "Sport"

    # O'chirish emas, arxivlash: o'tmish statistika buzilmasligi kerak
    assert (await client.delete(f"/api/habits/{habit['id']}")).status_code == 200
    assert (await client.get("/api/habits")).json() == []


async def test_odat_bugungi_royxatga_tushadi(client):
    await client.post("/api/habits", json={"title": "Kitob", "points": 2})
    r = await client.get("/api/day/today")
    nomlar = [t["title"] for t in r.json()["tasks"]]
    assert nomlar == ["Kitob"]


async def test_ball_chegarasi_apida(client):
    r = await client.post("/api/habits", json={"title": "Katta", "points": 50})
    assert r.status_code == 422, "1..10 dan tashqarisi qabul qilinmasligi kerak"


# ─── Jamoa ───────────────────────────────────────────────────────────────────


async def test_jamoa_ozi_yaratiladi(client):
    r = await client.get("/api/team")
    assert r.status_code == 200
    data = r.json()
    assert data["group"]["is_owner"] is True
    assert len(data["group"]["invite_code"]) == 6
    assert data["partners"] == []


async def test_taklif_kodi_me_da_ham_keladi(client):
    kod = (await client.get("/api/team")).json()["group"]["invite_code"]
    group = (await client.get("/api/me")).json()["group"]
    assert group["invite_code"] == kod
    assert group["partners"] == []


async def test_notogri_kod_bilan_qoshilish(client):
    r = await client.post("/api/team/join", json={"code": "YOQKOD"})
    assert r.status_code == 400


async def test_yolgiz_odam_chiqa_olmaydi(client):
    await client.get("/api/team")
    r = await client.post("/api/team/leave")
    assert r.status_code == 400


async def test_jamoa_nomini_ozgartirish(client):
    await client.get("/api/team")
    r = await client.patch("/api/team", json={"name": "Yangi nom"})
    assert r.status_code == 200
    assert (await client.get("/api/team")).json()["group"]["name"] == "Yangi nom"


async def test_kodni_yangilash(client):
    eski = (await client.get("/api/team")).json()["group"]["invite_code"]
    r = await client.post("/api/team/code")
    assert r.status_code == 200
    assert r.json()["invite_code"] != eski


async def test_ozimga_turtki_bera_olmayman(client):
    await client.get("/api/team")
    r = await client.post("/api/team/nudge", json={"to_user_id": MEN})
    assert r.status_code == 400


async def test_begonaga_turtki_taqiqlanadi(client):
    await client.get("/api/team")
    r = await client.post("/api/team/nudge", json={"to_user_id": 777})
    assert r.status_code == 403


async def test_yoq_odamni_chiqarib_bolmaydi(client):
    await client.get("/api/team")
    r = await client.delete("/api/team/members/777")
    assert r.status_code == 400


# ─── Statistika ──────────────────────────────────────────────────────────────


async def test_statistika(client):
    r = await client.get("/api/stats?days=7")
    assert r.status_code == 200
    data = r.json()
    assert len(data["series"]) == 7, "bo'sh kunlar ham qatorda bo'lishi kerak"
