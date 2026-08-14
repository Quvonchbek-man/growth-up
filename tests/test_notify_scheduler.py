"""Eslatmalar va ularning jadvali.

Bu qismning nosozligi eng xavflisi: hech qanday xato ko'rinmaydi, xabar
shunchaki kelmaydi (yoki kuniga o'n marta keladi).
"""

from __future__ import annotations

from datetime import time, timedelta

from services import groups, notify, planning, scheduler
from shared import clock
from shared.models import ReminderKind, TaskStatus


async def test_kechki_eslatma_bir_marta_ketadi(session, make_user, bot):
    """`ReminderLog` bo'lmasa, bot har restartda xabarni qayta yuborardi."""
    user = await make_user(1)

    assert await notify.send_plan_reminder(bot, session, user) is True
    assert await notify.send_plan_reminder(bot, session, user) is False
    assert len(bot.texts_for(1)) == 1


async def test_reja_tayyor_bolsa_boshqa_matn(session, make_user, bot):
    user = await make_user(1)
    await planning.submit_plan(session, user, clock.tomorrow_local(user.tz))

    await notify.send_plan_reminder(bot, session, user)
    (matn,) = bot.texts_for(1)
    assert "allaqachon tayyor" in matn


async def test_ertalabki_royxat_vazifalarni_sanaydi(session, make_user, make_habit, bot):
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    await make_habit(user, "Kitob")

    assert await notify.send_digest(bot, session, user) is True
    (matn,) = bot.texts_for(1)
    assert "2 ta ish" in matn
    assert "Yugurish" in matn and "Kitob" in matn


async def test_royxat_bosh_bolsa_boshqa_matn(session, make_user, bot):
    user = await make_user(1)
    await notify.send_digest(bot, session, user)
    (matn,) = bot.texts_for(1)
    assert "Bugunga reja yo'q" in matn


async def test_bloklagan_odamga_urinilmaydi(session, make_user):
    """Blok qilgan odam `is_blocked` bo'lib belgilanadi va qayta urinilmaydi."""
    from tests.conftest import FakeBot

    bot = FakeBot(fail_for={1})
    user = await make_user(1)

    assert await notify.safe_send(bot, session, user, "salom") is False
    assert user.is_blocked is True

    # Ikkinchi urinishda umuman so'rov ketmaydi (xato ham ko'tarilmaydi)
    assert await notify.safe_send(bot, session, user, "yana") is False


async def test_sherikka_ogohlantirish(session, make_user, bot):
    """Reja kiritilmasa sherikka xabar — ilovaning asosiy bosimi shu."""
    men = await make_user(1, "Men")
    sherik = await make_user(2, "Sherik")
    group = await groups.ensure_group(session, men)
    await groups.join_by_code(session, sherik, group.invite_code)

    yuborildi = await notify.nag_partners_about(bot, session, men)
    assert yuborildi == 1
    assert "Men" in bot.texts_for(2)[0]
    assert bot.texts_for(1) == [], "o'ziga xabar ketmaydi"


async def test_reja_kiritilgan_bolsa_sherik_bezovta_qilinmaydi(session, make_user, bot):
    men = await make_user(1, "Men")
    sherik = await make_user(2, "Sherik")
    group = await groups.ensure_group(session, men)
    await groups.join_by_code(session, sherik, group.invite_code)
    await planning.submit_plan(session, men, clock.tomorrow_local(men.tz))

    assert await notify.nag_partners_about(bot, session, men) == 0
    assert bot.sent == []


async def test_ozini_ochirgan_odam_haqida_xabar_ketmaydi(session, make_user, bot):
    """`allow_nag_about_me=False` — sozlamadagi tanlov hurmat qilinadi."""
    men = await make_user(1, "Men", allow_nag_about_me=False)
    sherik = await make_user(2, "Sherik")
    group = await groups.ensure_group(session, men)
    await groups.join_by_code(session, sherik, group.invite_code)

    assert await notify.nag_partners_about(bot, session, men) == 0


async def test_jamoadan_chiqqanda_qolganlarga_xabar(session, make_user, bot):
    sardor = await make_user(1, "Sardor")
    sherik = await make_user(2, "Sherik")
    group = await groups.ensure_group(session, sardor, "Bizning jamoa")
    await groups.join_by_code(session, sherik, group.invite_code)

    guruh, qolganlar = await groups.leave(session, sherik)
    await notify.notify_left(bot, session, sherik, guruh.name, qolganlar, guruh.owner_id)

    assert "Sherik" in bot.texts_for(1)[0], "qolgan odam sababini bilishi kerak"
    assert bot.texts_for(2), "chiquvchining o'ziga ham tasdiq boradi"


async def test_yangi_sardorga_aytiladi(session, make_user, bot):
    sardor = await make_user(1, "Sardor")
    sherik = await make_user(2, "Sherik")
    group = await groups.ensure_group(session, sardor, "Jamoa")
    await groups.join_by_code(session, sherik, group.invite_code)

    guruh, qolganlar = await groups.leave(session, sardor)
    await notify.notify_left(bot, session, sardor, guruh.name, qolganlar, guruh.owner_id)

    assert "sardori sizsiz" in bot.texts_for(2)[0]


async def test_kun_yopilib_xulosa_yuboriladi(session, make_user, make_habit, bot):
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    kecha = clock.today_local(user.tz) - timedelta(days=1)
    plan, _ = await planning.open_day(session, user, kecha, generate=False)
    task = await planning.add_task(session, user, kecha, "Kechagi ish")
    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)

    assert await notify.close_and_summarize(bot, session, user) is True
    plan = await planning.get_plan(session, user.id, kecha)
    assert plan.closed_at is not None
    assert bot.texts_for(1)


# ─── Jadval ──────────────────────────────────────────────────────────────────


async def test_jadval_tartibi(session, make_user, make_habit, bot):
    """Qadamlar shu tartibda ketishi kerak: kun_yopish → sabab → ertalabki →
    kechki → sherikka.

    Tartib buzilsa, ertalabki ro'yxat hali yopilmagan kechagi kun bilan
    aralashib ketadi. `fired` faqat ishlagan qadamlarni qaytaradi — shuning
    uchun tenglik emas, nisbiy tartib tekshiriladi.
    """
    TARTIB = ["kun_yopish", "sabab", "ertalabki", "kechki", "sherikka"]

    user = await make_user(1)
    await make_habit(user, "Yugurish")
    # Kechagi yopilmagan kun bo'lsin — shunda birinchi qadam ham ishlaydi
    kecha = clock.today_local(user.tz) - timedelta(days=1)
    await planning.open_day(session, user, kecha, generate=False)
    await planning.add_task(session, user, kecha, "Kechagi ish")

    fired = await scheduler.fire_due_for(bot, user, session, force=True)

    assert "kun_yopish" in fired and "ertalabki" in fired and "kechki" in fired
    o_rinlar = [TARTIB.index(name) for name in fired]
    assert o_rinlar == sorted(o_rinlar), f"tartib buzilgan: {fired}"


async def test_vaqti_kelmagan_eslatma_ketmaydi(session, make_user, bot, monkeypatch):
    user = await make_user(1)
    monkeypatch.setattr(clock, "is_due", lambda *a, **k: False)

    assert await scheduler.fire_due_for(bot, user, session) == []
    assert bot.sent == []


async def test_har_bir_eslatma_alohida_yoziladi(session, make_user, make_habit, bot):
    """Ertalabki va kechki bir-birini bloklamasligi kerak."""
    user = await make_user(1)
    await make_habit(user, "Yugurish")
    today = clock.today_local(user.tz)
    tomorrow = clock.tomorrow_local(user.tz)

    await scheduler.fire_due_for(bot, user, session, force=True)

    assert await notify.already_sent(session, user.id, ReminderKind.DIGEST, today) is True
    assert await notify.already_sent(session, user.id, ReminderKind.PLAN, tomorrow) is True


async def test_ikkinchi_tick_takrorlamaydi(session, make_user, make_habit, bot):
    user = await make_user(1)
    await make_habit(user, "Yugurish")

    await scheduler.fire_due_for(bot, user, session, force=True)
    birinchi = len(bot.sent)
    await scheduler.fire_due_for(bot, user, session, force=True)

    assert len(bot.sent) == birinchi, "kun davomida takroriy xabar ketmasligi kerak"
