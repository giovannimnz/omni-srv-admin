# External Integrations

**Analysis Date:** 2026-04-19

## APIs & External Services

**Crypto Exchanges (Backend `backend/exchanges/`):**
- **Binance** — Spot & Futures trading, signals, order management
  - SDKs: `binance` v2.10.3, `binance-api-node` v0.12.7, CCXT (Python)
  - Auth: API key/secret in database, HMAC-SHA256 signing
  - WebSocket streams for live price data and order updates
- **MEXC** — Futures trading with browser automation (anti-detection)
  - SDK: CCXT (Python) + direct REST via `got-scraping`
  - Auth: Cookie-based session with browser automation (`nodriver` + Playwright)
  - Browser: Embedded Chromium at `backend/exchanges/mexc/automation/browser/`
  - Session management: `session/index.js` with encrypted vault storage, session healer
- **Bybit** — Futures trading
  - SDK: CCXT (Python)
  - Auth: API key/secret via database
- **Hyperliquid** — DEX trading
  - SDK: `@nktkas/hyperliquid` v0.32.1
  - Auth: Ed25519 wallet signing (`@noble/ed25519`)
- **BingX** — Exchange integration (scaffolded)
- **OKX** — Exchange integration (scaffolded)

**LLM / AI Services:**
- **OpenRouter** (`router.atius.com.br`) — Unified LLM routing
  - Endpoint: `https://router.atius.com.br/v1/chat/completions`
  - API key stored in `docker/config.json` (vision-mcp)
  - Models: `openai/qwen3-vl-plus` (vision)
- **Google Gemini** — via `@google/gemini-cli` v0.27.3
- **Open WebUI** — Self-hosted at `127.0.0.1:3001` (Docker)
  - Image: `ghcr.io/open-webui/open-webui:main`
  - Connected via OpenRouter proxy

**Messaging & Notifications:**
- **Telegram Bot API** — Trade alerts, bot status, admin commands
  - SDK: `node-telegram-bot-api` v0.67.0, Telegraf v4.16.3 (Node)
  - SDK: Telethon v1.42.0 (Python) — MTProto client
  - Bot control via unified-bot-launcher
- **WhatsApp** — Not directly detected

**Vision MCP:**
- **vision-mcp** (`GitHub/vision-mcp/`) — Model Context Protocol server
  - SDK: `@modelcontextprotocol/sdk` v1.26.0
  - Config: `docker/config.json` — litellm endpoint, vision model, image size limits
  - Max image: 1920x1080, timeout: 300s

## Data Storage

**Databases:**
- **PostgreSQL 17** (system cluster, port 8745)
  - Primary data store: accounts, signals, orders, bot configs
  - Connection: `.env` in `config/.env`
  - Client: `pg` v8.16.3 (Node), `asyncpg` + `psycopg2-binary` (Python)
  - Cluster: `/var/lib/postgresql/17/main`

- **MongoDB** (port 27017, replica set `rs0`)
  - Used by PM2 Web dashboard (`pm2web` database)
  - Connection: `mongodb://admin:***@atius-srv-1:27017/pm2web?replicaSet=rs0&authSource=admin`
  - Client: native MongoDB driver (via pm2.web)

- **PostgreSQL 15** (Docker, port 8746) — New API database
  - Container: `db-newapi` (postgres:15-alpine)
  - Used by NewAPI/OpenRouter proxy

- **PostgreSQL 15.7** (Docker, port 8747) — Plane app database
  - Container: `plane-app-plane-db-1`

- **PostgreSQL 16** (Docker, internal) — Paperclip databases
  - Containers: `paperclip-atius-db`, `paperclip-pers-db`

- **Valkey/Redis** v7.2.11 (Docker, internal port 6379)
  - Container: `plane-app-plane-redis-1` (valkey/valkey:7.2.11-alpine)
  - Used by Plane app for caching/queues

- **RabbitMQ** 3.13.6 (Docker, internal)
  - Container: `plane-app-plane-mq-1` (rabbitmq:3.13.6-management-alpine)
  - Used by Plane app for message queuing

- **MySQL** — `mysql2` v3.14.0 present in dependencies (specific integration, not primary)

**File Storage:**
- **MinIO** (Docker, internal port 9000)
  - Container: `plane-app-plane-minio-1`
  - Used by Plane app for document/file storage

**Caching:**
- Valkey (Redis-compatible) for Plane app
- Node.js in-memory caching for trading signals (detected in backend services)

## Authentication & Identity

**Auth Provider:**
- **Custom JWT-based SSO** — Implemented in `backend/server/api.js`
  - JWT secret required at startup (`JWT_SECRET` env var)
  - Tokens issued on login, validated via middleware
  - Frontend uses `jose` v6.1.3 for JWT handling
  - SSO enforced for Swagger docs in production

**Password Hashing:**
- **bcrypt** v6.0.0 — User password hashing

**TOTP/MFA:**
- **pyotp** v2.9.0 — Python TOTP generation (Python pyproject.toml)

## Monitoring & Observability

**Process Monitoring:**
- **PM2 Web** (`docker/pm2.web/`) — Self-hosted PM2 dashboard
  - URL: `https://pm2.atius.com.br`
  - Backend connects to MongoDB for state
  - Mounts `/var/run/docker.sock` and `~/.pm2` for real-time monitoring
  - Nginx reverse proxy inside Docker

- **PM2** systemd service (`pm2-ubuntu.service`) — Automatic startup

**Logs:**
- **Pino** + **pino-pretty** v13.0.0 — Structured logging for Fastify API
  - Level: `info` in production
  - Transport: pretty-print for human-readable output

**Error Tracking:**
- No dedicated error tracking service (Sentry, etc.) detected
- Errors logged via Pino transport

**Health Checks:**
- PM2 MEXC health verification: `verifyPm2MexcHealth.test.js`
- Session healer: automatic cookie/session recovery for MEXC

## CI/CD & Deployment

**Hosting:**
- **Oracle Cloud Infrastructure** — ARM64 instance (atius-srv-1)
- **Internal DNS:** `10.1.1.2` (Oracle VCN)
- **Domains:** `*.atius.com.br`, `*.horistic.com`

**CI Pipeline:**
- **Jenkins** (Docker, port 8085)
  - Image: custom `atius-jenkins:lts-node`
  - Workspace: mounted `/home/ubuntu/GitHub/atius`
  - Pipeline: `Jenkinsfile` with stages for deps, deterministic tests, runtime tests, live API tests
  - Docker-in-Docker enabled (security warning noted in compose)
  - Plane integration: `PLANE-INTEGRATION.md`

**Deployment:**
- **PM2** — Production process management
  - `ecosystem.config.js` — Production config
  - `ecosystem.testnet.config.js` — Testnet config
  - Apps: API (8015), Web (3015), webhook signals, bot launcher, MEXC browser workers
- **Apache2** v2.4.52 — Reverse proxy to Docker/containerized services
  - 60+ vhosts for subdomains (`api.atius.com.br`, `trade.atius.com.br`, etc.)
  - SSL via Cloudflare origin certs (`/etc/ssl/cloudflare/`)
  - `ProxyPreserveHost On`, `ProxyPass` to internal IPs/ports
- **Portainer CE** (port 9443) — Docker management UI

## Environment Configuration

**Required env vars (from `config/.env`):**
- `JWT_SECRET` — JWT signing secret (required, exits if missing)
- `NODE_ENV` — `production` or `development`
- `API_URL` / `FRONTEND_URL` — Base URLs
- `API_PORT` — 8015 (production)
- `FRONTEND_PORT` — 3015
- `SQL_DSN` — PostgreSQL connection string (NewAPI)
- `DATABASE_URI` — Python database connection
- Database credentials (PostgreSQL, MongoDB) — 58 total variables

**Secrets location:**
- `.env` files: `GitHub/atius/config/.env`
- Docker compose envs: inline in compose files (pm2.web MongoDB URI)
- SSL certs: `/etc/ssl/cloudflare/` (Cloudflare origin certs)
- SSH keys: `~/.ssh/`
- Git credentials: `~/.git-credentials`

## Webhooks & Callbacks

**Incoming:**
- **Webhook Signals** (`atius-webhook-signals` PM2 app)
  - Script: `backend/indicators/webhook/webhookSignals.js`
  - Receives trading signals from external sources
- **N8N** (Docker, port 5678) — Workflow automation
  - URL: `https://n8n.atius.com.br`
  - Webhook URL: `https://n8n.atius.com.br/`
  - Basic auth: enabled
  - Used for automated workflows and integrations

**Outgoing:**
- **Telegram Bot** — Trade alerts, status notifications to users/groups
- **Telegram MTProto** — Real-time message listening (Python Telethon)

## Docker Container Ecosystem

**Running containers (25+):**

| Container | Image | Purpose | Ports |
|-----------|-------|---------|-------|
| `portainer` | portainer-ce | Docker management | 9443, 9001 |
| `jenkins` | atius-jenkins:lts-node | CI/CD | 8085, 50000 |
| `cloudbeaver` | dbeaver/cloudbeaver | DB admin UI | 8000 |
| `open-webui` | open-webui:main | AI chat UI | 3001→8080 |
| `new-api` | calciumion/new-api | LLM proxy/router | internal |
| `db-newapi` | postgres:15-alpine | NewAPI database | 8746 |
| `pm2web-backend` | custom | PM2 monitoring backend | internal |
| `pm2web-dashboard` | custom | PM2 web dashboard | 3000 |
| `paperclip-atius` | paperclip:latest | AI agent (atius) | 31800→3100 |
| `paperclip-pers` | paperclip:latest | AI agent (personal) | 31810→3100 |
| `plane-app-*` | plane v1.2.1 | Project management | 8080, 8090 |
| `model-detailed` | python:3.12-slim | LLM metadata proxy | 3300 |
| `plane-app-plane-mq-1` | rabbitmq:3.13.6 | Message queue | internal |
| `plane-app-plane-redis-1` | valkey:7.2.11 | Cache/queue | internal |
| `plane-app-plane-minio-1` | minio:latest | Object storage | internal |

**Docker Networks:**
- `atius` bridge network (172.28.0.0/16) — Shared service discovery
- `pm2web-network` — PM2 web internal
- `newapi-internal` + `atius-shared` — NewAPI stack

## Security Infrastructure

**Firewall (iptables):**
- Allowed inbound: 3399, 3389 (RDP), 443, 80, 5000, 5050, 8000, 8745, 8080, 27813, 28497
- Docker chains: DOCKER, DOCKER-ISOLATION, DOCKER-USER
- Libvirt chains for VM networking

**Antivirus:**
- ClamAV present (freshclam service available, masked)
- Scripts: `antivirus/scan.sh`, `antivirus/monitor.sh`

**Remote Access:**
- **SSH** — OpenBSD Secure Shell server (port 22)
- **RDP/VNC** — xrdp (ports 3389, 3399), NoMachine server
- **AnyDesk** — Remote desktop service
- **Cockpit** — Web-based server management

**VPN:**
- No WireGuard detected (configs absent, service not active)
- Oracle Cloud VCN provides internal networking (10.1.1.x range)

---

*Integration audit: 2026-04-19*
