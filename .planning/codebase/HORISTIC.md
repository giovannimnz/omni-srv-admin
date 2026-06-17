# Horistic Trading Platform — Codebase Map

**Analysis Date:** 2026-04-19
**Repository:** `/home/ubuntu/GitHub/Atius-Capital/horistic`
**Domain:** `horistic.com` (multi-subdomain)
**Server:** `10.1.1.1` (shared with other projects), proxied to `10.1.1.4` via Apache2

---

## 1. Technology Stack

### Languages

- **JavaScript (Node.js)** — Primary language for backend API, trading bots, and webhook services
- **TypeScript** — Frontend (Next.js app) and type definitions
- **Python 3.10** — INDAP indicator engine, backtests, and data analysis utilities (managed via `uv`)

### Runtime & Package Management

| Component | Details |
|-----------|---------|
| Node.js | Runtime for backend API + frontend |
| npm | Node package manager (root + frontend `package-lock.json` present) |
| uv | Python package manager (`pyproject.toml` + `uv.lock`) |
| Python venv | `.venv/` directory, Python 3.10.x |

### Backend Framework

| Package | Version | Purpose |
|---------|---------|---------|
| **Fastify** | ^5.7.1 | Core HTTP API server (`backend/server/api.js`) |
| @fastify/cors | ^11.2.0 | CORS with origin whitelisting |
| @fastify/helmet | ^13.0.2 | Security headers |
| @fastify/rate-limit | ^10.3.0 | Rate limiting (100 req/min) |
| @fastify/static | ^9.0.0 | Static file serving (public assets) |
| @fastify/swagger | ^9.5.1 | OpenAPI 3.0 spec generation |
| @fastify/swagger-ui | ^5.2.3 | API docs at `/v1/docs` |
| @fastify/cookie | ^11.0.2 | Cookie parsing for auth |
| **Express** | ^5.1.0 | Also present (legacy or specific routes) |

### Exchange Integrations

| Package | Purpose |
|---------|---------|
| `binance` | ^2.10.3 — Binance futures REST/WebSocket API |
| `binance-api-node` | ^0.12.7 — Binance unified API client |
| `telegraf` | ^4.16.3 — Telegram Bot API |
| `telegram` | ^2.20.10 — Telegram MTProto client |
| `node-telegram-bot-api` | ^0.67.0 — Alternative Telegram bot library |

### Database Drivers

| Package | Purpose |
|---------|---------|
| `pg` | ^8.16.3 — PostgreSQL client (Node.js, pool max: 20) |
| `mysql2` | ^3.14.0 — MySQL client (present but not actively used by main API) |
| `psycopg2-binary` | Python PostgreSQL driver |

### Frontend Stack (Next.js)

| Package | Version | Purpose |
|---------|---------|---------|
| **Next.js** | ^14.2.29 | React framework with App Router |
| React | ^18.2.0 | UI library |
| Tailwind CSS | ^3.4.17 | Styling |
| shadcn/ui | — | Component library (Radix primitives) |
| Recharts | latest | Charting/visualizations |
| Zod | ^3.24.1 | Schema validation |
| jose | ^6.1.3 | JWT handling (frontend) |

### Python Dependencies (`pyproject.toml`)

- `numpy<2`, `pandas` — Data manipulation
- `ccxt` — Unified crypto exchange library
- `vectorbt` — Backtesting framework
- `telethon` — Telegram MTProto client (Python)
- `python-dotenv` — Environment variables
- `schedule` — Task scheduling

### Auth & Security

| Package | Purpose |
|---------|---------|
| `jsonwebtoken` | ^9.0.2 — JWT token generation/verification |
| `bcrypt` | ^6.0.0 — Password hashing |
| `@noble/ed25519` | ^2.3.0 — Ed25519 signatures (Bybit) |
| `tweetnacl` | ^1.0.3 — Cryptographic utilities |
| `crypto-js` | ^4.2.0 — Client-side crypto (dev) |

### Testing

| Tool | Purpose |
|------|---------|
| Jest | ^30.0.5 — Unit/integration test runner |
| Playwright | ^1.58.2 — E2E browser testing |
| Mocha | ^11.7.5 — Alternative test framework |
| Chai | ^5.2.1 — Assertion library |
| Sinon | ^21.0.0 — Mocking/stubbing |
| Babel | ^7.28.0 — Transpilation for Jest |

---

## 2. Architecture

### High-Level Pattern

**Multi-process monorepo** — Backend API + trading bots + Python indicators + Next.js frontend, all orchestrated by PM2. Each process communicates with a shared PostgreSQL database.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Apache2 (10.1.1.4)                           │
│  trade.horistic.com → :8050 (API) + :3050 (Frontend)                │
│  backtest.horistic.com → :8050 (API) + :3050 (Frontend)             │
│  webhook.horistic.com → :8099 (Webhook service)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                        Server 10.1.1.1                              │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │ horistic-api │  │ horistic-web│  │ horistic-webhook-signals    │ │
│  │ Fastify :8050│  │ Next.js:3050│  │ HTTP server :8099           │ │
│  │ (PM2 managed)│  │ (PM2 managed)│  │ (PM2 managed)              │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────────────┘ │
│         │                │                     │                    │
│  ┌──────▼────────────────▼─────────────────────▼──────────────────┐ │
│  │                   PostgreSQL (:8745)                           │ │
│  │                   Database: horistic                           │ │
│  │   Tables: user_account, posicoes, ordens, signal_account,      │ │
│  │   posicoes_fechadas, ordens_fechadas, backtest_*, exchange_*   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────┐  ┌─────────────────────────────────────┐ │
│  │ Unified Bot Launcher │  │ horistic-divap-indicator (Python)   │ │
│  │ (PM2 managed)        │  │ (.venv/bin/python divap.py)          │ │
│  │ ┌──────────────────┐ │  │                                     │ │
│  │ │ Auto-discovers   │ │  │ Backtests, signal analysis,         │ │
│  │ │ eligible accounts│ │  │ volume/RSI divergence detection      │ │
│  │ │ from DB          │ │  │                                     │ │
│  │ └────────┬─────────┘ │  └─────────────────────────────────────┘ │
│  │          │           │                                         │
│  │  ┌───────▼──────┐    │  ┌─────────────────────────────────────┐ │
│  │  │ Bybit Bots   │    │  │  Trading Bots (per-account, PM2)    │ │
│  │  │ (per acct)   │    │  │  - Bybit: app.js per account        │ │
│  │  └──────────────┘    │  │  - Binance: orchMonitor.js per acct │ │
│  │  ┌───────┐           │  └─────────────────────────────────────┘ │
│  │  │Binance│           │                                         │
│  │  │Bots   │           │  WebSocket connections to exchanges      │ │
│  │  └───────┘           │  for real-time price/order updates       │ │
│  └──────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### PM2 Processes (`ecosystem.config.js`)

| Process Name | Script | Port | Description |
|-------------|--------|------|-------------|
| `horistic-api` | `backend/server/api.js` | :8050 (prod) / :8075 (dev) | Fastify REST API server |
| `horistic-web` | `npm start` (Next.js) | :3050 | Next.js frontend |
| `horistic-webhook-signals` | `backend/indicators/webhook/webhookSignals.js` | :8099 | TradingView → Telegram webhook receiver |
| `horistic-divap-indicator` | `.venv/bin/python divap.py` | N/A | Python DIVAP analysis engine |
| `horistic-unified-bot-launcher` | `backend/services/unified-bot-launcher.js` | N/A | Auto-discovers accounts and spawns per-account bot processes via PM2 CLI |

**Deprecated per-account processes** (commented out in `ecosystem.config.js`, replaced by unified launcher):
- `bybit-horistic-1`, `bybit-horistic-2`, `bybit-horistic-5`
- `binance-horistic-1`

**Testnet config** (`ecosystem.testnet.config.js`):
- `horistic-api-testnet` — API on port `:8075`
- `horistic-web-testnet` — Frontend on port `:3075`

### API Route Structure (`backend/server/routes/`)

```
backend/server/routes/
├── auth/           # JWT: /me, /refresh, /logout
├── token/          # Token generation
├── users/          # User management
├── admin/          # Admin-only operations
├── dashboard/      # Dashboard data + /prices/ws
├── accounts/       # Trading account CRUD
├── backtests/      # Backtest execution/results
├── orders/         # Manual order submission
├── telegram/       # Telegram integration
├── bybit/
│   ├── positions/  # Bybit position queries
│   ├── autonomous/ # Autonomous BTC trader endpoints
│   └── bot-control/  # Bot start/stop for Bybit
└── bot-control-multi/  # Multi-exchange bot control (/v1/bot/*)
```

All routes prefixed with `/v1` (except `bot-control-multi` which includes its own `/v1` prefix).

### WebSocket Endpoints

- `/v1/bybit/bot/ws` — Bot status updates (real-time)
- `/v1/dashboard/prices/ws` — Live price streaming

### Frontend App Routes (`frontend/src/app/`)

```
frontend/src/app/
├── page.tsx            # Landing page
├── layout.tsx          # Root layout
├── globals.css         # Global styles (Tailwind)
├── login/              # Login page
├── admin/              # Admin panel
├── dashboard/          # Trading dashboard
├── backtest/           # Backtest interface
├── (backtest)/         # Backtest route group
├── painel/             # Trading panel
├── sinal/              # Signal viewing
├── unauthorized/       # Access denied page
└── api/                # API route handlers (Next.js API)
```

### Frontend → Backend Communication

The Next.js app proxies `/v1/*` requests to the backend via rewrites in `next.config.mjs`:

```js
// next.config.mjs rewrites
{ source: '/v1/:path*', destination: 'http://localhost:${apiPort}/v1/:path*' }
```

This means the frontend serves as the single entry point, proxying API calls internally to avoid CORS issues.

---

## 3. Database

### PostgreSQL Configuration

| Setting | Value |
|---------|-------|
| **Host** | `10.1.1.1` (local server) |
| **Port** | `8745` (non-standard) |
| **Database** | `horistic` |
| **Driver** | `pg` (Node.js), `psycopg2` (Python) |
| **Node.js Pool** | max: 20 connections, idle: 300s, statement_timeout: 30s |
| **Python Pool** | SimpleConnectionPool, min: 1, max: 20 |
| **Launcher Pool** | max: 2 connections (dedicated lightweight pool) |

**Connection config file:** `config/.env` (symlinked to `frontend/.env`)

### Key Tables (from `conexao.js` schema auto-creation)

| Table | Purpose |
|-------|---------|
| `user_account` | Trading accounts with exchange credentials |
| `user` | System users |
| `exchange` | Exchange configuration (Binance, Bybit, etc.) |
| `posicoes` | Open positions |
| `posicoes_fechadas` | Closed position history |
| `ordens` | Active orders |
| `ordens_fechadas` | Closed order history |
| `signal_account` | Webhook signals from TradingView |
| `signal_base` | Base signal data |
| `backtest_signals` | Backtest signal data |
| `backtest_simulations` | Backtest simulation results |
| `backtest_results` | Backtest execution metadata |
| `backtest_results_monthly` | Monthly performance breakdown |
| `exchange_leverage_brackets` | Exchange leverage tier data |
| `exchange_symbols` | Symbol metadata (tick sizes, etc.) |
| `telegram_message_dispatches` | Telegram message idempotency tracking |
| `user_account_bot_status` | Bot running status per account |

### DB Architecture Pattern

- **Connection queuing** — All DB operations are serialized per (accountId + table) via `enqueueDbOperation()` to prevent deadlocks
- **Per-account isolation** — Each account gets its own queue key (`{table}_{accountId}`)
- **History archival** — Closed positions/orders moved to `_fechadas` tables via transactional `movePositionToHistory()` / `moveOrderToHistory()`
- **Credentials caching** — API credentials cached for 5 minutes (`apiCredentialsCache`)

---

## 4. Apache2 Integration

### Virtual Hosts (on `10.1.1.4`)

| Subdomain | Config File | Backend Target | Notes |
|-----------|------------|----------------|-------|
| `trade.horistic.com` | `/etc/apache2/sites-available/trade.horistic.com.conf` | :8050 (API) + :3050 (Frontend) | HTTP→HTTPS redirect. SSL config incomplete (missing cert directives in active config) |
| `backtest.horistic.com` | `/etc/apache2/sites-available/backtest.horistic.com.conf` | :8050 (API) + :3050 (Frontend) | `/api/` → :8050, `/` → :3050. HSTS enabled |
| `webhook.horistic.com` | `/etc/apache2/sites-available/webhook.horistic.com.conf` | :8099 (webhook service) | Uses Cloudflare SSL cert (`atius.com.br.pem`). ProxyTimeout: 300s. Max request: 1MB |

### Proxy Patterns

**backtest.horistic.com** (most complete config):
```apache
ProxyPass /api/ http://127.0.0.1:8050/api/
ProxyPass / http://127.0.0.1:3050/
```

**webhook.horistic.com:**
```apache
ProxyPass / http://localhost:8099/
```

### Security Headers (all vhosts)
- HSTS (max-age 31536000 / 63072000)
- X-Content-Type-Options: nosniff
- X-Frame-Options: SAMEORIGIN
- X-XSS-Protection

### SSL Certificates
- `webhook.horistic.com`: Cloudflare cert at `/etc/ssl/cloudflare/atius.com.br.pem`
- `backtest.horistic.com`: Let's Encrypt config commented out
- `trade.horistic.com`: Only HTTP→HTTPS redirect present, no SSL vhost found in enabled sites

---

## 5. Trading Bot Architecture

### Unified Bot Launcher (`backend/services/unified-bot-launcher.js`)

**Architecture:** One-shot PM2 process that runs a reconciliation cycle and exits. PM2 restarts it after `restart_delay` (60s).

**Flow:**
1. Query `user_account` + `exchange` for eligible accounts (active, not expired, user has automation access)
2. Compare desired state (DB) vs actual state (PM2)
3. Start new bot processes for eligible accounts not yet running
4. Stop processes for accounts no longer eligible
5. Health check all managed workers
6. Update `user_account_bot_status` table with current status
7. Exit — PM2 restarts after delay

**Process Naming Convention:**
- New: `horistic-bot-{SanitizedName}-{AccountId}-{exchange}` (e.g., `horistic-bot-SemFiltro-12-bybit`)
- Legacy: `bot-{SanitizedName}-{AccountId}-{exchange}`
- Fallback: `{exchange}-account-{AccountId}`

**Safeguards:**
- Max 6 concurrent workers (`LAUNCHER_MAX_WORKERS`)
- Max 2 new starts per cycle
- Exponential backoff on failures (base: 60s, max: 30min)
- Resource checks (memory >10%, load/CPU <2.0) before spawning
- Flapping detection (5 restarts = cooldown)

### Exchange-Specific Bot Entry Points

| Exchange | Entry Script | Location |
|----------|-------------|----------|
| **Bybit** | `app.js` | `backend/exchanges/bybit/processes/app.js` |
| **Binance** | `orchMonitor.js` | `backend/exchanges/binance/monitoring/orchMonitor.js` |

### Exchange Modules Structure

Both Binance and Bybit follow the same internal structure:

```
backend/exchanges/{binance,bybit}/
├── api/
│   ├── rest.js           # REST API client
│   └── websocket.js      # WebSocket connection manager
├── services/
│   ├── OrderManager.js   # Order lifecycle management
│   ├── positionSync.js   # Position synchronization
│   ├── stopLossManager.js # Stop loss tracking
│   ├── startupSync.js    # Startup position reconciliation
│   ├── telegramSender.js # Telegram notifications
│   ├── cleanup.js        # Resource cleanup
│   ├── orderIntegrity.js # Order state validation
│   ├── botProcessManager.js  # Process lifecycle
│   └── (exchange-specific)
├── monitoring/
│   ├── core/
│   │   ├── config.js
│   │   └── MonitorOrchestrator.js
│   ├── services/
│   │   ├── JobSchedulerService.js
│   │   └── DatabaseService.js
│   ├── trailingStopLoss.js
│   └── signalProcessor.js
├── strategies/
│   └── reverse.js        # Trading strategy
├── handlers/
│   ├── accountHandlers.js
│   └── orderHandlers.js
└── processes/
    ├── app.js             # Entry point (accepts --account ID)
    ├── instanceManager.js
    └── rateLimitMonitor.js
```

### DIVAP Indicator (Python)

- **Script:** `backend/indicators/divap.py` (166KB — large, main analysis engine)
- **Run via:** `.venv/bin/python divap.py`
- **Purpose:** Analyzes TradingView signals for DIVAP patterns (volume + RSI divergence)
- **Output:** Confirms or rejects signals before execution
- **Utilities:** `backend/indicators/utils/` — exchange info updaters for Binance, Bybit, MEXC, Hyperliquid, Aster

### Webhook Signal Receiver

- **Script:** `backend/indicators/webhook/webhookSignals.js`
- **Port:** 8099 (PM2 managed as `horistic-webhook-signals`)
- **Endpoints:**
  - `POST /divap` — Receives TradingView DIVAP alerts, persists to DB, forwards to Telegram
  - `POST /scalp` — Forwards scalping alerts to Telegram only (no persistence)
- **Integrates with:** Telegram Bot API for message forwarding

---

## 6. Key File Locations

### Entry Points

| File | Purpose |
|------|---------|
| `backend/server/api.js` | Fastify API server (main entry point) |
| `frontend/src/app/page.tsx` | Next.js landing page |
| `backend/services/unified-bot-launcher.js` | Bot auto-discovery and orchestration |
| `backend/indicators/divap.py` | Python DIVAP indicator engine |
| `backend/indicators/webhook/webhookSignals.js` | Webhook signal receiver |
| `start.sh` | Unified start/stop/build script |

### Configuration

| File | Purpose |
|------|---------|
| `config/.env` | Main environment variables (DB, secrets) |
| `config/private.pem` | Private key for crypto operations |
| `ecosystem.config.js` | PM2 production process config |
| `ecosystem.testnet.config.js` | PM2 testnet/dev process config |
| `package.json` | Root Node.js dependencies |
| `frontend/package.json` | Frontend dependencies |
| `pyproject.toml` | Python dependencies (uv managed) |
| `jest.config.js` | Jest test configuration |
| `tsconfig.json` | Root TypeScript config |
| `frontend/tsconfig.json` | Frontend TypeScript config |
| `frontend/next.config.mjs` | Next.js config with API proxy rewrites |

### Core Modules

| File | Purpose |
|------|---------|
| `backend/core/database/conexao.js` | PostgreSQL connection pool (Node.js, 2000+ lines) |
| `backend/core/database/conexao.py` | PostgreSQL connection pool (Python) |
| `backend/server/middleware/` | Fastify middleware |
| `backend/server/ws/` | WebSocket handlers |

### Scripts & Utilities

| File/Dir | Purpose |
|----------|---------|
| `scripts/` | Migration, fix, diagnostic scripts |
| `scripts/migration/` | Database migration scripts |
| `scripts/pm2/` | Desktop launcher entries for PM2 processes |
| `scripts/diagnostico-apache-10.1.1.3.sh` | Apache diagnostics |
| `scripts/recover_stack.sh` | Stack recovery script |
| `utils/` | Utility functions |
| `sessions/` | Trading session data |

### Tests

| Dir | Purpose |
|-----|---------|
| `tests/unit/` | Unit tests |
| `tests/integration/` | Integration tests |
| `tests/frontend/` | Frontend tests (E2E) |
| `tests/config/jest.setup.js` | Jest setup |
| `tests/mocks/` | Test mocks |

---

## 7. Port Map

| Port | Service | Process |
|------|---------|---------|
| `8050` | Backend API (production) | `horistic-api` |
| `8075` | Backend API (development) | `horistic-api-testnet` |
| `3050` | Frontend (production) | `horistic-web` |
| `3075` | Frontend (development) | `horistic-web-testnet` |
| `8099` | Webhook signals | `horistic-webhook-signals` |
| `8745` | PostgreSQL | External (same server) |

---

## 8. Concerns & Technical Debt

### 8.1 Security

**Credentials in testnet config:**
- `ecosystem.testnet.config.js` contains plaintext DB password and JWT secret
- **File:** `ecosystem.testnet.config.js` lines 26-31
- **Risk:** Committed to git — accessible to anyone with repo access
- **Fix:** Move to environment variables or encrypted config

**Secrets on disk:**
- `config/.env` and `config/private.pem` stored on filesystem
- Frontend `.env` is a symlink to `config/.env` (visible in `ls`)
- **Risk:** If repo is pushed, `.env` could leak (though it's in `.gitignore`)

**CORS allows wildcard in dev:**
- `api.js` line 74-77: `if (!isProd) return cb(null, true)` — any origin accepted in dev
- Not critical but worth noting for dev environment security

### 8.2 Architecture

**Monolithic conexao.js (2000+ lines):**
- `backend/core/database/conexao.js` contains connection pool, queueing, CRUD for all entities, position archival, Telegram dispatch, order management — all in one file
- **Impact:** Difficult to maintain, test, or modify without risk of regression
- **Fix:** Split into separate modules by domain (pool, positions, orders, signals, etc.)

**Tightly coupled exchange code:**
- Binance and Bybot share near-identical directory structures with duplicated patterns
- No shared abstraction layer for exchange-agnostic operations
- **Impact:** Adding a new exchange (e.g., Hyperliquid live trading) requires copying the entire structure

**DB credentials loaded in multiple places:**
- `conexao.js`, `conexao.py`, `unified-bot-launcher.js`, `webhookSignals.js` — each loads `.env` independently
- **Risk:** Inconsistent config if `.env` path resolution differs

### 8.3 Database

**No migration framework:**
- Schema changes handled ad-hoc (`checkAndCreateTables()`, `ALTER TABLE` inline)
- No versioned migrations or rollback capability
- **Risk:** Schema drift between environments, manual deployment errors

**Connection pool near saturation:**
- Main pool: max 20 connections
- Launcher notes: "pool de max: 20" and launcher uses dedicated max: 2 pool "to avoid saturating connections (server already runs ~96/100)"
- **Impact:** If many bot processes spawn, connection pool may be exhausted
- **Current mitigation:** Launcher uses separate pool (max: 2), bots likely use their own connections

### 8.4 Deployment

**No Docker:**
- No Dockerfile or docker-compose for horistic project
- Deployment is manual: git pull → npm install → PM2 restart
- **Risk:** Inconsistent environments, no container isolation

**Apache SSL incomplete for trade.horistic.com:**
- Only HTTP→HTTPS redirect exists, no SSL vhost configuration found
- `backtest.horistic.com` has SSL config but certificates are commented out
- `webhook.horistic.com` uses Cloudflare cert (different domain `atius.com.br`)

**start.sh references "STARBOY TRADING":**
- Script header still says "Starboy Trading" — likely a fork/rename
- Not a functional issue but indicates incomplete rebranding

### 8.5 Code Quality

**Duplicate files:**
- `backend/exchanges/binance/services/OrderManager_fixed.js` — parallel version of OrderManager
- `backend/exchanges/bybit/services/botProcessManager.js.bak` — backup file in source tree
- `backend/exchanges/binance/strategies/reverse.js.bak` — backup in source tree
- **Risk:** Confusion about which version is authoritative

**Large single files:**
- `backend/indicators/divap.py` — 166KB (estimated 4000+ lines)
- `backend/core/database/conexao.js` — 2000+ lines
- `start.sh` — 822 lines
- **Impact:** Difficult to navigate and maintain

**Mixed language boundary:**
- Node.js API spawns Python processes for DB context setup (`api.js` lines 421-432)
- Python and Node.js both connect to the same DB independently
- **Risk:** Race conditions, inconsistent connection state

### 8.6 Testing

**Test coverage limited:**
- Jest config ignores `tests/scripts/`, `tests/archive/`, `tests/frontend/e2e/`
- Single test worker (`maxWorkers: 1`) — slow test runs
- Test files in `tests/` but coverage not enforced

---

## 9. Environment Configuration

### Required Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DB_HOST` | PostgreSQL host | `10.1.1.1` |
| `DB_PORT` | PostgreSQL port | `8745` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | (in config/.env) |
| `DB_NAME` | Database name | `horistic` |
| `JWT_SECRET` | JWT signing key | (required — server exits without it) |
| `NODE_ENV` | Runtime mode | `production` / `development` |
| `API_HOST` | API bind address | `0.0.0.0` |
| `API_PORT` | API port | `8050` (prod) / `8075` (dev) |
| `FRONTEND_PORT` | Frontend port | `3050` (prod) / `3075` (dev) |
| `FRONTEND_URL` | Frontend base URL | `https://trade.horistic.com` |
| `API_URL` | API base URL | `https://api.horistic.com` |
| `WEBHOOK_PORT` | Webhook port | `8099` |
| `WEBHOOK_HOST` | Webhook bind | `0.0.0.0` |
| `PANEL_BASE_URL` | Panel URL | `https://trade.horistic.com` |
| `PYTHON_BIN` | Python binary path | `.venv/bin/python` |

### Env File Locations

- `config/.env` — Main config (symlinked to `frontend/.env`)
- `.env.test` — Test database credentials only

---

## 10. Where to Add New Code

| Need | Location |
|------|----------|
| New API route | `backend/server/routes/{domain}.js` (register in `api.js`) |
| New frontend page | `frontend/src/app/{route}/page.tsx` |
| New API component | `frontend/src/components/` |
| New exchange support | `backend/exchanges/{exchange}/` (follow existing pattern) |
| New bot feature | Modify `unified-bot-launcher.js` for orchestration, exchange-specific `processes/app.js` for execution |
| New Python indicator | `backend/indicators/` (add to `pyproject.toml` if new deps needed) |
| New DB table | Add to `checkAndCreateTables()` in `conexao.js` or create migration in `scripts/migrations/` |
| New test | `tests/unit/{feature}.test.js` or `tests/integration/{feature}.test.js` |
| New PM2 process | Add entry to `ecosystem.config.js` |
| New webhook endpoint | `backend/indicators/webhook/webhookSignals.js` |

---

*Codebase map generated: 2026-04-19*
