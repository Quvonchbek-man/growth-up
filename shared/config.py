"""Loyiha sozlamalari — .env faylidan o'qiladi.

Bot ham, API ham shu bitta manbadan sozlanadi.
Naqsh `shop-bot\\shared\\config.py` dan olingan.
"""

from __future__ import annotations

from datetime import time
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_hhmm(value: str, fallback: time) -> time:
    """`"21:00"` -> `time(21, 0)`. Noto'g'ri qiymatda standart qiymat qaytadi."""
    try:
        hh, mm = value.split(":", 1)
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return fallback


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Majburiy ---
    # Ataylab standart qiymatli: `seed_demo` va boshqa skriptlar tokensiz ham
    # ishlashi kerak. Yo'qligi bot ishga tushganda tekshiriladi (run.py).
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    # Ataylab satr: pydantic-settings ro'yxat turini avval JSON deb o'qishga
    # urinadi va "1,2,3" ko'rinishida xato beradi. Parsingni o'zimiz qilamiz.
    super_admin_ids_raw: str = Field(default="", alias="SUPER_ADMIN_IDS")

    # --- Mini App ---
    webapp_url: str = Field(default="", alias="WEBAPP_URL")

    # --- Server ---
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins_raw: str = Field(default="", alias="CORS_ORIGINS")

    # --- Baza ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/growth.db", alias="DATABASE_URL"
    )

    # --- Vaqt ---
    # Bazada `datetime` UTC'da, `date` esa foydalanuvchining MAHALLIY sanasi
    # sifatida saqlanadi. Ikkisini aralashtirish streak'ni buzadi.
    timezone: str = Field(default="Asia/Tashkent", alias="TIMEZONE")

    # --- Standart eslatma vaqtlari (foydalanuvchi o'zgartira oladi) ---
    default_plan_reminder: str = Field(default="21:00", alias="DEFAULT_PLAN_REMINDER")
    default_digest: str = Field(default="09:00", alias="DEFAULT_DIGEST")
    # Sherik ertangi rejani kiritmasa, boshqasiga shu vaqtda xabar ketadi
    nag_partner_at: str = Field(default="22:30", alias="NAG_PARTNER_AT")
    # Kun yopilishi va sabab so'rash (mahalliy vaqt)
    day_close_at: str = Field(default="00:05", alias="DAY_CLOSE_AT")
    ask_reason_at: str = Field(default="00:10", alias="ASK_REASON_AT")
    # Vaqti belgilangan vazifa boshlanishidan necha daqiqa oldin eslatiladi.
    # Bu — yangi foydalanuvchi uchun standart; keyin har kim o'zi sozlaydi.
    # 0 — bunday eslatmalar o'chirilgan.
    task_reminder_lead_min: int = Field(default=10, alias="TASK_REMINDER_LEAD_MIN")

    # --- O'yin qoidalari ---
    # Kun "muvaffaqiyatli" hisoblanishi (streak uzilmasligi) uchun kerakli foiz.
    # 100 — juda qattiq, odam bir kunda tashlab yuboradi. 60 — real.
    streak_success_pct: int = Field(default=60, alias="STREAK_SUCCESS_PCT")
    # Bir kunda bitta odamga yuborish mumkin bo'lgan qo'l turtkilari soni.
    # Cheklovsiz qoldirilsa turtki bezorilikka aylanadi.
    max_nudges_per_day: int = Field(default=3, alias="MAX_NUDGES_PER_DAY")

    # --- Ishlab chiqish ---
    check_init_data: bool = Field(default=True, alias="CHECK_INIT_DATA")
    dev_mock_user_id: int = Field(default=0, alias="DEV_MOCK_USER_ID")
    dev_time_shift_minutes: int = Field(default=0, alias="DEV_TIME_SHIFT_MINUTES")
    reminder_tick_seconds: int = Field(default=60, alias="REMINDER_TICK_SECONDS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ─── Hosilaviy qiymatlar ─────────────────────────────────────────────────

    @property
    def super_admin_ids(self) -> list[int]:
        """`SUPER_ADMIN_IDS=1,2,3` -> [1, 2, 3]. Noto'g'ri qiymatlar tashlanadi."""
        ids: list[int] = []
        for part in self.super_admin_ids_raw.replace(" ", "").split(","):
            if not part:
                continue
            try:
                ids.append(int(part))
            except ValueError:
                continue
        return ids

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def plan_reminder_time(self) -> time:
        return _parse_hhmm(self.default_plan_reminder, time(21, 0))

    @property
    def digest_time(self) -> time:
        return _parse_hhmm(self.default_digest, time(9, 0))

    @property
    def nag_time(self) -> time:
        return _parse_hhmm(self.nag_partner_at, time(22, 30))

    @property
    def day_close_time(self) -> time:
        return _parse_hhmm(self.day_close_at, time(0, 5))

    @property
    def ask_reason_time(self) -> time:
        return _parse_hhmm(self.ask_reason_at, time(0, 10))

    @property
    def web_dist_dir(self) -> Path:
        """Vite qurgan statik fayllar. Mavjud bo'lsa API o'zi tarqatadi."""
        return BASE_DIR / "web" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
