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
| 00:05 | tizim | Kun yopiladi: ball, streak, bajarilmaganlar `missed` bo'ladi |
| 00:10 | siz | Bajarilmaganlar uchun sabab so'raladi |

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
SUPER_ADMIN_IDS=6588496144
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
dushanba kunlari uzilib qoladigan sport odati, sabablar taqsimoti.
Grafiklarni real ma'lumot yig'ilishini kutmasdan ko'rish uchun.

**Diqqat:** skript sizning va namunaviy sherikning mavjud ma'lumotini
o'chirib qayta yozadi.

### Eslatmalarni sinash

Kechgacha kutmasdan, botda (faqat `SUPER_ADMIN_IDS` uchun):

```
/sinov
```

Barcha eslatmalarni darhol yuboradi — kechki, ertalabki, sherikka xabar,
kun yakuni, sabab so'rovi.

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
scripts/    init_db, seed_demo
run.py      hammasi bitta processda
```

### Ikkita qoida

**1. `date` — mahalliy sana, `datetime` — UTC.** Ikkisi aralashsa streak
yarim tunda noto'g'ri uziladi va buni ikki oydan keyin sezasiz. "Hozir"
tushunchasi faqat `shared/clock.py` dan olinadi.

**2. Odat — shablon, vazifa — o'sha kunning nusxasi.** Odatni o'zgartirsangiz
o'tmish o'zgarmaydi. Odat o'chirilmaydi — arxivlanadi.

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
