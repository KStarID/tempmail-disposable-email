# Disposable Email — Disposable Inbox Service

Generate temporary email addresses that auto-expire. Temp-mail style, self-hosted.

## Architecture

```
Internet  ──►  Postfix SMTP (port 25/1025)
                    │
                    │ catch-all *@kstarid.cloud → local user "tempmail"
                    ▼
              mailbox_command
                    │
                    ▼
              Python catcher.py (reads stdin, parses email)
                    │
                    │ HTTP POST /api/internal/incoming
                    ▼
              FastAPI backend ──► SQLite (./data/tempmail.db)
                    │
                    │ /api/inbox/{addr}/messages
                    ▼
              Next.js frontend (port 3000)
```

## Quick Start (Local Development)

```bash
# Start all services
docker compose up -d --build

# Open UI
start http://localhost:3000

# Check logs
docker compose logs -f postfix
docker compose logs -f backend
```

### Send a test email (from inside Docker network)

```bash
# Get an inbox first
curl -X POST http://localhost:8000/api/inbox/create
# Returns: {"id":1,"address":"abc123@kstarid.cloud",...}

# Send test email via SMTP (using Python or telnet)
docker compose exec postfix bash -c '
  apt-get update && apt-get install -y msmtp
  # ... or use python
'
```

Easiest: use Python:
```python
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["From"] = "test@gmail.com"
msg["To"] = "abc123@kstarid.cloud"
msg["Subject"] = "Hello from test"
msg.set_content("This is a test message body")

with smtplib.SMTP("localhost", 1025) as s:
    s.send_message(msg)
```

Then refresh the UI — message appears within 5 seconds.

## Services & Ports

| Service | Port (host) | Description |
|---------|-------------|-------------|
| Frontend | 3000 | Next.js UI |
| Backend | 8000 | FastAPI REST API + OpenAPI docs at `/docs` |
| SMTP | 1025 | Postfix SMTP (mapped from container port 25) |

## Project Structure

```
disposable-email/
├── docker-compose.yml          # Orchestrates all services
├── data/                       # SQLite DB persisted here
├── mail-server/
│   ├── postfix/                # Custom Postfix image with catch-all
│   │   ├── Dockerfile          # Builds boky/postfix + our configs
│   │   ├── main.cf             # Postfix config (catch-all routing)
│   │   ├── master.cf           # Postfix services (smtp, local, virtual)
│   │   └── virtual_regexp      # Catch-all pattern: *@kstarid.cloud
│   └── catcher/catcher.py      # Receives email from Postfix stdin
├── backend/                    # FastAPI app
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI entry
│       ├── routes.py           # All API endpoints
│       ├── services.py         # Business logic
│       ├── models.py           # SQLModel DB models
│       └── database.py         # SQLite engine + init
└── frontend/                   # Next.js UI
    ├── Dockerfile
    ├── package.json
    └── app/
        ├── page.tsx            # Main temp-mail UI
        ├── layout.tsx
        └── globals.css
```

## API Endpoints

### Public
- `POST /api/inbox/create` — create random inbox
- `GET  /api/inbox/{addr}` — get inbox details (refreshes expiry)
- `GET  /api/inbox/{addr}/messages` — list messages
- `GET  /api/inbox/{addr}/messages/{id}` — read full message
- `DELETE /api/inbox/{addr}` — manually expire inbox

### Internal (called by catcher.py)
- `POST /api/internal/incoming` — receive parsed email
- `POST /api/internal/cleanup` — soft-delete expired inboxes

## Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `DOMAIN` | `kstarid.cloud` | Catch-all domain |
| `INBOX_TTL_MINUTES` | `60` | Inbox lifetime |
| `DATABASE_URL` | `sqlite:////data/tempmail.db` | DB connection |

## Production Deployment to VPS (TODO)

When ready for production:
1. Upgrade VPS to 4GB RAM minimum
2. Verify port 25 inbound is open from VPS provider
3. Set PTR record: `VPS_IP → mail.kstarid.cloud` (HPanel: tidak bisa; minta provider)
4. Configure DNS at HPanel:
   - `A    mail.kstarid.cloud → VPS_IP`
   - `MX   kstarid.cloud → 10 mail.kstarid.cloud`
   - `TXT  kstarid.cloud → "v=spf1 mx ~all"`
5. Add Let's Encrypt SSL for SMTP
6. Remove `mynetworks` whitelist in main.cf (lock down to docker network only)
7. Add rate limiting + DKIM signing

## Limitations (Dev Mode)

- Port 25 inbound from internet NOT tested (VPS limitation)
- No anti-spam (Rspamd/ClamAV)
- No SSL/TLS for SMTP (uses snakeoil cert)
- No rate limiting
- Catch-all means anyone can use random addresses — could attract abuse

## License

MIT
