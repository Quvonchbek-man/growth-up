"""Vaqt bilan ishlashning yagona nuqtasi.

Ikki qoida butun loyiha bo'ylab amal qiladi:

1. `datetime` maydonlari — **UTC**, timezone-aware.
2. `date` maydonlari — foydalanuvchining **mahalliy** sanasi (Asia/Tashkent).

Bu ikkisi aralashsa, streak yarim tunda noto'g'ri uziladi va buni bir-ikki
oydan keyin, ya'ni juda kech sezasiz.

Shuning uchun "hozir" degan tushuncha faqat shu moduldan olinadi. Yon foyda:
`DEV_TIME_SHIFT_MINUTES` bilan vaqtni sun'iy siljitib, kun yopilishi va
eslatmalarni yarim tungacha kutmasdan sinash mumkin.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from shared.config import settings

UTC = timezone.utc


def tz_of(name: str | None = None) -> ZoneInfo:
    """Nomi bo'yicha vaqt mintaqasi; noto'g'ri bo'lsa loyiha standarti."""
    try:
        return ZoneInfo(name or settings.timezone)
    except Exception:
        return ZoneInfo(settings.timezone)


def is_valid_tz(name: str) -> bool:
    """Noto'g'ri mintaqa nomi butun eslatma siklini buzadi — saqlashdan oldin tekshiramiz."""
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def now_utc() -> datetime:
    """Hozirgi UTC vaqti (dev siljishi hisobga olingan holda)."""
    real = datetime.now(UTC)
    if settings.dev_time_shift_minutes:
        return real + timedelta(minutes=settings.dev_time_shift_minutes)
    return real


def now_local(tz_name: str | None = None) -> datetime:
    """Foydalanuvchi mintaqasidagi hozirgi vaqt."""
    return now_utc().astimezone(tz_of(tz_name))


def today_local(tz_name: str | None = None) -> date:
    """Foydalanuvchi uchun "bugun" qaysi sana."""
    return now_local(tz_name).date()


def tomorrow_local(tz_name: str | None = None) -> date:
    return today_local(tz_name) + timedelta(days=1)


def local_date_of(dt: datetime, tz_name: str | None = None) -> date:
    """UTC `datetime` qaysi mahalliy sanaga tushishini aniqlaydi."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz_of(tz_name)).date()


def local_time_of(dt: datetime, tz_name: str | None = None) -> time:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz_of(tz_name)).time()


def is_due(target: time, tz_name: str | None = None, window_minutes: int = 10) -> bool:
    """Mahalliy vaqt `target` dan o'tdimi, lekin oyna ichidami?

    Eslatma sikli har daqiqada ishlaydi, lekin kompyuter uxlab qolishi yoki
    bot restart bo'lishi mumkin. Oyna kechikkan eslatmani ham yuborishga
    imkon beradi; takror yuborilmasligini `ReminderLog` kafolatlaydi.

    Yarim tundan keyingi vaqtlar (00:05 kabi) uchun ham to'g'ri ishlaydi:
    solishtirishni sana boshidan hisoblangan daqiqalarda qilamiz.
    """
    now = now_local(tz_name).time()
    now_m = now.hour * 60 + now.minute
    target_m = target.hour * 60 + target.minute
    return target_m <= now_m < target_m + window_minutes


def shift_time(t: time, minutes: int) -> time:
    """Vaqtni `minutes` ga suradi (manfiy — orqaga).

    **Sana chegarasidan o'tmaydi:** `00:05` dan 10 daqiqa ayirilsa `23:55`
    emas, `00:00` chiqadi. Aks holda yarim tunga yaqin vazifaning eslatmasi
    kechagi kunga tushib ketardi va `is_due` uni o'sha kuni umuman ko'rmasdi.
    """
    total = t.hour * 60 + t.minute + minutes
    total = max(0, min(total, 23 * 60 + 59))
    return time(total // 60, total % 60)


def fmt_range(start: time | None, end: time | None) -> str:
    """`"07:00–07:45"` · `"07:00"` · `""` — xabarlar uchun yagona ko'rinish."""
    if start is None:
        return ""
    if end is None:
        return f"{start:%H:%M}"
    return f"{start:%H:%M}–{end:%H:%M}"


def week_start(d: date) -> date:
    """Haftaning boshi — dushanba."""
    return d - timedelta(days=d.weekday())


def iso_date(d: date) -> str:
    return d.isoformat()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)
