"""Maxfiylik — buzilsa foydalanuvchi ishonchini qaytarib bo'lmaydi.

Uch daraja: `public` (hammasi ko'rinadi), `stats_only` (nomi yashirin,
foizga kiradi), `private` (sherik umuman ko'rmaydi va reytingga ham
kirmaydi — aks holda "bu ball qayerdan keldi?" savoli uni fosh qiladi).
"""

from __future__ import annotations

from services import planning, stats
from shared import clock
from shared.models import TaskStatus, Visibility


async def _bajarilgan(session, user, title, visibility):
    today = clock.today_local(user.tz)
    task = await planning.add_task(session, user, today, title, points=5, visibility=visibility)
    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)
    return task


async def test_yashirin_vazifa_sherikka_kormaydi(session, make_user):
    user = await make_user(1)
    await _bajarilgan(session, user, "Ochiq ish", Visibility.PUBLIC)
    await _bajarilgan(session, user, "Yashirin ish", Visibility.PRIVATE)

    tasks = await planning.get_tasks(session, user.id, clock.today_local(user.tz))
    korinadi = stats.visible_to_partner(tasks)
    assert [t.title for t in korinadi] == ["Ochiq ish"]


async def test_stats_only_nomi_yashirin_lekin_sanaladi(session, make_user):
    user = await make_user(1)
    task = await _bajarilgan(session, user, "Terapiya", Visibility.STATS_ONLY)

    ozi = stats.serialize_task(task, owner=True)
    sherik = stats.serialize_task(task, owner=False)

    assert ozi["title"] == "Terapiya"
    assert ozi["hidden"] is False
    assert sherik["title"] == stats.HIDDEN_TITLE
    assert sherik["hidden"] is True
    assert sherik["points"] == 5, "ball ko'rinadi — foizga qo'shilishi shundan"


async def test_sherik_izohni_kormaydi(session, make_user):
    """Bajarmaganlik sababiga yozilgan izoh shaxsiy qoladi."""
    from shared.models import MissReason

    user = await make_user(1)
    today = clock.today_local(user.tz)
    task = await planning.add_task(session, user, today, "Ish")
    await planning.set_status(
        session,
        user.id,
        task.id,
        TaskStatus.MISSED,
        reason=MissReason.TIRED,
        note="Kasal bo'lib qoldim",
    )

    assert stats.serialize_task(task, owner=True)["miss_note"] == "Kasal bo'lib qoldim"
    assert stats.serialize_task(task, owner=False)["miss_note"] is None
    assert stats.serialize_task(task, owner=False)["miss_reason"] == "tired"


async def test_odat_maxfiyligi_vazifaga_meros_boladi(session, make_user, make_habit):
    user = await make_user(1)
    await make_habit(user, "Shaxsiy odat", visibility=Visibility.PRIVATE)
    _, tasks = await planning.open_day(session, user, clock.today_local(user.tz))

    assert tasks[0].effective_visibility == Visibility.PRIVATE
    assert stats.visible_to_partner(tasks) == []


async def test_kun_korinishi_sherik_uchun_yashirinni_hisobga_olmaydi(session, make_user):
    user = await make_user(1)
    await _bajarilgan(session, user, "Ochiq", Visibility.PUBLIC)
    await _bajarilgan(session, user, "Yashirin", Visibility.PRIVATE)
    today = clock.today_local(user.tz)

    ozi = await stats.day_view(session, user, today, owner=True)
    sherik = await stats.day_view(session, user, today, owner=False)

    assert ozi["done_count"] == 2
    assert ozi["score"] == 10
    assert sherik["done_count"] == 1
    assert sherik["score"] == 5, "yashirin ish sherikning ko'rinishida ball bermaydi"


async def test_yashirin_ish_reytingga_kirmaydi(session, make_user):
    """Eng muhim qoida: yashirin ball reytingda ko'rinsa, sir ochiladi."""
    men = await make_user(1, "Men")
    sherik = await make_user(2, "Sherik")

    await _bajarilgan(session, men, "Ochiq", Visibility.PUBLIC)  # 5 ball
    await _bajarilgan(session, men, "Yashirin", Visibility.PRIVATE)  # reytingga kirmaydi
    await _bajarilgan(session, sherik, "Ochiq", Visibility.PUBLIC)  # 5 ball

    today = clock.today_local(men.tz)
    board = await stats.leaderboard(session, [men, sherik], today, today)
    ballar = {row["name"]: row["score"] for row in board}

    assert ballar["Men"] == 5
    assert ballar["Sherik"] == 5
    assert board[0]["rank"] == 1


async def test_stats_only_reytingga_kiradi(session, make_user):
    """Nomi yashirin, lekin ball beradi — maxfiylikning o'rta darajasi."""
    user = await make_user(1, "Men")
    await _bajarilgan(session, user, "Terapiya", Visibility.STATS_ONLY)

    today = clock.today_local(user.tz)
    board = await stats.leaderboard(session, [user], today, today)
    assert board[0]["score"] == 5


async def test_qol_vazifasi_sukut_boyicha_ochiq(session, make_user):
    """`visibility=None` — PUBLIC degani, sherik ko'radi."""
    user = await make_user(1, "Men")
    today = clock.today_local(user.tz)
    task = await planning.add_task(session, user, today, "Oddiy ish", points=3)
    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)

    assert task.effective_visibility == Visibility.PUBLIC
    board = await stats.leaderboard(session, [user], today, today)
    assert board[0]["score"] == 3
