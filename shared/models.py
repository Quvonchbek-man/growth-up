"""Ma'lumot modeli.

Ikkita qaror butun modelni belgilaydi:

1. **Habit — shablon, Task — o'sha kunning nusxasi.** Odatni o'zgartirsangiz
   yoki o'chirsangiz, o'tmishdagi natijalar o'zgarmaydi. Aks holda "o'tgan oy
   nima qilgan edim" degan savolga javob yo'qoladi.

2. **`date` — mahalliy sana, `datetime` — UTC.** `shared/clock.py` ga qarang.

Faza 2 jadvallari (`Goal`, `JournalEntry`) hozircha bo'sh turadi, lekin
`Task.goal_id` maydoni bugundan mavjud: keyin migratsiya emas, faqat to'ldirish
kerak bo'ladi.
"""

from __future__ import annotations

import enum
from datetime import date as date_type, datetime, time as time_type

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _enum(enum_cls: type[enum.Enum]) -> Enum:
    """Sanoqni VARCHAR sifatida saqlaydi.

    SQLite'da native ENUM yo'q, Postgres'da esa native ENUM'ga yangi qiymat
    qo'shish `ALTER TYPE` talab qiladi. Satr sifatida saqlash ikkalasida ham
    bir xil ishlaydi va Faza 3 dagi ko'chishni osonlashtiradi.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


# ─── Sanoqlar ────────────────────────────────────────────────────────────────


class TaskStatus(str, enum.Enum):
    PLANNED = "planned"
    DONE = "done"
    MISSED = "missed"
    # Ataylab o'tkazib yuborilgan (kasal, safar, dam kuni). Streak'ni buzmaydi
    # va bajarilish foiziga kirmaydi — "halol o'tkazish" imkoniyati.
    SKIPPED = "skipped"


class TaskSource(str, enum.Enum):
    HABIT = "habit"      # odatdan avtomatik yaratilgan
    MANUAL = "manual"    # qo'lda kiritilgan bir martalik vazifa


class MissReason(str, enum.Enum):
    TIRED = "tired"
    NO_TIME = "no_time"
    FORGOT = "forgot"
    NOT_IMPORTANT = "not_important"
    OTHER = "other"


class Visibility(str, enum.Enum):
    """Sherik nimani ko'radi.

    PUBLIC     — nomini ham, holatini ham ko'radi
    STATS_ONLY — nomi yashirin, lekin umumiy foizga kiradi ("4/5 bajardi")
    PRIVATE    — sherik umuman ko'rmaydi va umumiy foizga ham KIRMAYDI
    """

    PUBLIC = "public"
    STATS_ONLY = "stats_only"
    PRIVATE = "private"


class ScheduleKind(str, enum.Enum):
    DAILY = "daily"        # har kuni
    WEEKDAYS = "weekdays"  # weekdays_mask bo'yicha tanlangan kunlarda


class NudgeKind(str, enum.Enum):
    MANUAL = "manual"  # odam tugmani bosdi
    AUTO = "auto"      # bot o'zi yubordi


class ReactionTarget(str, enum.Enum):
    TASK = "task"
    DAY = "day"


class ReminderKind(str, enum.Enum):
    PLAN = "plan"              # kechqurun: ertangi rejani kiriting
    NAG_PARTNER = "nag"        # sherikka: u hali reja kiritmadi
    DIGEST = "digest"          # ertalab: bugungi reja
    DAY_CLOSE = "close"        # yarim tun: kunni yopish (tizim ishi)
    ASK_REASON = "reason"      # bajarilmaganlar bo'yicha sabab so'rash
    TASK_SOON = "task_soon"    # kun ichida: falon vazifa boshlanay deb qoldi
    WEEKLY_REPORT = "weekly"   # Faza 2


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    DONE = "done"
    DROPPED = "dropped"


# Har kun uchun bitta bit: dushanba = 1, seshanba = 2, ... yakshanba = 64.
# `1 << d.weekday()` bilan tekshiriladi.
ALL_WEEKDAYS = 0b1111111  # 127


# ─── Foydalanuvchi va jamoa ──────────────────────────────────────────────────


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # Telegram ID — o'zimiz surrogat kalit o'ylab topmaymiz
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(128), default="")
    language: Mapped[str] = mapped_column(String(8), default="uz")
    tz: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")

    # --- Eslatma sozlamalari (mahalliy vaqt) ---
    plan_reminder_at: Mapped[time_type | None] = mapped_column(Time)
    digest_at: Mapped[time_type | None] = mapped_column(Time)
    # Vaqti belgilangan vazifa boshlanishidan necha daqiqa oldin eslatilsin.
    # 0 — bunday eslatmalar umuman yuborilmaydi.
    task_lead_min: Mapped[int] = mapped_column(Integer, default=10, server_default="10")

    # "Men ertangi rejani kiritmasam, sherigimga xabar ketsin"
    allow_nag_about_me: Mapped[bool] = mapped_column(Boolean, default=True)
    # "Sherigim bajarmasa menga xabar kelsin"
    notify_about_partner: Mapped[bool] = mapped_column(Boolean, default=True)
    # Reyting jadvalini ko'rsatish. O'chirilsa raqobat elementi yo'qoladi.
    show_ranking: Mapped[bool] = mapped_column(Boolean, default=True)

    # Bot bloklangan bo'lsa xabar yuborishga urinmaymiz
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    habits: Mapped[list[Habit]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def display_name(self) -> str:
        return self.full_name or (f"@{self.username}" if self.username else str(self.id))


class Group(Base, TimestampMixin):
    """Jamoa — 2 dan 10 kishigacha. Faza 1 da bitta jamoa bo'ladi."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="Jamoa")
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    max_members: Mapped[int] = mapped_column(Integer, default=10)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    group: Mapped[Group] = relationship(back_populates="memberships")


# ─── Odat va vazifa ──────────────────────────────────────────────────────────


class Habit(Base, TimestampMixin):
    """Takrorlanuvchi odat — SHABLON. Kunlik nusxasi `Task` da."""

    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str] = mapped_column(String(8), default="✅")

    schedule_kind: Mapped[ScheduleKind] = mapped_column(
        _enum(ScheduleKind), default=ScheduleKind.DAILY
    )
    weekdays_mask: Mapped[int] = mapped_column(Integer, default=ALL_WEEKDAYS)

    # Kun ichidagi oraliq — MAHALLIY vaqt (`date` maydonlari bilan bir mantiqda).
    # Ikkalasi ham ixtiyoriy: vaqtsiz odat kun bo'yi bajarilishi mumkin.
    start_time: Mapped[time_type | None] = mapped_column(Time)
    end_time: Mapped[time_type | None] = mapped_column(Time)

    # Ball og'irligi: sport 3, kitob 2, suv 1 — o'zingiz belgilaysiz
    points: Mapped[int] = mapped_column(Integer, default=1)
    visibility: Mapped[Visibility] = mapped_column(
        _enum(Visibility), default=Visibility.PUBLIC
    )

    # O'chirmaymiz — arxivlaymiz. O'tmishdagi Task'lar bog'liq bo'lib qoladi.
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="habits")

    def is_active_on(self, d: date_type) -> bool:
        if self.is_archived:
            return False
        if self.schedule_kind == ScheduleKind.DAILY:
            return True
        return bool(self.weekdays_mask & (1 << d.weekday()))


class Task(Base, TimestampMixin):
    """Bir kunning bitta vazifasi. Loyihaning o'zak jadvali."""

    __tablename__ = "tasks"
    __table_args__ = (
        # Bitta odat bir kunda ikki marta paydo bo'lmasin.
        # habit_id NULL bo'lganda (qo'lda kiritilgan vazifa) SQL cheklovi
        # ishlamaydi — bu ataylab: bir kunda istagancha qo'l vazifasi bo'ladi.
        UniqueConstraint("user_id", "date", "habit_id", name="uq_task_habit_day"),
        Index("ix_task_user_date", "user_id", "date"),
        Index("ix_task_date_status", "date", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # MAHALLIY sana — foydalanuvchi uchun "qaysi kun"
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[TaskSource] = mapped_column(
        _enum(TaskSource), default=TaskSource.MANUAL
    )
    habit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("habits.id", ondelete="SET NULL")
    )
    # Faza 2: maqsadga bog'lash. Maydon bugundan bor — keyin ALTER kerak emas.
    goal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("goals.id", ondelete="SET NULL")
    )

    # Odatdan meros oladi yoki qo'lda kiritiladi. Mahalliy vaqt.
    start_time: Mapped[time_type | None] = mapped_column(Time)
    end_time: Mapped[time_type | None] = mapped_column(Time)

    # Kun boshlangandan keyin qo'shilgan ish. Reja EMAS — va'da kechqurun
    # berilgan, bu esa ustiga chiqqani. Shuning uchun na foizga, na ballga,
    # na streakka kiradi (`services/scoring.py`).
    is_extra: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )

    status: Mapped[TaskStatus] = mapped_column(
        _enum(TaskStatus), default=TaskStatus.PLANNED
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    miss_reason: Mapped[MissReason | None] = mapped_column(_enum(MissReason))
    miss_note: Mapped[str | None] = mapped_column(Text)

    points: Mapped[int] = mapped_column(Integer, default=1)
    # None bo'lsa odatdan meros oladi; qo'l vazifasi uchun PUBLIC
    visibility: Mapped[Visibility | None] = mapped_column(_enum(Visibility))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    habit: Mapped[Habit | None] = relationship()

    @property
    def effective_visibility(self) -> Visibility:
        if self.visibility is not None:
            return self.visibility
        if self.habit is not None:
            return self.habit.visibility
        return Visibility.PUBLIC

    @property
    def counts_for_score(self) -> bool:
        """SKIPPED va qo'shimcha vazifa na foizga, na ballga kiradi."""
        if self.is_extra:
            return False
        return self.status in (TaskStatus.DONE, TaskStatus.MISSED, TaskStatus.PLANNED)


class DailyPlan(Base, TimestampMixin):
    """Kunning holati: reja kiritildimi, yopildimi, nechta ball.

    `planned_count`/`done_count` ataylab takrorlangan (denormalizatsiya):
    statistika so'rovlari har safar `tasks` ni sanamasin. 30 kunlik grafik
    bitta jadvaldan o'qiladi.
    """

    __tablename__ = "daily_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_plan_day"),
        Index("ix_plan_user_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    # Reja OLDINDAN (kechqurun) kiritilgani — ilovaning asosiy odati shu
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Quyidagi to'rttasi FAQAT rejadan hisoblanadi — qo'shimchalar kirmaydi.
    # Streak ham shu `completion_pct` ni o'qiydi (`services/streak.py`).
    planned_count: Mapped[int] = mapped_column(Integer, default=0)
    done_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    completion_pct: Mapped[int] = mapped_column(Integer, default=0)  # 0..100

    # Qo'shimchalar alohida sanaladi: ko'rsatiladi, lekin hech qayerga qo'shilmaydi
    extra_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    extra_done_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )


class StreakState(Base):
    """Keshlangan streak. Har so'rovda 200 kunlik tarixni qayta sanamaslik uchun."""

    __tablename__ = "streaks"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_len: Mapped[int] = mapped_column(Integer, default=0)
    best_len: Mapped[int] = mapped_column(Integer, default=0)
    last_success_date: Mapped[date_type | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ─── Ijtimoiy qism ───────────────────────────────────────────────────────────


class Nudge(Base):
    """Turtki — qo'lda yuborilgan yoki bot avtomatik yuborgan."""

    __tablename__ = "nudges"
    __table_args__ = (Index("ix_nudge_to_date", "to_user_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    to_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[NudgeKind] = mapped_column(_enum(NudgeKind), default=NudgeKind.MANUAL)
    text: Mapped[str] = mapped_column(String(200), default="")
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Reaction(Base):
    """Qo'llab-quvvatlash: emoji yoki qisqa izoh."""

    __tablename__ = "reactions"
    __table_args__ = (Index("ix_reaction_target", "target_type", "target_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[ReactionTarget] = mapped_column(_enum(ReactionTarget))
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), default="👍")
    comment: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReminderLog(Base):
    """Idempotentlik qo'riqchisi.

    Bot kuniga bir necha marta qayta ishga tushishi mumkin. Shu jadval
    bo'lmasa, foydalanuvchi har restartda o'sha eslatmani qayta oladi va
    bir haftada botni bloklaydi.

    `task_id` — vazifa eslatmasi uchun: bir kunda bir necha vazifa bo'ladi,
    har biriga alohida yozuv kerak. Kunlik eslatmalarda `0` turadi.
    """

    __tablename__ = "reminder_log"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "date", "task_id", name="uq_reminder_once"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ReminderKind] = mapped_column(_enum(ReminderKind), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    # NULL EMAS, standarti 0. SQLite `UNIQUE` da NULL'lar bir-biridan farqli
    # hisoblanadi — nullable qilinsa kunlik eslatmalarning "bir marta"
    # kafolati jimgina yo'qoladi va har restart xabarni qayta yuboradi.
    task_id: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─── Faza 2 uchun jadvallar (hozircha bo'sh) ─────────────────────────────────


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_date: Mapped[date_type | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(_enum(GoalStatus), default=GoalStatus.ACTIVE)
    visibility: Mapped[Visibility] = mapped_column(
        _enum(Visibility), default=Visibility.PUBLIC
    )


class JournalEntry(Base, TimestampMixin):
    """Kundalik. Standart holatda YOPIQ — sherik faqat "yozdi" faktini ko'radi."""

    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_journal_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    mood: Mapped[int | None] = mapped_column(Integer)  # 1..5
    visibility: Mapped[Visibility] = mapped_column(
        _enum(Visibility), default=Visibility.PRIVATE
    )
