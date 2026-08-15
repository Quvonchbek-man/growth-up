"""Odat jadvali: tanlangan kunlar QAT'IY bajarilishi.

Real ishlatishda chiqqan xato (2026-08-15): «har kuni» qilib yaratilgan
odat Du/Ch/Ju ga o'zgartirilgandan keyin ham yakshanba rejasida qolib
ketardi — nusxa allaqachon yaratilgan edi, uni hech kim olib tashlamasdi.
Shu yerdagi testlar aynan shuni qo'riqlaydi, shuning uchun ular
`test_planning.py` dagi "yaratish" testlaridan ajratilgan.
"""

from __future__ import annotations

from datetime import timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from services import planning, stats
from shared import clock
from shared.models import ScheduleKind, TaskSource, TaskStatus, User

MEN = 1001  # DEV_MOCK_USER_ID


@pytest_asyncio.fixture
async def client(session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def men(client, session) -> User:
    """API nomidan ishlaydigan foydalanuvchi (`test_extra_tasks.py` dagi kabi).

    API o'z sessiyasini ochadi, shuning uchun tayyorgarlik ma'lumoti
    so'rovdan oldin **commit** qilinishi shart — aks holda SQLite
    `database is locked` beradi.
    """
    await client.get("/api/me")
    return await session.get(User, MEN)


def _mask(*weekdays: int) -> int:
    mask = 0
    for weekday in weekdays:
        mask |= 1 << (weekday % 7)
    return mask


# ─── Jadval torayganda tozalanishi ───────────────────────────────────────────


async def test_jadvaldan_chiqqan_odat_ertangi_rejadan_olinadi(
    session, make_user, make_habit
):
    user = await make_user(MEN)
    habit = await make_habit(user, "Data analitika")  # har kuni
    ertaga = clock.tomorrow_local(user.tz)

    _, tasks = await planning.open_day(session, user, ertaga)
    assert [t.title for t in tasks] == ["Data analitika"]

    # Jadval toraydi: ertangi kun endi unga kirmaydi
    habit.schedule_kind = ScheduleKind.WEEKDAYS
    habit.weekdays_mask = _mask(ertaga.weekday() + 1, ertaga.weekday() + 2)
    await session.flush()

    _, tasks = await planning.open_day(session, user, ertaga)
    assert tasks == []

    plan = await planning.get_plan(session, user.id, ertaga)
    assert plan.planned_count == 0


async def test_jadvalga_kun_qoshilsa_nusxa_paydo_boladi(session, make_user, make_habit):
    user = await make_user(MEN)
    ertaga = clock.tomorrow_local(user.tz)
    habit = await make_habit(
        user,
        "English",
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=_mask(ertaga.weekday() + 1),
    )

    _, tasks = await planning.open_day(session, user, ertaga)
    assert tasks == []

    habit.weekdays_mask = _mask(ertaga.weekday(), ertaga.weekday() + 1)
    await session.flush()

    _, tasks = await planning.open_day(session, user, ertaga)
    assert [t.title for t in tasks] == ["English"]


async def test_bajarilgan_nusxa_jadval_ozgarsa_ham_saqlanadi(
    session, make_user, make_habit
):
    """Tarix o'zgarmas: `DONE` ish hech qachon yo'qolmaydi."""
    user = await make_user(MEN)
    habit = await make_habit(user, "Mutolaa")
    bugun = clock.today_local(user.tz)

    _, tasks = await planning.open_day(session, user, bugun)
    await planning.set_status(session, user.id, tasks[0].id, TaskStatus.DONE)

    habit.schedule_kind = ScheduleKind.WEEKDAYS
    habit.weekdays_mask = _mask(bugun.weekday() + 1)
    await session.flush()

    _, tasks = await planning.open_day(session, user, bugun)
    assert [t.status for t in tasks] == [TaskStatus.DONE]


async def test_otmish_kuni_tozalanmaydi(session, make_user, make_habit):
    """`open_day` o'tmishga umuman tegmaydi — na qo'shadi, na o'chiradi."""
    user = await make_user(MEN)
    habit = await make_habit(user, "Yugurish")
    bugun = clock.today_local(user.tz)
    kecha = bugun - timedelta(days=1)

    _, tasks = await planning.open_day(session, user, bugun)
    kechagi = tasks[0]
    kechagi.date = kecha  # kechagi nusxani taqlid qilamiz
    await session.flush()

    habit.schedule_kind = ScheduleKind.WEEKDAYS
    habit.weekdays_mask = _mask(kecha.weekday() + 1)
    await session.flush()

    _, tasks = await planning.open_day(session, user, kecha)
    assert [t.title for t in tasks] == ["Yugurish"]


async def test_odatni_tahrirlash_ertangi_rejani_yangilaydi(
    client, session, men, make_habit
):
    """`PUT /habits/{id}` javob qaytarganda ertangi reja allaqachon to'g'ri."""
    habit = await make_habit(men, "Data analitika")
    ertaga = clock.tomorrow_local(men.tz)
    await session.commit()

    assert len((await client.get("/api/day/tomorrow")).json()["tasks"]) == 1

    r = await client.put(
        f"/api/habits/{habit.id}",
        json={
            "title": "Data analitika",
            "schedule_kind": "weekdays",
            "weekdays_mask": _mask(ertaga.weekday() + 1),
        },
    )
    assert r.status_code == 200

    assert (await client.get("/api/day/tomorrow")).json()["tasks"] == []


# ─── Qo'lda qo'shish ─────────────────────────────────────────────────────────


async def test_qolda_qoshilgan_odat_qayta_ochilganda_saqlanadi(
    session, make_user, make_habit
):
    """Asosiy shart: tozalash faqat AVTOMATIK nusxalarga tegadi."""
    user = await make_user(MEN)
    ertaga = clock.tomorrow_local(user.tz)
    habit = await make_habit(
        user,
        "Data analitika",
        points=3,
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=_mask(ertaga.weekday() + 1),
    )

    task = await planning.add_habit_task(session, user, ertaga, habit)
    assert task.source == TaskSource.MANUAL
    assert task.habit_id == habit.id
    assert task.is_extra is False
    assert task.points == 3

    _, tasks = await planning.open_day(session, user, ertaga)
    assert [t.title for t in tasks] == ["Data analitika"]

    plan = await planning.get_plan(session, user.id, ertaga)
    assert plan.planned_count == 1

    # Qo'lda qo'shilgani ham REJA — ball imkoniga kiradi (qo'shimcha emas)
    view = await stats.day_view(session, user, ertaga, owner=True)
    assert view["max_score"] == 3
    assert view["extra_count"] == 0


async def test_qolda_qoshish_endpointi(client, session, men, make_habit):
    ertaga = clock.tomorrow_local(men.tz)
    habit = await make_habit(
        men,
        "Data analitika",
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=_mask(ertaga.weekday() + 1),
    )
    await session.commit()

    r = await client.post("/api/day/tomorrow/habits", json={"habit_id": habit.id})
    assert r.status_code == 201
    tasks = r.json()["tasks"]
    assert [t["title"] for t in tasks] == ["Data analitika"]
    # Frontend ✕ tugmasini aynan shu bo'yicha chizadi
    assert tasks[0]["source"] == "manual"

    # Ikkinchi marta — UNIQUE cheklovigacha bormay, tushunarli xato
    r = await client.post("/api/day/tomorrow/habits", json={"habit_id": habit.id})
    assert r.status_code == 400


async def test_bugunga_va_otmishga_odat_qoshib_bolmaydi(
    client, session, men, make_habit
):
    """Bugungi reja — kechqurun berilgan va'da, unga ortdan qo'shilmaydi."""
    habit = await make_habit(
        men,
        "Data analitika",
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=_mask(clock.today_local(men.tz).weekday() + 1),
    )
    kecha = (clock.today_local(men.tz) - timedelta(days=1)).isoformat()
    await session.commit()

    assert (
        await client.post("/api/day/today/habits", json={"habit_id": habit.id})
    ).status_code == 400
    assert (
        await client.post(f"/api/day/{kecha}/habits", json={"habit_id": habit.id})
    ).status_code == 400


async def test_begona_va_arxivlangan_odat_qoshilmaydi(
    client, session, men, make_user, make_habit
):
    boshqa = await make_user(2002, name="Sherik")
    begona = await make_habit(boshqa, "Sherikning odati")
    arxiv = await make_habit(men, "Eski odat", is_archived=True)
    await session.commit()

    assert (
        await client.post("/api/day/tomorrow/habits", json={"habit_id": begona.id})
    ).status_code == 404
    assert (
        await client.post("/api/day/tomorrow/habits", json={"habit_id": arxiv.id})
    ).status_code == 404
    assert (
        await client.post("/api/day/tomorrow/habits", json={"habit_id": 999})
    ).status_code == 404


async def test_qolda_qoshilgan_odat_kochirilmaydi(session, make_user, make_habit):
    """`UNIQUE(user, date, habit_id)` ni buzmaslik uchun shart `habit_id` bo'yicha."""
    user = await make_user(MEN)
    ertaga = clock.tomorrow_local(user.tz)
    habit = await make_habit(
        user,
        "Data analitika",
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=_mask(ertaga.weekday() + 1),
    )
    task = await planning.add_habit_task(session, user, ertaga, habit)

    assert await planning.move_task(session, user, task.id, ertaga + timedelta(days=1)) is None
