# Codebase Structure

**Analysis Date:** 2026-06-05

## Directory Layout

```
/home/ubuntu/GitHub/omni-srv-admin/
├── cli/                       # CLI tools (Python setuptools)
│   ├── setup.py               # omni CLI entry point (console_scripts)
│   └── omni/                  # omni package
│       ├── __init__.py        # v0.1.0
│       ├── __main__.py        # python -m omni
│       └── cli.py             # Click group → fork-sync + subcommands
├── modules/
│   └── fork-sync/             # fork-sync lib (CLI via omni)
│       ├── cli/               # fork-sync Python package (lib-only, no entry point)
│       │   ├── setup.py
│       │   └── fork_sync/
│       │       ├── cli.py     # Click group (imported by omni)
│       │       ├── core/      # Core modules (config, sync, deploy, etc.)
│       │       └── __init__.py
│       └── projects/          # Project configs (sync.yaml per fork)
├── antivirus/                 # Antivirus scan scripts
├── dark-theme-ubuntu/         # Desktop theme (LXDE/Apple fonts)
├── docs/                      # Project documentation
├── domain-infrastructure/     # FreeIPA + Keycloak + Samba
├── iptables/                  # Firewall rules
├── vscode-profile/            # VSCode config + memory bank
├── setup.sh                   # Base server provisioning
└── .planning/                 # GSD planning artifacts
    ├── PROJECT.md
    ├── ROADMAP.md
    ├── config.json
    ├── codebase/              # Codebase map (this file)
    └── phases/                # Phase plans

## Directory Purposes

### `/home/ubuntu/GitHub/Atius-Capital/ats/` - Primary Application
- Purpose: Main trading platform monorepo
- Contains: Backend (Node.js + Python), Frontend (Next.js), tests, docs
- Key files:
  - `ecosystem.config.js` — PM2 process definitions (all apps)
  - `package.json` — Dependencies and npm scripts
  - `start.sh` — Build/start/stop orchestration script
  - `Jenkinsfile` — CI/CD pipeline definition

### `/home/ubuntu/GitHub/Atius-Capital/ats/backend/` - Backend Logic
- Purpose: Server-side trading logic, exchange integrations, indicators
- Contains:
  - `server/api.js` — Fastify API entry point (24KB)
  - `server/routes/` — Route handlers by domain
  - `exchanges/` — Exchange adapters (binance, bingx, bybit, hyperliquid, mexc, okx)
  - `indicators/` — Python indicator engine (divap.py — 177KB)
  - `core/` — Database connections, backups, migrations
  - `services/` — Bot process manager, unified launcher
  - `sessions/` — Runtime session state
  - `backtest/` — Backtesting engine (Python)
  - `telegram/` — Telegram bot integration
  - `utils/` — Python utilities (market data, backtest, time)

### `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/` - Frontend
- Purpose: Next.js 14 App Router trading dashboard
- Contains:
  - `src/app/` — App Router pages (admin, api, backtest, dashboard, login, painel, sinal, strategy)
  - `src/components/` — React components (Dashboard, modals, trading UI, auth)
  - `src/contexts/` — React context providers
  - `src/hooks/` — Custom React hooks
  - `src/lib/` — Client-side utilities
  - `src/types/` — TypeScript type definitions
  - `next.config.mjs` — Next.js configuration
  - `tailwind.config.js` — Tailwind CSS config

### `/home/ubuntu/GitHub/Atius-Capital/ats/tests/` - Test Suites
- Purpose: Unit, integration, runtime, and E2E tests
- Contains:
  - `backend/` — Backend test suites (by exchange, service, auth)
  - `frontend/` — Frontend E2E and component tests
  - `backtest/` — Backtest validation tests
  - `debug/` — Debug test utilities
  - `mocks/` — Test fixtures and mocks
  - `setup.js` / `setup.runtime.js` — Test setup files

### `/home/ubuntu/docker/` - Docker Infrastructure
- Purpose: Docker Compose stacks for supporting services
- Contains:
  - `ai-apps/` — AI router, LLM instances, automation tools
  - `AtiusCapital/` — Jenkins, project management, CI/CD
  - `pm2.web/` — PM2 web dashboard
  - `portainer/` — Docker management UI
  - `cloudbeaver/` — Database management
  - `openclaw/` — Claude code instance
  - `postgres-mcp/` — PostgreSQL MCP server

### `/home/ubuntu/bin/` — CLI Entry Points
- Purpose: User-level command shortcuts
- Key files:
  - `gsd-browser` → `docker/AtiusCapital/scripts/gsd-browser-headless.sh`
  - `gsd-sync-clis` → `docker/AtiusCapital/scripts/gsd-sync-clis.sh`
  - `iflow`, `iflow1`, `iflow2`, `iflow3` → AI agent scripts
  - `qoder`, `qodercli`, `qoder-gsd` → Qoder CLI wrappers
  - `bonsai` / `bonsai-repatch` — Patch management tools
  - `pm2ns` — PM2 namespace script

### `/home/ubuntu/GitHub/Atius-Capital/horistic/` — Secondary Application
- Purpose: Trading platform variant/fork
- Contains: Same directory structure as `atius/` but smaller footprint
- Key files: `ecosystem.config.js` (5KB vs 15KB for atius)

## Key File Locations

### Entry Points
- `GitHub/Atius-Capital/ats/backend/server/api.js`: Fastify API server (port 8015)
- `GitHub/Atius-Capital/ats/frontend/src/app/`: Next.js App Router
- `GitHub/Atius-Capital/ats/ecosystem.config.js`: PM2 process definitions
- `GitHub/Atius-Capital/ats/start.sh`: Build/start orchestration

### Configuration
- `GitHub/Atius-Capital/ats/config/.env`: Environment variables (sourced by api.js)
- `GitHub/Atius-Capital/ats/tsconfig.json`: TypeScript config
- `GitHub/Atius-Capital/ats/jest.config.js`: Jest test runner config
- `GitHub/Atius-Capital/ats/playwright.config.js`: Playwright E2E config
- `GitHub/Atius-Capital/ats/pyproject.toml`: Python project config (uv)
- `GitHub/Atius-Capital/ats/.python-version`: Pinned Python version (3.11)

### Core Logic
- `GitHub/Atius-Capital/ats/backend/core/database/conexao.js`: MySQL connection pool (Node.js)
- `GitHub/Atius-Capital/ats/backend/core/database/conexao.py`: MySQL connection pool (Python)
- `GitHub/Atius-Capital/ats/backend/server/api.js`: Main API server
- `GitHub/Atius-Capital/ats/backend/services/botProcessManager.js`: Bot process management
- `GitHub/Atius-Capital/ats/backend/services/unified-bot-launcher.js`: Unified bot launcher

### Database & Migrations
- `GitHub/Atius-Capital/ats/backend/core/database/`: Connection management
- `GitHub/Atius-Capital/ats/backend/core/migrations/`: Database migrations
- `GitHub/Atius-Capital/ats/backend/core/backups/`: Database backup utilities

### Testing
- `GitHub/Atius-Capital/ats/tests/backend/`: Backend test suites
- `GitHub/Atius-Capital/ats/tests/frontend/`: Frontend E2E tests
- `GitHub/Atius-Capital/ats/tests/backtest/`: Backtest validation
- `GitHub/Atius-Capital/ats/tests/mocks/`: Test fixtures

## Naming Conventions

**Files:**
- Node.js: `camelCase.js` (e.g., `botProcessManager.js`, `conexao.js`)
- Python: `snake_case.py` (e.g., `divap.py`, `backtest_data_preloader.py`)
- TypeScript/React: `kebab-case.tsx` (e.g., `theme-provider.tsx`, `app.tsx`)
- Config files: `kebab-case.ext` (e.g., `next.config.mjs`, `tsconfig.json`)
- Test files: `{module}.test.js` or `{module}.runtime.test.js`

**Routes (Next.js App Router):**
- Pages: `page.tsx` inside directory named after route segment
- API routes: `route.ts` inside `src/app/api/{resource}/`
- Special files: `layout.tsx`, `loading.tsx`, `error.tsx`, `global-error.tsx`

**Processes (PM2):**
- Naming: `atius-{component}` (e.g., `atius-api`, `atius-web`, `atius-divap-indicator`)
- Horistic processes: `horistic-{component}`
- Bot processes: `atius-bot-{AccountName}-{Number}-{Exchange}`

**Environment Variables:**
- Node.js: `UPPER_SNAKE_CASE` (e.g., `JWT_SECRET`, `API_PORT`)
- MEXC specific: `MEXC_` prefix (e.g., `MEXC_PLAYWRIGHT_HEADLESS`)
- Launcher specific: `LAUNCHER_` prefix (e.g., `LAUNCHER_POLL_INTERVAL`)

**Exchanges:**
- Directory names: lowercase exchange names (`binance/`, `mexc/`, `bybit/`)
- Each exchange follows: `api/`, `services/`, `monitoring/`, `strategies/`, `processes/`

## Where to Add New Code

**New Exchange Integration:**
- Backend adapter: `backend/exchanges/{exchange-name}/`
- API routes: `backend/server/routes/{exchange-name}/`
- Tests: `tests/backend/exchanges/{exchange-name}/`

**New API Endpoint:**
- Route handler: `backend/server/routes/{domain}/`
- Create subdirectory if new domain, or add file to existing
- Register in `backend/server/api.js`

**New Frontend Page:**
- Page component: `frontend/src/app/{route}/page.tsx`
- API route: `frontend/src/app/api/{resource}/route.ts`
- Shared component: `frontend/src/components/{feature}/`

**New Python Indicator/Strategy:**
- Indicator script: `backend/indicators/`
- Strategy module: `backend/indicators/strategy_builder/strategies/`
- Backtest: `backend/backtest/`

**New Bot Service:**
- Process definition: `ecosystem.config.js` (add new app entry)
- Launcher config: `backend/services/unified-bot-launcher.js`
- Bot process template: `backend/services/botProcessManager.js`

**New Docker Service:**
- Create directory under appropriate `docker/` subdirectory
- Add `docker-compose.yml` and relevant configs
- Update `restart-containers.sh` if needed

**New PM2 Process:**
- Add app entry in `ecosystem.config.js`
- Follow naming convention: `atius-{component}` or `horistic-{component}`
- Use `withNodeEnv()` or `withUvEnv()` helper for environment setup

## Special Directories

**`.gsd/`** — GSD workflow state
- Purpose: Phase tracking, planning, execution state
- Generated: Yes (by GSD commands)
- Committed: No (gitignored)

**`test-results/`** — Test output
- Purpose: Playwright reports, Jest JUnit XML, runtime test events
- Generated: Yes (by test runs)
- Committed: No

**`node_modules/`** — Node.js dependencies
- Purpose: Installed npm packages
- Generated: Yes (`npm install`)
- Committed: No

**`.venv/`** — Python virtual environment
- Purpose: Isolated Python packages via uv
- Generated: Yes (`uv sync`)
- Committed: No

**`backend/logs/`** — Application logs
- Purpose: Runtime logs from bot launcher, indicators
- Generated: Yes (by application)
- Committed: No

**`backend/exchanges/mexc/automation/`** — MEXC browser automation
- Purpose: Playwright/nodriver session management for MEXC exchange
- Contains: Browser profiles, session healers, CDP workers
- Special: Uses Xvfb display (`:10.0`) for headless browser

**`frontend/.next/`** — Next.js build output
- Purpose: Compiled Next.js application
- Generated: Yes (`next build`)
- Committed: No

---

*Structure analysis: 2026-04-19*
