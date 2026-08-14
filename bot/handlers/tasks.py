"""Botdan tez belgilash: ✅ / ↩️ va bajarilmagan uchun sabab.

Bu ilovaning ritmini saqlaydigan qism. Mini App'ni ochish uchun 3 ta bosish
kerak, bu yerda esa bitta — kunlik odat aynan shu farqdan buziladi.
"""

from __future__ import annotations

from aiogram import Router, html
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.callbacks import ReasonCb, TaskCb
from bot.locales import uz as T
from services import notify, planning, scoring, streak
from shared.models import MissReason, Task, TaskStatus, User

router = Router(name="tasks")


async def _rerender(
    call: CallbackQuery, session: AsyncSession, user: User, task: Task
) -> None:
    """Xabarni o'sha kunning yangi holati bilan qayta chizadi."""
    tasks = await notify.day_task_list(session, user, task.date)
    if not tasks:
        return

    stats = scoring.summarize(tasks)
    state = await streak.recalc(session, user)

    lines = [T.DIGEST_HEADER.format(count=len(tasks))]
    for t in tasks:
        mark = "✅" if t.status == TaskStatus.DONE else "⬜"
        lines.append(f"{mark} {html.quote(t.title)}")
    lines.append(
        notify.progress_line(
            stats["done_count"],
            stats["planned_count"],
            stats["completion_pct"],
            stats["score"],
        )
    )
    if state.current_len:
        lines.append(T.STREAK_KEPT.format(n=state.current_len))

    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb.day_tasks(tasks))
    except Exception:
        # "message is not modified" yoki xabar juda eski — muhim emas
        pass


@router.callback_query(TaskCb.filter())
async def toggle_task(
    call: CallbackQuery, callback_data: TaskCb, session: AsyncSession, user: User
) -> None:
    new_status = (
        TaskStatus.DONE if callback_data.action == "done" else TaskStatus.PLANNED
    )
    task = await planning.set_status(session, user.id, callback_data.task_id, new_status)

    if task is None:
        await call.answer(T.TASK_NOT_FOUND, show_alert=True)
        return

    template = T.TASK_DONE if new_status == TaskStatus.DONE else T.TASK_UNDONE
    await call.answer(template.format(title=task.title))
    await _rerender(call, session, user, task)


@router.callback_query(ReasonCb.filter())
async def save_reason(
    call: CallbackQuery, callback_data: ReasonCb, session: AsyncSession, user: User
) -> None:
    try:
        reason = MissReason(callback_data.reason)
    except ValueError:
        await call.answer(T.GENERIC_ERROR)
        return

    task = await planning.set_miss_reason(
        session, user.id, callback_data.task_id, reason
    )
    if task is None:
        await call.answer(T.TASK_NOT_FOUND, show_alert=True)
        return

    from services.stats import REASON_LABELS

    label = REASON_LABELS.get(reason.value, reason.value)
    await call.answer(T.REASON_SAVED.format(label=label))
    try:
        await call.message.edit_text(
            f"✔️ <b>{html.quote(task.title)}</b>\n{T.REASON_SAVED.format(label=label)}"
        )
    except Exception:
        pass
