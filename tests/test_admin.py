"""Admin paneli va ommaviy xabar.

Ikkita xavf bor va ikkalasi ham jim:

1. **Ruxsat.** `SUPER_ADMIN_IDS` bo'sh yoki noto'g'ri bo'lsa, panel hamma
   foydalanuvchiga ochilib qolishi mumkin — va buni hech kim sezmaydi,
   chunki hech qanday xato chiqmaydi.
2. **Ommaviy xabar.** Bloklagan odamga urinish, yoki aksincha — tirik
   odamning tashlab ketilishi. Har ikkisi ham faqat yuborilgandan keyin
   bilinadi, o'shanda esa kech.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from services import admin, groups, planning
from shared import clock
from shared.config import settings
from shared.models import Membership, TaskStatus, User

MEN = 1001  # DEV_MOCK_USER_ID va conftest'dagi SUPER_ADMIN_IDS


@pytest_asyncio.fixture
async def client(session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def adminlar(monkeypatch):
    """`SUPER_ADMIN_IDS` ni test davomida almashtiradi.

    `settings` — lru_cache'langan yagona obyekt, shuning uchun xom
    `super_admin_ids_raw` maydonini almashtiramiz: hosilaviy `super_admin_ids`
    o'shandan hisoblanadi.
    """

    def _set(*ids: int) -> None:
        monkeypatch.setattr(
            settings, "super_admin_ids_raw", ",".join(str(i) for i in ids)
        )

    return _set


# ─── Ruxsat ──────────────────────────────────────────────────────────────────


async def test_bosh_royxat_hech_kimga_ruxsat_bermaydi(client, adminlar):
    """Bo'sh `SUPER_ADMIN_IDS` — «tekshiruv o'chirilgan» degani EMAS."""
    adminlar()  # bo'sh
    assert (await client.get("/api/admin/overview")).status_code == 403
    assert (await client.get("/api/me")).json()["is_admin"] is False


async def test_admin_bolmaganga_403(client, adminlar):
    adminlar(999999)  # boshqa odam admin
    assert (await client.get("/api/admin/overview")).status_code == 403


async def test_adminga_ochiq(client, adminlar):
    adminlar(MEN)
    r = await client.get("/api/admin/overview")
    assert r.status_code == 200

    data = r.json()
    for kalit in ("users", "teams", "activity", "results", "members", "recent"):
        assert kalit in data, f"javobda {kalit} yo'q"
    assert data["users"]["total"] >= 1


async def test_me_dagi_is_admin(client, adminlar):
    adminlar(MEN)
    assert (await client.get("/api/me")).json()["is_admin"] is True
    adminlar(999999)
    assert (await client.get("/api/me")).json()["is_admin"] is False


# ─── Ko'rsatkichlar ──────────────────────────────────────────────────────────


async def test_sherigi_bor_va_yolgizlar(session, make_user):
    """Ilovaning eng muhim raqami — nechta odam sherik topgan."""
    a = await make_user(1)
    b = await make_user(2)
    await make_user(3)  # yolg'iz

    group = await groups.ensure_group(session, a)
    await groups.ensure_group(session, b)
    await groups.join_by_code(session, b, group.invite_code)
    await session.flush()

    data = await admin.overview(session)
    assert data["users"]["total"] == 3
    assert data["teams"]["with_partner"] == 2
    assert data["teams"]["alone"] == 1
    assert data["teams"]["paired_groups"] == 1


async def test_bloklaganlar_sanaladi(session, make_user):
    await make_user(1)
    await make_user(2, is_blocked=True)

    data = await admin.overview(session)
    assert data["users"]["total"] == 2
    assert data["users"]["blocked"] == 1


async def test_faollik_va_natija(session, make_user):
    user = await make_user(1)
    today = clock.today_local(user.tz)

    task = await planning.add_task(session, user, today, "Ish")
    await planning.set_status(session, user.id, task.id, TaskStatus.DONE)
    await planning.submit_plan(session, user, today)

    data = await admin.overview(session)
    assert data["activity"]["submitted_today"] == 1
    assert data["activity"]["done_7d"] == 1
    assert data["results"]["tasks_done_7d"] == 1
    assert data["results"]["avg_pct_7d"] == 100


async def test_dinamika_bosh_kunlarni_toldiradi(session, make_user):
    await make_user(1)
    qatorlar = await admin.members_series(session, days=5)

    assert len(qatorlar) == 5, "bo'sh kunlar ham qatorda bo'lishi kerak"
    assert qatorlar[-1]["date"] == clock.today_local().isoformat()
    assert qatorlar[-1]["total"] == 1
    assert qatorlar[-1]["joined"] == 1


async def test_dinamika_jamgarma_bolib_osadi(session, make_user):
    """`total` — jamg'arma: kunlik son emas, o'sha kunga QADAR jami.

    Uchalasi bugun qo'shilgan, ya'ni chiziq kechagacha 0 da turadi va
    bugun 3 ga ko'tariladi.
    """
    for i in (1, 2, 3):
        await make_user(i)

    qatorlar = await admin.members_series(session, days=3)
    assert [r["total"] for r in qatorlar] == [0, 0, 3]
    assert [r["joined"] for r in qatorlar] == [0, 0, 3]
    assert qatorlar[-1]["active"] == 3


async def test_dinamika_ketganlarni_ayiradi(session, make_user):
    """Bloklagan odam `total` da qoladi, `active` dan chiqadi."""
    await make_user(1)
    ketgan = await make_user(2)
    planning.mark_blocked(ketgan)
    await session.flush()

    oxirgi = (await admin.members_series(session, days=3))[-1]
    assert oxirgi["total"] == 2, "ro'yxatdan o'tganlar soni kamaymaydi"
    assert oxirgi["active"] == 1
    assert oxirgi["left"] == 1


async def test_dinamika_oynadan_oldingilarni_hisoblaydi(session, make_user):
    """Oyna boshidan oldin qo'shilgan odam ham `total` ga kirishi kerak.

    Faqat oynadagi yozuvlarni sanash — eng oson xato: 30 kunlik grafik
    ilovaning butun tarixini emas, oxirgi oyni ko'rsatib qo'yardi va
    o'sish chizig'i noldan boshlanardi.
    """
    eski = await make_user(1)
    eski.created_at = clock.now_utc() - timedelta(days=100)
    await session.flush()

    qatorlar = await admin.members_series(session, days=7)
    assert qatorlar[0]["total"] == 1
    assert qatorlar[0]["joined"] == 0, "u bu oynada qo'shilmagan"


async def test_qaytib_kelgan_odam_faolga_qaytadi(session, make_user):
    """Bloklab, keyin qaytgan odam `left` hisobidan chiqadi."""
    user = await make_user(1)
    planning.mark_blocked(user)
    await session.flush()
    assert (await admin.members_series(session, days=3))[-1]["active"] == 0

    await planning.get_or_create_user(session, 1)
    await session.flush()

    oxirgi = (await admin.members_series(session, days=3))[-1]
    assert oxirgi["active"] == 1
    assert oxirgi["left"] == 0
    assert user.blocked_at is None


async def test_recent_users_sanasi_mahalliy(session, make_user):
    """Sana MAHALLIY bo'lishi kerak — `created_at` esa UTC'da saqlanadi.

    UTC'ni o'z holicha ko'rsatsak, kechqurun qo'shilgan odam ro'yxatda
    kechagi sana bilan chiqadi va «bugun qo'shildi: 1» yozuviga zid
    ko'rinadi (Asia/Tashkent = UTC+5).
    """
    await make_user(1)
    (row,) = await admin.recent_users(session, tz="Asia/Tashkent")
    data = await admin.overview(session, "Asia/Tashkent")

    assert row["joined"] == clock.today_local("Asia/Tashkent").isoformat()
    assert data["users"]["new_today"] == 1, "ikkala raqam bir kunni ko'rsatsin"


async def test_recent_users_sherikni_korsatadi(session, make_user):
    a = await make_user(1, "Birinchi")
    b = await make_user(2, "Ikkinchi")
    group = await groups.ensure_group(session, a)
    await groups.join_by_code(session, b, group.invite_code)
    await make_user(3, "Yolg'iz")
    await session.flush()

    rows = {r["name"]: r for r in await admin.recent_users(session, limit=10)}
    assert rows["Birinchi"]["has_partner"] is True
    assert rows["Ikkinchi"]["has_partner"] is True
    assert rows["Yolg'iz"]["has_partner"] is False


# ─── Ommaviy xabar ───────────────────────────────────────────────────────────


async def test_broadcast_hammaga_ketadi(session, make_user, bot):
    for i in (1, 2, 3):
        await make_user(i)

    natija = await admin.broadcast(bot, session, "Salom")
    assert natija == {"sent": 3, "blocked": 0, "failed": 0}
    assert len(bot.sent) == 3


async def test_broadcast_bloklaganlarni_chetlab_otadi(session, make_user, bot):
    await make_user(1)
    await make_user(2, is_blocked=True)

    natija = await admin.broadcast(bot, session, "Salom")
    assert natija["sent"] == 1
    assert bot.texts_for(2) == [], "bloklagan odamga urinilmasligi kerak"


async def test_broadcast_yangi_bloklaganni_belgilaydi(session, make_user):
    """Yuborish paytida bloklagan odam keyingi eslatmalarda o'tkazib yuborilsin."""
    from tests.conftest import FakeBot

    bot = FakeBot(fail_for={2})
    await make_user(1)
    bloklagan = await make_user(2)

    natija = await admin.broadcast(bot, session, "Salom")
    assert natija == {"sent": 1, "blocked": 1, "failed": 0}
    assert bloklagan.is_blocked is True
    assert bloklagan.blocked_at is not None, "dinamika uchun sana ham kerak"

    # Ikkinchi yuborishda unga umuman urinilmaydi
    bot2 = FakeBot(fail_for={2})
    assert (await admin.broadcast(bot2, session, "Yana"))["sent"] == 1


async def test_broadcast_auditoriyasi(session, make_user):
    await make_user(1)
    await make_user(2, is_blocked=True)
    assert [u.id for u in await admin.broadcast_audience(session)] == [1]


async def test_broadcast_matni_ozgarmaydi(session, make_user, bot):
    """Matn qanday berilsa, shundayligicha ketadi — qirqilmaydi, o'zgarmaydi."""
    await make_user(1)
    matn = "<b>Yangilik</b>\n\nIkkinchi qator"
    await admin.broadcast(bot, session, matn)
    assert bot.texts_for(1) == [matn]
