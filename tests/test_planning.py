"""Kun hayoti: odatdan vazifa yaratish, belgilash, tasdiqlash, yopish.

Loyihaning o'zagi shu yerda — bu testlar yiqilsa ilova ishlamaydi.
"""

from __future__ import annotations

from datetime import timedelta

from services import planning
from shared import clock
from shared.models import ScheduleKind, TaskSource, TaskStatus


async def test_odatdan_kunlik_vazifa_yaratiladi(session, make_user, make_habit):
    user = await make_user(1)
    await make_habit(user, "Yugurish", points=3)
    await make_habit(user, "Kitob", points=2)

    today = clock.today_local(user.tz)
    plan, tasks = await planning.open_day(session, user, today)

    assert len(tasks) == 2
    assert {t.title for t in tasks} == {"Yugurish", "Kitob"}
    assert all(t.source == TaskSource.HABIT for t in tasks)
    assert plan.planned_count == 2
    assert plan.score == 0


async def test_takroriy_ochilishda_nusxa_kopaymaydi(session, make_user, make_habit):
    """Ilova kuniga o'nlab marta ochiladi — har safar vazifa qo'shilmasligi kerak."""
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    today = clock.today_local(user.tz)

    await planning.open_day(session, user, today)
    await planning.open_day(session, user, today)
    _, tasks = await planning.open_day(session, user, today)

    assert len(tasks) == 1


async def test_hafta_kunlari_jadvali(session, make_user, make_habit):
    user = await make_user(1)
    today = clock.today_local(user.tz)
    # Faqat bugungi hafta kuni yoqilgan odat
    await make_habit(
        user,
        "Faqat bugun",
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=1 << today.weekday(),
    )
    # Faqat ertangi hafta kuni yoqilgan odat
    await make_habit(
        user,
        "Faqat ertaga",
        schedule_kind=ScheduleKind.WEEKDAYS,
        weekdays_mask=1 << ((today.weekday() + 1) % 7),
    )

    _, tasks = await planning.open_day(session, user, today)
    assert [t.title for t in tasks] == ["Faqat bugun"]

    _, tomorrow_tasks = await planning.open_day(session, user, today + timedelta(days=1))
    assert [t.title for t in tomorrow_tasks] == ["Faqat ertaga"]


async def test_arxivlangan_odat_yaratilmaydi(session, make_user, make_habit):
    user = await make_user(1)
    await make_habit(user, "Eski odat", is_archived=True)
    await make_habit(user, "Yangi odat")

    _, tasks = await planning.open_day(session, user, clock.today_local(user.tz))
    assert [t.title for t in tasks] == ["Yangi odat"]


async def test_otmish_kunga_odat_qoshilmaydi(session, make_user, make_habit):
    """Soxta tarix yaratmaslik: kecha ochilsa, bugungi odat u yerga tushmasin."""
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    kecha = clock.today_local(user.tz) - timedelta(days=1)

    _, tasks = await planning.open_day(session, user, kecha)
    assert tasks == []


async def test_qol_vazifasi_qoshiladi_va_ochiriladi(session, make_user):
    user = await make_user(1)
    today = clock.today_local(user.tz)
    await planning.open_day(session, user, today)

    task = await planning.add_task(session, user, today, "Hisobotni tugatish", points=5)
    assert task.source == TaskSource.MANUAL
    assert task.points == 5

    plan = await planning.get_plan(session, user.id, today)
    assert plan.planned_count == 1

    assert await planning.delete_task(session, user.id, task.id) is True
    plan = await planning.get_plan(session, user.id, today)
    assert plan.planned_count == 0


async def test_ball_chegarasi(session, make_user):
    """1..10 oralig'idan chiqmasligi kerak — reyting shunga tayanadi."""
    user = await make_user(1)
    today = clock.today_local(user.tz)
    kop = await planning.add_task(session, user, today, "Katta", points=999)
    kam = await planning.add_task(session, user, today, "Kichik", points=-5)
    assert kop.points == 10
    assert kam.points == 1


async def test_begona_vazifaga_tegib_bolmaydi(session, make_user):
    """Boshqa odamning vazifasini o'zgartirish/o'chirish mumkin emas."""
    egasi = await make_user(1)
    begona = await make_user(2)
    today = clock.today_local(egasi.tz)
    task = await planning.add_task(session, egasi, today, "Shaxsiy ish")

    assert await planning.set_status(session, begona.id, task.id, TaskStatus.DONE) is None
    assert await planning.delete_task(session, begona.id, task.id) is False
    assert await planning.move_task(session, begona.id, task.id, today) is None


async def test_belgilash_hisoblagichlarni_yangilaydi(session, make_user, make_habit):
    user = await make_user(1)
    await make_habit(user, "Yugurish", points=3)
    await make_habit(user, "Kitob", points=2)
    today = clock.today_local(user.tz)
    _, tasks = await planning.open_day(session, user, today)

    await planning.set_status(session, user.id, tasks[0].id, TaskStatus.DONE)
    plan = await planning.get_plan(session, user.id, today)
    assert plan.done_count == 1
    assert plan.score == tasks[0].points
    assert plan.completion_pct == 50

    # Fikrdan qaytish: belgini olib tashlash
    await planning.set_status(session, user.id, tasks[0].id, TaskStatus.PLANNED)
    plan = await planning.get_plan(session, user.id, today)
    assert plan.done_count == 0
    assert plan.score == 0


async def test_bajarilganda_eski_sabab_tozalanadi(session, make_user):
    from shared.models import MissReason

    user = await make_user(1)
    today = clock.today_local(user.tz)
    task = await planning.add_task(session, user, today, "Ish")

    await planning.set_status(
        session, user.id, task.id, TaskStatus.MISSED, reason=MissReason.TIRED, note="charchadim"
    )
    assert task.miss_reason == MissReason.TIRED

    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)
    assert task.miss_reason is None
    assert task.miss_note is None
    assert task.done_at is not None


async def test_odat_nusxasini_kochirib_bolmaydi(session, make_user, make_habit):
    """Odat vazifasi ertaga baribir yaratiladi — ko'chirish ikki nusxa berardi."""
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    today = clock.today_local(user.tz)
    _, tasks = await planning.open_day(session, user, today)

    natija = await planning.move_task(session, user.id, tasks[0].id, today + timedelta(days=1))
    assert natija is None


async def test_qol_vazifasi_kochadi(session, make_user):
    user = await make_user(1)
    today = clock.today_local(user.tz)
    ertaga = today + timedelta(days=1)
    task = await planning.add_task(session, user, today, "Ko'chadigan ish")
    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)

    moved = await planning.move_task(session, user.id, task.id, ertaga)
    assert moved.date == ertaga
    assert moved.status == TaskStatus.PLANNED, "ko'chgach qaytadan bajarilmagan bo'ladi"

    assert (await planning.get_plan(session, user.id, today)).planned_count == 0
    assert (await planning.get_plan(session, user.id, ertaga)).planned_count == 1


async def test_tasdiqlash_bir_marta_yoziladi(session, make_user):
    user = await make_user(1)
    ertaga = clock.tomorrow_local(user.tz)

    plan = await planning.submit_plan(session, user, ertaga)
    birinchi = plan.submitted_at
    assert birinchi is not None
    assert await planning.has_submitted_plan_for(session, user.id, ertaga) is True

    plan = await planning.submit_plan(session, user, ertaga)
    assert plan.submitted_at == birinchi, "qayta tasdiqlash vaqtni o'zgartirmasligi kerak"


async def test_kun_yopilganda_bajarilmaganlar_missed_boladi(session, make_user, make_habit):
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    await make_habit(user, "Kitob")
    today = clock.today_local(user.tz)
    _, tasks = await planning.open_day(session, user, today)
    await planning.set_status(session, user.id, tasks[0].id, TaskStatus.DONE)

    plan = await planning.close_day(session, user, today)
    assert plan.closed_at is not None

    yangilangan = await planning.get_tasks(session, user.id, today)
    holatlar = sorted(t.status.value for t in yangilangan)
    assert holatlar == ["done", "missed"]


async def test_kun_yopish_idempotent(session, make_user, make_habit):
    """Ikkinchi marta yopilsa hech narsa o'zgarmasligi kerak."""
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    today = clock.today_local(user.tz)
    await planning.open_day(session, user, today)

    birinchi = await planning.close_day(session, user, today)
    vaqt = birinchi.closed_at
    ikkinchi = await planning.close_day(session, user, today)
    assert ikkinchi.closed_at == vaqt


async def test_yoq_kunni_yopish_xato_bermaydi(session, make_user):
    user = await make_user(1)
    natija = await planning.close_day(session, user, clock.today_local(user.tz))
    assert natija is None
