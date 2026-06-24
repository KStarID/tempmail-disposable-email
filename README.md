# 📧 TempMail - Disposable Email Service

Layanan email temporary yang bisa menerima email dari Gmail/Outlook/layanan email lainnya. Auto-expire inbox, ganti domain dari UI, deploy lokal (development) atau VPS (production).

## 🚀 Live Demo

**http://175.41.160.250** (VPS Production)

## ✨ Fitur

- **Generate inbox** — alamat email random `xxx@kstarid.cloud`
- **Terima email nyata** — dari Gmail, Outlook, dll
- **Auto-expire** — inbox hilang setelah 60 menit
- **Copy button** — dengan fallback untuk HTTP
- **Auto-refresh** — inbox update setiap 5 detik
- **Ganti domain** — dari UI Settings panel
- **Delete inbox** — hapus manual

## 🏗️ Architecture

```
Internet (Gmail/Outlook)
        ↓ MX record → VPS
   Postfix (port 25)
        ↓ catch-all → catcher.py
   FastAPI Backend (port 8000)
        ↓ SQLite database
   Static HTML Frontend (nginx port 80)
```

## 📦 Local Development (Docker)

```bash
git clone https://github.com/KStarID/tempmail-disposable-email.git
cd tempmail-disposable-email
docker compose up -d
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- SMTP: localhost:1025

> ⚠️ Local tidak bisa terima email dari internet (di belakang NAT). Hanya untuk development/testing.

## 🌐 Production Deployment (VPS)

### Prerequisites
- VPS Ubuntu 22.04+ dengan public IP
- Domain + DNS MX record pointing ke VPS

### Steps

```bash
# 1. Install dependencies
sudo apt update && sudo apt install -y postfix python3-pip nginx

# 2. Install Python packages
pip3 install fastapi uvicorn sqlalchemy aiosqlite python-multipart

# 3. Clone repo
git clone https://github.com/KStarID/tempmail-disposable-email.git /opt/tempmail
cd /opt/tempmail

# 4. Create database directory
mkdir -p /opt/tempmail/data

# 5. Configure Postfix
sudo postconf -e 'myhostname=mail.yourdomain.com'
sudo postconf -e 'mydomain=yourdomain.com'
sudo postconf -e 'virtual_alias_maps=regexp:/etc/postfix/virtual_regexp'
sudo postconf -e 'mailbox_command=/usr/local/bin/catcher.py'
sudo postconf -e 'local_recipient_maps='
sudo postconf -e 'maillog_file=/var/log/mail.log'
echo '/^(.+)@yourdomain.com$/  tempmail' | sudo tee /etc/postfix/virtual_regexp
sudo systemctl restart postfix

# 6. Configure nginx
echo 'server { listen 80; location / { proxy_pass http://127.0.0.1:8000; } }' | sudo tee /etc/nginx/sites-available/tempmail
sudo ln -sf /etc/nginx/sites-available/tempmail /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

# 7. Start backend with PM2
cd /opt/tempmail/backend
pm2 start uvicorn --name tempmail-backend -- app.main:app --host 0.0.0.0 --port 8000
pm2 save

# 8. Set DNS MX record
# Type: MX, Name: @, Value: mail.yourdomain.com, Priority: 10
# Type: A, Name: mail, Value: <your-vps-ip>
```

### DNS Records Required

| Type | Name | Value | Priority |
|------|------|-------|----------|
| A | mail | `<your-vps-ip>` | - |
| MX | @ | mail.yourdomain.com | 10 |
| TXT | @ | `v=spf1 mx ~all` | - |
| TXT | _dmarc | `v=DMARC1; p=quarantine` | - |

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── database.py      # SQLite async engine
│   │   ├── models.py        # SQLAlchemy models + Pydantic schemas
│   │   ├── services.py      # Business logic (generate address, store messages)
│   │   └── routes.py        # API routes + domain settings
│   ├── static/
│   │   └── index.html       # Single-page frontend (no build needed)
│   ├── Dockerfile
│   └── requirements.txt
├── mail-server/
│   ├── postfix/
│   │   ├── main.cf          # Postfix configuration
│   │   ├── master.cf        # Service definitions
│   │   ├── virtual_regexp   # Catch-all email rule
│   │   └── Dockerfile
│   └── catcher/
│       └── catcher.py       # Postfix → backend bridge
├── frontend/                 # Next.js (local development only)
├── docker-compose.yml
└── README.md
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/inbox/create` | Generate new inbox |
| GET | `/api/inbox/{address}` | Get inbox info |
| GET | `/api/inbox/{address}/messages` | List messages |
| GET | `/api/inbox/{address}/messages/{id}` | Get message detail |
| DELETE | `/api/inbox/{address}` | Delete inbox |
| GET | `/api/settings/domain` | Get current domain |
| POST | `/api/settings/domain` | Change domain |
| POST | `/api/internal/incoming` | Inject email (testing) |
| GET | `/api/health` | Health check |

## 📝 License

MIT
