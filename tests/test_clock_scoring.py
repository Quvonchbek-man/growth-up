"""Vaqt va ball formulasi — butun loyihaning poydevori.

Bu yerda xato bo'lsa, streak yarim tunda noto'g'ri uziladi yoki reyting
yolg'on gapiradi, lekin hech qanday xato xabari chiqmaydi.
"""

from __future__ import annotations

from datetime import date, time

import pytest

from services import scoring
from shared import clock
from shared.models import Task, TaskStatus


def _task(status: TaskStatus, points: int = 1) -> Task:
    return Task(title="t", points=points, status=status)


# ─── clock ───────────────────────────────────────────────────────────────────


def test_week_start_dushanba():
    # 2026-08-14 — juma
    assert clock.week_start(date(2026, 8, 14)) == date(2026, 8, 10)
    # Dushanbaning o'zi o'zgarmaydi
    assert clock.week_start(date(2026, 8, 10)) == date(2026, 8, 10)
    # Yakshanba — o'sha haftaning oxiri, oldingi dushanbaga tushadi
    assert clock.week_start(date(2026, 8, 16)) == date(2026, 8, 10)


def test_is_due_oyna(monkeypatch):
    """Eslatma o'z vaqtida va kechikkanda ketadi, lekin oynadan keyin yo'q."""

    def at(hh: int, mm: int):
        monkeypatch.setattr(
            clock, "now_local", lambda tz_name=None: __import__("datetime").datetime(
                2026, 8, 14, hh, mm, tzinfo=clock.UTC
            )
        )

    target = time(21, 0)

    at(20, 59)
    assert clock.is_due(target) is False, "vaqtidan oldin yubormaydi"
    at(21, 0)
    assert clock.is_due(target) is True, "aniq vaqtida yuboradi"
    at(21, 9)
    assert clock.is_due(target) is True, "10 daqiqalik oyna ichida hali ham yuboradi"
    at(21, 10)
    assert clock.is_due(target) is False, "oynadan keyin yubormaydi"


def test_is_due_yarim_tundan_keyin(monkeypatch):
    """00:05 kabi vaqtlar ham ishlashi kerak — kun yopilishi shunga bog'liq."""
    import datetime as dt

    monkeypatch.setattr(
        clock, "now_local", lambda tz_name=None: dt.datetime(2026, 8, 14, 0, 6, tzinfo=clock.UTC)
    )
    assert clock.is_due(time(0, 5)) is True
    assert clock.is_due(time(23, 55)) is False


def test_is_valid_tz():
    assert clock.is_valid_tz("Asia/Tashkent") is True
    assert clock.is_valid_tz("Mars/Olympus") is False


# ─── scoring ─────────────────────────────────────────────────────────────────


def test_ball_bajarilganlardan_yigiladi():
    tasks = [
        _task(TaskStatus.DONE, 3),
        _task(TaskStatus.DONE, 2),
        _task(TaskStatus.MISSED, 5),
        _task(TaskStatus.PLANNED, 4),
    ]
    assert scoring.day_score(tasks) == 5
    assert scoring.max_score(tasks) == 14


def test_foiz_soni_boyicha_hisoblanadi():
    """Ball emas, SON bo'yicha — 1 ballik 2 ta ish 10 ballik 1 tadan ustun."""
    tasks = [_task(TaskStatus.DONE, 1), _task(TaskStatus.DONE, 1), _task(TaskStatus.MISSED, 10)]
    assert scoring.completion_pct(tasks) == 67


def test_skipped_maxrajdan_ham_chiqadi():
    """Kasal bo'lgan kun natijani buzmasligi kerak."""
    tasks = [_task(TaskStatus.DONE), _task(TaskStatus.SKIPPED), _task(TaskStatus.SKIPPED)]
    assert scoring.completion_pct(tasks) == 100
    assert scoring.max_score(tasks) == 1

    summary = scoring.summarize(tasks)
    assert summary["planned_count"] == 1
    assert summary["done_count"] == 1


def test_bosh_kun_nolga_bolinmaydi():
    assert scoring.completion_pct([]) == 0
    assert scoring.summarize([])["completion_pct"] == 0


@pytest.mark.parametrize(
    "done,total,kutilgan",
    [(0, 3, 0), (1, 3, 33), (2, 3, 67), (3, 3, 100)],
)
def test_foiz_yaxlitlash(done, total, kutilgan):
    tasks = [_task(TaskStatus.DONE) for _ in range(done)]
    tasks += [_task(TaskStatus.MISSED) for _ in range(total - done)]
    assert scoring.completion_pct(tasks) == kutilgan
