"""Jamoa: qo'shilish, chiqish, chiqarish va sardor huquqlari."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from services import groups
from shared.models import Group, Membership, User


async def _jamoa(session, sardor, *azolar, name="Sinov"):
    group = await groups.ensure_group(session, sardor, name)
    for a in azolar:
        await groups.join_by_code(session, a, group.invite_code)
    return group


async def test_yolgiz_odam_ozining_sardori(session, make_user):
    """Yangi odamga darhol jamoa yaratiladi — 'avval jamoa tuzing' qadami yo'q."""
    user = await make_user(1)
    group = await groups.ensure_group(session, user)

    assert group.owner_id == user.id
    assert len(group.invite_code) == 6
    assert groups.is_owner(group, user.id) is True


async def test_ikkinchi_marta_yangi_jamoa_yaratilmaydi(session, make_user):
    user = await make_user(1)
    birinchi = await groups.ensure_group(session, user)
    ikkinchi = await groups.ensure_group(session, user)
    assert birinchi.id == ikkinchi.id


async def test_kod_bilan_qoshilish(session, make_user):
    sardor = await make_user(1, "Sardor")
    sherik = await make_user(2, "Sherik")
    group = await groups.ensure_group(session, sardor)

    await groups.join_by_code(session, sherik, group.invite_code.lower())  # katta-kichik farqsiz
    partners = await groups.partners(session, sardor)
    assert [p.id for p in partners] == [2]


async def test_notogri_kod(session, make_user):
    user = await make_user(1)
    with pytest.raises(groups.JoinError):
        await groups.join_by_code(session, user, "YOQKOD")


async def test_qoshilganda_eski_jamoadan_chiqadi(session, make_user):
    """Bir vaqtda bitta jamoa — aks holda reyting ikki joyda hisoblanardi."""
    sardor = await make_user(1)
    sherik = await make_user(2)
    eski = await groups.ensure_group(session, sherik, "Eski")
    yangi = await groups.ensure_group(session, sardor, "Yangi")

    await groups.join_by_code(session, sherik, yangi.invite_code)

    azoliklar = list(
        await session.scalars(select(Membership).where(Membership.user_id == sherik.id))
    )
    assert len(azoliklar) == 1
    assert azoliklar[0].group_id == yangi.id != eski.id


async def test_toldirilgan_jamoaga_qoshilib_bolmaydi(session, make_user):
    sardor = await make_user(1)
    group = await groups.ensure_group(session, sardor)
    group.max_members = 2
    await session.flush()

    await groups.join_by_code(session, await make_user(2), group.invite_code)
    with pytest.raises(groups.JoinError):
        await groups.join_by_code(session, await make_user(3), group.invite_code)


# ─── Sardor huquqlari ────────────────────────────────────────────────────────


async def test_oddiy_azo_sardor_amalini_qila_olmaydi(session, make_user):
    sardor = await make_user(1)
    sherik = await make_user(2)
    await _jamoa(session, sardor, sherik)

    with pytest.raises(groups.NotOwnerError):
        await groups.require_owner(session, sherik)


async def test_kod_yangilanganda_eskisi_olmaydi(session, make_user):
    sardor = await make_user(1)
    group = await _jamoa(session, sardor)
    eski_kod = group.invite_code

    await groups.reset_invite_code(session, group)
    assert group.invite_code != eski_kod

    with pytest.raises(groups.JoinError):
        await groups.join_by_code(session, await make_user(2), eski_kod)


async def test_nom_bosh_bolmasin(session, make_user):
    sardor = await make_user(1)
    group = await _jamoa(session, sardor)
    with pytest.raises(groups.TeamError):
        await groups.rename(session, group, "   ")


async def test_sardorni_chiqarib_bolmaydi(session, make_user):
    sardor = await make_user(1)
    sherik = await make_user(2)
    group = await _jamoa(session, sardor, sherik)

    with pytest.raises(groups.TeamError):
        await groups.remove_member(session, group, sardor.id)


async def test_azoni_chiqarish(session, make_user):
    sardor = await make_user(1)
    sherik = await make_user(2)
    group = await _jamoa(session, sardor, sherik)

    chiqarilgan = await groups.remove_member(session, group, sherik.id)
    assert chiqarilgan.id == sherik.id
    assert await groups.partners(session, sardor) == []
    assert await session.get(User, 2) is not None, "odam o'chmaydi, faqat a'zolik uziladi"


# ─── Jamoadan chiqish ────────────────────────────────────────────────────────


async def test_yolgiz_odam_chiqa_olmaydi(session, make_user):
    """Chiqsa ham keyingi ochilishda yana o'ziga jamoa yaratilardi."""
    user = await make_user(1)
    await groups.ensure_group(session, user)
    with pytest.raises(groups.TeamError):
        await groups.leave(session, user)


async def test_oddiy_azo_chiqadi(session, make_user):
    sardor = await make_user(1)
    sherik = await make_user(2)
    group = await _jamoa(session, sardor, sherik)

    qaytgan, qolganlar = await groups.leave(session, sherik)
    assert qaytgan.owner_id == sardor.id, "sardorlik o'zgarmasligi kerak"
    assert [u.id for u in qolganlar] == [sardor.id]
    assert await groups.partners(session, sardor) == []
    assert await session.get(Group, group.id) is not None


async def test_sardor_chiqsa_sardorlik_otadi(session, make_user):
    """Aks holda jamoa boshqaruvsiz qolardi: kod ham, chiqarish ham yopiq."""
    sardor = await make_user(1)
    birinchi = await make_user(2, "Birinchi")
    ikkinchi = await make_user(3, "Ikkinchi")
    group = await _jamoa(session, sardor, birinchi, ikkinchi)

    qaytgan, qolganlar = await groups.leave(session, sardor)
    assert qaytgan.owner_id == birinchi.id, "eng erta qo'shilganga o'tadi"
    assert sorted(u.id for u in qolganlar) == [2, 3]

    yangilangan = await session.get(Group, group.id)
    assert yangilangan.owner_id == birinchi.id


async def test_chiqqandan_keyin_yangi_jamoa_olinadi(session, make_user):
    sardor = await make_user(1)
    sherik = await make_user(2)
    eski = await _jamoa(session, sardor, sherik)

    await groups.leave(session, sherik)
    yangi = await groups.ensure_group(session, sherik)

    assert yangi.id != eski.id
    assert yangi.owner_id == sherik.id


async def test_jamoasiz_odam_chiqa_olmaydi(session, make_user):
    user = await make_user(1)
    with pytest.raises(groups.TeamError):
        await groups.leave(session, user)
