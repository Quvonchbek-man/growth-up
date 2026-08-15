"""Foydalanuvchiga ko'rinadigan barcha matnlar.

Ohang: qisqa, do'stona, buyruqbozliksiz. Bu ilova har kuni ikki marta
xabar yuboradi — quruq yoki dag'al matn bir haftada blokka olib keladi.
"""

from __future__ import annotations

# ─── Boshlanish ──────────────────────────────────────────────────────────────

START_NEW = (
    "Salom, {name}! 👋\n\n"
    "Bu — <b>birgalikda rivojlanish</b> ilovasi. Ishlash tartibi oddiy:\n\n"
    "🌙 <b>Kechqurun</b> ertangi kunga reja yozasiz\n"
    "☀️ <b>Ertalab</b> bot rejani eslatadi\n"
    "✅ <b>Kun davomida</b> bajarganingizni belgilaysiz\n"
    "👀 <b>Sherigingiz</b> buni ko'rib turadi — va siz ham uni\n\n"
    "Butun gap shunda: yolg'iz o'zingizga va'da bersangiz tashlab yuborasiz, "
    "sherigingiz ko'rib turganda esa yo'q.\n\n"
    "Boshlash uchun ilovani oching 👇"
)

START_BACK = "Xush kelibsiz, {name}! Bugungi holatingizni ilovada ko'ring 👇"

HELP = (
    "<b>Qanday ishlaydi</b>\n\n"
    "• <b>Odat</b> — takrorlanadigan ish (sport, kitob). Bir marta yaratasiz, "
    "har kuni o'zi paydo bo'ladi.\n"
    "• <b>Vazifa</b> — faqat shu kunga tegishli bir martalik ish.\n"
    "• <b>Streak</b> — ketma-ket muvaffaqiyatli kunlar. Kun muvaffaqiyatli "
    "hisoblanadi, agar rejaning kamida {pct}% i bajarilsa.\n"
    "• <b>Ball</b> — har bajarilgan vazifa uchun. Haftalik reyting shundan chiqadi.\n\n"
    "<b>Maxfiylik.</b> Har odat uchun alohida sozlaysiz: sherik nomini ham "
    "ko'radi, yoki faqat foizga qo'shiladi, yoki umuman ko'rmaydi. "
    "Yashirin vazifalar jamoa reytingiga kirmaydi.\n\n"
    "<b>Buyruqlar</b>\n"
    "/start — ilovani ochish\n"
    "/jamoa — taklif kodi va sheriklar\n"
    "/qoshil KOD — jamoaga qo'shilish\n"
    "/bugun — bugungi reja\n"
    "/help — shu yordam"
)

# ─── Jamoa ───────────────────────────────────────────────────────────────────

GROUP_INFO = (
    "<b>{group_name}</b>\n\n"
    "Taklif kodi: <code>{code}</code>\n\n"
    "Sherigingizga shu kodni yuboring. U botni ochib "
    "<code>/qoshil {code}</code> deb yozsa, jamoaga qo'shiladi.\n\n"
    "{members_block}"
)

GROUP_INFO_MEMBER = (
    "<b>{group_name}</b>\n\n"
    "Jamoa sardori: {owner}\n"
    "Yangi odam qo'shish uchun taklif kodini sardordan so'rang.\n\n"
    "{members_block}"
)

GROUP_MEMBERS_TITLE = "A'zolar:"
GROUP_ALONE = (
    "Hozircha jamoada yolg'izsiz. Ilovaning butun ma'nosi sherikda — "
    "kodni yuboring 🙂"
)

JOIN_OK = (
    "✅ <b>{group_name}</b> jamoasiga qo'shildingiz!\n\n"
    "Endi bir-biringizning rejalaringizni ko'rasiz. "
    "Birinchi qadam — ertangi kunga reja yozish 👇"
)
JOIN_USAGE = "Kodni ham yozing: <code>/qoshil ABC123</code>"
JOIN_ALREADY = "Siz allaqachon <b>{group_name}</b> jamoasidasiz."
PARTNER_JOINED = "🎉 <b>{name}</b> jamoangizga qo'shildi! Endi bir-biringizni ko'rasiz."

REMOVED_FROM_GROUP = (
    "Siz <b>{group_name}</b> jamoasidan chiqarildingiz.\n\n"
    "Rejalaringiz, odatlaringiz va statistikangiz o'z joyida qoldi. "
    "Yangi taklif kodi bilan boshqa jamoaga qo'shilishingiz mumkin."
)
MEMBER_REMOVED = "<b>{name}</b> jamoadan chiqarildi."

PARTNER_LEFT = (
    "<b>{name}</b> <b>{group_name}</b> jamoasidan chiqdi.\n\n"
    "Uning rejalari endi sizga ko'rinmaydi. Yangi sherikni taklif kodi bilan "
    "chaqirishingiz mumkin."
)
YOU_ARE_OWNER_NOW = (
    "Endi jamoa sardori sizsiz: taklif kodi va a'zolarni boshqarish sizda."
)
YOU_LEFT_GROUP = (
    "Siz <b>{group_name}</b> jamoasidan chiqdingiz.\n\n"
    "Rejalaringiz, odatlaringiz va statistikangiz o'z joyida qoldi. "
    "Yangi taklif kodi bilan boshqa jamoaga qo'shilishingiz mumkin."
)

# ─── Eslatmalar ──────────────────────────────────────────────────────────────

PLAN_REMINDER = (
    "🌙 <b>Ertangi kun uchun reja</b>\n\n"
    "Odatlaringiz avtomatik qo'shiladi — faqat qo'shimcha vazifalarni yozing "
    "va rejani tasdiqlang.\n\n"
    "Bu 2 daqiqa oladi, lekin ertangi kuningizni belgilaydi."
)

PLAN_REMINDER_DONE = "🌙 Ertangi reja allaqachon tayyor. Zo'r! Ko'rish uchun ilovani oching."

DIGEST_HEADER = "☀️ <b>Bugungi reja</b> — {count} ta ish\n"
DIGEST_EMPTY = (
    "☀️ Bugunga reja yo'q.\n\n"
    "Kechqurun reja yozish odatini boshlang — ertalab nima qilishni bilib "
    "turish kunni butunlay o'zgartiradi."
)
DIGEST_FOOTER = "\nBajarganingizni shu yerdan belgilang 👇"

NAG_PARTNER = (
    "👀 <b>{name}</b> hali ertangi rejani kiritmagan.\n\n"
    "Bir turtki bering — bu bir bosish, lekin ishlaydi."
)

# Vaqti belgilangan ish boshlanishidan oldin. Qisqa bo'lishi shart: kun
# davomida keladi va uzun matn bezovta qilishga aylanadi.
TASK_SOON = "⏰ <b>{lead} daqiqadan keyin:</b> {title}\n{range}\n\nUnutmang 🙂"
TASK_SOON_NOW = "⏰ <b>Hozir boshlanadi:</b> {title}\n{range}"

ASK_REASON_HEADER = (
    "🌙 Kecha <b>{count} ta</b> ish bajarilmadi.\n\n"
    "Har biri uchun sababni belgilang. Bu ayblov emas — bir oydan keyin "
    "shu ma'lumot nima aslida xalaqit berayotganini ko'rsatadi."
)
ASK_REASON_TASK = "❓ <b>{title}</b>\nNega bajarilmadi?"
REASON_SAVED = "Yozib oldim: {label}"

# ─── Turtki va reaksiya ──────────────────────────────────────────────────────

NUDGE_SENT = "👉 Turtki yuborildi."
NUDGE_LIMIT = "Bugun bu odamga yetarlicha turtki berdingiz 🙂 Ertaga davom etamiz."
NUDGE_RECEIVED = "👉 <b>{name}</b> sizga turtki berdi!\n\n{comment}"
NUDGE_DEFAULT_COMMENT = "Rejani kiritishni unutmang 🙂"
NUDGE_SELF = "O'zingizga turtki bera olmaysiz 🙂"

# ─── Vazifalar ───────────────────────────────────────────────────────────────

TASK_DONE = "✅ Bajarildi: {title}"
TASK_UNDONE = "↩️ Belgi olib tashlandi: {title}"
TASK_NOT_FOUND = "Bu vazifa topilmadi — ehtimol o'chirilgan."
DAY_PROGRESS = "\n\n<b>{done}/{planned}</b> bajarildi · {pct}% · {score} ball"

STREAK_KEPT = "🔥 Streak: {n} kun"
STREAK_LOST = "💔 Streak uzildi. Bugundan yangisini boshlaymiz."

# ─── Kun yakuni ──────────────────────────────────────────────────────────────

DAY_CLOSED_GOOD = (
    "🌙 <b>Kun yakunlandi</b>\n\n"
    "{done}/{planned} bajarildi ({pct}%) · {score} ball\n"
    "🔥 Streak: {streak} kun\n\n"
    "Yaxshi ish. Ertangi reja tayyormi?"
)
DAY_CLOSED_WEAK = (
    "🌙 <b>Kun yakunlandi</b>\n\n"
    "{done}/{planned} bajarildi ({pct}%) · {score} ball\n\n"
    "Bo'ladigan gap. Muhimi — ertaga qaytish."
)

# ─── Admin (faqat SUPER_ADMIN_IDS) ───────────────────────────────────────────

ADMIN_REPORT = (
    "🛠 <b>Admin panel</b> — {date}\n\n"
    "👥 <b>Odamlar</b>\n"
    "Jami: <b>{total}</b> · bloklagan: {blocked}\n"
    "Yangi: bugun {new_today} · 7 kun {new_7d} · 30 kun {new_30d}\n\n"
    "🤝 <b>Sherik</b>\n"
    "Sherigi bor: <b>{with_partner}</b>\n"
    "Yolg'iz: <b>{alone}</b>\n"
    "Jamoalar: {groups} (2+ kishilik: {paired_groups})\n\n"
    "⚡ <b>Faollik</b>\n"
    "Bugun reja tasdiqlagan: {submitted_today}\n"
    "7 kunda faol: {active_7d}\n"
    "7 kunda ✅ bosgan: {done_7d}\n\n"
    "📈 <b>Natija (7 kun)</b>\n"
    "O'rtacha bajarilish: {avg_pct_7d}%\n"
    "Bajarilgan vazifa: {tasks_done_7d}\n"
    "Eng uzun streak: {best_streak} kun\n\n"
    "🔔 Bugun yuborilgan eslatma: {reminders_today}\n\n"
    "Ommaviy xabar uchun /xabar"
)

ADMIN_RECENT_TITLE = "\n🆕 <b>Oxirgi qo'shilganlar</b>"

BROADCAST_ASK = (
    "📣 <b>Ommaviy xabar</b>\n\n"
    "Yubormoqchi bo'lgan matnni yozing. Telegramning o'z belgilashi "
    "(qalin, kursiv, havola) saqlanadi.\n\n"
    "Bekor qilish uchun /bekor"
)
BROADCAST_PREVIEW = (
    "☝️ Xabar shu ko'rinishda <b>{count}</b> kishiga boradi.\n\n"
    "Yuboraymi?"
)
BROADCAST_BAD_TEXT = (
    "❌ Bu xabarni yuborib bo'lmadi: {error}\n\n"
    "Ehtimol juda uzun (4096 belgidan ko'p). Qisqartirib qayta yuboring "
    "yoki /bekor"
)
BROADCAST_SENDING = "📤 Yuborilyapti — {count} kishi. Biroz vaqt oladi…"
BROADCAST_DONE = (
    "✅ <b>Tayyor</b>\n\n"
    "Yuborildi: <b>{sent}</b>\n"
    "Bloklagan: {blocked}\n"
    "Xato: {failed}"
)
BROADCAST_CANCELLED = "Bekor qilindi — hech kimga xabar ketmadi."
BROADCAST_EMPTY = "Xabar bo'sh. Matn yozing yoki /bekor"

# ─── Xatolar ─────────────────────────────────────────────────────────────────

NO_WEBAPP_URL = (
    "⚠️ Mini App manzili sozlanmagan (<code>WEBAPP_URL</code>).\n"
    "Tunnel ishga tushirilib, <code>.env</code> ga manzil yozilishi kerak."
)
GENERIC_ERROR = "Nimadir xato ketdi. Birozdan keyin qayta urinib ko'ring."
UNKNOWN_COMMAND = "Bunday buyruq yo'q. /help ni bosing."

# ─── Tugma yozuvlari ─────────────────────────────────────────────────────────

BTN_OPEN_APP = "📱 Ilovani ochish"
BTN_PLAN_TOMORROW = "🌙 Ertangi reja"
BTN_TODAY = "☀️ Bugungi reja"
BTN_TEAM = "👥 Jamoa"
BTN_STATS = "📊 Statistika"
BTN_NUDGE = "👉 Turtki ber"
BTN_UNDO = "↩️ Bekor qilish"
BTN_BROADCAST_SEND = "📣 Ha, yuborilsin"
BTN_BROADCAST_CANCEL = "Bekor"

REASON_BUTTONS = [
    ("tired", "😴 Charchadim"),
    ("no_time", "⏰ Vaqt yetmadi"),
    ("forgot", "🤦 Unutdim"),
    ("not_important", "🤷 Muhim emas edi"),
]
