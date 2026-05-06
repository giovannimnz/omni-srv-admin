# Testing Patterns

**Analysis Date:** 2026-04-19

## Test Framework

**Runner:**
- Jest 30.x (backend unit + runtime tests)
- Playwright 1.58.x (frontend E2E tests)
- pytest 9.x (Python — declared in `pyproject.toml` dev deps, minimal usage observed)

**Assertion Library:**
- Jest built-in `expect()` for all backend tests
- `chai` mapped to Node.js `assert` via `tests/mocks/assert-mock.js` (compatibility shim)
- Playwright's built-in `expect()` for E2E tests

**Config Files:**
- `jest.backend.config.js` — primary backend test config
- `jest.backend.runtime.config.js` — extends base, adds runtime setup and longer timeouts
- `jest.config.js` — legacy entrypoint, delegates to `jest.backend.config.js`
- `jest.reporters.js` — JUnit reporter builder for CI
- `playwright.config.js` — E2E configuration

**Run Commands:**
```bash
npm test                              # Run backend Jest tests (deterministic)
npm run test:backend:jest             # Same as above
npm run test:backend:runtime          # Run runtime tests (non-live, mocked exchanges)
npm run test:backend:runtime:api-live # Run live API tests (requires running server)
npm run test:backend:all              # Jest + runtime
npm run test:e2e                      # Playwright E2E tests
npm run test:e2e:frontend:smoke       # Smoke test: demo login UI
npm run test:e2e:headed               # Playwright with visible browser
npm run test:e2e:debug                # Playwright debug mode
npm run test:e2e:report               # View Playwright HTML report
```

## Test File Organization

**Location:** Separate `tests/` directory (not co-located with source):
```
tests/
├── setup.js                    # Jest global setup (minimal)
├── setup.runtime.js            # Runtime setup (retries, timeout tuning)
├── mocks/
│   └── assert-mock.js          # chai → assert shim
├── backend/
│   ├── admin/                  # Admin API tests
│   ├── auth/                   # Auth + RBAC tests
│   ├── dashboard/              # Dashboard API tests
│   ├── exchanges/
│   │   ├── binance/
│   │   ├── bingx/
│   │   ├── bybit/              # Signal processor, order manager tests
│   │   ├── mexc/automation/    # Session, crypto, automation tests
│   │   ├── okx/                # OKX-specific tests
│   │   └── regression/         # Cross-exchange regression tests
│   ├── orders/                 # Order API tests (runtime)
│   ├── services/               # Bot launcher tests
│   ├── websocketHandlers/      # WebSocket handler tests
│   └── ...
├── frontend/
│   ├── admin/                  # Admin UI specs
│   └── e2e/
│       ├── helpers/
│       │   └── ui-auth.js      # Shared login helpers
│       ├── test_demo_login_ui.spec.js
│       ├── test_trade_history.spec.ts
│       └── ...
└── backtest/                   # Backtest-specific tests
```

**Naming:**
- Deterministic unit tests: `test_{description}.test.js` or `{module}.test.js`
- Runtime/live API tests: `test_{description}.runtime.test.js`
- Playwright E2E: `test_{description}.spec.{js,ts}` or `{feature}.spec.{js,ts}`
- Ignored patterns: `.runtime.test.js` excluded from deterministic config; `.playwright.test.js` excluded from both

**58 total test files** across backend and frontend.

## Test Structure

**Backend Unit Test Pattern:**
```javascript
// 1. Declare mock functions at module scope
const mockFindSignalsByStatus = jest.fn();

// 2. Mock dependencies before require
jest.mock('../../../../backend/core/database/conexao', () => ({
  getDatabaseInstance: jest.fn(),
  findSignalsByStatus: (...args) => mockFindSignalsByStatus(...args),
  enqueueUpdateWebhookSignal: jest.fn()
}));

// 3. Require the module under test AFTER mocks
const { initializeSignalProcessor } = require('../../../../backend/exchanges/bybit/monitoring/signalProcessor');

// 4. Test suite
describe('Bybit SignalProcessor DB resilience', () => {
  beforeEach(() => {
    mockFindSignalsByStatus.mockReset();
  });

  test('deve ativar circuit breaker apos falhas repetidas', async () => {
    mockFindSignalsByStatus.mockRejectedValue(new Error('timeout'));
    // ... assertions with expect()
  });
});
```

**Runtime/Live API Test Pattern:**
```javascript
const axios = require('axios');

const runLive = process.env.RUN_LIVE_API_TESTS === '1';
const testLive = runLive ? test : test.skip;

const API_URL = process.env.BACKEND_API_URL || 'http://localhost:8015';

describe('Trigger Order API (runtime)', () => {
  testLive('single_tp_mode=true nao falha por validacao', async () => {
    const response = await axios.post(`${API_URL}/v1/orders/manual`, payload, {
      validateStatus: () => true,
      timeout: 30000
    });
    expect(response.data?.error || '').not.toContain('gaps');
  });
});
```

**E2E (Playwright) Test Pattern:**
```javascript
const { test, expect } = require('@playwright/test');
const { getDemoCredentials, loginViaUi } = require('./helpers/ui-auth');

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3015';

test.describe('Frontend UI - demo user login', () => {
  test('login form submit and auth response', async ({ page, request }) => {
    await loginViaUi(page, BASE_URL, getDemoCredentials());
    // ... assertions
  });
});
```

## Mocking

**Framework:** Jest built-in (`jest.fn()`, `jest.mock()`)

**Patterns:**

**Module mocking (most common):**
```javascript
jest.mock('pg', () => ({
  Pool: jest.fn().mockImplementation(() => ({
    query: (...args) => mockQuery(...args),
    end: jest.fn()
  }))
}));
```

**Class mocking:**
```javascript
jest.mock('../../../../backend/exchanges/bybit/services/OrderManager', () => {
  return jest.fn().mockImplementation(() => ({
    placeFromSignal: jest.fn().mockResolvedValue({ success: true, positionId: 1 })
  }));
});
```

**CLI/Process mocking:**
```javascript
jest.mock('child_process', () => ({
  execSync: (cmd, opts) => {
    mockExecSyncCalls.push(cmd);
    if (cmd.includes('jlist')) return JSON.stringify(mockProcessList);
    if (cmd.includes('pm2 start')) return 'started';
    return '';
  }
}));
```

**What to Mock:**
- Database connections (`pg.Pool`, `conexao.js` functions)
- External API calls (exchange SDKs)
- `child_process.execSync` for PM2 CLI commands
- Environment variables (`process.env.JWT_SECRET = 'test-secret'`)
- File system operations when needed

**What NOT to Mock:**
- Business logic under test (signal processors, order managers, validators)
- Crypto functions used in integration (e.g., `sessionCrypto.encrypt` tested with real implementation)
- HTTP requests in runtime/live tests (they hit real server)

## Fixtures and Factories

**Test Data:**
- Inline test data in each test file (no shared fixture files)
- Environment variables set in test files: `process.env.JWT_SECRET = 'test-secret-key-for-store-tests'`
- Mock process lists as arrays: `let mockProcessList = [];`
- Credential helpers in `tests/frontend/e2e/helpers/ui-auth.js`

**Helper Functions (Runtime tests):**
```javascript
async function loginToken(email, senha) {
  const response = await axios.post(`${API_URL}/v1/token/generate`, { email, senha });
  const match = raw.match(/auth-token=([^;]+)/);
  return match[1];
}

async function apiGet(path, token) {
  return axios.get(`${API_URL}${path}`, {
    headers: token ? { Cookie: `auth-token=${token}` } : undefined,
    validateStatus: () => true,
    timeout: 20000
  });
}
```

**Location:**
- No dedicated fixtures directory
- Helpers in `tests/frontend/e2e/helpers/`
- Mock data inline per test file

## Coverage

**Requirements:** No coverage thresholds enforced

**No coverage reporting configured** — no `--coverage` flag in any npm script.

## Test Types

**Unit Tests (deterministic):**
- Config: `jest.backend.config.js`
- Root: `tests/backend/`
- Timeout: 30s per test
- Exclude: `*.runtime.test.js`, `*.playwright.test.js`
- Mock all external dependencies (DB, APIs, filesystem)
- Run with `maxWorkers: 1` (serial execution)
- Transform: babel-jest for ES module compatibility (chai)

**Runtime Tests (non-live):**
- Config: `jest.backend.runtime.config.js`
- Extends base config, adds `tests/setup.runtime.js`
- Timeout: 120s per test (configurable via `JEST_RUNTIME_TIMEOUT_MS`)
- Retries: configurable via `JEST_RUNTIME_RETRY_TIMES`
- Include `*.runtime.test.js` files
- May hit real server at `localhost:8015`

**Runtime Tests (live API):**
- Gated by `RUN_LIVE_API_TESTS=1` env var
- Use `testLive = runLive ? test : test.skip` pattern
- Hit actual running backend with real credentials
- Used for RBAC, order validation, SSO endpoint testing

**E2E Tests (Playwright):**
- Config: `playwright.config.js`
- Test dir: `tests/frontend/e2e/`
- Browser: Chromium only
- Serial execution (`workers: 1`, `fullyParallel: false`)
- Traces/screenshots/video on failure
- Base URL: `http://localhost:3015` (configurable)
- Shared login helpers in `tests/frontend/e2e/helpers/ui-auth.js`

## CI/CD Integration

**Jenkins Pipeline (`Jenkinsfile`):**
```
Stages:
1. Install dependencies (npm ci)
2. Backend deterministic (npm run test:backend:ci)
3. Backend runtime non-live (npm run test:backend:runtime:ci) — parameterized
4. Backend runtime live (npm run test:backend:runtime:api-live:ci) — parameterized, off by default
```

**JUnit Reporting:**
- `jest-junit` reporter enabled when `CI=true` or `JEST_JUNIT_ENABLED=1`
- Output: `test-results/junit/*.xml`
- Jenkins collects via `junit` step and `archiveArtifacts`
- Reporter config in `jest.reporters.js`: `buildJestReporters()` adds JUnit conditionally

## Common Patterns

**Async Testing:**
```javascript
test('deve retornar sessao decriptada quando existe', async () => {
  mockQuery.mockResolvedValueOnce({ rows: [{ id: 1, ... }] })
           .mockResolvedValueOnce({ rows: [] });
  const result = await sessionStore.getValidSession(42, 'playwright');
  expect(result).not.toBeNull();
  expect(result.data).toEqual(JSON.parse(original));
});
```

**Error Testing:**
```javascript
test('deve ativar circuit breaker apos falhas repetidas', async () => {
  mockFindSignalsByStatus.mockRejectedValue(new Error('timeout'));
  await processor.checkNewTrades();
  await processor.checkNewTrades();
  await processor.checkNewTrades();
  expect(current.dbCircuitOpenUntil).toBeGreaterThan(Date.now());
});
```

**Conditional Test Execution:**
```javascript
const runLive = process.env.RUN_LIVE_API_TESTS === '1';
const testLive = runLive ? test : test.skip;
// Then use testLive('description', async () => { ... });
```

**Test Description Language:**
- Portuguese for unit tests: `'deve ativar circuit breaker apos falhas'`
- English for E2E tests: `'login form submit and auth response for demo/demo'`
- Mix of both in runtime tests

## Key Testing Gaps

- No frontend unit tests (React component tests) — only E2E via Playwright
- No coverage thresholds or reporting
- No Python tests observed (pytest declared but no test files found)
- Backend unit tests focused on exchanges/automation — limited coverage of core API routes
- No snapshot testing
- No contract/schema testing for API endpoints

---

*Testing analysis: 2026-04-19*
