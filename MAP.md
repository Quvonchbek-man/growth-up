# Duo Growth — kod xaritasi

> **Claude uchun:** yangi sessiyada kod bo'ylab qidiruv qilishdan oldin shu
> faylni o'qi. Bu yerda javob bo'lsa — `grep`/`find` qilma.
> **Kod o'zgarganda shu faylni ham yangila** (fayl qo'shilsa/o'chsa, endpoint
> yoki servis funksiyasi o'zgarsa, qaror qabul qilinsa). Qator raqamlari
> taxminiy — ular bo'yicha `offset` bilan o'qish mumkin, lekin tekshirib ol.
>
> Oxirgi yangilangan: 2026-08-15 (odat jadvalining sinxronlanishi,
> tasdiqlash tugmasining joyi) · Faza 1 tugagan

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
| [models.py](shared/models.py) | **11 jadval + 9 sanoq.** Enumlar, `User`, `Group`, `Membership`, `Habit`, `Task`, `DailyPlan`, `StreakState`, `Nudge`, `Reaction`, `ReminderLog`, Faza 2: `Goal`, `JournalEntry`. **Vaqt maydonlari:** `Habit.start_time/end_time` (shablon) → `Task.start_time/end_time` (nusxa), `User.task_lead_min` (0 = o'chirilgan). **Qo'shimcha:** `Task.is_extra`, `DailyPlan.extra_count/extra_done_count`. `ReminderLog.task_id` (NOT NULL, standart 0). `User.blocked_at` — a'zolar dinamikasi uchun (bayroqning o'zi qachonligini aytmaydi) |
| [config.py](shared/config.py) | `Settings` pydantic (`:28`), barcha `.env` kalitlari, `get_settings()` lru_cache |
| [clock.py](shared/clock.py) | "Hozir" tushunchasining **yagona manbayi**: `now_utc`, `today_local`, `is_due`, `week_start`, `shift_time` (vazifa eslatmasi uchun, sana chegarasidan o'tmaydi), `fmt_range` (`"07:00–07:45"`) |
| [db.py](shared/db.py) | async engine, `session_factory`, `create_all()`. **SQLite PRAGMA'lari `:48`** — WAL + `busy_timeout=5s`: usiz bot, API va eslatma sikli bir vaqtda yozganda `database is locked` chiqadi |

### services/ — biznes-logika

| Fayl | Asosiy funksiyalar |
|---|---|
| [planning.py](services/planning.py) | `get_or_create_user`, **`_sync_habit_tasks`** (odat jadvaliga moslash — yaratadi **va** jadvaldan chiqqanini o'chiradi, **vaqtni ham ko'chiradi**), `open_day`, `recalc_day`, `get_task`, `get_tasks` (**tartib: vaqtlilar avval, vaqtsizlari oxirida**), `add_task` (`start_time`/`end_time`/`is_extra`), **`add_habit_task`** (odatni jadvalida yo'q kunga qo'lda qo'shish — `MANUAL` + `habit_id`), `set_task_time`, `set_status`, `set_miss_reason`, `move_task` (**`user` obyektini oladi**, `user_id` emas; `habit_id` li vazifani ko'chirmaydi), `submit_plan`, `close_day`, `missed_tasks_without_reason` (qo'shimchani chiqarib tashlaydi) |
| [stats.py](services/stats.py) | **Maxfiylik shu yerda qo'llanadi:** `visible_to_partner`, `serialize_task`. Yana: `day_view`, `partner_cards`, `daily_series`, `reason_breakdown`, `habit_matrix`, `leaderboard` (**`is_extra` filtri shu yerda qo'lda yozilgan**), `week_leaderboard` |
| [notify.py](services/notify.py) | Barcha Telegram xabarlari: `safe_send` (blok/xatoni yutadi), `already_sent/mark_sent` (idempotentlik, `task_id` bilan), `send_plan_reminder`, `send_digest` (qatorlarda vaqt), **`send_task_reminders`** (vazifa boshlanishidan oldin), `nag_partners_about`, `close_and_summarize`, `ask_reasons`, `send_nudge`, `notify_removed`, `notify_left` |
| [scheduler.py](services/scheduler.py) | `fire_due_for` — 5 belgilangan qadam **shu tartibda**: kun_yopish → sabab → ertalabki → kechki → sherikka, keyin **6-qadam: vazifa eslatmalari** (vaqti yo'q — tekshiruv `notify` ichida). `tick` (har foydalanuvchi alohida sessiya), `run_forever` |
| [scoring.py](services/scoring.py) | Ball formulasi va **reja/qo'shimcha ajratmasi shu yerda**: `counted` (reja), `extras`, `day_score`, `completion_pct`, `summarize` |
| [streak.py](services/streak.py) | `_is_success:33` (`STREAK_SUCCESS_PCT` shu yerda), `recalc:39` |
| [admin.py](services/admin.py) | **Butun bot bo'yicha** (yagona shunday modul): `overview` (odamlar, sherik holati, faollik, natija), `members_series` (**a'zolar dinamikasi** — kunlik `total`/`active`/`joined`/`left`, butun tarixdan jamg'ariladi), `recent_users` (**sana mahalliy qilib qaytariladi**), `broadcast` + `broadcast_audience`. Maxfiylik filtri yo'q — ma'lumot faqat adminga chiqadi |
| [groups.py](services/groups.py) 250q | Taklif kodi, `ensure_group:47`, `join_by_code:84`, `partners:130`. **Sardor huquqlari:** `is_owner:153`, `require_owner:157`, `rename:167`, `reset_invite_code:176`, `leave:183`, `remove_member:223`. Xatolar: `TeamError:76`, `NotOwnerError:80` (API 403 ga aylantiradi) |

### api/ — REST (barcha yo'llar `/api` prefiksi bilan)

| Metod + yo'l | Fayl:qator |
|---|---|
| `GET /api/health` | [main.py:45](api/main.py) |
| `GET /me` · `PATCH /me` | [user_settings.py:50,62](api/routers/user_settings.py) — javobda `group` bloki ham bor (nom, `partner_count`, `is_owner`, `invite_code` — kod faqat sardorga) |
| `GET /day/{day}` | [days.py:28](api/routers/days.py) — `day` = `today`/`tomorrow`/ISO sana |
| `POST /day/{day}/tasks` | days.py — **qo'shimcha/reja qarori shu yerda**: `is_extra = (kun == bugun)`. O'tgan kun → 400, bugungi qo'shimchaga o'tgan vaqt → 400 |
| `POST /day/{day}/habits` | days.py — odatni **jadvalida yo'q kunga** qo'lda qo'shish. Faqat kelajakdagi kun (bugun/o'tmish → 400), begona/arxiv odat → 404, takror → 400 |
| `POST /day/{day}/submit` | days.py:69 |
| `PATCH /tasks/{id}` · `POST /tasks/{id}/move` · `POST /tasks/{id}/time` · `DELETE /tasks/{id}` | days.py — `DELETE` bugungi **rejani** o'chirtirmaydi (qo'shimchani o'chirsa bo'ladi) |
| `GET/POST /habits` · `PUT/DELETE /habits/{id}` | [habits.py:32,45,75,114](api/routers/habits.py) (DELETE = arxivlash) |
| `GET /team` · `POST /team/join` · `/team/nudge` · `/team/react` | [team.py:37,158,177,210](api/routers/team.py) |
| `POST /team/leave` | team.py:133 — o'z ixtiyori bilan chiqish (sardor ham). Yolg'iz bo'lsa 400 |
| **Sardor:** `PATCH /team` (nom) · `POST /team/code` (kodni yangilash) · `DELETE /team/members/{id}` | team.py:79,94,108 — sardor bo'lmasa 403 |
| `GET /stats?days=30` | [stats.py:16](api/routers/stats.py) |
| `GET /admin/overview?days=30` | [admin.py](api/routers/admin.py) — `current_admin` bog'liqligi, admin bo'lmasa 403. Ommaviy xabar bu yerda ATAYLAB yo'q (faqat botda) |

- [auth.py](api/auth.py): `parse_init_data` (HMAC imzo), `current_user`
  Depends. `CHECK_INIT_DATA=false` bo'lsa `DEV_MOCK_USER_ID` nomidan ishlaydi.
  Yana: `is_admin(user_id)` va `current_admin` — admin endpointlari uchun.
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
| `/sinov`, `/vaqt`, `/admin`, `/xabar` — **faqat admin** | [dev.py](bot/handlers/dev.py) — `/admin` butun bot ko'rsatkichlari, `/xabar` ommaviy xabar (FSM: matn → ko'rinish → tasdiq). Ular `bot/main.py` dagi `COMMANDS` ro'yxatida yo'q: menyu hammaga ko'rinadi |

- [callbacks.py](bot/callbacks.py): `TaskCb/ReasonCb/NudgeCb/DayCb/BroadcastCb`.
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
| [telegram.ts](web/src/telegram.ts) | `tg`, `initTelegram`, `haptic`, `alertUser`, `confirmUser` (qaytarib bo'lmaydigan amallar uchun), **`popupConfirm`** (tugmalari o'z matniga ega tasdiq), `showBackButton` (sozlamalar oynasini yopadi). **`showMainButton` yo'q** — §5.10 ga qarang |
| [hooks.ts](web/src/hooks.ts) | `ROUTES` (barcha marshrutlar), `useRoute` (hash router — Telegram parametrlarini ajratadi), `useAsync` |
| [pages/Today.tsx](web/src/pages/Today.tsx) | **Ikki bo'lim: «Reja» va «Qo'shimcha».** Rejada faqat ✅ (qulf saqlanadi), qo'shimchada ✅ + ✕ + kiritish qatori. Sherigi yo'q bo'lsa tepada Jamoa tabiga yo'llovchi kartochka |
| [pages/Tomorrow.tsx](web/src/pages/Tomorrow.tsx) | Reja kiritish (vaqt bilan), vazifa vaqtini joyida tahrirlash, submit. **Tasdiqlash tugmasi tepada** (§5.10) va `popupConfirm` so'raydi. **«Odatlardan qo'shish»** — ertangi jadvalga tushmagan odatlar (ro'yxatda yo'qlari), bir bosishda qo'shiladi |
| [pages/Team.tsx](web/src/pages/Team.tsx) 300q | **Faqat kunlik ko'rinish:** sherik kartochkalari, ularning bugungi ro'yxati, reaksiya, turtki, haftalik reyting. Boshqaruv amallari yo'q — hammasi sozlamalarda. **Sherigi yo'q bo'lsa butun sahifa `Invite` ekraniga almashadi** (nega sherik kerak + kod + qo'shilish) |
| [pages/Stats.tsx](web/src/pages/Stats.tsx) | Grafiklarni yig'adi. Taqqoslash uchun tanlangan sherik `localStorage` da (`growth:taqqoslash`) — serverda emas, chunki bu ko'rinish sozlamasi |
| [pages/Admin.tsx](web/src/pages/Admin.tsx) | **Bot admini uchun kuzatuv ekrani.** Tab emas — sozlamalardagi tugmadan ochiladi. Ommaviy xabar bu yerda yo'q (botda) |
| [pages/Habits.tsx](web/src/pages/Habits.tsx) 205q | **Odatlar CRUD** (ro'yxat, tahrir formasi, jadval, maxfiylik, arxivlash) |
| [pages/Settings.tsx](web/src/pages/Settings.tsx) 300q | Eslatma vaqtlari, sherik toggle'lari, reytingni o'chirish + **«Jamoa» bo'limi = jamoani boshqarishning yagona joyi:** nomni tahrirlash, a'zolar ro'yxati va ularni chiqarish, taklif kodi (nusxalash, yangilash), jamoadan chiqish. Uchta qaytmas amal ham `confirmUser` so'raydi. Barchasi `/me` dagi `group` blokidan. `onClose` propini oladi |
| [components/charts.tsx](web/src/components/charts.tsx) | `comparePeople` (**kim taqqoslanadi — sof funksiya**), `TrendChart`, `ReasonsChart`, `HabitHeatmap`, `SeriesTable`, `MembersChart` (admin: jami/faol chiziqlari) |
| [components/ui.tsx](web/src/components/ui.tsx) | `Card`, `Tiles`, `ProgressBar`, `TaskRow` (vaqt yorlig'i; amal tugmalari `readonly` ga bog'liq emas), `timeRange`, `TaskComposer` (nom + ⏱ bilan ochiladigan vaqt maydonlari — «Bugun» va «Ertaga» da bir xil), `TimeEditor`, `Loading`, `ErrorBox` |
| [theme.css](web/src/theme.css) 472q | Telegram theme o'zgaruvchilari, barcha stil |

## 5. Buzib bo'lmaydigan qoidalar

1. **`date` = mahalliy sana, `datetime` = UTC.** Aralashsa streak yarim tunda
   noto'g'ri uziladi va buni ikki oydan keyin sezasan. "Hozir" faqat
   `shared/clock.py` dan.
2. **Habit = shablon, Task = o'sha kunning nusxasi.** Odat o'zgarsa o'tmish
   o'zgarmaydi. Odat **o'chirilmaydi — arxivlanadi**.
2a. **`source` nusxani KIM yaratganini aytadi, `habit_id` esa NIMA ekanini.**
   `HABIT` = jadval yaratdi (foydalanuvchi uni rejadan olib tashlay olmaydi,
   jadvaldan chiqsa o'zi yo'qoladi); `MANUAL` + `habit_id` = odam o'zi
   qo'shdi (✕ bilan o'chiriladi, `_sync_habit_tasks` unga tegmaydi).
   Shuning uchun odat nusxasini qidiruvchi shart `source` emas, **`habit_id`
   bo'yicha** yozilishi kerak (`move_task` dagi kabi) — aks holda qo'lda
   qo'shilgani `UNIQUE(user_id, date, habit_id)` ga urilib ketadi.
3. **Biznes-logika `services/` da.** Bot va API — faqat qobiq.
4. **Maxfiylik bitta joyda:** `services/stats.py:54-77`. `private` odat
   sherikka ham, umumiy foizga ham, **reyting baliga ham** kirmaydi — aks
   holda "ball qayerdan keldi?" savoli uning borligini fosh qiladi.
5. **Eslatma bir marta ketadi:** `ReminderLog` (user+kind+date+**task_id**
   unique). Bu jadvalsiz restart har safar xabarni qayta yuboradi.
   **`task_id` NULL bo'lmaydi** (standarti `0`): SQLite `UNIQUE` da NULL'lar
   bir-biridan farqli hisoblanadi, ya'ni maydonni `nullable` qilish beshta
   kunlik eslatma turining kafolatini **jimgina** buzadi — xato ko'rinmaydi,
   shunchaki xabar takrorlana boshlaydi.
5a. **Qo'shimcha — reja emas.** Bugungi kunga qo'shilgan ish (`Task.is_extra`)
   na `completion_pct` ga, na `score` ga, na streakka kiradi; ular faqat
   `extra_count`/`extra_done_count` da ko'rinadi. Sabab: reja kechqurun
   berilgan va'da — kun ichida unga qo'shsa bo'lsa, ertalab bajarilgan ishni
   yozib qo'yish orqali foizni ko'tarish mumkin bo'lardi (2/4 = 50% →
   3/5 = 60%) va sherik ko'rgan ro'yxat kun davomida o'zgarib turardi.
   Ajratma **`services/scoring.py`** da; lekin `stats.leaderboard` reytingni
   `daily_plans` dan emas, `tasks` dan hisoblaydi — **u yerda `is_extra`
   filtri qo'lda yozilgan** va yangi so'rov qo'shilsa ham yozilishi shart.
   Xuddi shu sabab `reason_breakdown` da ham (qo'shimchadan sabab so'ralmaydi,
   ya'ni ular grafikni "noma'lum" bilan to'ldirib yuborardi).
6. **Matnlar `bot/locales/uz.py` da**, kodga yozilmaydi.
7. **Taklif kodi faqat sardorga ko'rinadi** (API `invite_code` ni boshqalarga
   `null` qaytaradi, bot `/jamoa` da `GROUP_INFO_MEMBER` ni ko'rsatadi).
   Chiqarish huquqi shu bilan ma'noga ega: kodni yangilagach chiqarilgan odam
   qaytib kira olmaydi. Yolg'iz foydalanuvchi doim o'z jamoasining sardori —
   ya'ni bu qoida yangi odamning ishga kirishishiga xalaqit bermaydi.
7c. **`is_blocked` va `blocked_at` doim birga o'zgaradi** —
   `planning.mark_blocked()` orqali, boshqa joyda qo'lda emas. Sanasiz
   bloklangan odam a'zolar dinamikasida "ketgan" bo'lib ko'rinmaydi:
   `total` chizig'i to'g'ri, `active` esa jimgina yuqori qoladi. Odam
   qaytib kelsa (`get_or_create_user`) ikkalasi ham tozalanadi.
7a. **`SUPER_ADMIN_IDS` bo'sh = hech kimga ruxsat yo'q.** Bo'sh ro'yxatni
   "tekshiruv o'chirilgan" deb talqin qilish taqiqlanadi: `.env`
   to'ldirilmagan yoki noto'g'ri yozilgan serverda admin paneli barcha
   foydalanuvchiga ochilib qolardi va buni hech kim sezmasdi. Tekshiruv —
   `api/auth.py:is_admin`, test — `tests/test_admin.py`.
7b. **Grafikda rang ROLGA biriktiriladi, shaxsga emas.** 1 — men, 2 — eng
   zo'r ketayotgan sherik, 3 — tanlangan odam. Ikkinchi slotdagi odam
   natijalar o'zgarishi bilan almashadi, ya'ni rangni odamga bog'lab
   bo'lmaydi. **Shaxsni izoh (legend) ko'rsatadi** — shuning uchun izohni
   olib tashlash grafikni o'qib bo'lmaydigan qiladi.
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
10. **Telegram'ning `MainButton`'i ishlatilmaydi (2026-08-15).** U webview'ning
   TASHQARISIDA, tab qatorining aynan tagida chiziladi — «Ertaga» tabini
   bosgan barmoq «Rejani tasdiqlash» ga tegib ketardi va tasdiqni qaytarish
   yo'li yo'q (`submit_plan` faqat qo'yadi). Tugma endi sahifaning tepasida,
   ogohlantirish blokidan oldin, ustiga `popupConfirm` so'raydi. Yangi ekranga
   ham `MainButton` qo'shmang — o'sha tuzoq qaytadi.
11. **SDK metodi «bor» degani «ishlaydi» degani emas.** `showPopup` va
   `showConfirm` — Bot API 6.2 dan; eski mijozda ular obyektda ko'rinadi,
   lekin chaqirilganda `WebAppMethodUnsupported` deb **otiladi**. Shu sabab
   ular `telegram.ts` dagi `askViaSdk` orqali chaqiriladi: u xatoni ushlab
   `undefined` qaytaradi va chaqiruvchi brauzer muloqotiga tushadi. To'g'ridan
   `new Promise` ichida chaqirsangiz xato `reject` ga aylanadi — tugma
   bosiladi, hech narsa bo'lmaydi va konsolga qaramaguningizcha bilmaysiz.

## 6. Vazifa → qayerga qarash

| Nima qilmoqchiman | Qayerga |
|---|---|
| Odat qaysi kunlarda chiqishi | `shared/models.py` (`Habit.is_active_on`) → `services/planning.py` (`_sync_habit_tasks`) — **ikkalasi birga**, faqat tekshiruv yetmaydi |
| Yangi jadval / maydon | `shared/models.py` → yangi baza uchun `scripts/init_db.py`, **mavjud bazani yangilash uchun migratsiya skripti** (naqsh: `scripts/migrate_002_time.py` — idempotent `ADD COLUMN`, `UNIQUE` o'zgarsa jadvalni qayta qurish) |
| Yangi `.env` sozlamasi | `shared/config.py:28` + `.env.example` + README jadvali |
| Ball / foiz formulasi | `services/scoring.py` (yagona joy) |
| Streak qoidasi | `services/streak.py:33` |
| Eslatma vaqti yoki tartibi | `services/scheduler.py` (`steps`) + `shared/config.py` |
| Vazifa vaqti / undan oldingi eslatma | `shared/clock.py` (`shift_time`, `fmt_range`) → `services/notify.py` (`send_task_reminders`) → `scheduler.fire_due_for` ning 6-qadami |
| Qo'shimcha nimaga ta'sir qilishi | `services/scoring.py` (`counted`/`extras`) **va** `services/stats.py` dagi `is_extra` filtrlari |
| Xabar matni | `bot/locales/uz.py` |
| Yangi endpoint | `api/routers/*.py` + `api/schemas.py` + `web/src/api.ts` |
| Yangi ekran | `web/src/pages/` + `App.tsx` dagi `TABS` (5 tadan oshirmang — 375px ekranda yorliqlar o'qilmay qoladi; kam ishlatiladigani ⚙️ oynasiga) |
| Grafik | `web/src/components/charts.tsx` (SVG qo'lda, kutubxona qo'shma) |
| Sherik nimani ko'rishi | `services/stats.py:54` |
| Admin ko'rsatkichi qo'shish | `services/admin.py` (`overview`) → bot `/admin` matni `bot/locales/uz.py` da, Mini App `web/src/pages/Admin.tsx` |
| Grafikda kim taqqoslanishi | `web/src/components/charts.tsx` (`comparePeople`) |
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

**Yangilash — bitta buyruq:**

```bash
ssh -i ~/.ssh/growth-up ubuntu@158.178.149.128 /opt/growth-up/deploy/update.sh
```

[deploy/update.sh](deploy/update.sh) o'zi hal qiladi: `git pull` → o'zgargan
bo'lsa bog'liqliklar va frontend → ilovani to'xtatish → **zaxira** →
`scripts/migrate_*.py` larni ketma-ket bajarish → ishga tushirish →
`/api/health` tekshiruvi. Migratsiyalar idempotent, shuning uchun har safar
ishga tushiriladi va "qaysi birini bajargan edim" degan savol tug'ilmaydi.
Yangi migratsiya `scripts/migrate_NNN_nom.py` deb qo'yilsa yetadi.

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
**Serverga chiqarishdan oldin majburiy.** 207 ta test, ~35 soniya.

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
| [test_task_time.py](tests/test_task_time.py) | `shift_time` sana chegarasi, `fmt_range`, odat vaqtining nusxaga ko'chishi, ro'yxat tartibi, eslatmaning vaqtida ketishi va **har vazifaga bir martadan** (`task_id` ishlashi), `task_lead_min=0`, jadvalning 6-qadami. `soatni_toxtat` fixture'i `clock.now_local` ni qotiradi — aks holda testlar sutkaning qaysi soatida ishga tushirilganiga qarab yiqilardi |
| [test_admin.py](tests/test_admin.py) | **Ruxsat:** bo'sh `SUPER_ADMIN_IDS` da hech kimga ochilmasligi, admin bo'lmaganga 403, `/me` dagi `is_admin`. **Ko'rsatkichlar:** sherigi bor / yolg'iz, bloklaganlar, faollik, `recent_users` sanasi mahalliy bo'lishi. **Dinamika:** jamg'arma o'sishi, ketganlar `active` dan chiqib `total` da qolishi, **oynadan oldin qo'shilganlar ham hisoblanishi**, qaytib kelgan odam faolga qaytishi. **Ommaviy xabar:** bloklaganlar chetlab o'tilishi, `is_blocked` + `blocked_at` birga qo'yilishi, natija sonlari |
| [test_habit_schedule.py](tests/test_habit_schedule.py) | **Tanlangan kunlar qat'iy bajarilishi:** jadval toraysa nusxaning yo'qolishi, kengaysa paydo bo'lishi, `DONE` va o'tmishga tegilmasligi, `PUT /habits/{id}` javobida ertangi rejaning to'g'ri bo'lishi. **Qo'lda qo'shish:** `MANUAL` nusxaning tozalanmasligi, rejaga (qo'shimchaga emas) kirishi, takror/bugun/o'tmish/begona holatlarining rad etilishi. API testlari `men` fixture'ini ishlatadi va tayyorgarlikni **commit** qiladi (aks holda SQLite `database is locked`) |
| [test_extra_tasks.py](tests/test_extra_tasks.py) | **Asosiy qoida:** qo'shimcha foizni, ballni, reytingni va streakni tebratmasligi. Yana: bugun→qo'shimcha / ertaga→reja, o'tgan kunga va o'tgan vaqtga taqiq, qo'shimchadan sabab so'ralmasligi, bugungi rejani o'chirib bo'lmasligi |

`tests/conftest.py` `os.environ` ni **import'lardan oldin** qo'yadi —
`shared/db.py` dvigatelni import paytida yaratadi, kech qo'ysak testlar
haqiqiy `data/growth.db` ga tegib ketardi.

## 10. Holat va ochiq savollar

**Tugagan:** Faza 1 to'liq — reja, odatlar, eslatmalar, jamoa, reyting,
statistika, maxfiylik, sardor huquqlari (nom / kod / a'zoni chiqarish),
jamoadan chiqish. **2026-08-15:** vazifa vaqti (boshlanish–tugash) va
undan oldingi eslatma, bugungi kunga qo'shimcha vazifalar, taqqoslash
grafigining tanlanishi, admin panel (bot + Mini App), a'zolar dinamikasi
va ommaviy xabar. **Shu kuni kechroq:** odat jadvalining sinxronlanishi,
tasdiqlash tugmasining joyi va tasdiq oynasi, «Odatlardan qo'shish».

**Loyiha real ishlatish bosqichiga o'tdi (2026-08-14).** Endi o'zgarishlar
taxmindan emas, ishlatib ko'rgandan keyin keladi — odatlarning sozlamalardan
ajratilishi ham, chiqish tugmasi ham shundan tug'ildi. Yangi taklifni
baholaganda: shikoyat ishonchli, unga ilova qilingan yechim — har doim emas.

**Yo'q:** Alembic (model o'zgarsa qo'lda migratsiya skripti yoziladi —
`scripts/migrate_002_time.py` naqshi), Faza 2 (`Goal`, `JournalEntry`
jadvallari bo'sh turibdi), CI (testlar qo'lda ishga tushiriladi).

**Kod GitHub'da:** <https://github.com/Quvonchbek-man/growth-up> (public).
`.env` va baza repoda yo'q va bo'lmasligi kerak.

**Testlar topgan bo'shliqlar** (xato emas, ulanmagan joylar — `tests/test_integrity.py`
dagi `ULANMAGAN_MATNLAR` ro'yxati): `STREAK_LOST` matni yozilgan, lekin streak
uzilganini foydalanuvchiga hech kim aytmaydi; `UNKNOWN_COMMAND` — bot notanish
xabarga umuman javob bermaydi.

**Hal qilinmagan:**
0a. **Tasdiqlangan rejaga hamon odat qo'shsa bo'ladi (topilgan 2026-08-15,
   KEYINGI YANGILANISHDA hal qilinadi).** «Odatlardan qo'shish» bo'limi
   `submitted` holatini umuman tekshirmaydi — reja tasdiqlangandan keyin
   ham ko'rinib turadi va `POST /day/{day}/habits` uni qabul qiladi.
   Bu §5a ning o'sha buzilishi: tasdiq — berilgan va'da, undan keyin
   rejaga qo'shilgan ish maxrajni o'zgartiradi. **Yechim ikki qavatda:**
   (1) `Tomorrow.tsx` da `submitted` bo'lsa butun kartochka chizilmasin;
   (2) endpoint 400 qaytarsin (`planning.has_submitted_plan_for` allaqachon
   bor) — faqat frontendni yashirish yetmaydi, aks holda qoida tekshirilmay
   qoladi. **Bir vaqtda hal qilinsin:** erkin matnli «Qo'shimcha vazifa»
   ham ertangi tasdiqlangan rejaga qo'shilaveradi (`POST /day/{day}/tasks`)
   — bir xil teshik, bir xil yechim. Test: tasdiqlangandan keyin ikkala
   endpoint ham 400.
0b. **Baza o'sishi va serverning to'lib qolishi — TAHLIL kerak.**
   Hech qanday tozalash yo'q: `tasks` har kuni har odam uchun 5–10 qator,
   `reminder_logs` har eslatmaga bitta, `nudges`/`reactions` cheksiz
   to'planadi, `data/backups/` da 30 kunlik nusxa (har biri butun baza),
   WAL fayli esa `-wal` bo'lib o'sib boradi. Server — 1 yadro / 1 GB,
   ya'ni disk ham, xotira ham tor. **Avval o'lchash, keyin qirqish:**
   jadval-jadval qator soni va fayl hajmi (`sqlite3 growth.db
   "SELECT COUNT(*) …"`, `PRAGMA page_count`), 100 va 1000 foydalanuvchida
   bir yillik prognoz. **Ehtimoliy chora:** `reminder_logs` ni 60 kundan
   eskisini o'chirish (u faqat "bugun yubordikmi?" uchun kerak — tarixiy
   qiymati yo'q), `nudges`/`reactions` ni 6 oydan keyin, zaxira sonini
   30 dan 14 ga tushirish + `VACUUM`. **`tasks`/`daily_plans` ga
   tegilmaydi** — ular statistikaning o'zi. Ishga tushirish: kunlik
   zaxira skripti yonida, `deploy/` da cron.
0. **Birinchi ochilishda 500 — `UNIQUE constraint failed: users.id`
   (topilgan 2026-08-15, KEYINGI YANGILANISHDA hal qilinadi).** Mini App
   ochilganda bir nechta so'rov bir vaqtda ketadi (`/me`, `/day/today`,
   `/team`…), har biri `current_user` → `planning.get_or_create_user` ni
   chaqiradi. Foydalanuvchi hali bazada bo'lmasa, hammasi "yo'q ekan"
   deb ko'radi va hammasi INSERT qiladi — biri o'tadi, qolganlari
   yiqiladi. Faqat **eng birinchi** ochilishda ko'rinadi (sahifani
   yangilash yetadi), shuning uchun sinovda deyarli hech qachon
   uchramaydi — lekin bu aynan yangi odamning birinchi taassuroti.
   **Yechim:** `planning.get_or_create_user:50` dagi `flush` ni
   `IntegrityError` uchun `try/except` ga o'rab, xato bo'lsa
   `session.rollback()` qilib qayta `SELECT` qilish (INSERT ... ON
   CONFLICT emas: SQLite'da ham, kelajakdagi Postgres'da ham bir xil
   ishlashi kerak). Test: bitta foydalanuvchi uchun bir nechta parallel
   so'rov (`asyncio.gather`) — hammasi 200 qaytarishi shart.
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
5. **Bugungi REJA hamon qulflangan (2026-08-14), qo'shimcha esa ochildi
   (2026-08-15).** `Today.tsx` dagi «Reja» bo'limida faqat ✅ — qo'shish
   ham, o'chirish ham yo'q, va bu shunday qoladi: kun ichida tahrirlanadigan
   reja va'da bo'lishdan to'xtaydi. Ertalab paydo bo'ladigan haqiqiy ish
   uchun **alohida sinf** qo'shildi (§5a) — u rejaga qo'shilmaydi, yonida
   turadi va hech qanday raqamga tegmaydi. **Rejaning o'zini ochish taklif
   qilinsa — avval foydalanuvchi bilan gaplashing.**
   Yon ta'siri o'z joyida: `SKIPPED` holati (`scoring.py` da na songa, na
   maxrajga kiradi — "kasal bo'lgan kun") UI'dan hamon qo'yib bo'lmaydi.
   Foydalanuvchida bunga **boshqacha logika** bor, ataylab qoldirilgan —
   o'zicha "skip tugmasi" qo'shmang, avval so'rang.
6b. **"Ketganlar" tarixi 2026-08-15 dan boshlanadi.** `blocked_at` shu
   sanada qo'shildi; undan oldin kim qachon bloklagani hech qachon
   saqlanmagan va tiklab bo'lmaydi. Migratsiya eskilariga `updated_at` ni
   taxminiy sana qilib qo'yadi. Ya'ni shu sanadan oldingi "ketganlar"
   raqamiga ishonmang; keyingisi aniq. **"Ketdi" = botni bloklagan**
   degani, jamoadan chiqqan emas.
6a. **Ommaviy xabar faqat botda (2026-08-15).** Mini App'dagi admin paneli
   — kuzatuv uchun, unda yuborish tugmasi yo'q. Sabab: uzun matnni terib,
   ko'rinishini tekshirib, tasdiqlash botda tabiiyroq va tasodifan bosib
   yuborish qiyinroq. Yuborish jarayoni handler ichida ketadi — jarayon
   restart bo'lsa to'xtaydi; yuz kishigacha bu muammo emas, mingtaga
   chiqsa navbat (queue) kerak bo'ladi.
6. **Qo'shimchaga cheklov qo'yilmagan (2026-08-15).** Kuniga nechta va
   qaysi soatda qo'shish mumkinligi cheklanmagan — foydalanuvchining ochiq
   qarori. Bu xavfsiz, chunki qo'shimcha ball bermaydi; agar kelajakda
   qo'shimchaga ball berish qaytadan ko'rib chiqilsa, **avval cheklov
   masalasi hal qilinishi kerak** (aks holda kun oxirida mayda ish qo'shib
   reyting yig'ish yo'li ochiladi).

**Rejada, lekin ataylab kechiktirilgan:** taklif **havolasi** (`t.me/<bot>?start=KOD`).
Bot tomoni tayyor — `start.py:37` deep link'ni allaqachon qabul qiladi. Qilinsa:
`run.py` da `bot.get_me().username` ni `app.state` ga qo'yish → `GET /team` ga
`invite_link` → `Invite` ekraniga «Telegramda ulashish» tugmasi. Foydalanuvchi
hozircha kod yetarli dedi (2026-08-14).

**Keyingi:** Faza 2 — haftalik hisobot (yakshanba 20:00), kundalik, maqsadlar
(`Task.goal_id` maydoni allaqachon bor), ruscha til. Faza 3 — VPS, barqaror
tunnel, backup, 10 kishidan oshsa Postgres.
