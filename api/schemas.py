"""So'rov va javob sxemalari.

Javoblar ataylab `dict` sifatida qaytariladi (`services/stats.py` tayyorlaydi):
sxemani ikki joyda saqlash frontend o'zgarganda sinxronlikni yo'qotadi.
Bu yerda faqat KIRUVCHI ma'lumot tekshiriladi — u ishonchsiz.
"""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from shared.models import MissReason, ScheduleKind, TaskStatus, Visibility


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    points: int = Field(default=1, ge=1, le=10)
    visibility: Visibility | None = None
    # Kun ichidagi oraliq. Ikkalasi ham ixtiyoriy; tugash vaqti yolg'iz
    # kelolmaydi (tekshiruv `services/planning.py` da).
    start_time: time | None = None
    end_time: time | None = None


class HabitTaskCreate(BaseModel):
    """Odatni jadvalida yo'q kunga qo'lda qo'shish. Qolgan maydonlar odatdan."""

    habit_id: int


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    reason: MissReason | None = None
    note: str | None = Field(default=None, max_length=500)


class TaskMove(BaseModel):
    date: date


class TaskTime(BaseModel):
    """Mavjud vazifaning oralig'i. Ikkalasi ham `None` — vaqtni olib tashlash."""

    start_time: time | None = None
    end_time: time | None = None


class HabitPayload(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    icon: str = Field(default="✅", max_length=8)
    schedule_kind: ScheduleKind = ScheduleKind.DAILY
    # 7 bitlik maska: dushanba = 1 … yakshanba = 64
    weekdays_mask: int = Field(default=127, ge=1, le=127)
    points: int = Field(default=1, ge=1, le=10)
    visibility: Visibility = Visibility.PUBLIC
    start_time: time | None = None
    end_time: time | None = None


class JoinPayload(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class GroupRename(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class NudgePayload(BaseModel):
    to_user_id: int
    comment: str = Field(default="", max_length=200)


class ReactionPayload(BaseModel):
    target_user_id: int
    emoji: str = Field(default="👍", max_length=8)
    comment: str | None = Field(default=None, max_length=200)


class SettingsPayload(BaseModel):
    plan_reminder_at: time | None = None
    digest_at: time | None = None
    # 0 — vazifa eslatmalari o'chirilgan. Yuqori chegara: 2 soat oldin
    # eslatishning ma'nosi qolmaydi.
    task_lead_min: int | None = Field(default=None, ge=0, le=120)
    allow_nag_about_me: bool | None = None
    notify_about_partner: bool | None = None
    show_ranking: bool | None = None
    tz: str | None = Field(default=None, max_length=64)
