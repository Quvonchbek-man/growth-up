"""Inline klaviaturalar.

Mini App tugmalari `WebAppInfo` orqali ochiladi — manzil `.env` dan olinadi,
BotFather'da qo'lda sozlash shart emas. `WEBAPP_URL` bo'sh bo'lsa web-app
tugmalari umuman chizilmaydi (aks holda Telegram xato beradi).
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callbacks import BroadcastCb, NudgeCb, ReasonCb, TaskCb
from bot.locales import uz as T
from shared.config import settings
from shared.models import Task, TaskStatus


def _webapp(path: str = "") -> WebAppInfo | None:
    url = settings.webapp_url.strip()
    if not url:
        return None
    return WebAppInfo(url=url.rstrip("/") + path)


def open_app(path: str = "", label: str = T.BTN_OPEN_APP) -> InlineKeyboardMarkup | None:
    info = _webapp(path)
    if info is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, web_app=info)]]
    )


def plan_tomorrow() -> InlineKeyboardMarkup | None:
    return open_app("/#/tomorrow", T.BTN_PLAN_TOMORROW)


def main_menu() -> InlineKeyboardMarkup | None:
    """Asosiy menyu — hammasi Mini App ichida ochiladi."""
    if _webapp() is None:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text=T.BTN_TODAY, web_app=_webapp("/#/today"))
    kb.button(text=T.BTN_PLAN_TOMORROW, web_app=_webapp("/#/tomorrow"))
    kb.button(text=T.BTN_TEAM, web_app=_webapp("/#/team"))
    kb.button(text=T.BTN_STATS, web_app=_webapp("/#/stats"))
    kb.adjust(2, 2)
    return kb.as_markup()


def day_tasks(tasks: list[Task]) -> InlineKeyboardMarkup:
    """Bugungi vazifalar — har biri bitta tugma.

    Botdagi tez belgilash Mini App'ni ochmasdan ishlashi kerak: ritmni
    aynan shu bir bosish saqlaydi.
    """
    kb = InlineKeyboardBuilder()
    for task in tasks:
        done = task.status == TaskStatus.DONE
        mark = "✅" if done else "⬜"
        action = "undo" if done else "done"
        # Uzun nomlar tugmani buzadi
        title = task.title if len(task.title) <= 28 else task.title[:27] + "…"
        kb.button(
            text=f"{mark} {title}",
            callback_data=TaskCb(action=action, task_id=task.id).pack(),
        )
    kb.adjust(1)

    app_btn = _webapp("/#/today")
    if app_btn is not None:
        kb.row(InlineKeyboardButton(text=T.BTN_OPEN_APP, web_app=app_btn))
    return kb.as_markup()


def reason_choices(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for value, label in T.REASON_BUTTONS:
        kb.button(
            text=label,
            callback_data=ReasonCb(task_id=task_id, reason=value).pack(),
        )
    kb.adjust(2)
    return kb.as_markup()


def broadcast_confirm() -> InlineKeyboardMarkup:
    """Ommaviy xabar tasdig'i.

    Tugmasiz yuborib bo'lmaydi: bu qaytarib bo'lmaydigan amal — yuborilgan
    xabarni hamma foydalanuvchidan o'chirib bo'lmaydi.
    """
    kb = InlineKeyboardBuilder()
    kb.button(
        text=T.BTN_BROADCAST_SEND, callback_data=BroadcastCb(action="send").pack()
    )
    kb.button(
        text=T.BTN_BROADCAST_CANCEL, callback_data=BroadcastCb(action="cancel").pack()
    )
    kb.adjust(1)
    return kb.as_markup()


def nudge_partner(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=T.BTN_NUDGE, callback_data=NudgeCb(to_user_id=user_id).pack())
    app_btn = _webapp("/#/team")
    if app_btn is not None:
        kb.row(InlineKeyboardButton(text=T.BTN_TEAM, web_app=app_btn))
    return kb.as_markup()
