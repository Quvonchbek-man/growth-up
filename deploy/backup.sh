#!/usr/bin/env bash
# Kunlik zaxira nusxa. `growth.db` — butun tarixning yagona nusxasi:
# odatlar, rejalar, streaklar. Yo'qolsa qaytarib bo'lmaydi.
#
# Cron'ga qo'yish (har kuni 03:00):
#   0 3 * * * /opt/growth-up/deploy/backup.sh >> /var/log/growth-backup.log 2>&1

set -euo pipefail

APP_DIR="/opt/growth-up"
BACKUP_DIR="$APP_DIR/data/backups"
KEEP_DAYS=30

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y-%m-%d_%H%M)
TARGET="$BACKUP_DIR/growth-$STAMP.db"

# `cp` emas, `sqlite3 .backup`: ilova yozayotgan paytda ham butun nusxa oladi
sqlite3 "$APP_DIR/data/growth.db" ".backup '$TARGET'"
gzip -f "$TARGET"

# Eskilarini tozalaymiz — disk to'lib qolmasin
find "$BACKUP_DIR" -name "growth-*.db.gz" -mtime +$KEEP_DAYS -delete

echo "$(date '+%F %T') — zaxira tayyor: $TARGET.gz ($(du -h "$TARGET.gz" | cut -f1))"
