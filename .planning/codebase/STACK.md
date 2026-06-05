# Technology Stack

**Analysis Date:** 2026-06-05

## Languages

**Primary:**
- **Python** 3.10+ — CLI tooling (omni CLI, fork-sync lib, Click framework)
- **Bash** 5.x — Setup scripts, deployment helpers, automation

## Runtime

**Environment:**
- **Python** 3.10.12 (system) managed via `uv`
- **Node.js** (for horus-spec-driven CLI wrapper via bin/install.js)

**Package Manager:**
- `pip` (setuptools) for Python packages
- `uv` for project-level Python management

## Frameworks

**CLI Framework:**
- **Click** v8.0+ — CLI framework for Python (both omni and fork-sync)
- **prompt-toolkit** v3.0+ — REPL mode (fork-sync)
- **Rich** v13.0+ — Terminal output formatting (fork-sync)
- **PyYAML** v6.0+ — YAML config parsing

**No application frameworks** — omni-srv-admin is a server administration repo, not a web app.

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| click | ^8.0 | CLI framework |
| prompt-toolkit | ^3.0 | REPL mode |
| rich | ^13.0 | Terminal formatting |
| pyyaml | ^6.0 | Config parsing |
| setuptools | — | Package installation |

## Infrastructure

| Tool | Version | Purpose |
|------|---------|---------|
| iptables | — | Firewall rules |
| systemd | — | Service management |
| crontab | — | Scheduled tasks |
| rsync | — | File sync/backup |


**Testing:**
- **Jest** v30.0.5 — Backend unit/integration tests
- **Playwright** v1.58.2 — E2E tests and browser automation (MEXC exchange)
- **Mocha** v11.7.5 — Alternative test runner
- **Chai** v5.2.1 — Assertion library

**Build/Dev:**
- **Turbo** v2.1.2 — Monorepo build system (pm2.web)
- **TypeScript** — strict mode, `tsconfig.json` with path aliases (`@/*`)
- **Pyright** v1.1.405 — Python type checking
- **Nodemon** v3.0.1 — Dev hot-reload
- **Babel** v7.28.0 — Jest transformation

## Key Dependencies

**Critical:**
- **`pg`** v8.16.3 — PostgreSQL client for Node.js (accounts, signals, bot configs)
- **`mysql2`** v3.14.0 — MySQL client (legacy/specific integrations)
- **`asyncpg`** + **`psycopg2-binary`** — Python PostgreSQL drivers
- **`bcrypt`** v6.0.0 — Password hashing
- **`jsonwebtoken`** v9.0.2 — JWT auth tokens
- **`jose`** v6.1.3 — Frontend JWT handling
- **`ethers`** v6.16.0 — Ethereum/cryptography utilities
- **`@noble/ed25519`** v2.3.0 — Ed25519 signing
- **`tweetnacl`** v1.0.3 — Cryptographic library

**Exchange SDKs:**
- **`binance`** v2.10.3 + **`binance-api-node`** v0.12.7 — Binance exchange
- **`@nktkas/hyperliquid`** v0.32.1 — Hyperliquid exchange
- **`ccxt`** v4.5.46 — Unified crypto exchange interface (Python)
- **`got-scraping`** v4.2.1 — Web scraping for exchange auth

**Browser Automation:**
- **`playwright-extra`** v4.3.6 — Stealth browser automation
- **`puppeteer-extra-plugin-stealth`** v2.11.2 — Anti-detection for MEXC exchange
- **`nodriver`** v0.48.1 — Python browser automation (MEXC)
- Embedded **Chromium** at `backend/exchanges/mexc/automation/browser/bin/chromium`

**Communication:**
- **`ws`** v8.5.0 — WebSocket (bot status, real-time signals)
- **`node-telegram-bot-api`** v0.67.0 — Telegram notifications
- **`telegraf`** v4.16.3 — Telegram Bot framework
- **`telegram`** v2.20.10 — MTProto Telegram client (Python: Telethon)
- **`node-cron`** v4.2.1 — Scheduled tasks
- **`node-schedule`** v2.1.1 — Cron-like job scheduling
- **`msgpack-lite`** v0.1.26 — Binary serialization

**API Docs:**
- **`@fastify/swagger`** v9.5.1 + **`@fastify/swagger-ui`** v5.2.3 — OpenAPI docs at `/v1/docs`

## Configuration

**Environment:**
- `.env` files in `GitHub/atius/config/.env` (58 variables)
- `dotenv` loaded at entry point (`backend/server/api.js`)
- PM2 env vars in `ecosystem.config.js` via `withNodeEnv()` and `withUvEnv()`
- Critical: `JWT_SECRET` required at startup, `API_PORT: 8015`, `FRONTEND_PORT: 3015`
- PM2 home: `~/.pm2`

**Build:**
- `start.sh` — Build/start/stop orchestration script
- `next.config.mjs` — Next.js build config
- `postcss.config.js` / `postcss.config.mjs` — CSS processing
- `tsconfig.json` (root + frontend) — TypeScript with bundler module resolution
- `pyproject.toml` — Python dependencies (uv-managed)
- `Jenkinsfile` — CI/CD pipeline

**PM2 Ecosystem (`ecosystem.config.js`):**
- `atius-api` — Fastify API on port 8015
- `atius-web` — Next.js frontend on port 3015
- `atius-webhook-signals` — Webhook signal processor
- `atius-bot-launcher` — Unified multi-exchange bot launcher
- Python worker processes via `uv` bridge

## Platform Requirements

**Development:**
- Ubuntu 22.04 (Oracle Cloud Infrastructure, ARM64/aarch64)
- Node.js 24.x via NVM
- Python 3.11 via uv
- PostgreSQL 17 (system cluster, port 8745)
- MongoDB (for PM2 web replica set)
- Docker + containerd
- Apache 2.4.52 (reverse proxy)

**Production:**
- **Hosting:** Oracle Cloud Infrastructure (atius-srv-1)
- **DNS:** Internal nameserver `10.1.1.2` (Oracle VCN)
- **Domain:** `*.atius.com.br` + `*.horistic.com` proxied via Cloudflare
- **SSL:** Cloudflare origin certs at `/etc/ssl/cloudflare/`
- **Database ports:** PostgreSQL 8745, MongoDB 27017
- **Process manager:** PM2 with systemd wrapper (`pm2-ubuntu.service`)

---

*Stack analysis: 2026-04-19*
