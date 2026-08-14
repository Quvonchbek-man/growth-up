"""Jamoa: yaratish, taklif kodi bilan qo'shilish, sheriklar ro'yxati.

Faza 1 da har foydalanuvchi bitta jamoada bo'ladi. Model ko'p jamoani
ko'taradi, lekin interfeys hozircha birinchisini oladi — keraksiz murakkablik
kiritmaslik uchun.
"""

from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Group, Membership, User

# Chalkashadigan belgilar yo'q: 0/O, 1/I/L olib tashlandi.
# Kod og'zaki aytiladi va qo'lda teriladi — bu muhim.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LEN = 6


def _random_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


async def _unique_code(session: AsyncSession) -> str:
    for _ in range(20):
        code = _random_code()
        exists = await session.scalar(select(Group.id).where(Group.invite_code == code))
        if exists is None:
            return code
    # 31^6 ≈ 887 million variant — bu yerga tushish amalda imkonsiz
    raise RuntimeError("Taklif kodi yaratib bo'lmadi")


async def get_user_group(session: AsyncSession, user_id: int) -> Group | None:
    return await session.scalar(
        select(Group)
        .join(Membership, Membership.group_id == Group.id)
        .where(Membership.user_id == user_id)
        .order_by(Membership.joined_at)
        .limit(1)
    )


async def ensure_group(
    session: AsyncSession, user: User, name: str = "Jamoa"
) -> Group:
    """Foydalanuvchining jamoasi bo'lmasa yaratadi.

    /start bosilganda chaqiriladi: odam darhol taklif kodini ko'radi va
    sherigini chaqira oladi. "Avval jamoa yarating" degan qo'shimcha qadam
    kerak emas.
    """
    group = await get_user_group(session, user.id)
    if group is not None:
        return group

    group = Group(
        name=name,
        owner_id=user.id,
        invite_code=await _unique_code(session),
    )
    session.add(group)
    await session.flush()
    session.add(Membership(user_id=user.id, group_id=group.id))
    await session.flush()
    return group


class JoinError(Exception):
    """Qo'shilishning muvaffaqiyatsiz sababi — foydalanuvchiga ko'rsatiladi."""


class TeamError(Exception):
    """Sardor amali bajarilmadi — sababi foydalanuvchiga ko'rsatiladi."""


class NotOwnerError(TeamError):
    """Amalni faqat sardor bajara oladi (API buni 403 ga aylantiradi)."""


async def join_by_code(session: AsyncSession, user: User, code: str) -> Group:
    code = code.strip().upper()
    group = await session.scalar(select(Group).where(Group.invite_code == code))
    if group is None:
        raise JoinError("Bunday taklif kodi topilmadi. Kodni tekshirib qayta yuboring.")

    already = await session.scalar(
        select(Membership.id).where(
            Membership.user_id == user.id, Membership.group_id == group.id
        )
    )
    if already is not None:
        return group

    count = await session.scalar(
        select(func.count(Membership.id)).where(Membership.group_id == group.id)
    )
    if (count or 0) >= group.max_members:
        raise JoinError(f"Bu jamoada joy qolmagan ({group.max_members} kishi).")

    # Eski (bo'sh) jamoasidan chiqaramiz — bir vaqtda bitta jamoa
    old = await get_user_group(session, user.id)
    if old is not None and old.id != group.id:
        old_membership = await session.scalar(
            select(Membership).where(
                Membership.user_id == user.id, Membership.group_id == old.id
            )
        )
        if old_membership is not None:
            await session.delete(old_membership)

    session.add(Membership(user_id=user.id, group_id=group.id))
    await session.flush()
    return group


async def members(session: AsyncSession, group_id: int) -> list[User]:
    rows = await session.scalars(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.group_id == group_id)
        .order_by(Membership.joined_at)
    )
    return list(rows)


async def partners(session: AsyncSession, user: User) -> list[User]:
    """Jamoadagi boshqa a'zolar."""
    group = await get_user_group(session, user.id)
    if group is None:
        return []
    return [m for m in await members(session, group.id) if m.id != user.id]


async def partners_of(session: AsyncSession, user_id: int) -> list[User]:
    group = await get_user_group(session, user_id)
    if group is None:
        return []
    return [m for m in await members(session, group.id) if m.id != user_id]


# ─── Sardor huquqlari ────────────────────────────────────────────────────────
#
# Jamoani yaratgan odam sardor bo'ladi (`Group.owner_id`). Uchta amal faqat
# unga ochiq: nomni o'zgartirish, taklif kodini yangilash, a'zoni chiqarish.
# Uchalasi bir-biriga bog'liq: kodni yangilamasdan chiqarishning ma'nosi yo'q —
# chiqarilgan odam eski kod bilan qaytib kiraverardi.


def is_owner(group: Group, user_id: int) -> bool:
    return group.owner_id == user_id


async def require_owner(session: AsyncSession, user: User) -> Group:
    """Jamoani qaytaradi, sardor bo'lmasa `TeamError`."""
    group = await get_user_group(session, user.id)
    if group is None:
        raise TeamError("Sizda jamoa yo'q")
    if not is_owner(group, user.id):
        raise NotOwnerError("Bu amalni faqat jamoa sardori bajara oladi")
    return group


async def rename(session: AsyncSession, group: Group, name: str) -> Group:
    name = name.strip()
    if not name:
        raise TeamError("Jamoa nomi bo'sh bo'lishi mumkin emas")
    group.name = name[:64]
    await session.flush()
    return group


async def reset_invite_code(session: AsyncSession, group: Group) -> Group:
    """Yangi kod beradi — eskisi shu zahoti ishlamay qoladi."""
    group.invite_code = await _unique_code(session)
    await session.flush()
    return group


async def leave(session: AsyncSession, user: User) -> tuple[Group, list[User]]:
    """Foydalanuvchi jamoadan o'z ixtiyori bilan chiqadi.

    Qaytaradi: (jamoa, qolgan a'zolar) — chaqiruvchi ularga xabar beradi.

    **Sardor chiqsa, sardorlik eng erta qo'shilgan a'zoga o'tadi.** Aks holda
    jamoa boshqaruvsiz qolardi: taklif kodini yangilash ham, a'zo chiqarish
    ham faqat sardorga ochiq.

    Yolg'iz odam chiqa olmaydi: o'zi chiqib, keyingi ochilishda `ensure_group`
    unga yangi jamoa yaratardi — foydasiz amal. Shu tufayli bo'sh jamoa ham
    qolmaydi va guruh o'chirish mantiqi kerak emas.

    `remove_member` kabi: vazifa, odat va statistika o'chmaydi.
    """
    group = await get_user_group(session, user.id)
    if group is None:
        raise TeamError("Sizda jamoa yo'q")

    remaining = [m for m in await members(session, group.id) if m.id != user.id]
    if not remaining:
        raise TeamError("Jamoada sizdan boshqa hech kim yo'q")

    membership = await session.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.group_id == group.id
        )
    )
    if membership is None:
        raise TeamError("Siz bu jamoada emassiz")

    await session.delete(membership)

    if is_owner(group, user.id):
        # `members()` qo'shilish vaqti bo'yicha tartiblangan — birinchisi eng eskisi
        group.owner_id = remaining[0].id

    await session.flush()
    return group, remaining


async def remove_member(session: AsyncSession, group: Group, target_id: int) -> User:
    """A'zoni jamoadan chiqaradi. Uning vazifa va odatlari o'chmaydi.

    Chiqarilgan odam ilovani keyingi ochganda `ensure_group` unga yangi
    yolg'iz jamoa yaratadi — ya'ni ilova ishlayveradi, faqat sherigi yo'q.
    """
    if target_id == group.owner_id:
        raise TeamError("Sardorni jamoadan chiqarib bo'lmaydi")

    membership = await session.scalar(
        select(Membership).where(
            Membership.user_id == target_id, Membership.group_id == group.id
        )
    )
    if membership is None:
        raise TeamError("Bu odam jamoada yo'q")

    target = await session.get(User, target_id)
    if target is None:
        raise TeamError("Foydalanuvchi topilmadi")

    await session.delete(membership)
    await session.flush()
    return target
