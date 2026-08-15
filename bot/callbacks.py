"""Inline tugmalar uchun callback ma'lumotlari.

aiogram callback_data uchun 64 bayt chegara qo'yadi — shuning uchun
prefikslar qisqa.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class TaskCb(CallbackData, prefix="t"):
    """Vazifa holatini o'zgartirish: bajarildi / bekor qilish."""

    action: str  # "done" | "undo"
    task_id: int


class ReasonCb(CallbackData, prefix="r"):
    """Bajarilmagan vazifa uchun sabab."""

    task_id: int
    reason: str


class NudgeCb(CallbackData, prefix="n"):
    """Sherikka turtki berish."""

    to_user_id: int


class DayCb(CallbackData, prefix="d"):
    """Kun ro'yxatini qayta chizish."""

    action: str  # "refresh"
    date: str    # ISO sana


class BroadcastCb(CallbackData, prefix="bc"):
    """Ommaviy xabarni tasdiqlash yoki bekor qilish (faqat admin)."""

    action: str  # "send" | "cancel"
