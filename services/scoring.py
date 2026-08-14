"""Ball va bajarilish foizi.

Formula ataylab shu bitta faylda: raqobat elementi keyin o'zgarishi ehtimoli
yuqori (masalan streak bonusi qo'shilishi), o'shanda faqat shu fayl o'zgaradi.

Qoidalar:
- Ball = bajarilgan vazifalarning `points` yig'indisi.
- `SKIPPED` (ataylab o'tkazilgan) na ballga, na foizga kiradi — maxrajdan
  ham chiqadi. Kasal bo'lgan kun natijani buzmasligi kerak.
- `PRIVATE` vazifa o'z statistikangizga kiradi, sherikning ko'rinishiga esa
  umuman chiqmaydi (`stats.py` da filtrlanadi).
"""

from __future__ import annotations

from collections.abc import Iterable

from shared.models import Task, TaskStatus


def counted(tasks: Iterable[Task]) -> list[Task]:
    """Hisobga kiradigan vazifalar — SKIPPED tashlanadi."""
    return [t for t in tasks if t.status != TaskStatus.SKIPPED]


def done_tasks(tasks: Iterable[Task]) -> list[Task]:
    return [t for t in tasks if t.status == TaskStatus.DONE]


def day_score(tasks: Iterable[Task]) -> int:
    return sum(t.points for t in done_tasks(tasks))


def max_score(tasks: Iterable[Task]) -> int:
    """Shu kun uchun mumkin bo'lgan eng yuqori ball."""
    return sum(t.points for t in counted(tasks))


def completion_pct(tasks: Iterable[Task]) -> int:
    """0..100. Vazifa soni bo'yicha, ball bo'yicha emas.

    Nega soni bo'yicha: "5 tadan 4 tasini qildim" degan gap odamga
    "12 balldan 9 ball" dan ko'ra tushunarliroq.
    """
    items = counted(tasks)
    if not items:
        return 0
    return round(len(done_tasks(items)) * 100 / len(items))


def summarize(tasks: Iterable[Task]) -> dict[str, int]:
    items = counted(tasks)
    done = done_tasks(items)
    return {
        "planned_count": len(items),
        "done_count": len(done),
        "score": sum(t.points for t in done),
        "max_score": sum(t.points for t in items),
        "completion_pct": round(len(done) * 100 / len(items)) if items else 0,
    }
