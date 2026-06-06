<!-- generated-by: gsd-doc-writer -->
# Server Configuration

**Host:** atius-srv-1 — `ubuntu@10.1.1.11` (WireGuard VPN)

## Environment Variables

Critical environment variables for ATS. See `~/GitHub/Atius-Capital/ats/config/.env` for the full list (58 variables).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | Yes | — | Secret key for JWT token signing — must be set at startup |
| `API_PORT` | No | 8015 | Fastify API listen port |
| `FRONTEND_PORT` | No | 3015 | Next.js frontend port |
| `NODE_ENV` | No | production | Runtime environment |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string (port 8745) |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot token for alerts |
| `EXCHANGE_API_KEY` | Per-exchange | — | Exchange API key (per exchange) |
| `EXCHANGE_SECRET` | Per-exchange | — | Exchange API secret (per exchange) |

## Config Files

| File | Purpose |
|------|---------|
| `~/GitHub/Atius-Capital/ats/config/.env` | Primary env vars for ATS (58 variables) |
| `~/GitHub/Atius-Capital/ats/ecosystem.config.js` | PM2 process definitions |
| `~/GitHub/Atius-Capital/ats/ecosystem.testnet.config.js` | PM2 testnet process definitions |
| `~/.bashrc` | Shell configuration |
| `~/.config/nvim/` | Neovim config |
| `~/.hermes/config.yaml` | Hermes Agent configuration |
| `~/docker/Atius/router-ai-atius/config.yaml` | Atius AI Router config |

## Node.js / Python Runtime

| Setting | Value |
|---------|-------|
| Node.js version | v24.13.1 (NVM 0.39.7, default alias) |
| npm version | 11.8.0 |
| Python (system) | 3.10.12 |
| Python (project) | 3.11 via `uv` |
| uv binary | `~/.local/bin/uv` |

## PM2 Configuration

PM2 home: `~/.pm2`

PM2 is wrapped by `pm2-ubuntu.service` (systemd) for auto-restart on boot.

Key ecosystem file: `~/GitHub/Atius-Capital/ats/ecosystem.config.js`

## Database Configuration

| Database | Port | Purpose |
|----------|------|---------|
| PostgreSQL 17 | 8745 | ATS main DB, signals DB, horistic DB |
| MongoDB | 27017 | PM2 web replica set |

## SSH Access

- **User:** `ubuntu`
- **Host:** `10.1.1.11` (WireGuard) or public IP
- **Auth:** Key-based (no password for SSH)
- **Sudo:** Password required; do not store password in repo docs

## Docker Networks

| Network | Purpose |
|---------|---------|
| `atius` | Main Docker network for Atius containers |
| `plane_app_network` | Plane (project management) internal network |

Container hostname for RabbitMQ (Plane stack): `plane-mq`

## Service Ports

| Service | Port | Notes |
|---------|------|-------|
| Apache (alt) | 8080, 8443 | Alternative ports, coexist with FreeIPA |
| Fastify API | 8015 | `atius-api` PM2 process |
| Next.js Frontend | 3015 | `atius-web` PM2 process |
| PostgreSQL | 8745 | System cluster |
| MongoDB | 27017 | PM2 web replica set |
| Plane (web) | 2222 | Docker mapped port |

## Hermes Agent

Config: `~/.hermes/config.yaml`

Active features:
- Telegram bot (Atius Capital Group: chat_id=-1003797723446)
- PostgreSQL memory provider (schema `hermes_memory`)
- YOLO mode (no approval prompts)
- Atius AI Router management

## Cloudflare

- Domain: `*.atius.com.br`, `*.horistic.com`
- SSL: Cloudflare origin certificates at `/etc/ssl/cloudflare/`
- DNS: Internal resolution via Oracle VCN nameserver `10.1.1.2`
