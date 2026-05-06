# Technology Stack

**Analysis Date:** 2026-04-19

## Languages

**Primary:**
- **TypeScript/JavaScript** (ES2020+) — Backend API (`GitHub/atius/backend/`), frontend (`GitHub/atius/frontend/`), Horistic (`GitHub/horistic/`), pm2.web (`docker/pm2.web/`)
- **Python** 3.11+ — Backtesting, data analysis, MEXC browser automation, trading signal processing (`GitHub/atius/backend/`, `GitHub/horistic/`)

**Secondary:**
- **Bash** 5.x — Infrastructure scripts (`atius-srv/setup.sh`, `start.sh`, `restart-containers.sh`, `install-chromium.sh`)

## Runtime

**Environment:**
- **Node.js** v24.13.1 (managed via NVM 0.39.7, default alias)
- **npm** 11.8.0
- **Python** 3.10.12 (system) / 3.11 (via `uv` at `~/.local/bin/uv` for project use)
- Lockfile: `package-lock.json` present; `uv.lock` present for Python

**Package Manager:**
- npm for JavaScript/TypeScript
- `uv` for Python (pinned to 3.11 in `.python-version`)

## Frameworks

**Core Backend:**
- **Fastify** v5.7.1 — Primary API framework (`backend/server/api.js`) with plugins for CORS, cookies, Helmet, rate-limit, static, Swagger
- **Express** v5.1.0 — Also present in dependencies (legacy/auxiliary routes)
- **Uvicorn** (via pyproject.toml) — ASGI server for Python FastAPI services

**Core Frontend:**
- **Next.js** v14.2.29 — React SSR/SSG (`GitHub/atius/frontend/`)
- **React** v18.2.0 — UI framework
- **Tailwind CSS** — Styling with `tailwind.config.js`
- **shadcn/ui** — Component library (Radix UI primitives)
- **Recharts** — Charting/data visualization

**Python Stack:**
- **FastAPI** v0.135.3 — Python REST API (`pyproject.toml`)
- **Pandas** v2.3.3 — Data analysis and processing
- **NumPy** <2 — Numerical computing
- **CCXT** v4.5.46 — Crypto exchange unified API
- **VectorBT** v0.28.2 — Algorithmic trading backtesting
- **Lightweight Charts** v2.1 — Trading chart visualization

**Process Management:**
- **PM2** v6.0.14 — Process manager (`ecosystem.config.js`) with 10+ app instances across API, frontend, webhook signals, bot launchers, browser automation

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
