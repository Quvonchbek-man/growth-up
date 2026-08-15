"""Foydalanuvchi sozlamalari."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, get_session, is_admin
from api.schemas import SettingsPayload
from services import groups
from shared import clock
from shared.config import settings
from shared.models import User

router = APIRouter(prefix="/me", tags=["me"])


async def _serialize(session: AsyncSession, user: User) -> dict:
    # Jamoa qisqacha: sozlamalar oynasi «jamoadan chiqish» tugmasini
    # ko'rsatish-ko'rsatmaslikni shunga qarab hal qiladi (yolg'iz odamga
    # chiqishning ma'nosi yo'q). To'liq ma'lumot — `GET /team` da.
    group = await groups.get_user_group(session, user.id)
    group_info = None
    if group is not None:
        member_list = await groups.members(session, group.id)
        owner = groups.is_owner(group, user.id)
        group_info = {
            "name": group.name,
            "partner_count": len(member_list) - 1,
            "is_owner": owner,
            # `GET /team` dagi qoida shu yerda ham: kod faqat sardorga
            "invite_code": group.invite_code if owner else None,
            # A'zolarni boshqarish sozlamalarda — sardorga ro'yxat kerak.
            # Qo'shimcha so'rov emas: `member_list` allaqachon olingan.
            "partners": [
                {"user_id": m.id, "name": m.display_name}
                for m in member_list
                if m.id != user.id
            ],
        }

    return {
        "group": group_info,
        "id": user.id,
        "name": user.display_name,
        "username": user.username,
        "tz": user.tz,
        "today": clock.today_local(user.tz).isoformat(),
        "plan_reminder_at": (user.plan_reminder_at or settings.plan_reminder_time).strftime("%H:%M"),
        "digest_at": (user.digest_at or settings.digest_time).strftime("%H:%M"),
        "task_lead_min": user.task_lead_min,
        "allow_nag_about_me": user.allow_nag_about_me,
        "notify_about_partner": user.notify_about_partner,
        "show_ranking": user.show_ranking,
        "streak_success_pct": settings.streak_success_pct,
        # Mini App sozlamalarda «Admin panel» tugmasini shunga qarab
        # ko'rsatadi. Tugmani yashirish himoya emas — himoya `current_admin`
        # da; bu shunchaki oddiy odamga keraksiz tugma ko'rinmasin.
        "is_admin": is_admin(user.id),
    }


@router.get("")
async def me(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _serialize(session, user)


@router.patch("")
async def update_me(
    payload: SettingsPayload,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.plan_reminder_at is not None:
        user.plan_reminder_at = payload.plan_reminder_at
    if payload.digest_at is not None:
        user.digest_at = payload.digest_at
    if payload.task_lead_min is not None:
        user.task_lead_min = payload.task_lead_min
    if payload.allow_nag_about_me is not None:
        user.allow_nag_about_me = payload.allow_nag_about_me
    if payload.notify_about_partner is not None:
        user.notify_about_partner = payload.notify_about_partner
    if payload.show_ranking is not None:
        user.show_ranking = payload.show_ranking
    if payload.tz and clock.is_valid_tz(payload.tz):
        user.tz = payload.tz

    await session.flush()
    return await _serialize(session, user)
