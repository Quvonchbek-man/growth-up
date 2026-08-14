"""30 kunlik namunaviy ma'lumot yaratadi.

    python -m scripts.seed_demo

Nega kerak: grafiklar bo'sh ekranda qurilmaydi. Real ma'lumot bir oydan
keyin paydo bo'ladi, statistika sahifasi esa bugun yozilishi kerak.

Ma'lumot ataylab "notekis" qilingan — ichida topsa bo'ladigan naqshlar bor:
  • dam olish kunlari bajarilish pasayadi
  • "Sport" dushanba kunlari deyarli hech qachon bajarilmaydi (heatmap'da ko'rinadi)
  • sabablar orasida "vaqt yetmadi" ustun (sabab grafigi ma'noli chiqadi)
  • bir necha kun umuman reja yo'q (streak uzilishi ko'rinadi)

DIQQAT: skript maqsadli foydalanuvchi va namunaviy sherikning MAVJUD
ma'lumotlarini o'chirib, qaytadan yozadi.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import time, timedelta

from sqlalchemy import delete, select

from services import groups, planning, streak
from shared import clock
from shared.config import settings
from shared.db import create_all, engine, session_factory
from shared.models import (
    DailyPlan,
    Habit,
    MissReason,
    Membership,
    Nudge,
    ReminderLog,
    ScheduleKind,
    StreakState,
    Task,
    TaskSource,
    TaskStatus,
    User,
    Visibility,
)

# Haqiqiy Telegram ID'lari bu diapazonga chiqmaydi — to'qnashuv bo'lmaydi
DEMO_PARTNER_ID = 900_000_000_001
DAYS = 30
SEED = 20260813  # takrorlanadigan natija uchun

# Vaqt ataylab hammasiga qo'yilmagan: kun jadval bo'lib ham, ro'yxat bo'lib
# ham ko'rinishi kerak — ikkala holat ham namunada bo'lsin.
MY_HABITS = [
    # (nom, ikonka, ball, ko'rinish, jadval, bajarilish ehtimoli, boshlanish, tugash)
    ("Ertalabki sport", "🏃", 3, Visibility.PUBLIC, ScheduleKind.DAILY, 0.62, time(7, 0), time(7, 45)),
    ("30 daqiqa kitob", "📚", 2, Visibility.PUBLIC, ScheduleKind.DAILY, 0.80, time(21, 30), time(22, 0)),
    ("Ingliz tili", "🇬🇧", 2, Visibility.PUBLIC, ScheduleKind.WEEKDAYS, 0.70, time(19, 0), time(20, 0)),
    ("2 litr suv", "💧", 1, Visibility.PUBLIC, ScheduleKind.DAILY, 0.88, None, None),
    ("Erta yotish", "🌙", 2, Visibility.STATS_ONLY, ScheduleKind.DAILY, 0.55, time(23, 0), None),
    ("Meditatsiya", "🧘", 1, Visibility.PRIVATE, ScheduleKind.DAILY, 0.45, None, None),
]

PARTNER_HABITS = [
    ("Yugurish", "🏃", 3, Visibility.PUBLIC, ScheduleKind.WEEKDAYS, 0.58, time(6, 30), time(7, 15)),
    ("Kitob o'qish", "📚", 2, Visibility.PUBLIC, ScheduleKind.DAILY, 0.72, None, None),
    ("Kurs darslari", "💻", 3, Visibility.PUBLIC, ScheduleKind.DAILY, 0.66, time(20, 0), time(21, 30)),
    ("Suv rejimi", "💧", 1, Visibility.PUBLIC, ScheduleKind.DAILY, 0.90, None, None),
]

MANUAL_POOL = [
    "Hisobotni tugatish",
    "Onamga qo'ng'iroq",
    "Xarid ro'yxati",
    "Hujjatlarni tartiblash",
    "Do'st bilan uchrashuv",
    "Uy tozalash",
    "Byudjetni yangilash",
]

# Ertalab kutilmaganda chiqadigan ishlar — «Qo'shimcha» bo'limi uchun
EXTRA_POOL = [
    "Ustozga qo'ng'iroq",
    "Shoshilinch xat",
    "Dorixonaga kirish",
    "Mashinani yuvdirish",
    "Hamkasbga yordam",
]

# Sabablar taqsimoti — "vaqt yetmadi" ataylab ustun
REASON_WEIGHTS = [
    (MissReason.NO_TIME, 40),
    (MissReason.TIRED, 30),
    (MissReason.FORGOT, 20),
    (MissReason.NOT_IMPORTANT, 10),
]


def _pick_reason(rnd: random.Random) -> MissReason:
    total = sum(w for _, w in REASON_WEIGHTS)
    roll = rnd.randint(1, total)
    acc = 0
    for reason, weight in REASON_WEIGHTS:
        acc += weight
        if roll <= acc:
            return reason
    return MissReason.OTHER


async def _wipe(session, user_ids: list[int]) -> None:
    # Tartib muhim: avval bog'liq yozuvlar, keyin odatlar
    for table in (Task, DailyPlan, ReminderLog, StreakState, Habit):
        await session.execute(delete(table).where(table.user_id.in_(user_ids)))
    await session.execute(delete(Nudge).where(Nudge.from_user_id.in_(user_ids)))
    await session.execute(delete(Nudge).where(Nudge.to_user_id.in_(user_ids)))
    await session.flush()


async def _make_habits(session, user: User, specs) -> list[tuple[Habit, float]]:
    out = []
    for order, (title, icon, points, vis, kind, prob, start, end) in enumerate(specs):
        habit = Habit(
            user_id=user.id,
            title=title,
            icon=icon,
            points=points,
            visibility=vis,
            schedule_kind=kind,
            # WEEKDAYS bo'lsa dushanba–juma
            weekdays_mask=0b0011111 if kind == ScheduleKind.WEEKDAYS else 0b1111111,
            start_time=start,
            end_time=end,
            sort_order=order,
        )
        session.add(habit)
        out.append((habit, prob))
    await session.flush()
    return out


async def _fill_history(session, user: User, habits, rnd: random.Random) -> None:
    today = clock.today_local(user.tz)
    start = today - timedelta(days=DAYS - 1)

    # Reja umuman yozilmagan kunlar — streak uzilishi ko'rinishi uchun
    skipped_days = {start + timedelta(days=n) for n in rnd.sample(range(2, DAYS - 2), 3)}

    d = start
    while d <= today:
        if d in skipped_days:
            d += timedelta(days=1)
            continue

        is_weekend = d.weekday() >= 5
        mood = rnd.uniform(0.82, 1.18)  # kunning "kayfiyati"

        created: list[Task] = []
        for habit, prob in habits:
            if not habit.is_active_on(d):
                continue

            p = prob * mood
            if is_weekend:
                p *= 0.80
            # Naqsh: sport dushanba kunlari deyarli yo'q
            if habit.title.startswith(("Ertalabki sport", "Yugurish")) and d.weekday() == 0:
                p *= 0.25

            done = rnd.random() < min(p, 0.97)
            task = Task(
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
                status=TaskStatus.DONE if done else TaskStatus.MISSED,
            )
            if done:
                task.done_at = clock.now_utc() - timedelta(days=(today - d).days)
            else:
                # Ba'zilarida sabab yo'q — real hayotda ham hamma javob bermaydi
                if rnd.random() < 0.75:
                    task.miss_reason = _pick_reason(rnd)
            session.add(task)
            created.append(task)

        # Qo'lda kiritilgan vazifalar
        for _ in range(rnd.choice([0, 1, 1, 2])):
            done = rnd.random() < 0.68
            task = Task(
                user_id=user.id,
                date=d,
                title=rnd.choice(MANUAL_POOL),
                source=TaskSource.MANUAL,
                points=1,
                status=TaskStatus.DONE if done else TaskStatus.MISSED,
            )
            if done:
                task.done_at = clock.now_utc() - timedelta(days=(today - d).days)
            elif rnd.random() < 0.7:
                task.miss_reason = _pick_reason(rnd)
            session.add(task)
            created.append(task)

        # Kun ichida chiqib qolgan qo'shimcha ishlar. Hisobga kirmaydi —
        # namunada aynan shu ko'rinishi kerak: bajarilgan, lekin foizni
        # ko'tarmagan qatorlar.
        for _ in range(rnd.choice([0, 0, 1, 1, 2])):
            qoshimcha = Task(
                user_id=user.id,
                date=d,
                title=rnd.choice(EXTRA_POOL),
                source=TaskSource.MANUAL,
                points=1,
                is_extra=True,
                status=TaskStatus.DONE if rnd.random() < 0.75 else TaskStatus.MISSED,
            )
            if qoshimcha.status == TaskStatus.DONE:
                qoshimcha.done_at = clock.now_utc() - timedelta(days=(today - d).days)
            session.add(qoshimcha)
            created.append(qoshimcha)

        await session.flush()

        plan = DailyPlan(user_id=user.id, date=d)
        # Reja kechqurun oldindan kiritilgan deb hisoblaymiz
        plan.submitted_at = clock.now_utc() - timedelta(days=(today - d).days + 1)
        if d < today:
            plan.closed_at = clock.now_utc() - timedelta(days=(today - d).days - 1)
        session.add(plan)
        await session.flush()
        await planning.recalc_day(session, user.id, d, tasks=created, plan=plan)

        d += timedelta(days=1)

    # Bugungi kun hali tugamagan — bir qismi bajarilmagan holatga qaytariladi
    todays = await planning.get_tasks(session, user.id, today)
    for task in todays:
        if task.status == TaskStatus.MISSED:
            task.status = TaskStatus.PLANNED
            task.miss_reason = None
    await session.flush()
    await planning.recalc_day(session, user.id, today)


async def main() -> None:
    await create_all()
    rnd = random.Random(SEED)

    my_id = settings.super_admin_ids[0] if settings.super_admin_ids else DEMO_PARTNER_ID - 1
    if "--id" in sys.argv:
        my_id = int(sys.argv[sys.argv.index("--id") + 1])

    async with session_factory() as session:
        me = await planning.get_or_create_user(session, my_id, full_name="Men")
        partner = await planning.get_or_create_user(
            session, DEMO_PARTNER_ID, username="sherik_demo", full_name="Sherik (namuna)"
        )
        # Namunaviy sherik — mavjud bo'lmagan Telegram hisobi.
        # Bloklangan deb belgilaymiz, aks holda bot unga xabar yuborishga
        # urinib, har daqiqada loglarni xato bilan to'ldiradi.
        partner.is_blocked = True

        print(f"Foydalanuvchi: {my_id}, namunaviy sherik: {DEMO_PARTNER_ID}")
        await _wipe(session, [me.id, partner.id])

        group = await groups.ensure_group(session, me, name="Biz ikkimiz")
        exists = await session.scalar(
            select(Membership).where(
                Membership.user_id == partner.id, Membership.group_id == group.id
            )
        )
        if exists is None:
            session.add(Membership(user_id=partner.id, group_id=group.id))
        await session.flush()

        my_habits = await _make_habits(session, me, MY_HABITS)
        partner_habits = await _make_habits(session, partner, PARTNER_HABITS)

        await _fill_history(session, me, my_habits, rnd)
        await _fill_history(session, partner, partner_habits, rnd)

        my_streak = await streak.recalc(session, me)
        partner_streak = await streak.recalc(session, partner)

        await session.commit()

        print(f"  {DAYS} kunlik tarix yozildi")
        print(f"  Taklif kodi: {group.invite_code}")
        print(f"  Sizning streak: {my_streak.current_len} (eng yaxshi {my_streak.best_len})")
        print(f"  Sherik streak:  {partner_streak.current_len}")

    await engine.dispose()
    print("\nTayyor. `python run.py` va Mini App'ni oching.")


if __name__ == "__main__":
    asyncio.run(main())
