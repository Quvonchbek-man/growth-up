# Duo Growth — kod xaritasi

> **Claude uchun:** yangi sessiyada kod bo'ylab qidiruv qilishdan oldin shu
> faylni o'qi. Bu yerda javob bo'lsa — `grep`/`find` qilma.
> **Kod o'zgarganda shu faylni ham yangila** (fayl qo'shilsa/o'chsa, endpoint
> yoki servis funksiyasi o'zgarsa, qaror qabul qilinsa). Qator raqamlari
> taxminiy — ular bo'yicha `offset` bilan o'qish mumkin, lekin tekshirib ol.
>
> Oxirgi yangilangan: 2026-08-14 (odatlar ajratildi, jamoadan chiqish) · Faza 1 tugagan

---

## 1. Nima bu

Telegram Mini App + bot: 2–10 kishi shaxsiy rivojlanish rejalarini birga
olib boradi. **Accountability ilovasi, kontent ilovasi emas** — butun qiymat
"sherigim ko'rib turibdi" mexanizmida. Kontent/kurs moduli ataylab yo'q.

Batafsil foydalanuvchi hujjati: [README.md](README.md) (ishga tushirish,
`.env`, dev buyruqlar, o'yin qoidalari). Bu fayl — **kod tuzilishi**.

## 2. Umumiy arxitektura

```
                 run.py  (bitta process, 3 ta vazifa)
                   │
      ┌────────────┼────────────────┐
      │            │                │
   bot/         api/          services/scheduler.py
 (aiogram)   (FastAPI)          (eslatma sikli)
      │            │                │
      └────────────┴───► services/ ◄┘      ← BUTUN biznes-logika shu yerda
                            │
                         shared/  (config, db, models, clock)
                            │
                        SQLite  data/growth.db
```

- **Qoida:** bot ham, API ham o'zi SQL yozmaydi — `services/` ni chaqiradi.
  Yangi logika `services/` ga tushadi, aks holda ikki joyda ikki xil bo'ladi.
- Frontend (`web/`, React+Vite) qurilib `web/dist` ga tushadi va **o'sha
  FastAPI serveri** tarqatadi (bitta port, bitta tunnel).

## 3. Papkalar

| Papka | Nima | Qator |
|---|---|---|
| `shared/` | config, baza, modellar, vaqt | ~780 |
| `services/` | biznes-logika (o'zak) | ~1400 |
| `api/` | FastAPI REST + initData auth | ~730 |
| `bot/` | aiogram: eslatma, ✅ tugma, turtki | ~790 |
| `web/src/` | React Mini App | ~1900 |
| `scripts/` | `init_db`, `seed_demo` | ~300 |
| `tests/` | pytest to'plami — 158 ta test | ~900 |

## 4. Fayllar — nima uchun javobgar

### shared/ — poydevor

| Fayl | Mazmuni |
|---|---|
| [models.py](shared/models.py) | **11 jadval + 9 sanoq.** Enumlar `:73-140`, `User:146`, `Group:183`, `Membership:201`, `Habit:223`, `Task:260`, `DailyPlan:320`, `StreakState:350`, `Nudge:369`, `Reaction:390`, `ReminderLog:409`, Faza 2: `Goal:436`, `JournalEntry:452` |
| [config.py](shared/config.py) | `Settings` pydantic (`:28`), barcha `.env` kalitlari, `get_settings()` lru_cache (`:136`) |
| [clock.py](shared/clock.py) | "Hozir" tushunchasining **yagona manbayi**: `now_utc`, `today_local`, `is_due` (`:78`), `week_start` |
| [db.py](shared/db.py) | async engine, `session_factory`, `create_all()`. **SQLite PRAGMA'lari `:48`** — WAL + `busy_timeout=5s`: usiz bot, API va eslatma sikli bir vaqtda yozganda `database is locked` chiqadi |

### services/ — biznes-logika

| Fayl | Asosiy funksiyalar |
|---|---|
| [planning.py](services/planning.py) 376q | `get_or_create_user:32`, `_generate_habit_tasks:80` (odatdan kunlik vazifa), `open_day:132`, `recalc_day:154`, `add_task:184`, `set_status:230`, `set_miss_reason:261`, `move_task:278`, `submit_plan:303`, `close_day:319` |
| [stats.py](services/stats.py) 312q | **Maxfiylik shu yerda qo'llanadi:** `visible_to_partner:54`, `serialize_task:58`. Yana: `day_view:79`, `partner_cards:98`, `daily_series:125`, `reason_breakdown:166`, `habit_matrix:202`, `leaderboard:255`, `week_leaderboard:309` |
| [notify.py](services/notify.py) 310q | Barcha Telegram xabarlari: `safe_send:43` (blok/xatoni yutadi), `already_sent/mark_sent:72,85` (idempotentlik), `send_plan_reminder:95`, `send_digest:108`, `nag_partners_about:133`, `close_and_summarize:164`, `ask_reasons:199`, `send_nudge:248`, `notify_removed:278`, `notify_left:290` (chiqqanda qolganlarga + chiquvchining o'ziga) |
| [scheduler.py](services/scheduler.py) | `fire_due_for:32` — 5 qadam **shu tartibda**: kun_yopish → sabab → ertalabki → kechki → sherikka. `tick:64` (har foydalanuvchi alohida sessiya), `run_forever:109` |
| [scoring.py](services/scoring.py) | Ball formulasi ajratib qo'yilgan: `day_score:30`, `completion_pct:39`, `summarize:51` |
| [streak.py](services/streak.py) | `_is_success:33` (`STREAK_SUCCESS_PCT` shu yerda), `recalc:39` |
| [groups.py](services/groups.py) 250q | Taklif kodi, `ensure_group:47`, `join_by_code:84`, `partners:130`. **Sardor huquqlari:** `is_owner:153`, `require_owner:157`, `rename:167`, `reset_invite_code:176`, `leave:183`, `remove_member:223`. Xatolar: `TeamError:76`, `NotOwnerError:80` (API 403 ga aylantiradi) |

### api/ — REST (barcha yo'llar `/api` prefiksi bilan)

| Metod + yo'l | Fayl:qator |
|---|---|
| `GET /api/health` | [main.py:45](api/main.py) |
| `GET /me` · `PATCH /me` | [user_settings.py:50,62](api/routers/user_settings.py) — javobda `group` bloki ham bor (nom, `partner_count`, `is_owner`, `invite_code` — kod faqat sardorga) |
| `GET /day/{day}` | [days.py:28](api/routers/days.py) — `day` = `today`/`tomorrow`/ISO sana |
| `POST /day/{day}/tasks` | days.py:47 |
| `POST /day/{day}/submit` | days.py:69 |
| `PATCH /tasks/{id}` · `POST /tasks/{id}/move` · `DELETE /tasks/{id}` | days.py:85,105,121 |
| `GET/POST /habits` · `PUT/DELETE /habits/{id}` | [habits.py:32,45,75,114](api/routers/habits.py) (DELETE = arxivlash) |
| `GET /team` · `POST /team/join` · `/team/nudge` · `/team/react` | [team.py:37,158,177,210](api/routers/team.py) |
| `POST /team/leave` | team.py:133 — o'z ixtiyori bilan chiqish (sardor ham). Yolg'iz bo'lsa 400 |
| **Sardor:** `PATCH /team` (nom) · `POST /team/code` (kodni yangilash) · `DELETE /team/members/{id}` | team.py:79,94,108 — sardor bo'lmasa 403 |
| `GET /stats?days=30` | [stats.py:16](api/routers/stats.py) |

- [auth.py](api/auth.py): `parse_init_data:42` (HMAC imzo), `current_user:100`
  Depends. `CHECK_INIT_DATA=false` bo'lsa `DEV_MOCK_USER_ID` nomidan ishlaydi.
- [main.py](api/main.py): CORS, `_mount_web:57` — `web/dist` bo'lmasa 503 va
  tushuntirish qaytaradi. Docs: `/api/docs`.
- [schemas.py](api/schemas.py): pydantic so'rov modellari (8 ta).

### bot/ — aiogram

| Buyruq/hodisa | Handler |
|---|---|
| `/start`, `/start KOD` (deep link) | [start.py:55,37](bot/handlers/start.py) |
| `/help`, `/jamoa`\|`/team`, `/qoshil`\|`/join`, `/bugun`\|`/today` | start.py:75,82,107,122 |
| ✅ tugma (TaskCb) | [tasks.py:55](bot/handlers/tasks.py) → `_rerender:22` |
| Sabab tanlash (ReasonCb) | tasks.py:73 |
| «Turtki ber» (NudgeCb) | [nudge.py:17](bot/handlers/nudge.py) |
| `/sinov`, `/vaqt` — **faqat admin** | [dev.py:22,42](bot/handlers/dev.py) |

- [callbacks.py](bot/callbacks.py): `TaskCb/ReasonCb/NudgeCb/DayCb` CallbackData.
- [keyboards.py](bot/keyboards.py): `open_app:26` (WebApp tugmasi), `day_tasks:52`,
  `reason_choices:77`.
- [locales/uz.py](bot/locales/uz.py): **barcha matnlar shu yerda** (157 qator).
  Yangi matn qo'shilsa shu faylga.
- `middlewares/`: `db` (sessiya), `user` (`get_or_create_user` + `is_admin`),
  `throttle`.

### web/src/ — React Mini App

| Fayl | Mazmuni |
|---|---|
| [App.tsx](web/src/App.tsx) | 5 ta tab: `today`/`tomorrow`/`team`/`stats`/`habits`. **`settings` tab emas** — har sahifada suzib turgan ⚙️ (`.iconbtn--float`) ochadigan yaxlit oyna; yopilganda `lastTab` orqali kelgan tabga qaytadi |
| [api.ts](web/src/api.ts) | Barcha TS tiplari + `api` obyekti (oxirida) — endpoint o'zgarsa shu yer |
| [telegram.ts](web/src/telegram.ts) | `tg`, `initTelegram`, `haptic`, `alertUser`, `confirmUser` (qaytarib bo'lmaydigan amallar uchun), `showMainButton`, `showBackButton` (sozlamalar oynasini yopadi) |
| [hooks.ts](web/src/hooks.ts) | `ROUTES` (barcha marshrutlar), `useRoute` (hash router — Telegram parametrlarini ajratadi), `useAsync` |
| [pages/Today.tsx](web/src/pages/Today.tsx) 95q | Bugungi ro'yxat, ✅. Sherigi yo'q bo'lsa tepada Jamoa tabiga yo'llovchi kartochka (`/me` dagi `group.partner_count` dan) |
| [pages/Tomorrow.tsx](web/src/pages/Tomorrow.tsx) 120q | Reja kiritish, submit |
| [pages/Team.tsx](web/src/pages/Team.tsx) 300q | **Faqat kunlik ko'rinish:** sherik kartochkalari, ularning bugungi ro'yxati, reaksiya, turtki, haftalik reyting. Boshqaruv amallari yo'q — hammasi sozlamalarda. **Sherigi yo'q bo'lsa butun sahifa `Invite` ekraniga almashadi** (nega sherik kerak + kod + qo'shilish) |
| [pages/Stats.tsx](web/src/pages/Stats.tsx) 83q | Grafiklarni yig'adi |
| [pages/Habits.tsx](web/src/pages/Habits.tsx) 205q | **Odatlar CRUD** (ro'yxat, tahrir formasi, jadval, maxfiylik, arxivlash) |
| [pages/Settings.tsx](web/src/pages/Settings.tsx) 300q | Eslatma vaqtlari, sherik toggle'lari, reytingni o'chirish + **«Jamoa» bo'limi = jamoani boshqarishning yagona joyi:** nomni tahrirlash, a'zolar ro'yxati va ularni chiqarish, taklif kodi (nusxalash, yangilash), jamoadan chiqish. Uchta qaytmas amal ham `confirmUser` so'raydi. Barchasi `/me` dagi `group` blokidan. `onClose` propini oladi |
| [components/charts.tsx](web/src/components/charts.tsx) 309q | `TrendChart`, `ReasonsChart`, `HabitHeatmap`, `SeriesTable` — SVG, kutubxonasiz |
| [components/ui.tsx](web/src/components/ui.tsx) | `Card`, `Tiles`, `ProgressBar`, `TaskRow`, `Loading`, `ErrorBox` |
| [theme.css](web/src/theme.css) 472q | Telegram theme o'zgaruvchilari, barcha stil |

## 5. Buzib bo'lmaydigan qoidalar

1. **`date` = mahalliy sana, `datetime` = UTC.** Aralashsa streak yarim tunda
   noto'g'ri uziladi va buni ikki oydan keyin sezasan. "Hozir" faqat
   `shared/clock.py` dan.
2. **Habit = shablon, Task = o'sha kunning nusxasi.** Odat o'zgarsa o'tmish
   o'zgarmaydi. Odat **o'chirilmaydi — arxivlanadi**.
3. **Biznes-logika `services/` da.** Bot va API — faqat qobiq.
4. **Maxfiylik bitta joyda:** `services/stats.py:54-77`. `private` odat
   sherikka ham, umumiy foizga ham, **reyting baliga ham** kirmaydi — aks
   holda "ball qayerdan keldi?" savoli uning borligini fosh qiladi.
5. **Eslatma bir marta ketadi:** `ReminderLog` (user+kind+date unique). Bu
   jadvalsiz restart har safar xabarni qayta yuboradi.
6. **Matnlar `bot/locales/uz.py` da**, kodga yozilmaydi.
7. **Taklif kodi faqat sardorga ko'rinadi** (API `invite_code` ni boshqalarga
   `null` qaytaradi, bot `/jamoa` da `GROUP_INFO_MEMBER` ni ko'rsatadi).
   Chiqarish huquqi shu bilan ma'noga ega: kodni yangilagach chiqarilgan odam
   qaytib kira olmaydi. Yolg'iz foydalanuvchi doim o'z jamoasining sardori —
   ya'ni bu qoida yangi odamning ishga kirishishiga xalaqit bermaydi.
8. **Hash Telegramniki ham.** Mini App ochilganda Telegram hash'ga o'z
   parametrlarini yozadi (`#tgWebAppData=...`, bot havolasida esa
   `#/team&tgWebAppData=...`). `useRoute` shuning uchun birinchi bo'lakni
   ajratib, `ROUTES` ro'yxatidan tekshiradi. Bu tekshiruv olib tashlansa,
   ilova ochilishida bo'sh ekran ko'rinadi (foydalanuvchi tab bosgunicha).
   **Brauzerda bu xato ko'rinmaydi** — `tgWebAppData` ni faqat Telegram
   qo'yadi. SDK'ga, URL'ga yoki marshrutga tegilsa, telefonda ochib
   tekshirish shart; brauzerdagi tekshiruv yetmaydi.
9. **Jamoadan jim ketib bo'lmaydi.** Chiqish ham, chiqarish ham qolganlarga
   xabar yuboradi (`notify_left`, `notify_removed`). Aks holda qolgan odam
   sherigi shunchaki dangasalik qilyapti deb haftalab kutib yuraveradi —
   accountability ilovasi uchun bu eng yomon holat. Sardor chiqsa sardorlik
   eng eski a'zoga o'tadi; jamoa hech qachon boshqaruvsiz qolmaydi.

## 6. Vazifa → qayerga qarash

| Nima qilmoqchiman | Qayerga |
|---|---|
| Yangi jadval / maydon | `shared/models.py` → `scripts/init_db.py` (migratsiya yo'q, SQLite qayta yaratiladi) |
| Yangi `.env` sozlamasi | `shared/config.py:28` + `.env.example` + README jadvali |
| Ball / foiz formulasi | `services/scoring.py` (yagona joy) |
| Streak qoidasi | `services/streak.py:33` |
| Eslatma vaqti yoki tartibi | `services/scheduler.py:42` + `shared/config.py` |
| Xabar matni | `bot/locales/uz.py` |
| Yangi endpoint | `api/routers/*.py` + `api/schemas.py` + `web/src/api.ts` |
| Yangi ekran | `web/src/pages/` + `App.tsx` dagi `TABS` (5 tadan oshirmang — 375px ekranda yorliqlar o'qilmay qoladi; kam ishlatiladigani ⚙️ oynasiga) |
| Grafik | `web/src/components/charts.tsx` (SVG qo'lda, kutubxona qo'shma) |
| Sherik nimani ko'rishi | `services/stats.py:54` |
| Jamoani boshqarish (nom, kod, a'zo chiqarish, chiqish) | `services/groups.py:153+` → `api/routers/team.py:79+` → **`web/src/pages/Settings.tsx`** (Team.tsx da emas) |
| Jamoadan chiqish | `services/groups.py:183` → `api/routers/team.py:133` → `web/src/pages/Settings.tsx` |

## 7. Server (2026-08-14 dan beri shu yerda ishlaydi)

| | |
|---|---|
| Manzil | <https://158.178.149.128.nip.io> |
| Server | Oracle Cloud Always Free, Amsterdam, Ubuntu 24.04, 1 yadro / 1 GB |
| SSH | `ssh -i ~/.ssh/growth-up ubuntu@158.178.149.128` |
| Papka | `/opt/growth-up` (GitHub'dan `git pull`) |
| Xizmat | `systemctl status\|restart growth-up` · log: `journalctl -u growth-up -f` |
| HTTPS | Caddy + Let's Encrypt, sertifikat o'zi yangilanadi |
| Zaxira | har kuni 03:00, `data/backups/`, 30 kun saqlanadi |

Batafsil o'rnatish va yangilash: [deploy/SERVER.md](deploy/SERVER.md).

**Domen `nip.io` — vaqtinchalik yechim:** u IP manzilni domenga aylantiradi
(`158.178.149.128.nip.io` → o'sha IP), ro'yxatdan o'tish talab qilmaydi.
Kamchiligi: IP o'zgarsa domen ham o'zgaradi. Doimiy nom kerak bo'lsa —
DuckDNS yoki o'z domeningiz; o'shanda `.env` dagi `WEBAPP_URL`, Caddyfile
va restart yetadi.

## 8. Ishga tushirish (lokal, qisqacha)

```bash
python run.py                 # bot + API + eslatma sikli
python run.py --api-only      # frontend uchun, Telegramsiz
cd web && npm run dev         # Vite :5173  (CHECK_INIT_DATA=false kerak)
python -m scripts.seed_demo   # 30 kunlik namunaviy tarix
python -m pytest              # testlar (deploydan oldin majburiy)
```

Botda (admin): `/sinov` — barcha eslatmalarni darhol yuboradi, `/vaqt` — jadval.
Kun chegarasini sinash: `.env` da `DEV_TIME_SHIFT_MINUTES`, `REMINDER_TICK_SECONDS`.

**Tunnel — `--protocol http2` bilan ishga tushiring:**

```bash
cloudflared tunnel --url http://127.0.0.1:8000 --protocol http2
```

Sukut bo'yicha cloudflared QUIC (UDP:7844) ishlatadi; bu yerdagi tarmoqda u
bo'g'iladi — internet bir soniya uzilsa tunnel qaytib ulanmay `control stream
encountered a failure` deb aylanib qoladi va Mini App ishlamaydi (jarayon esa
tirik ko'rinadi, shuning uchun sabab darrov ko'rinmaydi). `http2` TCP:443 dan
yuradi va qayta ulanadi. Tunnel qayta ishga tushsa URL o'zgaradi → `.env`
dagi `WEBAPP_URL` ni yangilab, ilovani restart qiling (menyu tugmasi startupda
o'rnatiladi).

## 9. Testlar

`python -m pytest` (o'rnatish: `pip install -r requirements-dev.txt`).
**Serverga chiqarishdan oldin majburiy.** 161 ta test, ~25 soniya.

| Fayl | Nimani qo'riqlaydi |
|---|---|
| [test_clock_scoring.py](tests/test_clock_scoring.py) | `is_due` oynasi (yarim tundan keyin ham), hafta boshi, ball/foiz formulasi, `SKIPPED` maxrajdan chiqishi |
| [test_planning.py](tests/test_planning.py) | Odatdan vazifa yaratish (takrorlanmasligi, hafta kunlari, arxiv, o'tmishga tegmaslik), belgilash, ko'chirish, tasdiqlash, kun yopish idempotentligi, begona vazifaga tegib bo'lmasligi |
| [test_streak.py](tests/test_streak.py) | Uzilish, `best_len` saqlanishi, chegara foizi, "bugun hali tugamagan" qoidasi |
| [test_privacy.py](tests/test_privacy.py) | **Maxfiylikning uchala darajasi**, `private` reytingga kirmasligi, izohning sherikka ko'rinmasligi |
| [test_groups.py](tests/test_groups.py) | Qo'shilish, sardor huquqlari, chiqarish, chiqish, sardorlikning o'tishi |
| [test_notify_scheduler.py](tests/test_notify_scheduler.py) | Eslatma bir marta ketishi (`ReminderLog`), bloklangan foydalanuvchi, sherikka ogohlantirish, jadval tartibi |
| [test_api.py](tests/test_api.py) | Barcha endpointlar ASGI orqali (tarmoqsiz), `index.html` kesh sarlavhasi |
| [test_auth.py](tests/test_auth.py) | **initData imzosi:** buzilgan `user_id`, begona token, muddati o'tgani rad etilishi |
| [test_integrity.py](tests/test_integrity.py) | Har modul import bo'lishi, `T.NOM` mavjudligi, `.format()` kalitlari matnga mosligi, o'lik matnlar ro'yxati |
| [test_db.py](tests/test_db.py) | WAL rejimi, `busy_timeout`, ikki sessiyaning parallel yozuvi |

`tests/conftest.py` `os.environ` ni **import'lardan oldin** qo'yadi —
`shared/db.py` dvigatelni import paytida yaratadi, kech qo'ysak testlar
haqiqiy `data/growth.db` ga tegib ketardi.

## 10. Holat va ochiq savollar

**Tugagan:** Faza 1 to'liq — reja, odatlar, eslatmalar, jamoa, reyting,
statistika, maxfiylik, sardor huquqlari (nom / kod / a'zoni chiqarish),
jamoadan chiqish.

**Loyiha real ishlatish bosqichiga o'tdi (2026-08-14).** Endi o'zgarishlar
taxmindan emas, ishlatib ko'rgandan keyin keladi — odatlarning sozlamalardan
ajratilishi ham, chiqish tugmasi ham shundan tug'ildi. Yangi taklifni
baholaganda: shikoyat ishonchli, unga ilova qilingan yechim — har doim emas.

**Yo'q:** migratsiya (Alembic — model o'zgarsa baza qo'lda yangilanadi),
Faza 2 (`Goal`, `JournalEntry` jadvallari bo'sh turibdi), CI (testlar
qo'lda ishga tushiriladi).

**Kod GitHub'da:** <https://github.com/Quvonchbek-man/growth-up> (public).
`.env` va baza repoda yo'q va bo'lmasligi kerak.

**Testlar topgan bo'shliqlar** (xato emas, ulanmagan joylar — `tests/test_integrity.py`
dagi `ULANMAGAN_MATNLAR` ro'yxati): `STREAK_LOST` matni yozilgan, lekin streak
uzilganini foydalanuvchiga hech kim aytmaydi; `UNKNOWN_COMMAND` — bot notanish
xabarga umuman javob bermaydi.

**Hal qilinmagan:**
1. **Raqobat.** Men yumshoq "jamoa natijasi"ni tavsiya qilgandim, foydalanuvchi
   ball+reytingni tanladi. Xavf: 2 kishida ortda qolgan uyalib qochadi.
   Yumshatish: `show_ranking` sozlamasi + formulaning `scoring.py` da ajratilgani.
   **Real ishlatishdan keyin qayta so'rash kerak.**
2. `STREAK_SUCCESS_PCT=60` taxminiy — sinovdan keyin kelishiladi.
3. Ball og'irligi 1–10 yetarlimi?
4. **Qo'l vazifasiga ball tanlash — ataylab qo'shilmadi (2026-08-14).**
   `POST /day/{day}/tasks` `points` ni allaqachon qabul qiladi, faqat
   frontend yubormaydi (doim 1). Sabab: ball faqat reytingga ta'sir qiladi
   (streak `completion_pct` dan, u esa vazifa **soni** bo'yicha), kechqurun
   reja kiritish esa eng nozik qadam — u yerdagi har qo'shimcha qaror reja
   kiritilmay qolish xavfini oshiradi. Yana: o'ziga o'zi ball qo'yish
   2 kishilik jamoada ishonch masalasi. **Kerak bo'lib qolsa:** kiritish
   qatoriga emas, yaratilgan vazifaga bosib o'zgartirish va 1–10 emas,
   3 pog'ona (oddiy / katta / juda katta).
5. **Bugungi kun ataylab qulflangan (2026-08-14).** `Today.tsx` da faqat ✅
   bor: qo'shish ham, o'chirish ham yo'q. Sabab: kun ichida tahrirlanadigan
   ro'yxat va'da bo'lishdan to'xtaydi — kechqurun bajarilgan ishni qo'shib
   qo'yish foizni ham, ballni ham yolg'on qiladi, sherik esa buni ko'rmaydi.
   **Buni ochish taklif qilinsa — avval foydalanuvchi bilan gaplashing.**
   Yon ta'siri: `SKIPPED` holati (`scoring.py` da na songa, na maxrajga
   kiradi — "kasal bo'lgan kun") UI'dan umuman qo'yib bo'lmaydi, ya'ni
   mo'ljallangan yumshatish ulanmagan. Foydalanuvchida bunga **boshqacha
   logika** bor, hozircha ataylab qoldirilgan — o'zicha "skip tugmasi"
   qo'shmang, avval so'rang.

**Rejada, lekin ataylab kechiktirilgan:** taklif **havolasi** (`t.me/<bot>?start=KOD`).
Bot tomoni tayyor — `start.py:37` deep link'ni allaqachon qabul qiladi. Qilinsa:
`run.py` da `bot.get_me().username` ni `app.state` ga qo'yish → `GET /team` ga
`invite_link` → `Invite` ekraniga «Telegramda ulashish» tugmasi. Foydalanuvchi
hozircha kod yetarli dedi (2026-08-14).

**Keyingi:** Faza 2 — haftalik hisobot (yakshanba 20:00), kundalik, maqsadlar
(`Task.goal_id` maydoni allaqachon bor), ruscha til. Faza 3 — VPS, barqaror
tunnel, backup, 10 kishidan oshsa Postgres.
