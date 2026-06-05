# Architecture

**Analysis Date:** 2026-06-05

## Pattern Overview

**Overall:** Server administration tools repository with Click-based Python CLI. Modular architecture where `omni` CLI orchestrates subcommands from separate packages.

**Key Characteristics:**
- Single entry point (`omni`) dispatches to modular subcommand groups
- `fork-sync` lib imported dynamically by `omni` CLI (no separate binary)
- Bash scripts for server provisioning (setup.sh, iptables)
- All Python packages using setuptools (setup.py, not pyproject.toml)

**Key Characteristics:**
- Two primary trading platforms (Atius, Horistic) sharing the same codebase fork under `/home/ubuntu/GitHub/`
- Node.js + Python hybrid backend managed by PM2
- Next.js frontend served alongside Fastify API
- Docker Compose for AI/infrastructure services (Plane, Jenkins, Portainer, Paperclip, Open WebUI)
- Apache virtual hosts handle reverse proxy + Let's Encrypt SSL for all subdomains
- WebSocket real-time communication for bot status

## Layers

### API Layer (Fastify)
- Purpose: REST API + WebSocket endpoints for trading platform
- Location: `GitHub/atius/backend/server/api.js`
- Contains: Route registration, plugin setup, WebSocket server, CORS, Helmet, Swagger
- Depends on: Database layer, exchange APIs, auth middleware
- Used by: Next.js frontend, external webhook integrations

### Backend Domain Layer
- Purpose: Trading logic, exchange integrations, indicators, bot management
- Location: `GitHub/atius/backend/`
- Contains: Exchange adapters, indicators (Python), services, backtest engine
- Depends on: Database connection (`backend/core/database/conexao.js`), external exchange APIs
- Used by: API routes, bot launcher, session management

### Frontend Layer (Next.js)
- Purpose: User-facing dashboard and trading interface
- Location: `GitHub/atius/frontend/`
- Contains: App Router routes, React components, middleware for auth
- Depends on: Backend API (`/api/` routes proxy to `api.atius.com.br`)
- Used by: End users (traders)

### Exchange Adapter Layer
- Purpose: Exchange-specific API bindings and automation
- Location: `GitHub/atius/backend/exchanges/{binance,bingx,bybit,hyperliquid,mexc,okx}/`
- Contains: REST wrappers, WebSocket streams, services, monitoring, strategies
- Depends on: Exchange SDKs (binance-api-node, @nktkas/hyperliquid)
- Used by: API routes, bot processes, unified launcher

### Process Orchestration Layer (PM2)
- Purpose: Manage all application processes with restart policies
- Location: `GitHub/atius/ecosystem.config.js`
- Contains: App definitions for API, frontend, webhooks, Python workers, session healers
- Depends on: Node.js + uv (Python runner)
- Used by: `pm2-ubuntu.service` systemd unit

### Infrastructure Layer (Docker)
- Purpose: Supporting services (databases, CI/CD, project management, AI tools)
- Location: `docker/` directory with multiple Docker Compose stacks
- Contains: PostgreSQL, RabbitMQ, Jenkins, Portainer, Plane, Open WebUI, Paperclip
- Depends on: Docker + containerd
- Used by: All applications

### Reverse Proxy Layer (Apache)
- Purpose: SSL termination, domain routing, virtual host management
- Location: `/etc/apache2/sites-enabled/` (50+ vhost configs)
- Contains: Per-subdomain Apache configs with Let's Encrypt SSL
- Depends on: Apache2 systemd service
- Used by: All external traffic

### Data Layer
- Purpose: Persistent storage for trading data, sessions, user accounts
- Location: Multiple
  - MySQL: Primary trading database (`backend/core/database/conexao.js`)
  - PostgreSQL 17: System services (`postgresql@17-main.service`)
  - MongoDB: Horistic sessions (`mongod.service`)
  - PostgreSQL in Docker: Per-app databases (Plane, Paperclip, New API)
- Used by: Backend API, indicators, backtest engine

## Data Flow

### API Request Flow:
1. Client hits `trade.atius.com.br` or `api.atius.com.br`
2. Apache terminates SSL, reverse proxies to internal port
3. Fastify API (`backend/server/api.js` on port 8015) receives request
4. Auth middleware (`middleware/permissions.js`) validates JWT + RBAC
5. Route handler (`server/routes/{module}/`) processes request
6. Data layer (`core/database/conexao.js`) queries MySQL
7. Response returned via Fastify serialization

### Bot Execution Flow:
1. `atius-unified-bot-launcher` (PM2 process) polls for eligible accounts
2. Spawns worker processes via `botProcessManager.js` (`backend/services/`)
3. Each worker uses exchange-specific adapter (`backend/exchanges/{exchange}/services/`)
4. Trades execute via exchange REST/WebSocket APIs
5. Bot status broadcast via WebSocket (`server/ws/bot-status-ws.js`)
6. Frontend receives real-time updates

### Indicator Processing Flow:
1. `atius-divap-indicator` Python process (via uv) runs `backend/indicators/divap.py`
2. Fetches market data via exchange adapters
3. Computes technical indicators, writes results to MySQL
4. API exposes results via `routes/indicators/` endpoints

### Strategy Builder Flow:
1. `atius-strategy-builder` runs Python FastAPI on port 8091 (`strategy.atius.com.br`)
2. `backend/indicators/strategy_builder/server.py` serves chart + analysis endpoints
3. Candle fetcher pulls historical data
4. Analysis workers process strategies
5. Results returned to Next.js frontend (`/strategy/` routes)

**State Management:**
- Backend: Session state in MySQL, bot state in `backend/logs/unified-launcher-state.json`
- Frontend: React contexts (`frontend/src/contexts/`), hooks (`frontend/src/hooks/`)
- MEXC session: `/tmp/mexc-runtime/` directory for token/cookie state
- Database connection: Singleton pool in `conexao.js` (Node.js) and `conexao.py` (Python)

## Key Abstractions

**Exchange Adapter Pattern:**
- Purpose: Normalize multi-exchange API differences into common interface
- Examples: `backend/exchanges/binance/`, `backend/exchanges/mexc/`, `backend/exchanges/bybit/`
- Pattern: Each exchange has `api/`, `services/`, `monitoring/`, `strategies/` subdirectories
- Cross-exchange abstraction happens at `backend/indicators` and `backend/services` layer

**Unified Bot Launcher:**
- Purpose: Single entry point for spawning trading bots across all exchanges/accounts
- Location: `backend/services/unified-bot-launcher.js`
- Pattern: Polls database for eligible accounts, spawns workers via PM2, manages lifecycle with flapping detection and backoff

**Database Abstraction:**
- Purpose: Centralize MySQL connection management for both Node.js and Python
- Location: `backend/core/database/conexao.js` (140KB, 45KB Python)
- Pattern: Singleton connection pool with validation interceptor

**Strategy Builder Server:**
- Purpose: Python FastAPI server for technical analysis and backtesting
- Location: `backend/indicators/strategy_builder/server.py` (108KB)
- Pattern: Moduvular strategy framework with candle fetching, chart rendering, and analysis workers

## Entry Points

**Main API Server:**
- Location: `backend/server/api.js`
- Triggers: PM2 process `atius-api` (port 8015)
- Responsibilities: Route registration, plugin setup, WebSocket, Swagger docs, CORS

**Frontend:**
- Location: `frontend/src/app/` (Next.js App Router)
- Triggers: PM2 process `atius-web` (port 3015)
- Responsibilities: User interface, authentication, trading dashboard, strategy visualization

**Webhook Server:**
- Location: `backend/indicators/webhook/webhookSignals.js`
- Triggers: PM2 process `atius-webhook-signals` (port 8199)
- Responsibilities: Receive external trading signals

**Strategy Builder:**
- Location: `backend/indicators/strategy_builder/server.py`
- Triggers: PM2 process `atius-strategy-builder` (port 8091)
- Responsibilities: Technical analysis, backtesting, chart generation

**Bot Launcher:**
- Location: `backend/services/unified-bot-launcher.js`
- Triggers: PM2 process `atius-unified-bot-launcher` (60s poll interval)
- Responsibilities: Spawn/monitor trading bot processes across exchanges

**Docker Infrastructure:**
- Location: `docker/ai-apps/`, `docker/AtiusCapital/`, `docker/pm2.web/`
- Triggers: Docker Compose (`docker-compose.yml`)
- Responsibilities: CI/CD, project management, AI routing, PM2 dashboard

## Error Handling

**Strategy:** Multi-layer approach — Fastify validation, PM2 autorestart, Python uv supervision, session healers

**Patterns:**
- Fastify AJV JSON Schema validation with `allowUnionTypes`
- PM2 autorestart with configurable `restart_delay`, `max_restarts`, `min_uptime`
- MEXC session healer with health checks and token recovery monitoring
- Bot launcher with flapping detection (restart threshold: 5), exponential backoff (60s to 30min)
- Database validation interceptor (`core/database/validationInterceptor.js`)
- Frontend middleware (`middleware.ts`) for auth routing and error pages (`/unauthorized/`, `global-error.tsx`)

## Cross-Cutting Concerns

**Logging:**
- Backend: Pino with pino-pretty transport (`pino-pretty` package)
- Format: `YYYY-MM-DD HH:mm:ss` (configured in PM2 `log_date_format`)
- PM2 merge logs enabled for consolidated output per process
- Python: Unbuffered output (`PYTHONUNBUFFERED=1`)

**Validation:**
- Backend: Fastify AJV JSON Schema validation at route level
- Database: Validation interceptor on DB operations (`core/database/validationInterceptor.js`)
- Frontend: TypeScript strict mode (`tsconfig.json`)

**Authentication:**
- JWT-based with RBAC permissions (`middleware/permissions.js`)
- SSO integration for Swagger docs in production
- Next.js middleware (`middleware.ts`) handles auth redirects
- MEXC: Browser automation with Playwright stealth + nodriver for session management

**Security:**
- Helmet for HTTP security headers
- CORS with explicit allowed origins list
- Rate limiting (`@fastify/rate-limit`)

---

*Architecture analysis: 2026-04-19*
