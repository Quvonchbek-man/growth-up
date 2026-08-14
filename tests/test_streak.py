"""Streak — ilovaning eng ko'p ko'riladigan raqami.

Noto'g'ri uzilsa foydalanuvchi ishonchini yo'qotadi, noto'g'ri o'ssa
ma'nosini yo'qotadi.
"""

from __future__ import annotations

from datetime import timedelta

from services import streak
from shared import clock
from shared.config import settings
from shared.models import DailyPlan


async def _kun(session, user, offset: int, pct: int, planned: int = 2):
    """`offset` kun oldingi kun uchun tayyor `DailyPlan`."""
    plan = DailyPlan(
        user_id=user.id,
        date=clock.today_local(user.tz) - timedelta(days=offset),
        planned_count=planned,
        done_count=round(planned * pct / 100),
        completion_pct=pct,
    )
    session.add(plan)
    await session.flush()
    return plan


async def test_ketma_ket_kunlar_sanaladi(session, make_user):
    user = await make_user(1)
    for offset in (1, 2, 3):
        await _kun(session, user, offset, 100)

    state = await streak.recalc(session, user)
    assert state.current_len == 3
    assert state.best_len == 3


async def test_uzilish_joriy_hisobni_nolga_tushiradi(session, make_user):
    user = await make_user(1)
    await _kun(session, user, 1, 100)
    await _kun(session, user, 2, 0)  # uzilish
    for offset in (3, 4, 5, 6):
        await _kun(session, user, offset, 100)

    state = await streak.recalc(session, user)
    assert state.current_len == 1, "kechadan boshlab faqat 1 kun"
    assert state.best_len == 4, "eng uzun natija saqlanib qoladi"


async def test_eng_uzun_natija_yoqolmaydi(session, make_user):
    """Streak kuysa ham 'men 5 kun qilgandim' degan natija qolishi kerak."""
    user = await make_user(1)
    for offset in range(2, 7):
        await _kun(session, user, offset, 100)
    await _kun(session, user, 1, 0)  # kecha buzildi

    state = await streak.recalc(session, user)
    assert state.current_len == 0
    assert state.best_len == 5


async def test_chegara_foizi(session, make_user):
    """`STREAK_SUCCESS_PCT` dan past kun muvaffaqiyatsiz."""
    pct = settings.streak_success_pct
    user = await make_user(1)
    await _kun(session, user, 1, pct)  # aynan chegarada — hisoblanadi
    await _kun(session, user, 2, pct - 1)  # bir foiz kam — uziladi

    state = await streak.recalc(session, user)
    assert state.current_len == 1


async def test_bugun_hali_tugamagan(session, make_user):
    """Bugun 0% bo'lsa ham streak uzilmaydi — kun hali tugamadi."""
    user = await make_user(1)
    await _kun(session, user, 0, 0)  # bugun, hali hech narsa qilinmagan
    await _kun(session, user, 1, 100)
    await _kun(session, user, 2, 100)

    state = await streak.recalc(session, user)
    assert state.current_len == 2


async def test_bugun_bajarilsa_qoshiladi(session, make_user):
    user = await make_user(1)
    await _kun(session, user, 0, 100)
    await _kun(session, user, 1, 100)

    state = await streak.recalc(session, user)
    assert state.current_len == 2


async def test_bosh_tarix(session, make_user):
    user = await make_user(1)
    state = await streak.recalc(session, user)
    assert state.current_len == 0
    assert state.best_len == 0
    assert state.last_success_date is None


async def test_rejasiz_kun_muvaffaqiyat_emas(session, make_user):
    """Hech narsa rejalashtirmagan kun 'muvaffaqiyatli' deb sanalmasligi kerak."""
    user = await make_user(1)
    await _kun(session, user, 1, 0, planned=0)
    await _kun(session, user, 2, 100)

    state = await streak.recalc(session, user)
    assert state.current_len == 0
