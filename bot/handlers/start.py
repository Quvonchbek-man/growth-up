"""/start, /help, jamoa buyruqlari va bugungi reja."""

from __future__ import annotations

from aiogram import Bot, Router, html
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.locales import uz as T
from services import groups, notify, planning, scoring
from shared import clock
from shared.config import settings
from shared.models import TaskStatus, User

router = Router(name="start")


async def _join_and_greet(
    message: Message, session: AsyncSession, user: User, bot: Bot, code: str
) -> bool:
    """Taklif kodi bo'yicha qo'shadi. Muvaffaqiyatli bo'lsa `True`."""
    try:
        group = await groups.join_by_code(session, user, code)
    except groups.JoinError as exc:
        await message.answer(str(exc))
        return False

    await message.answer(
        T.JOIN_OK.format(group_name=html.quote(group.name)), reply_markup=kb.main_menu()
    )
    await notify.notify_partner_joined(bot, session, user)
    return True


@router.message(CommandStart(deep_link=True))
async def start_with_code(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    """`t.me/bot?start=ABC123` — havola orqali jamoaga qo'shilish.

    Sherikni chaqirishning eng qisqa yo'li: u kod terishi shart emas.
    """
    code = (command.args or "").strip()
    if code and await _join_and_greet(message, session, user, bot, code):
        return
    await start(message, session, user)


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession, user: User) -> None:
    is_new = user.onboarded_at is None
    group = await groups.ensure_group(session, user)

    if is_new:
        user.onboarded_at = clock.now_utc()
        text = T.START_NEW.format(name=html.quote(message.from_user.first_name or ""))
    else:
        text = T.START_BACK.format(name=html.quote(message.from_user.first_name or ""))

    markup = kb.main_menu()
    if markup is None:
        text += "\n\n" + T.NO_WEBAPP_URL
    await message.answer(text, reply_markup=markup)

    if is_new:
        await team(message, session, user, group=group)


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        T.HELP.format(pct=settings.streak_success_pct), reply_markup=kb.main_menu()
    )


@router.message(Command("jamoa", "team"))
async def team(
    message: Message, session: AsyncSession, user: User, group=None
) -> None:
    group = group or await groups.ensure_group(session, user)
    members = await groups.members(session, group.id)

    if len(members) <= 1:
        members_block = T.GROUP_ALONE
    else:
        lines = [T.GROUP_MEMBERS_TITLE]
        for m in members:
            lines.append(f"• {html.quote(m.display_name)}")
        members_block = "\n".join(lines)

    # Taklif kodi faqat sardorga — jamoaga kimni qo'shishni u hal qiladi
    if groups.is_owner(group, user.id):
        text = T.GROUP_INFO.format(
            group_name=html.quote(group.name),
            code=group.invite_code,
            members_block=members_block,
        )
    else:
        owner = next((m for m in members if m.id == group.owner_id), None)
        text = T.GROUP_INFO_MEMBER.format(
            group_name=html.quote(group.name),
            owner=html.quote(owner.display_name) if owner else "—",
            members_block=members_block,
        )

    await message.answer(text, reply_markup=kb.main_menu())


@router.message(Command("qoshil", "join"))
async def join(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    code = (command.args or "").strip()
    if not code:
        await message.answer(T.JOIN_USAGE)
        return
    await _join_and_greet(message, session, user, bot, code)


@router.message(Command("bugun", "today"))
async def today(message: Message, session: AsyncSession, user: User) -> None:
    d = clock.today_local(user.tz)
    _, all_tasks = await planning.open_day(session, user, d)
    tasks = [t for t in all_tasks if t.status != TaskStatus.SKIPPED]

    if not tasks:
        await message.answer(T.DIGEST_EMPTY, reply_markup=kb.plan_tomorrow())
        return

    stats = scoring.summarize(tasks)
    lines = [T.DIGEST_HEADER.format(count=len(tasks))]
    for t in tasks:
        mark = "✅" if t.status == TaskStatus.DONE else "⬜"
        lines.append(f"{mark} {html.quote(t.title)}")
    lines.append(
        notify.progress_line(
            stats["done_count"], stats["planned_count"], stats["completion_pct"], stats["score"]
        )
    )

    await message.answer("\n".join(lines), reply_markup=kb.day_tasks(tasks))
