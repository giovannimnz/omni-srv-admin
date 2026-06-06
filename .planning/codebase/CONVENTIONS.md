# Coding Conventions

**Analysis Date:** 2026-04-19

## Project Overview

The Atius Trade System (ATS) is a multi-exchange crypto trading platform at `~/GitHub/Atius-Capital/ats/`. It is a polyglot project: **JavaScript/Node.js** backend with **Fastify**, **Python** services (indicators, browser automation), and a **Next.js/TypeScript** frontend. PM2 orchestrates all processes in production.

## Naming Patterns

**Files (Backend JS):**
- Use `camelCase.js` for modules: `signalProcessor.js`, `orderIntegrity.js`, `telegramSender.js`
- Use `PascalCase.js` for classes/constructors: `OrderManager.js`, `ManualPanelExecutor.js`, `BybitRestApi` (implied from `rest.js`)
- Use `kebab-case.js` for scripts/processes: `unified-bot-launcher.js`, `fee-updater.js`, `bot-control-multi.js`
- Service directories by exchange: `backend/exchanges/{exchange}/services/`

**Files (Backend Python):**
- Use `snake_case.py`: `divap.py`, `divap_check.py`, `exchange_bracket_updater_binance.py`
- Module packages with `__init__.py`

**Files (Frontend TSX/TS):**
- Use `kebab-case` for components: `trading-interface.tsx`, `bot-settings.tsx`, `open-positions.tsx`
- Use `kebab-case` for hooks: `use-mobile.tsx`, `use-toast.ts`
- Use `kebab-case` for contexts: `auth-context.tsx`, `language-context.tsx`
- UI primitives in `frontend/src/components/ui/` (Radix/shadcn pattern)

**Files (Tests):**
- Backend unit tests: `test_{description}.test.js` — e.g., `test_bybit_signal_processor_db_resilience.test.js`
- Backend runtime/live tests: `test_{description}.runtime.test.js` — e.g., `test_trigger_order_api.runtime.test.js`
- Frontend E2E tests: `test_{description}.spec.{js,ts}` — e.g., `test_demo_login_ui.spec.js`
- Legacy tests use `{module}.test.js` without `test_` prefix: `sessionStore.test.js`, `endpointMapper.test.js`

**Functions (Backend JS):**
- Use `camelCase`: `checkNewTrades()`, `placeFromSignal()`, `loadCredentialsFromDatabase()`
- Private methods prefixed with `_`: `_registerOrderId()`, `_isDuplicate()`, `_initialized`
- Factory functions: `buildOrderApiClient()`, `buildJestReporters()`
- Helper/utility functions: `roundPriceWithPrecision()`, `getCliFlagValue()`

**Functions (Python):**
- Use `snake_case`: `verify_divap_pattern()`, `update_leverage_brackets_binance()`
- Module-level imports organized by stdlib, third-party, project

**Variables (Backend JS):**
- Use `camelCase` for locals: `mockQuery`, `adminToken`, `testUserId`
- Use `SCREAMING_SNAKE_CASE` for constants: `POLL_INTERVAL_MS`, `MAX_WORKERS`, `DRY_RUN`
- Use `SCREAMING_SNAKE_CASE` for env var names: `JWT_SECRET`, `API_PORT`, `FRONTEND_PORT`

**Types (Frontend TS):**
- Use `PascalCase` interfaces: `UserPermissions`, `AuthContextType`, `LoginResult`, `BrokerAccount`
- Define interfaces inline in context files, not in separate type files (except `frontend/src/types/`)

**Database columns:**
- Use `snake_case`: `conta_id`, `session_data_encrypted`, `auth_tag`, `user_agent`, `last_used_at`
- Portuguese naming for domain tables: `posicoes`, `contas`, `sinais`

## Code Style

**Formatting:**
- No project-level Prettier or ESLint config at root `~/GitHub/Atius-Capital/ats/`
- Frontend uses Next.js built-in ESLint: `frontend/.eslintrc.json` extends `next/core-web-vitals`
- No `.prettierrc` at project level
- Indentation: 2 spaces (JS/TS), 4 spaces (Python)
- Semicolons: inconsistent — some files use them, some don't. Newer files tend to use them.
- Strings: single quotes dominant in backend JS, double quotes in some frontend TSX

**Linting:**
- Frontend only: ESLint with `next/core-web-vitals`
- Backend: no ESLint configuration
- CSS: `stylelint` + `stylelint-config-tailwindcss` in devDependencies (frontend)
- Python: `pyright` in devDependencies for type checking (`pyrightconfig.json` present)

## Import Organization

**Backend JS (CommonJS):**
1. Node.js built-ins: `const path = require('path');`, `const fs = require('fs');`
2. Third-party packages: `const { Pool } = require('pg');`, `const axios = require('axios');`
3. Project modules with relative paths: `require('../../../core/database/conexao')`
4. No path aliases in backend — all relative paths

**Frontend TS (ES Modules):**
1. React/Next.js imports: `import React from 'react'`, `import Link from "next/link"`
2. UI components via path alias: `import { Card } from "@/components/ui/card"`
3. Project components: `import TradingInterface from "@/components/trading/trading-interface"`
4. Contexts/hooks: `import { useAuth } from "@/contexts/auth-context"`
5. Types: `import { BrokerAccount } from "@/types/accounts"`

**Path Aliases:**
- Frontend: `@/*` maps to `./src/*` (configured in `frontend/tsconfig.json`)
- Backend: none — use relative paths only

**Python:**
1. Standard library
2. Third-party: `import ccxt`, `from telethon import ...`
3. Project imports with `sys.path` manipulation for absolute paths: `from backend.indicators.utils.helpers import ...`

## Error Handling

**Backend API (Fastify):**
- Fatal startup errors: `console.error()` + `process.exit(1)` — see `backend/server/api.js` line 7-9
- Request errors: return structured JSON `{ error: 'message' }` with appropriate HTTP status
- Authentication: 401 with specific message (`'Sessao expirada'`, `'Token invalido'`)
- Authorization: 403 with permission denial message
- Security blocks: silent 403 for malicious routes, logged via `console.log`

**Backend Services:**
- Circuit breaker pattern for DB failures: count failures, open circuit after threshold — see `backend/exchanges/bybit/monitoring/signalProcessor.js`
- Constructor validation: `if (!accountId) throw new Error('OrderManager Bybit requer accountId')`
- Async errors: try/catch with `console.error` logging

**Frontend:**
- API calls wrapped in try/catch with error state management
- `validateStatus: () => true` pattern in axios calls to handle all HTTP statuses without throwing

**Bash Scripts:**
- `set -e` at script start for fail-fast
- Signal traps for graceful shutdown (SIGINT/SIGTERM) — see `start.sh`
- Color-coded console output with log levels

## Logging

**Framework:** `console.*` (backend JS) + Pino via Fastify (API server)

**Patterns:**
- API server uses Fastify's built-in Pino logger with `pino-pretty` transport
- Backend services use `console.log`, `console.error`, `console.warn` directly
- Log messages often include emoji prefixes for visual scanning: `[CORS] shield`, `[SECURITY] shield`
- Bracketed context prefix: `[CORS]`, `[SECURITY]`, `[LAUNCHER]`
- PM2 handles log aggregation with `merge_logs: true` and `log_date_format: 'YYYY-MM-DD HH:mm:ss'`

**Python:** Uses `logging` module with standard configuration

## Comments

**When to Comment:**
- Module-level header blocks with `═══` borders for major files — describes purpose, architecture, and usage
- Inline comments in Portuguese (project language) for domain logic
- `// Sprint 1:` annotations for incremental development tracking
- Section separators using `// ─── Section Name ───────────`
- Comments explain "why" for non-obvious business logic
- Removal tracking: `// bybit-atius-8 removido — substituido pelo unified-launcher acima (07/03/2026)`

**JSDoc:**
- Used in middleware and public APIs: see `backend/server/middleware/permissions.js`
- `@param` and `@returns` annotations for factory functions
- Not consistently used across all backend modules

## Function Design

**Size:** No strict limit. Service classes can be large (OrderManager, SignalProcessor).

**Parameters:**
- Options objects for complex configuration: `{ projectRoot, pythonVersion }`
- Positional parameters for simple functions: `saveSession(accountId, sessionType, data, userAgent)`
- Default values via `||` or `??` operators

**Return Values:**
- API responses: `{ success: boolean, data?: any, error?: string }`
- Database queries: return rows directly or null
- Async functions: always return Promises (async/await pattern)

## Module Design

**Exports (Backend JS - CommonJS):**
- Single class export: `module.exports = OrderManager;`
- Named exports object: `module.exports = { buildJestReporters };`
- Mixed: functions and constants in same export

**Barrel Files:** Not used in backend. Frontend uses implicit Next.js routing.

**Frontend (ES Modules):**
- Named exports for contexts/hooks: `export function AuthProvider()`
- Default exports for page components
- `"use client"` directive at top of client-side components

## Process Management

**PM2 Ecosystem Pattern (`ecosystem.config.js`):**
- All apps under `namespace: 'atius'`
- Environment config via helper functions: `withNodeEnv()`, `withUvEnv()`
- Python processes use `uv` runtime with `interpreter: 'none'`
- One-shot architecture for bot launcher: runs 1 cycle, exits, PM2 restarts after `restart_delay`
- Extensive env var configuration per process

## Language

**Primary human language:** Portuguese (Brazilian)
- Comments, error messages, database column names, and UI strings are predominantly in Portuguese
- Some technical terms and newer code uses English
- Mix of Portuguese and English in the same file is common

---

*Convention analysis: 2026-04-19*
