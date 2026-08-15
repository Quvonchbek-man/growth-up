"""Kun, reja va vazifalar bilan ishlash — loyihaning o'zak logikasi.

Asosiy tushuncha: **kun ob'ekti** (`DailyPlan`) + o'sha kunning vazifalari
(`Task`). Odatlar (`Habit`) shablon bo'lib, kun ochilganda ulardan nusxa
yaratiladi. Nusxa yaratilgandan keyin odat o'zgarsa, o'tmish o'zgarmaydi.
"""

from __future__ import annotations

from datetime import date as date_type, time as time_type, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services import scoring
from shared import clock
from shared.config import settings
from shared.models import (
    DailyPlan,
    Habit,
    MissReason,
    Task,
    TaskSource,
    TaskStatus,
    User,
)


# ─── Foydalanuvchi ───────────────────────────────────────────────────────────


async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None = None,
    full_name: str = "",
) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(
            id=tg_id,
            username=username,
            full_name=full_name,
            tz=settings.timezone,
            plan_reminder_at=settings.plan_reminder_time,
            digest_at=settings.digest_time,
            task_lead_min=settings.task_reminder_lead_min,
        )
        session.add(user)
        await session.flush()
        return user

    # Telegram profilidagi o'zgarishlarni ergashtirib boramiz
    if username is not None and user.username != username:
        user.username = username
    if full_name and user.full_name != full_name:
        user.full_name = full_name
    if user.is_blocked:
        # Qaytib keldi — "ketganlar" hisobidan chiqadi
        user.is_blocked = False
        user.blocked_at = None
    return user


def mark_blocked(user: User) -> None:
    """Botni bloklaganini belgilaydi — bayroq va sanani BIRGA.

    Ikkalasi doim birga o'zgarishi kerak: sanasiz bloklangan odam a'zolar
    dinamikasida "ketgan" bo'lib ko'rinmaydi, ya'ni grafik jimgina noto'g'ri
    bo'ladi. Shuning uchun bu yagona nuqta.
    """
    if user.is_blocked and user.blocked_at is not None:
        return
    user.is_blocked = True
    user.blocked_at = clock.now_utc()


# ─── Kun va vazifalar ────────────────────────────────────────────────────────


async def get_plan(session: AsyncSession, user_id: int, d: date_type) -> DailyPlan | None:
    return await session.scalar(
        select(DailyPlan).where(DailyPlan.user_id == user_id, DailyPlan.date == d)
    )


async def get_tasks(session: AsyncSession, user_id: int, d: date_type) -> list[Task]:
    """Kun vazifalari: avval vaqtlilar (vaqt bo'yicha), keyin vaqtsizlari.

    Tartib shu bitta joyda — digest, Mini App va bot ro'yxatlari hammasi
    shu funksiyadan o'qiydi, ya'ni kun hamma joyda bir xil ko'rinadi.
    """
    rows = await session.scalars(
        select(Task)
        .where(Task.user_id == user_id, Task.date == d)
        .order_by(
            Task.start_time.is_(None), Task.start_time, Task.sort_order, Task.id
        )
    )
    return list(rows)


async def _sync_habit_tasks(session: AsyncSession, user: User, d: date_type) -> int:
    """Kunning odat nusxalarini odatlarning JADVALIGA moslaydi.

    Ikki tomonlama: tegishli kunga nusxa yaratadi va **tegishli bo'lmagan
    kundan olib tashlaydi**. Ikkinchisisiz odatning jadvali torayganda
    (masalan «har kuni» → Du/Ch/Ju) allaqachon yaratilgan nusxa yakshanba
    rejasida qolib ketardi — ya'ni tanlangan kunlar ishlamayotgandek
    ko'rinardi.

    Ikkita himoya sharti bor va ikkalasi ham majburiy:
    - `source == HABIT` — qo'lda qo'shilgan odat (`add_habit_task`) `MANUAL`
      bo'ladi. Usiz foydalanuvchi ataylab qo'shgan ish sahifa har ochilganda
      jimgina yo'qolardi.
    - `status == PLANNED` — bajarilgan yoki o'tkazilgan ish hech qachon
      o'chmaydi, aks holda tarix soxtalashardi.

    Takror yaratmaydi: `UNIQUE(user_id, date, habit_id)` cheklovi bor, lekin
    unga tayanmasdan avval mavjudlarini o'qiymiz — xato emas, oddiy holat.
    """
    habits = list(
        await session.scalars(
            select(Habit)
            .where(Habit.user_id == user.id, Habit.is_archived.is_(False))
            .order_by(Habit.sort_order, Habit.id)
        )
    )
    if not habits:
        return 0

    existing: dict[int, Task] = {
        task.habit_id: task
        for task in await session.scalars(
            select(Task).where(
                Task.user_id == user.id,
                Task.date == d,
                Task.habit_id.is_not(None),
            )
        )
    }

    changed = 0
    for habit in habits:
        task = existing.get(habit.id)
        active = habit.is_active_on(d)

        if task is None:
            if not active:
                continue
            session.add(
                Task(
                    user_id=user.id,
                    date=d,
                    title=habit.title,
                    source=TaskSource.HABIT,
                    habit_id=habit.id,
                    points=habit.points,
                    visibility=habit.visibility,
                    sort_order=habit.sort_order,
                    start_time=habit.start_time,
                    end_time=habit.end_time,
                    status=TaskStatus.PLANNED,
                )
            )
            changed += 1
        elif (
            not active
            and task.source == TaskSource.HABIT
            and task.status == TaskStatus.PLANNED
        ):
            await session.delete(task)
            changed += 1

    if changed:
        await session.flush()
    return changed


async def open_day(
    session: AsyncSession, user: User, d: date_type, *, generate: bool = True
) -> tuple[DailyPlan, list[Task]]:
    """Kunni ochadi: `DailyPlan` yaratadi va odat nusxalarini jadvalga moslaydi.

    `generate` faqat bugun va kelajak uchun ishlaydi. O'tmish kunga odat
    qo'shish soxta tarix yaratardi — hech qachon qilmaymiz. Shu sabab
    jadvaldan chiqib qolgan nusxani tozalash ham faqat shu yerdan o'tadi.
    """
    plan = await get_plan(session, user.id, d)
    if plan is None:
        plan = DailyPlan(user_id=user.id, date=d)
        session.add(plan)
        await session.flush()

    if generate and d >= clock.today_local(user.tz):
        await _sync_habit_tasks(session, user, d)

    tasks = await get_tasks(session, user.id, d)
    await recalc_day(session, user.id, d, tasks=tasks, plan=plan)
    return plan, tasks


async def recalc_day(
    session: AsyncSession,
    user_id: int,
    d: date_type,
    *,
    tasks: list[Task] | None = None,
    plan: DailyPlan | None = None,
) -> DailyPlan:
    """`DailyPlan` dagi takrorlangan hisoblagichlarni yangilaydi.

    Har o'zgarishdan keyin chaqiriladi. Shu tufayli statistika so'rovlari
    `tasks` jadvalini umuman sanamaydi.
    """
    if plan is None:
        plan = await get_plan(session, user_id, d)
        if plan is None:
            plan = DailyPlan(user_id=user_id, date=d)
            session.add(plan)
            await session.flush()
    if tasks is None:
        tasks = await get_tasks(session, user_id, d)

    stats = scoring.summarize(tasks)
    plan.planned_count = stats["planned_count"]
    plan.done_count = stats["done_count"]
    plan.score = stats["score"]
    plan.completion_pct = stats["completion_pct"]
    plan.extra_count = stats["extra_count"]
    plan.extra_done_count = stats["extra_done_count"]
    return plan


async def add_task(
    session: AsyncSession,
    user: User,
    d: date_type,
    title: str,
    *,
    points: int = 1,
    visibility=None,
    start_time: time_type | None = None,
    end_time: time_type | None = None,
    is_extra: bool = False,
) -> Task:
    """Kunga vazifa qo'shadi.

    `is_extra` — bugungi kunga qo'shilgan ish uchun. Qarorni chaqiruvchi
    (`api/routers/days.py`) qabul qiladi, bu yer faqat saqlaydi.
    """
    title = title.strip()[:200]
    if not title:
        raise ValueError("Vazifa nomi bo'sh")
    if end_time is not None and start_time is None:
        raise ValueError("Tugash vaqti uchun boshlanish vaqti ham kerak")
    if start_time is not None and end_time is not None and end_time <= start_time:
        raise ValueError("Tugash vaqti boshlanishidan keyin bo'lishi kerak")

    last_order = await session.scalar(
        select(Task.sort_order)
        .where(Task.user_id == user.id, Task.date == d)
        .order_by(Task.sort_order.desc())
        .limit(1)
    )
    task = Task(
        user_id=user.id,
        date=d,
        title=title,
        source=TaskSource.MANUAL,
        points=max(1, min(points, 10)),
        visibility=visibility,
        sort_order=(last_order or 0) + 1,
        start_time=start_time,
        end_time=end_time,
        is_extra=is_extra,
        status=TaskStatus.PLANNED,
    )
    session.add(task)
    await session.flush()
    await recalc_day(session, user.id, d)
    return task


async def add_habit_task(
    session: AsyncSession, user: User, d: date_type, habit: Habit
) -> Task:
    """Odatni jadvalida yo'q kunga QO'LDA qo'shadi.

    `source` ataylab `MANUAL`: bu nusxani odatning jadvali emas, odam o'zi
    yaratdi. Shundan ikki natija chiqadi — `_sync_habit_tasks` uni keyingi
    ochilishda o'chirmaydi va ro'yxatda ✕ tugmasi bilan chiqadi (o'zi
    qo'shgan ishni o'zi olib tashlay oladi). `habit_id` esa saqlanadi:
    issiqlik xaritasi va statistika buni o'sha odatning kuni deb sanaydi.

    `is_extra=False` — chaqiruvchi buni faqat kelajakdagi kunga ruxsat
    beradi, ya'ni bu kechqurun beriladigan va'daning bir qismi.
    """
    last_order = await session.scalar(
        select(Task.sort_order)
        .where(Task.user_id == user.id, Task.date == d)
        .order_by(Task.sort_order.desc())
        .limit(1)
    )
    task = Task(
        user_id=user.id,
        date=d,
        title=habit.title,
        source=TaskSource.MANUAL,
        habit_id=habit.id,
        points=habit.points,
        visibility=habit.visibility,
        sort_order=(last_order or 0) + 1,
        start_time=habit.start_time,
        end_time=habit.end_time,
        is_extra=False,
        status=TaskStatus.PLANNED,
    )
    session.add(task)
    await session.flush()
    await recalc_day(session, user.id, d)
    return task


async def set_task_time(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    start_time: time_type | None,
    end_time: time_type | None,
) -> Task | None:
    """Mavjud vazifaning oralig'ini o'zgartiradi (ikkalasi ham `None` — olib tashlaydi).

    Odat nusxasiga ham ruxsat: bir kunga vaqtni surish odatning o'zini
    o'zgartirmaydi (`Habit` — shablon, `Task` — nusxa).
    """
    if end_time is not None and start_time is None:
        raise ValueError("Tugash vaqti uchun boshlanish vaqti ham kerak")
    if start_time is not None and end_time is not None and end_time <= start_time:
        raise ValueError("Tugash vaqti boshlanishidan keyin bo'lishi kerak")

    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        return None

    task.start_time = start_time
    task.end_time = end_time
    await session.flush()
    return task


async def get_task(session: AsyncSession, user_id: int, task_id: int) -> Task | None:
    """Vazifani egasini tekshirib qaytaradi. Begonasi uchun `None`."""
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        return None
    return task


async def delete_task(session: AsyncSession, user_id: int, task_id: int) -> bool:
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        return False
    d = task.date
    await session.delete(task)
    await session.flush()
    await recalc_day(session, user_id, d)
    return True


async def set_status(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    status: TaskStatus,
    *,
    reason: MissReason | None = None,
    note: str | None = None,
) -> Task | None:
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        return None

    task.status = status
    if status == TaskStatus.DONE:
        task.done_at = clock.now_utc()
        # Bajarilgan vazifada eski "sabab" qolib ketmasin
        task.miss_reason = None
        task.miss_note = None
    else:
        task.done_at = None
        if reason is not None:
            task.miss_reason = reason
        if note is not None:
            task.miss_note = note.strip()[:500] or None

    await session.flush()
    await recalc_day(session, user_id, task.date)
    return task


async def set_miss_reason(
    session: AsyncSession,
    user_id: int,
    task_id: int,
    reason: MissReason,
    note: str | None = None,
) -> Task | None:
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user_id:
        return None
    task.miss_reason = reason
    if note is not None:
        task.miss_note = note.strip()[:500] or None
    await session.flush()
    return task


async def move_task(
    session: AsyncSession, user: User, task_id: int, new_date: date_type
) -> Task | None:
    """Bajarilmagan vazifani boshqa kunga ko'chirish.

    Avtomatik ko'chirish ataylab yo'q: nima ko'chishini odam o'zi hal qilsin,
    aks holda ro'yxat cheksiz o'sib ketadi va ma'nosini yo'qotadi.
    """
    task = await session.get(Task, task_id)
    if task is None or task.user_id != user.id:
        return None
    if task.habit_id is not None:
        # Odat nusxasini ko'chirish mantiqsiz — u ertaga baribir yaratiladi.
        # Shart `source` bo'yicha emas, `habit_id` bo'yicha: qo'lda qo'shilgan
        # odat `MANUAL` bo'ladi, uni ko'chirish `UNIQUE(user, date, habit_id)`
        # ni buzib yuborardi.
        return None

    old_date = task.date
    task.date = new_date
    task.status = TaskStatus.PLANNED
    task.done_at = None
    # Kelajakka ko'chirilgan ish o'sha kunning REJASI bo'ladi; bugunga
    # ko'chirilgani esa qo'shimcha bo'lib qoladi — bugungi va'da allaqachon
    # berilgan, unga ortdan qo'shib bo'lmaydi.
    task.is_extra = new_date <= clock.today_local(user.tz)
    await session.flush()
    await recalc_day(session, user.id, old_date)
    await recalc_day(session, user.id, new_date)
    return task


async def submit_plan(session: AsyncSession, user: User, d: date_type) -> DailyPlan:
    """Rejani "kiritilgan" deb belgilaydi.

    Aynan shu fakt bo'yicha sherikka "hali reja kiritmadi" xabari ketadi,
    shuning uchun bu alohida harakat — vazifa qo'shishning o'zi yetarli emas.
    """
    plan, _ = await open_day(session, user, d)
    if plan.submitted_at is None:
        plan.submitted_at = clock.now_utc()
    await session.flush()
    return plan


# ─── Kunni yopish ────────────────────────────────────────────────────────────


async def close_day(session: AsyncSession, user: User, d: date_type) -> DailyPlan | None:
    """Yarim tundan keyin: bajarilmaganlarni `MISSED` qiladi va kunni muhrlaydi.

    Idempotent — ikkinchi marta chaqirilsa hech narsa o'zgarmaydi.
    """
    plan = await get_plan(session, user.id, d)
    if plan is None:
        return None
    if plan.closed_at is not None:
        return plan

    tasks = await get_tasks(session, user.id, d)
    for task in tasks:
        if task.status == TaskStatus.PLANNED:
            task.status = TaskStatus.MISSED

    plan.closed_at = clock.now_utc()
    await session.flush()
    await recalc_day(session, user.id, d, tasks=tasks, plan=plan)
    return plan


async def missed_tasks_without_reason(
    session: AsyncSession, user_id: int, d: date_type
) -> list[Task]:
    """Sabab so'raladigan vazifalar — faqat REJA.

    Qo'shimcha kun ichida o'z ixtiyori bilan qo'shilgan, va'da qilinmagan.
    Uni bajarmaganlik uchun hisobot so'rash odamni "qo'shmay qo'ya qolay"
    degan xulosaga olib keladi — qo'shimcha imkoniyatining o'zi o'ladi.
    """
    rows = await session.scalars(
        select(Task).where(
            Task.user_id == user_id,
            Task.date == d,
            Task.status == TaskStatus.MISSED,
            Task.miss_reason.is_(None),
            Task.is_extra.is_(False),
        )
    )
    return list(rows)


async def has_submitted_plan_for(
    session: AsyncSession, user_id: int, d: date_type
) -> bool:
    plan = await get_plan(session, user_id, d)
    return plan is not None and plan.submitted_at is not None


async def recent_plans(
    session: AsyncSession, user_id: int, days: int = 30, until: date_type | None = None
) -> list[DailyPlan]:
    until = until or clock.today_local()
    since = until - timedelta(days=days - 1)
    rows = await session.scalars(
        select(DailyPlan)
        .where(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= since,
            DailyPlan.date <= until,
        )
        .order_by(DailyPlan.date)
    )
    return list(rows)
