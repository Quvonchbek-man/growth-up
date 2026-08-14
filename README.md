# Duo Growth

Ikki (yoki 10 tagacha) odam shaxsiy rivojlanish rejalarini birgalikda olib
boradigan Telegram Mini App + bot.

Bu ro'yxat ilovasi emas. Butun qiymat bitta mexanizmda: **sherigim ko'rib
turibdi, shuning uchun tashlab yubormayman.** Kod shu mexanizmga xizmat qiladi.

---

## Kunlik oqim

| Vaqt | Kim | Nima |
|---|---|---|
| 21:00 | siz | Bot ertangi rejani so'raydi. Odatlar avtomatik, qo'shimchasini yozasiz |
| 22:30 | **sherigingiz** | Siz kiritmagan bo'lsangiz — unga xabar + «Turtki ber» tugmasi |
| 09:00 | siz | Bugungi ro'yxat, botdan bir bosishda ✅ |
| kun bo'yi | siz | Vaqti belgilangan ish boshlanishidan 10 daqiqa oldin eslatma |
| 00:05 | tizim | Kun yopiladi: ball, streak, bajarilmaganlar `missed` bo'ladi |
| 00:10 | siz | Bajarilmaganlar uchun sabab so'raladi |

### Vaqt va qo'shimchalar

Har vazifaga **oraliq** qo'yish mumkin (`07:00–07:45`) — odatga qo'ysangiz,
har kungi nusxasiga o'zi ko'chadi. Belgilangan vaqtdan oldin bot eslatadi:
*«⏰ 10 daqiqadan keyin: Sport»*. Necha daqiqa oldin — sozlamalarda
(`0` = o'chirilgan).

Ertalab reja tashqarisida ish chiqsa, uni **«Bugun» ekranidagi «Qo'shimcha»
bo'limiga** yozasiz. Qo'shimcha bajarilishi foiziga, ballga va streakka
**kirmaydi** — reja kechqurun berilgan va'da, uni kun ichida o'zgartirib
bo'lmaydi, aks holda raqamlar ma'nosini yo'qotadi. Sherigingiz esa uni
ko'radi: *«4/5 +2»*.

---

## Ishga tushirish

### 1. Bot yarating

Telegram'da [@BotFather](https://t.me/BotFather):

```
/newbot
```

Nom va username so'raydi (username `bot` bilan tugashi shart). Bergan
tokenini nusxa oling.

### 2. `.env` ni to'ldiring

```bash
cp .env.example .env
```

Kamida shularni yozing:

```
BOT_TOKEN=1234567890:AA...
SUPER_ADMIN_IDS=123456789
CHECK_INIT_DATA=true
```

### 3. Mini App'ni qurib oling

```bash
cd web && npm install && npm run build && cd ..
```

### 4. HTTPS tunnel oching

Telegram Mini App faqat HTTPS orqali ochiladi. Alohida oynada:

```bash
cloudflared tunnel --url http://localhost:8000
```

Bergan `https://...trycloudflare.com` manzilini `.env` dagi `WEBAPP_URL` ga
yozing.

> **Muhim:** bu manzil tunnel har qayta ishga tushganda o'zgaradi. Shuning
> uchun uni BotFather'ga qo'lda kiritmaymiz — bot startupda menyu tugmasini
> `.env` dagi manzilga o'zi o'rnatadi. URL o'zgarsa: `.env` ni yangilab,
> botni qayta ishga tushiring, tamom.
>
> Barqaror manzil kerak bo'lsa (Faza 3) — Cloudflare akkaunti bilan *named
> tunnel* yoki VPS.

### 5. Ishga tushiring

```bash
python run.py
```

Bitta buyruq uchtasini ko'taradi: bot, API va eslatma sikli.

Telegram'da botni oching → `/start`. Taklif kodini sherigingizga yuboring,
u `/qoshil KOD` deb yozadi.

---

## Ishlab chiqish

### Frontend ustida ishlash

Telegram'siz, brauzerda:

```bash
python run.py --api-only
```

```bash
cd web && npm run dev
```

`.env` da `CHECK_INIT_DATA=false` bo'lsa, har so'rov `DEV_MOCK_USER_ID`
nomidan bajariladi va `http://localhost:5173` da hammasi ishlaydi.

> ⚠️ `CHECK_INIT_DATA=false` — imzo tekshirilmaydi. Faqat lokal ish uchun.

### Namunaviy ma'lumot

```bash
python -m scripts.seed_demo
```

30 kunlik tarix yozadi: notekis bajarilish, dam olish kunlarida pasayish,
dushanba kunlari uzilib qoladigan sport odati, sabablar taqsimoti, vaqti
belgilangan va belgilanmagan odatlar, kun ichida qo'shilgan qo'shimchalar.
Grafiklarni real ma'lumot yig'ilishini kutmasdan ko'rish uchun.

**Diqqat:** skript sizning va namunaviy sherikning mavjud ma'lumotini
o'chirib qayta yozadi.

### Mavjud bazani yangilash

Modelga yangi maydon qo'shilganda `init_db` mavjud jadvalni o'zgartirmaydi —
bir martalik migratsiya skripti ishlatiladi. Vaqt va qo'shimchalar uchun:

```bash
cp data/growth.db data/backups/growth-$(date +%F).db
python -m scripts.migrate_002_time
```

Skript idempotent: ikkinchi marta ishga tushirilsa hech narsa qilmaydi.
Yangi o'rnatishda kerak emas — `init_db` hammasini o'zi yaratadi.

### Eslatmalarni sinash

Kechgacha kutmasdan, botda (faqat `SUPER_ADMIN_IDS` uchun):

```
/sinov
```

Barcha eslatmalarni darhol yuboradi — kechki, ertalabki, sherikka xabar,
kun yakuni, sabab so'rovi va bugungi eng yaqin 3 ta vazifa eslatmasi.

```
/vaqt
```

Hozirgi UTC/mahalliy vaqt va eslatma jadvalini ko'rsatadi.

Kun chegarasi bilan bog'liq narsalarni sinash uchun `.env`:

```
DEV_TIME_SHIFT_MINUTES=600     # 10 soat oldinga
REMINDER_TICK_SECONDS=5        # sikl tezroq aylansin
```

---

## Tuzilma

```
shared/     config, baza, modellar, vaqt (clock.py)
services/   biznes-logika — bot ham, API ham shu qatlamni chaqiradi
bot/        aiogram: eslatmalar, tez belgilash, turtki
api/        FastAPI: Mini App uchun REST + initData imzosini tekshirish
web/        React + Vite Mini App
scripts/    init_db, seed_demo, migrate_* (mavjud bazani yangilash)
run.py      hammasi bitta processda
```

### Ikkita qoida

**1. `date` — mahalliy sana, `datetime` — UTC.** Ikkisi aralashsa streak
yarim tunda noto'g'ri uziladi va buni ikki oydan keyin sezasiz. "Hozir"
tushunchasi faqat `shared/clock.py` dan olinadi.

**2. Odat — shablon, vazifa — o'sha kunning nusxasi.** Odatni o'zgartirsangiz
o'tmish o'zgarmaydi. Odat o'chirilmaydi — arxivlanadi.

**3. Qo'shimcha — reja emas.** Kun ichida qo'shilgan ish alohida sanaladi va
foizga, ballga, streakka kirmaydi. Bo'lmasa, bajarib bo'lgan ishni ro'yxatga
yozib qo'yish orqali foizni ko'tarish mumkin bo'lardi.

### Maxfiylik

Har odat uchun uch daraja, `services/stats.py` da bitta joyda qo'llanadi:

| Daraja | Sherik ko'radi | Umumiy foizga | Reyting baliga |
|---|---|---|---|
| `public` | nomini ham, holatini ham | ✅ | ✅ |
| `stats_only` | «Yashirin vazifa» | ✅ | ✅ |
| `private` | umuman yo'q | ❌ | ❌ |

Yashirin vazifa jamoa reytingida ball bermaydi — aks holda «ball qayerdan
keldi?» degan savol orqali uning borligi fosh bo'lardi.

---

## O'yin qoidalari (`.env` dan sozlanadi)

| Sozlama | Standart | Ma'nosi |
|---|---|---|
| `STREAK_SUCCESS_PCT` | 60 | Kun muvaffaqiyatli hisoblanishi uchun kerakli foiz |
| `MAX_NUDGES_PER_DAY` | 3 | Bir odamga kuniga necha marta turtki berish mumkin |
| `TASK_REMINDER_LEAD_MIN` | 10 | Vazifa boshlanishidan necha daqiqa oldin eslatiladi (yangi foydalanuvchi uchun standart; `0` = o'chirilgan) |

Streak haqida: **rejasiz kun streak'ni uzadi** (ilovaning maqsadi rejani
yozdirish). Kasal yoki safar kunlari uchun vazifani `skipped` qilish yo'li
bor — u foizga ta'sir qilmaydi. **Bugungi kun streak'ni uzmaydi**, u hali
tugamagan.

---

## Keyingi bosqichlar

**Faza 2** — haftalik hisobot (yakshanba 20:00), kundalik (yopiq),
maqsadlar va `Task.goal_id` bog'lanishi, ruscha til.

**Faza 3** — VPS (~$5/oy), barqaror tunnel manzili, avtomatik backup,
10 kishidan oshsa SQLite → Postgres.

## Hal qilinmagan savollar

1. Ball formulasi: hozir har odatning o'z og'irligi bor (1–10). Yetarlimi?
2. Streak chegarasi 60% — real ishlatgandan keyin qayta ko'riladi
3. Haftalik reyting dushanbadan boshlanadi
4. Sherikka xabar 22:30 da ketadi
