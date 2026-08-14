# Serverga o'rnatish

Oracle Cloud Always Free (Ubuntu 24.04) uchun. Bir marta bajariladi,
keyingi yangilanishlar — pastdagi «Yangilash» bo'limi.

## 0. Nima bo'ladi

```
Telegram ──► Caddy (443, HTTPS)  ──►  run.py (127.0.0.1:8000)
                domen: DuckDNS         ├── bot (polling)
                                       ├── API + Mini App
                                       └── eslatma sikli
                                              │
                                        data/growth.db  ──► kunlik zaxira
```

Ilova **tashqariga ochilmaydi**: faqat `127.0.0.1:8000` da tinglaydi,
tashqi so'rovlar Caddy orqali keladi.

## 1. Ulanish

```bash
ssh -i ~/.ssh/growth-up ubuntu@SERVER_IP
```

## 2. Portlarni ochish — ikki joyda

Oracle'da bu eng ko'p vaqt oldiradigan qadam, chunki **ikkita** to'siq bor:

1. **VCN Security List** (konsolda): Networking → Virtual Cloud Networks →
   subnet → Security List → Ingress rules: `0.0.0.0/0` uchun TCP 80 va 443.
2. **Serverning o'z iptables'i** (Ubuntu image'da yopiq turadi):

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

Faqat birinchisini qilib, ikkinchisini unutish — eng tez-tez uchraydigan xato.

## 3. Kerakli dasturlar

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git sqlite3 caddy
```

Caddy `apt` da bo'lmasa: <https://caddyserver.com/docs/install#debian-ubuntu-raspbian>

## 4. Kodni olish

```bash
sudo mkdir -p /opt/growth-up && sudo chown ubuntu:ubuntu /opt/growth-up
git clone https://github.com/Quvonchbek-man/growth-up.git /opt/growth-up
cd /opt/growth-up
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 5. `.env` — serverda qo'lda yoziladi

Repoda yo'q va bo'lmasligi ham kerak. `.env.example` dan nusxa olib
to'ldiring; `WEBAPP_URL` — DuckDNS domeningiz:

```bash
cp .env.example .env && nano .env
```

Majburiylari: `BOT_TOKEN`, `SUPER_ADMIN_IDS`, `WEBAPP_URL=https://SIZNING.duckdns.org`,
`CHECK_INIT_DATA=true`, `CORS_ORIGINS=` (bo'sh).

## 6. Mini App'ni qurish

Serverda Node kerak bo'ladi:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
cd /opt/growth-up/web && npm ci && npm run build
```

`web/dist` repoda yo'q (`.gitignore` da) — shuning uchun har yangilanishdan
keyin qayta qurish kerak.

## 7. Bazani ko'chirish (ixtiyoriy)

Uy kompyuteridagi tarixni saqlab qolish uchun, **ilova to'xtatilgan holda**:

```bash
scp -i ~/.ssh/growth-up data/growth.db ubuntu@SERVER_IP:/opt/growth-up/data/
```

Yo'q bo'lsa `python -m scripts.init_db` bo'sh baza yaratadi.

## 8. Xizmat sifatida ishga tushirish

```bash
sudo cp /opt/growth-up/deploy/growth-up.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growth-up
journalctl -u growth-up -f          # log'lar
```

## 9. HTTPS

```bash
sudo cp /opt/growth-up/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile       # domenni o'zingiznikiga almashtiring
sudo systemctl reload caddy
```

Tekshirish: `curl https://SIZNING.duckdns.org/api/health`

## 10. Zaxira

```bash
chmod +x /opt/growth-up/deploy/backup.sh
crontab -e
# 0 3 * * * /opt/growth-up/deploy/backup.sh >> /var/log/growth-backup.log 2>&1
```

---

## Yangilash

```bash
cd /opt/growth-up
git pull
.venv/bin/pip install -r requirements.txt     # bog'liqlik o'zgargan bo'lsa
cd web && npm ci && npm run build              # frontend o'zgargan bo'lsa
sudo systemctl restart growth-up
```

## Nosozlik

| Belgi | Qayerga qarash |
|---|---|
| Mini App ochilmaydi | `curl https://DOMEN/api/health` — 200 bermasa Caddy yoki portlar |
| Bot javob bermaydi | `journalctl -u growth-up -n 50` |
| Eslatma kelmadi | Server vaqti va `.env` dagi `TIMEZONE` |
| 502 Bad Gateway | Ilova o'lgan: `systemctl status growth-up` |
