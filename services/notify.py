"""Telegram xabarlari.

Bu — `services/` ichidagi yagona modul, u Telegram haqida biladi. Sabab:
xabar matni va uni yuborish qarori biznes qoidasi (kimga, qachon, nechta),
handler emas. Handlerlar faqat foydalanuvchi bosgan tugmaga javob beradi.

Har yuborish `safe_send` orqali o'tadi: botni bloklagan odam tufayli butun
eslatma sikli to'xtab qolmasligi kerak.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.locales import uz as T
from services import groups, planning, streak
from shared import clock
from shared.config import settings
from shared.models import (
    Nudge,
    NudgeKind,
    ReminderKind,
    ReminderLog,
    Task,
    TaskStatus,
    User,
)

logger = logging.getLogger(__name__)


# ─── Yuborish ────────────────────────────────────────────────────────────────


async def safe_send(
    bot: Bot,
    session: AsyncSession,
    user: User,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Xabar yuboradi. Bloklangan foydalanuvchini belgilab, `False` qaytaradi."""
    if user.is_blocked:
        return False
    try:
        await bot.send_message(user.id, text, reply_markup=markup)
        return True
    except TelegramForbiddenError:
        # Foydalanuvchi botni bloklagan — boshqa urinmaymiz
        logger.info("Foydalanuvchi %s botni bloklagan", user.id)
        user.is_blocked = True
        return False
    except TelegramRetryAfter as exc:
        logger.warning("Flood limit: %s soniya kutish kerak", exc.retry_after)
        return False
    except Exception:
        logger.exception("Xabar yuborilmadi: user=%s", user.id)
        return False


# ─── Takrorlanmaslik qo'riqchisi ─────────────────────────────────────────────


async def already_sent(
    session: AsyncSession,
    user_id: int,
    kind: ReminderKind,
    d: date_type,
    task_id: int = 0,
) -> bool:
    """`task_id` — vazifa eslatmalari uchun. Kunlik turlarida doim `0`."""
    row = await session.scalar(
        select(ReminderLog.id).where(
            ReminderLog.user_id == user_id,
            ReminderLog.kind == kind,
            ReminderLog.date == d,
            ReminderLog.task_id == task_id,
        )
    )
    return row is not None


async def mark_sent(
    session: AsyncSession,
    user_id: int,
    kind: ReminderKind,
    d: date_type,
    task_id: int = 0,
) -> None:
    session.add(ReminderLog(user_id=user_id, kind=kind, date=d, task_id=task_id))
    await session.flush()


# ─── Eslatmalar ──────────────────────────────────────────────────────────────


async def send_plan_reminder(bot: Bot, session: AsyncSession, user: User) -> bool:
    """Kechqurun: ertangi kunga reja yozing."""
    tomorrow = clock.tomorrow_local(user.tz)
    if await already_sent(session, user.id, ReminderKind.PLAN, tomorrow):
        return False

    submitted = await planning.has_submitted_plan_for(session, user.id, tomorrow)
    text = T.PLAN_REMINDER_DONE if submitted else T.PLAN_REMINDER
    sent = await safe_send(bot, session, user, text, kb.plan_tomorrow())
    await mark_sent(session, user.id, ReminderKind.PLAN, tomorrow)
    return sent


async def send_digest(bot: Bot, session: AsyncSession, user: User) -> bool:
    """Ertalab: bugungi reja + tez belgilash tugmalari."""
    today = clock.today_local(user.tz)
    if await already_sent(session, user.id, ReminderKind.DIGEST, today):
        return False

    _, tasks = await planning.open_day(session, user, today)
    active = [t for t in tasks if t.status != TaskStatus.SKIPPED]

    if not active:
        sent = await safe_send(bot, session, user, T.DIGEST_EMPTY, kb.plan_tomorrow())
    else:
        lines = [T.DIGEST_HEADER.format(count=len(active))]
        for t in active:
            mark = "✅" if t.status == TaskStatus.DONE else "⬜"
            span = clock.fmt_range(t.start_time, t.end_time)
            lines.append(f"{mark} {span} {t.title}" if span else f"{mark} {t.title}")
        lines.append(T.DIGEST_FOOTER)
        sent = await safe_send(
            bot, session, user, "\n".join(lines), kb.day_tasks(active)
        )

    await mark_sent(session, user.id, ReminderKind.DIGEST, today)
    return sent


async def send_task_reminders(
    bot: Bot, session: AsyncSession, user: User, *, force: bool = False
) -> int:
    """Boshlanishiga oz qolgan vazifalar haqida eslatadi.

    Kunlik eslatmalardan farqi: bittasi emas, bir kunda bir nechtasi ketadi.
    Shuning uchun takrorlanmaslik `ReminderLog.task_id` bo'yicha hisoblanadi.

    `force` (admin `/sinov`) — vaqtga qaramay, lekin faqat eng yaqin 3 tasi:
    kunning hamma vazifasi ketma-ket kelsa sinov o'zi bezovtalikka aylanadi.
    """
    lead = user.task_lead_min
    if lead <= 0 and not force:
        return 0

    today = clock.today_local(user.tz)
    rows = await session.scalars(
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.date == today,
            Task.status == TaskStatus.PLANNED,
            Task.start_time.is_not(None),
        )
        .order_by(Task.start_time)
    )
    tasks = list(rows)
    if force:
        tasks = tasks[:3]

    sent = 0
    for task in tasks:
        if not force and not clock.is_due(
            clock.shift_time(task.start_time, -lead), user.tz
        ):
            continue
        if await already_sent(
            session, user.id, ReminderKind.TASK_SOON, today, task_id=task.id
        ):
            continue

        span = clock.fmt_range(task.start_time, task.end_time)
        # Ataylab ikkita alohida `T.X.format(...)` chaqiruvi: `tests/
        # test_integrity.py` shablon kalitlarini faqat shu shaklda ko'radi.
        # O'zgaruvchi orqali chaqirilsa, yetishmagan `{kalit}` faqat
        # ishlab chiqarishda, xabar yuborilmay qolganda bilinardi.
        if lead <= 0:
            text = T.TASK_SOON_NOW.format(title=task.title, range=span)
        else:
            text = T.TASK_SOON.format(lead=lead, title=task.title, range=span)
        ok = await safe_send(bot, session, user, text, kb.day_tasks([task]))
        await mark_sent(
            session, user.id, ReminderKind.TASK_SOON, today, task_id=task.id
        )
        sent += int(ok)

    return sent


async def nag_partners_about(bot: Bot, session: AsyncSession, user: User) -> int:
    """`user` ertangi rejani kiritmadi — sheriklariga xabar beramiz.

    Ikki tomonlama rozilik tekshiriladi: `user` o'zi haqida xabar ketishiga
    ruxsat berganmi, va sherik bunday xabarlarni olishni xohlaydimi.
    """
    tomorrow = clock.tomorrow_local(user.tz)
    if not user.allow_nag_about_me:
        return 0
    if await planning.has_submitted_plan_for(session, user.id, tomorrow):
        return 0
    if await already_sent(session, user.id, ReminderKind.NAG_PARTNER, tomorrow):
        return 0

    sent_count = 0
    for partner in await groups.partners(session, user):
        if not partner.notify_about_partner:
            continue
        ok = await safe_send(
            bot,
            session,
            partner,
            T.NAG_PARTNER.format(name=user.display_name),
            kb.nudge_partner(user.id),
        )
        sent_count += int(ok)

    await mark_sent(session, user.id, ReminderKind.NAG_PARTNER, tomorrow)
    return sent_count


async def close_and_summarize(bot: Bot, session: AsyncSession, user: User) -> bool:
    """Yarim tundan keyin: kechagi kunni yopib, natijani yuboradi."""
    today = clock.today_local(user.tz)
    yesterday = today - timedelta(days=1)

    if await already_sent(session, user.id, ReminderKind.DAY_CLOSE, yesterday):
        return False

    plan = await planning.close_day(session, user, yesterday)
    await mark_sent(session, user.id, ReminderKind.DAY_CLOSE, yesterday)

    if plan is None or plan.planned_count == 0:
        return False

    state = await streak.recalc(session, user)
    template = (
        T.DAY_CLOSED_GOOD
        if plan.completion_pct >= settings.streak_success_pct
        else T.DAY_CLOSED_WEAK
    )
    return await safe_send(
        bot,
        session,
        user,
        template.format(
            done=plan.done_count,
            planned=plan.planned_count,
            pct=plan.completion_pct,
            score=plan.score,
            streak=state.current_len,
        ),
        kb.plan_tomorrow(),
    )


async def ask_reasons(bot: Bot, session: AsyncSession, user: User) -> int:
    """Kechagi bajarilmagan ishlar uchun sabab so'raydi.

    Har vazifa uchun alohida xabar — sabab tugmasi aynan o'sha vazifaga
    tegishli bo'lishi kerak. Ko'p bo'lsa faqat birinchi 5 tasi so'raladi:
    10 ta xabar ketma-ket kelsa, odam hech biriga javob bermaydi.
    """
    today = clock.today_local(user.tz)
    yesterday = today - timedelta(days=1)

    if await already_sent(session, user.id, ReminderKind.ASK_REASON, yesterday):
        return 0

    missed = await planning.missed_tasks_without_reason(session, user.id, yesterday)
    await mark_sent(session, user.id, ReminderKind.ASK_REASON, yesterday)
    if not missed:
        return 0

    await safe_send(bot, session, user, T.ASK_REASON_HEADER.format(count=len(missed)))
    asked = 0
    for task in missed[:5]:
        ok = await safe_send(
            bot,
            session,
            user,
            T.ASK_REASON_TASK.format(title=task.title),
            kb.reason_choices(task.id),
        )
        asked += int(ok)
    return asked


# ─── Turtki ──────────────────────────────────────────────────────────────────


async def nudges_sent_today(
    session: AsyncSession, from_user_id: int, to_user_id: int, d: date_type
) -> int:
    count = await session.scalar(
        select(func.count(Nudge.id)).where(
            Nudge.from_user_id == from_user_id,
            Nudge.to_user_id == to_user_id,
            Nudge.date == d,
            Nudge.kind == NudgeKind.MANUAL,
        )
    )
    return int(count or 0)


async def send_nudge(
    bot: Bot,
    session: AsyncSession,
    sender: User,
    target: User,
    comment: str = "",
) -> bool:
    """Qo'lda turtki. Kunlik chegaradan oshsa `False` qaytaradi."""
    today = clock.today_local(sender.tz)
    if await nudges_sent_today(session, sender.id, target.id, today) >= settings.max_nudges_per_day:
        return False

    text = T.NUDGE_RECEIVED.format(
        name=sender.display_name,
        comment=comment.strip() or T.NUDGE_DEFAULT_COMMENT,
    )
    ok = await safe_send(bot, session, target, text, kb.plan_tomorrow())
    session.add(
        Nudge(
            from_user_id=sender.id,
            to_user_id=target.id,
            kind=NudgeKind.MANUAL,
            text=comment.strip()[:200],
            date=today,
        )
    )
    await session.flush()
    return ok


async def notify_removed(
    bot: Bot, session: AsyncSession, removed: User, group_name: str
) -> None:
    """Jamoadan chiqarilgan odamga xabar. Ayblovsiz — faqat fakt."""
    await safe_send(
        bot,
        session,
        removed,
        T.REMOVED_FROM_GROUP.format(group_name=group_name),
    )


async def notify_left(
    bot: Bot,
    session: AsyncSession,
    leaver: User,
    group_name: str,
    remaining: list[User],
    new_owner_id: int,
) -> None:
    """Sherik o'zi chiqqanda qolganlarga xabar.

    Jim ketishga yo'l qo'yib bo'lmaydi: qolgan odam sherigi shunchaki
    javob bermayapti deb o'ylab, haftalab kutib yuraveradi. Chiqqan odamning
    o'ziga ham tasdiq boradi — ilovadan tashqarida ham izi qolsin.
    """
    for partner in remaining:
        text = T.PARTNER_LEFT.format(name=leaver.display_name, group_name=group_name)
        if partner.id == new_owner_id:
            text += "\n\n" + T.YOU_ARE_OWNER_NOW
        await safe_send(bot, session, partner, text)

    await safe_send(bot, session, leaver, T.YOU_LEFT_GROUP.format(group_name=group_name))


async def notify_partner_joined(bot: Bot, session: AsyncSession, newcomer: User) -> None:
    for partner in await groups.partners(session, newcomer):
        await safe_send(
            bot,
            session,
            partner,
            T.PARTNER_JOINED.format(name=newcomer.display_name),
            kb.main_menu(),
        )


# ─── Vazifa holati o'zgarganda ───────────────────────────────────────────────


def progress_line(done: int, planned: int, pct: int, score: int) -> str:
    return T.DAY_PROGRESS.format(done=done, planned=planned, pct=pct, score=score)


async def day_task_list(session: AsyncSession, user: User, d: date_type) -> list[Task]:
    tasks = await planning.get_tasks(session, user.id, d)
    return [t for t in tasks if t.status != TaskStatus.SKIPPED]
