#!/usr/bin/env bash
# Serverni GitHub'dagi oxirgi holatga keltiradi.
#
#   ssh -i ~/.ssh/growth-up ubuntu@158.178.149.128 /opt/growth-up/deploy/update.sh
#
# Frontend va bog'liqliklar faqat haqiqatan o'zgargan bo'lsa qayta quriladi —
# har safar `npm ci` qilish 1 GB xotirali serverda bekorga vaqt oladi.
#
# Baza migratsiyalari har safar ishga tushadi (ular idempotent) va oldidan
# zaxira olinadi. Alembic yo'q: model o'zgarsa `scripts/migrate_NNN_*.py`
# yoziladi, shu skript uni o'zi topib bajaradi.

set -euo pipefail

APP_DIR="/opt/growth-up"
cd "$APP_DIR"

ESKI=${GROWTH_ESKI:-$(git rev-parse HEAD)}
git pull -q origin main
YANGI=$(git rev-parse HEAD)

# **Skript o'zini yangilagan bo'lishi mumkin.** Bash faylni bo'lak-bo'lak
# o'qiydi va o'qilgan joyni eslab qoladi; `git pull` faylni almashtirgach
# o'sha joy boshqa matnga to'g'ri keladi. Natijasi jim va yomon: 2026-08-15
# da shu sabab yangi qo'shilgan migratsiya qadami umuman bajarilmadi va
# ilova yangi kod bilan eski sxemada ko'tarildi.
#
# Shuning uchun yangilanish bo'lsa — yangi nusxani boshidan ishga tushiramiz.
# `GROWTH_ESKI` ikki vazifani bajaradi: cheksiz aylanishni to'xtatadi va
# "qaysi commitdan keldik" ma'lumotini yangi nusxaga uzatadi.
if [ "$ESKI" != "$YANGI" ] && [ -z "${GROWTH_ESKI:-}" ]; then
    export GROWTH_ESKI="$ESKI"
    exec "$APP_DIR/deploy/update.sh" "$@"
fi

# `--force`: kod allaqachon tortib olingan bo'lsa ham hammasini qayta quradi.
# (Qo'lda `git pull` qilib, keyin shu skriptni chaqirish oson xato.)
if [ "$ESKI" = "$YANGI" ] && [ "${1:-}" != "--force" ]; then
    echo "Yangilanish yo'q — kod allaqachon oxirgi holatda ($(git log --oneline -1))"
    echo "Baribir qayta qurish kerak bo'lsa: $0 --force"
    exit 0
fi

if [ "${1:-}" = "--force" ]; then
    echo "--force: hamma narsa qayta quriladi"
    OZGARGAN=$(git ls-files)
fi

if [ "$ESKI" != "$YANGI" ]; then
    echo "Yangilanish: $(git log --oneline "$ESKI..$YANGI" | wc -l) ta commit"
    git log --oneline "$ESKI..$YANGI"
    echo
    OZGARGAN=$(git diff --name-only "$ESKI" "$YANGI")
fi

if echo "$OZGARGAN" | grep -q "^requirements.txt"; then
    echo "→ Python bog'liqliklari yangilanyapti"
    .venv/bin/pip install -q -r requirements.txt
fi

if echo "$OZGARGAN" | grep -q "^web/"; then
    echo "→ Mini App qayta qurilyapti"
    cd web
    if echo "$OZGARGAN" | grep -q "^web/package"; then
        npm ci --silent
    fi
    npm run build 2>&1 | tail -2
    cd "$APP_DIR"
fi

if echo "$OZGARGAN" | grep -q "^deploy/growth-up.service"; then
    echo "→ systemd xizmati yangilanyapti"
    sudo cp deploy/growth-up.service /etc/systemd/system/
    sudo systemctl daemon-reload
fi

if echo "$OZGARGAN" | grep -q "^deploy/Caddyfile"; then
    echo "→ DIQQAT: Caddyfile o'zgargan. Domenni tekshirib, qo'lda ko'chiring:"
    echo "   sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy"
fi

# Migratsiyalar ilova TO'XTAGANDA bajariladi: ular jadval qayta qurishi
# mumkin (`DROP` + `RENAME`), ishlab turgan process esa o'sha paytda bazani
# ushlab turadi. Frontend yuqorida, ilova hali tirik ekan qurildi — shuning
# uchun to'xtash vaqti bir necha soniya bo'ladi.
echo "→ Ilova to'xtatilyapti"
sudo systemctl stop growth-up

# Migratsiyadan OLDIN zaxira. Kunlik zaxira yetarli emas: xato migratsiya
# bilan o'sha zaxira orasida bir kunlik ma'lumot bo'lishi mumkin.
echo "→ Migratsiyadan oldingi zaxira"
deploy/backup.sh

# Hammasi ketma-ket ishga tushiriladi — har biri idempotent, ya'ni allaqachon
# bajarilgani hech narsa qilmaydi. "Qaysi birini ishga tushirgan edim" degan
# savol umuman tug'ilmasligi uchun shunday.
for MIG in $(ls scripts/migrate_*.py 2>/dev/null | sort); do
    MODUL="scripts.$(basename "$MIG" .py)"
    echo "→ $MODUL"
    .venv/bin/python -m "$MODUL"
done

echo "→ Ilova ishga tushirilyapti"
sudo systemctl start growth-up
sleep 6

if systemctl is-active --quiet growth-up; then
    curl -sf --max-time 10 http://127.0.0.1:8000/api/health > /dev/null \
        && echo "TAYYOR — ilova javob beryapti" \
        || { echo "XATO: xizmat ishlayapti, lekin API javob bermayapti"; exit 1; }
else
    echo "XATO: xizmat ko'tarilmadi. Sabab:"
    sudo journalctl -u growth-up -n 20 --no-pager
    exit 1
fi
