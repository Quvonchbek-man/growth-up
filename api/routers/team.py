"""Jamoa: sheriklar, taklif kodi, reyting, turtki, reaksiya."""

from __future__ import annotations

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_user, get_session
from api.schemas import GroupRename, JoinPayload, NudgePayload, ReactionPayload
from services import groups, notify, planning, stats
from shared import clock
from shared.models import Reaction, ReactionTarget, User

router = APIRouter(prefix="/team", tags=["team"])


def _owner_only(exc: groups.TeamError) -> HTTPException:
    """Sardor xatosini HTTP javobiga aylantiradi."""
    code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, groups.NotOwnerError)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(code, str(exc))


def _bot(request: Request) -> Bot | None:
    """Bot `run.py` da app.state ga qo'yiladi.

    API alohida (botsiz) ishga tushirilgan bo'lsa `None` bo'ladi — o'shanda
    turtki yuborib bo'lmaydi, lekin qolgan hamma narsa ishlayveradi.
    """
    return getattr(request.app.state, "bot", None)


@router.get("")
async def get_team(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    group = await groups.ensure_group(session, user)
    members = await groups.members(session, group.id)
    partners = [m for m in members if m.id != user.id]

    today = clock.today_local(user.tz)
    my_day = await stats.day_view(session, user, today, owner=True)

    owner = groups.is_owner(group, user.id)

    return {
        "group": {
            "id": group.id,
            "name": group.name,
            # Taklif kodi faqat sardorga ko'rinadi — jamoaga kimni qo'shishni
            # u hal qiladi. A'zoni chiqarish huquqi shu bilan ma'noga ega
            # bo'ladi: chiqarilgan odamda qaytib kirish kodi qolmaydi.
            "invite_code": group.invite_code if owner else None,
            "member_count": len(members),
            "max_members": group.max_members,
            "owner_id": group.owner_id,
            "is_owner": owner,
        },
        "me": {
            "user_id": user.id,
            "name": user.display_name,
            "today": my_day,
        },
        "partners": await stats.partner_cards(session, user, partners),
        "leaderboard": (
            await stats.week_leaderboard(session, members, user.tz)
            if user.show_ranking
            else []
        ),
        "show_ranking": user.show_ranking,
    }


@router.patch("")
async def rename_team(
    payload: GroupRename,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Jamoa nomini o'zgartirish — faqat sardor."""
    try:
        group = await groups.require_owner(session, user)
        await groups.rename(session, group, payload.name)
    except groups.TeamError as exc:
        raise _owner_only(exc) from exc
    return {"ok": True, "name": group.name}


@router.post("/code")
async def reset_code(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Taklif kodini yangilash — eskisi shu zahoti ishlamay qoladi."""
    try:
        group = await groups.require_owner(session, user)
        await groups.reset_invite_code(session, group)
    except groups.TeamError as exc:
        raise _owner_only(exc) from exc
    return {"ok": True, "invite_code": group.invite_code}


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """A'zoni jamoadan chiqarish — faqat sardor.

    Chiqarilgan odamga xabar beriladi: aks holda u sherigi nega yo'qolganini
    tushunmay, ilovaga reja yozib yuraveradi.
    """
    try:
        group = await groups.require_owner(session, user)
        removed = await groups.remove_member(session, group, member_id)
    except groups.TeamError as exc:
        raise _owner_only(exc) from exc

    bot = _bot(request)
    if bot is not None:
        await notify.notify_removed(bot, session, removed, group.name)

    return {"ok": True, "removed_id": removed.id}


@router.post("/leave")
async def leave_team(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Jamoadan o'z ixtiyori bilan chiqish.

    Sardor chiqsa sardorlik qolganlarga o'tadi (`groups.leave`). Qolganlarga
    xabar ketadi — sherikning jim g'oyib bo'lishi ilovaning ma'nosini
    yo'qotadi.
    """
    try:
        group, remaining = await groups.leave(session, user)
    except groups.TeamError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    bot = _bot(request)
    if bot is not None:
        await notify.notify_left(
            bot, session, user, group.name, remaining, group.owner_id
        )

    return {"ok": True}


@router.post("/join")
async def join(
    payload: JoinPayload,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        group = await groups.join_by_code(session, user, payload.code)
    except groups.JoinError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    bot = _bot(request)
    if bot is not None:
        await notify.notify_partner_joined(bot, session, user)

    return {"ok": True, "group_id": group.id, "name": group.name}


@router.post("/nudge")
async def nudge(
    payload: NudgePayload,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.to_user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O'zingizga turtki bera olmaysiz")

    partner_ids = {p.id for p in await groups.partners(session, user)}
    if payload.to_user_id not in partner_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu odam sizning jamoangizda emas")

    bot = _bot(request)
    if bot is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Bot ishlamayapti — turtki yuborilmadi"
        )

    target = await session.get(User, payload.to_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foydalanuvchi topilmadi")

    ok = await notify.send_nudge(bot, session, user, target, payload.comment)
    if not ok:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Bugun bu odamga yetarlicha turtki berdingiz",
        )
    return {"ok": True}


@router.post("/react")
async def react(
    payload: ReactionPayload,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Sherikning bugungi kuniga qo'llab-quvvatlash reaksiyasi."""
    partner_ids = {p.id for p in await groups.partners(session, user)}
    if payload.target_user_id not in partner_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu odam sizning jamoangizda emas")

    target = await session.get(User, payload.target_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foydalanuvchi topilmadi")

    today = clock.today_local(target.tz)
    plan = await planning.get_plan(session, target.id, today)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bu kunda reja yo'q")

    session.add(
        Reaction(
            from_user_id=user.id,
            target_type=ReactionTarget.DAY,
            target_id=plan.id,
            emoji=payload.emoji,
            comment=payload.comment,
        )
    )
    await session.flush()
    return {"ok": True}
