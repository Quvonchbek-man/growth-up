"""Qo'shimcha vazifalar — reja va'dasini buzmasligi.

Butun o'zgarishning ma'nosi bitta qoidada: **kun ichida qo'shilgan ish
foizga ham, ballga ham, streakka ham kirmaydi.** Bu qoida buzilsa, ertalab
bajarilgan ishni qo'shib qo'yish orqali foizni ko'tarish mumkin bo'ladi
(2/4 = 50% edi, 3/5 = 60% bo'lardi) va sherik ko'rgan raqam yolg'onga
aylanadi — ya'ni ilovaning yagona qiymati yo'qoladi.

Qo'shimcha ekanini API hal qiladi (`api/routers/days.py`), shuning uchun
tekshiruvlar ham API orqali.
"""

from __future__ import annotations

from datetime import time, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from services import notify, planning, scoring, stats, streak
from shared import clock
from shared.models import TaskStatus, User

MEN = 1001  # DEV_MOCK_USER_ID


@pytest_asyncio.fixture
async def client(session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def men(client, session) -> User:
    """API nomidan ishlaydigan foydalanuvchi.

    Birinchi so'rov uni yaratadi (`get_or_create_user`) — shundan keyin uni
    servis funksiyalari uchun to'g'ridan-to'g'ri olamiz.
    """
    await client.get("/api/me")
    return await session.get(User, MEN)


def _kech_vaqt() -> str:
    """Hozirgidan keyingi vaqt (o'tgan vaqt taqiqiga tushmasligi uchun)."""
    return clock.shift_time(clock.now_local().time(), 30).isoformat("minutes")


# ─── Sinf ajratmasi ──────────────────────────────────────────────────────────


async def test_bugunga_qoshilgani_qoshimcha(client):
    r = await client.post("/api/day/today/tasks", json={"title": "Kutilmagan ish"})
    assert r.status_code == 201
    (task,) = [t for t in r.json()["tasks"] if t["title"] == "Kutilmagan ish"]
    assert task["is_extra"] is True


async def test_ertangiga_qoshilgani_reja(client):
    r = await client.post("/api/day/tomorrow/tasks", json={"title": "Rejadagi ish"})
    assert r.status_code == 201
    (task,) = r.json()["tasks"]
    assert task["is_extra"] is False


async def test_otgan_kunga_qoshib_bolmaydi(client):
    kecha = (clock.today_local() - timedelta(days=1)).isoformat()
    r = await client.post(f"/api/day/{kecha}/tasks", json={"title": "Soxta tarix"})
    assert r.status_code == 400


# ─── Asosiy qoida: hisobga kirmaslik ─────────────────────────────────────────


async def test_qoshimcha_foizni_ozgartirmaydi(client, session, men):
    """Ikkita rejadan bittasi bajarilgan = 50%. Qo'shimcha buni tebratmasligi kerak."""
    # Kechqurun kiritilgan va'dani taqlid qilamiz: API orqali bugunga
    # reja qo'shib bo'lmaydi (aynan shu taqiq sinalayotgan qoida), shuning
    # uchun servis qatlamidan to'g'ridan-to'g'ri yozamiz.
    bugun = clock.today_local(men.tz)
    reja1 = await planning.add_task(session, men, bugun, "Reja 1", is_extra=False)
    await planning.add_task(session, men, bugun, "Reja 2", is_extra=False)
    await planning.set_status(session, men.id, reja1.id, TaskStatus.DONE)
    await session.commit()

    oldin = (await client.get("/api/day/today")).json()
    assert oldin["completion_pct"] == 50
    assert oldin["planned_count"] == 2

    r = await client.post("/api/day/today/tasks", json={"title": "Qo'shimcha"})
    keyin = r.json()
    assert keyin["completion_pct"] == 50, "qo'shimcha maxrajga kirmasligi kerak"
    assert keyin["planned_count"] == 2
    assert keyin["extra_count"] == 1

    # Bajarib qo'yish ham foizni ko'tarmasligi kerak
    (qoshimcha,) = [t for t in keyin["tasks"] if t["is_extra"]]
    bajarildi = (
        await client.patch(f"/api/tasks/{qoshimcha['id']}", json={"status": "done"})
    ).json()
    assert bajarildi["completion_pct"] == 50
    assert bajarildi["done_count"] == 1
    assert bajarildi["extra_done_count"] == 1


async def test_qoshimcha_ball_bermaydi(client, session, men):
    await planning.add_task(
        session, men, clock.today_local(men.tz), "Reja", points=5
    )
    await session.commit()

    r = await client.post(
        "/api/day/today/tasks", json={"title": "Qo'shimcha", "points": 10}
    )
    (qoshimcha,) = [t for t in r.json()["tasks"] if t["is_extra"]]
    keyin = (
        await client.patch(f"/api/tasks/{qoshimcha['id']}", json={"status": "done"})
    ).json()

    assert keyin["score"] == 0, "qo'shimcha bajarilsa ham ball bermaydi"
    assert keyin["max_score"] == 5, "qo'shimcha imkoniyat balliga ham kirmaydi"


async def test_qoshimcha_reytingga_kirmaydi(session, make_user):
    """Reyting `tasks` dan hisoblanadi — `scoring.py` dagi ajratma u yerga yetmaydi."""
    user = await make_user(1)
    bugun = clock.today_local(user.tz)

    reja = await planning.add_task(session, user, bugun, "Reja", points=3)
    qosh = await planning.add_task(
        session, user, bugun, "Qo'shimcha", points=7, is_extra=True
    )
    await planning.set_status(session, user.id, reja.id, TaskStatus.DONE)
    await planning.set_status(session, user.id, qosh.id, TaskStatus.DONE)

    (qator,) = await stats.leaderboard(session, [user], bugun, bugun)
    assert qator["score"] == 3, "7 ball qo'shimchadan — reytingga o'tmasligi kerak"
    assert qator["done_count"] == 1


async def test_qoshimcha_streakni_tebratmaydi(session, make_user):
    """Rejasi yo'q kunda bir nechta qo'shimcha bajarilsa ham kun muvaffaqiyatli bo'lmaydi."""
    user = await make_user(1)
    kecha = clock.today_local(user.tz) - timedelta(days=1)

    for i in range(3):
        task = await planning.add_task(
            session, user, kecha, f"Qo'shimcha {i}", is_extra=True
        )
        await planning.set_status(session, user.id, task.id, TaskStatus.DONE)

    holat = await streak.recalc(session, user)
    assert holat.current_len == 0


# ─── Vaqt qoidasi ────────────────────────────────────────────────────────────


async def test_qoshimchaga_otgan_vaqt_qoyilmaydi(client):
    otgan = clock.shift_time(clock.now_local().time(), -60).isoformat("minutes")
    r = await client.post(
        "/api/day/today/tasks", json={"title": "Orqadan", "start_time": otgan}
    )
    assert r.status_code == 400
    assert "o'tgan vaqt" in r.json()["detail"].lower()


async def test_qoshimchaga_kelajak_vaqt_qoyiladi(client):
    r = await client.post(
        "/api/day/today/tasks", json={"title": "Keyinroq", "start_time": _kech_vaqt()}
    )
    assert r.status_code == 201
    (task,) = [t for t in r.json()["tasks"] if t["is_extra"]]
    assert task["start_time"] == _kech_vaqt()


async def test_ertangi_rejaga_istagan_vaqt(client):
    """Ertangi kunga ertalabki vaqt qo'yish taqiqlanmasligi kerak."""
    r = await client.post(
        "/api/day/tomorrow/tasks", json={"title": "Ertalabki", "start_time": "06:00"}
    )
    assert r.status_code == 201


# ─── Qolgan ta'sirlar ────────────────────────────────────────────────────────


async def test_qoshimchadan_sabab_soralmaydi(session, make_user, bot):
    """Va'da qilinmagan ish uchun hisobot so'rash qo'shimchani o'ldiradi."""
    user = await make_user(1)
    kecha = clock.today_local(user.tz) - timedelta(days=1)
    await planning.add_task(session, user, kecha, "Reja", is_extra=False)
    await planning.add_task(session, user, kecha, "Qo'shimcha", is_extra=True)
    await planning.close_day(session, user, kecha)

    soraladi = await planning.missed_tasks_without_reason(session, user.id, kecha)
    assert [t.title for t in soraladi] == ["Reja"]

    await notify.ask_reasons(bot, session, user)
    matnlar = " ".join(bot.texts_for(1))
    assert "Qo'shimcha" not in matnlar


async def test_bugungi_rejani_ochirib_bolmaydi(client, session, men):
    reja = await planning.add_task(
        session, men, clock.today_local(men.tz), "Va'da", is_extra=False
    )
    await session.commit()

    r = await client.delete(f"/api/tasks/{reja.id}")
    assert r.status_code == 400


async def test_qoshimchani_ochirish_mumkin(client):
    r = await client.post("/api/day/today/tasks", json={"title": "Keraksiz"})
    (qoshimcha,) = [t for t in r.json()["tasks"] if t["is_extra"]]

    assert (await client.delete(f"/api/tasks/{qoshimcha['id']}")).status_code == 200
    assert (await client.get("/api/day/today")).json()["extra_count"] == 0


def test_summarize_ikki_guruhni_ajratadi():
    """Ajratmaning o'zi — `scoring.py`. Bu yerda formulaning o'zi tekshiriladi."""

    class SoxtaVazifa:
        def __init__(self, status, points, is_extra):
            self.status = status
            self.points = points
            self.is_extra = is_extra

    vazifalar = [
        SoxtaVazifa(TaskStatus.DONE, 3, False),
        SoxtaVazifa(TaskStatus.PLANNED, 2, False),
        SoxtaVazifa(TaskStatus.DONE, 9, True),
    ]
    natija = scoring.summarize(vazifalar)

    assert natija["planned_count"] == 2
    assert natija["done_count"] == 1
    assert natija["completion_pct"] == 50
    assert natija["score"] == 3
    assert natija["max_score"] == 5
    assert natija["extra_count"] == 1
    assert natija["extra_done_count"] == 1
