"""Vazifa vaqti va uning eslatmasi.

Eng nozik joyi — takrorlanmaslik. Kunlik eslatmalarda bir kunga bitta
yozuv yetardi, bu yerda esa har vazifaga alohida yozuv kerak
(`ReminderLog.task_id`). Agar u ishlamasa, eslatma sikli har daqiqada
o'sha xabarni qayta yuboradi va odam botni bir kunda bloklaydi.
"""

from __future__ import annotations

from datetime import datetime, time

import pytest

from services import notify, planning, scheduler
from shared import clock
from shared.models import ReminderKind, TaskStatus


@pytest.fixture
def soatni_toxtat(monkeypatch):
    """Mahalliy vaqtni qotirib qo'yadi.

    `clock.now_local` ni almashtiramiz — `today_local` ham, `is_due` ham
    o'shani chaqiradi, ya'ni butun modul bitta soatga bo'ysunadi. Aks holda
    testlar kunning qaysi soatida ishga tushirilganiga qarab goh o'tib,
    goh yiqilardi.
    """

    def _set(hh: int, mm: int) -> datetime:
        tz = clock.tz_of("Asia/Tashkent")
        bugun = datetime.now(tz).date()
        qotgan = datetime.combine(bugun, time(hh, mm), tzinfo=tz)
        monkeypatch.setattr(clock, "now_local", lambda tz_name=None: qotgan)
        return qotgan

    return _set


# ─── Vaqt arifmetikasi ───────────────────────────────────────────────────────


def test_shift_time_sana_chegarasidan_otmaydi():
    """`00:05` dan 10 daqiqa ayirilsa kechagi `23:55` emas, `00:00` chiqadi.

    Aks holda yarim tunga yaqin vazifaning eslatmasi oldingi kunga tushib,
    `is_due` uni o'sha kuni umuman ko'rmasdi.
    """
    assert clock.shift_time(time(0, 5), -10) == time(0, 0)
    assert clock.shift_time(time(23, 30), 120) == time(23, 59)
    assert clock.shift_time(time(7, 0), -10) == time(6, 50)


def test_fmt_range_uch_holat():
    assert clock.fmt_range(time(7, 0), time(7, 45)) == "07:00–07:45"
    assert clock.fmt_range(time(7, 0), None) == "07:00"
    assert clock.fmt_range(None, None) == ""


# ─── Vaqtning ko'chishi va tartib ────────────────────────────────────────────


async def test_odat_vaqti_nusxaga_kochadi(session, make_user, make_habit):
    user = await make_user(1)
    await make_habit(user, "Sport", start_time=time(7, 0), end_time=time(7, 45))

    _, tasks = await planning.open_day(session, user, clock.today_local(user.tz))
    assert tasks[0].start_time == time(7, 0)
    assert tasks[0].end_time == time(7, 45)


async def test_vaqtsizlar_royxat_oxirida(session, make_user):
    """Vaqtlilar vaqt bo'yicha, vaqtsizlari oxirida — kun jadval bo'lib ko'rinsin."""
    user = await make_user(1)
    d = clock.today_local(user.tz)

    await planning.add_task(session, user, d, "Vaqtsiz")
    await planning.add_task(session, user, d, "Kechqurun", start_time=time(20, 0))
    await planning.add_task(session, user, d, "Ertalab", start_time=time(7, 0))

    nomlar = [t.title for t in await planning.get_tasks(session, user.id, d)]
    assert nomlar == ["Ertalab", "Kechqurun", "Vaqtsiz"]


async def test_tugash_vaqti_boshlanishidan_oldin_bolmaydi(session, make_user):
    user = await make_user(1)
    d = clock.today_local(user.tz)

    with pytest.raises(ValueError):
        await planning.add_task(
            session, user, d, "Teskari", start_time=time(9, 0), end_time=time(8, 0)
        )
    with pytest.raises(ValueError):
        await planning.add_task(session, user, d, "Yolg'iz tugash", end_time=time(8, 0))


# ─── Eslatma ─────────────────────────────────────────────────────────────────


async def test_vaqti_kelganda_eslatma_ketadi(session, make_user, bot, soatni_toxtat):
    hozir = soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=10)
    d = clock.today_local(user.tz)
    await planning.add_task(
        session, user, d, "Sport", start_time=time(9, 0), end_time=time(9, 45)
    )

    assert await notify.send_task_reminders(bot, session, user) == 1
    (matn,) = bot.texts_for(1)
    assert "10 daqiqadan keyin" in matn
    assert "Sport" in matn
    assert "09:00–09:45" in matn
    assert hozir.hour == 8  # soat haqiqatan qotirilgan


async def test_vaqti_kelmaganda_eslatma_ketmaydi(session, make_user, bot, soatni_toxtat):
    soatni_toxtat(8, 0)
    user = await make_user(1, task_lead_min=10)
    d = clock.today_local(user.tz)
    await planning.add_task(session, user, d, "Sport", start_time=time(14, 0))

    assert await notify.send_task_reminders(bot, session, user) == 0
    assert bot.texts_for(1) == []


async def test_har_vazifaga_bir_martadan(session, make_user, bot, soatni_toxtat):
    """Ikkinchi tick xabarni takrorlamasligi kerak."""
    soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=10)
    d = clock.today_local(user.tz)
    await planning.add_task(session, user, d, "Sport", start_time=time(9, 0))

    assert await notify.send_task_reminders(bot, session, user) == 1
    assert await notify.send_task_reminders(bot, session, user) == 0
    assert len(bot.texts_for(1)) == 1


async def test_ikki_vazifa_ikkita_alohida_xabar(session, make_user, bot, soatni_toxtat):
    """`ReminderLog.task_id` ishlamasa, ikkinchi vazifa "yuborilgan" deb o'tkazib yuborilardi."""
    soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=10)
    d = clock.today_local(user.tz)
    await planning.add_task(session, user, d, "Sport", start_time=time(9, 0))
    await planning.add_task(session, user, d, "Kitob", start_time=time(8, 55))

    assert await notify.send_task_reminders(bot, session, user) == 2
    matnlar = " ".join(bot.texts_for(1))
    assert "Sport" in matnlar and "Kitob" in matnlar


async def test_nol_daqiqa_eslatmani_ochiradi(session, make_user, bot, soatni_toxtat):
    soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=0)
    d = clock.today_local(user.tz)
    await planning.add_task(session, user, d, "Sport", start_time=time(9, 0))

    assert await notify.send_task_reminders(bot, session, user) == 0
    assert bot.texts_for(1) == []


async def test_bajarilgan_vazifaga_eslatma_ketmaydi(session, make_user, bot, soatni_toxtat):
    soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=10)
    d = clock.today_local(user.tz)
    task = await planning.add_task(session, user, d, "Sport", start_time=time(9, 0))
    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)

    assert await notify.send_task_reminders(bot, session, user) == 0


async def test_vaqtsiz_vazifaga_eslatma_ketmaydi(session, make_user, bot, soatni_toxtat):
    soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=10)
    await planning.add_task(session, user, clock.today_local(user.tz), "Vaqtsiz ish")

    assert await notify.send_task_reminders(bot, session, user) == 0


async def test_jadval_oltinchi_qadamni_bajaradi(session, make_user, bot, soatni_toxtat):
    """`fire_due_for` vazifa eslatmasini ham chaqirishi kerak."""
    soatni_toxtat(8, 50)
    user = await make_user(1, task_lead_min=10)
    await planning.add_task(
        session, user, clock.today_local(user.tz), "Sport", start_time=time(9, 0)
    )

    fired = await scheduler.fire_due_for(bot, user, session)
    assert "vazifa" in fired


async def test_kunlik_eslatma_hamon_bir_marta(session, make_user, bot):
    """`task_id` qo'shilgach kunlik turlarning kafolati buzilmaganini tekshiramiz.

    Ustun `nullable` bo'lib qolsa, SQLite `UNIQUE` da NULL'lar farqli
    hisoblanib, quyidagi ikkinchi chaqiruv ham xabar yuborardi.
    """
    user = await make_user(1)
    assert await notify.send_plan_reminder(bot, session, user) is True
    assert await notify.send_plan_reminder(bot, session, user) is False

    ertaga = clock.tomorrow_local(user.tz)
    assert await notify.already_sent(session, user.id, ReminderKind.PLAN, ertaga) is True
