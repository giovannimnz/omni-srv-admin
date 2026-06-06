<!-- generated-by: gsd-doc-writer -->
# Testing — Atius Home Server

## Test Frameworks

| Project | Framework | Config |
|---------|-----------|--------|
| Atius Trade System (ATS) | Jest | `jest.config.js`, `jest.backend.config.js`, `jest.backend.runtime.config.js` |
| Horistic | Jest | `jest.config.js` |
| Python components | pytest | `pyproject.toml` |

## Running Tests

### ATS

```bash
cd ~/GitHub/atius

# All tests
npm test

# Backend unit tests
npm run test:backend

# Backend runtime/live tests
npm run test:backend:runtime

# Watch mode
npm run test:watch
```

### Horistic

```bash
cd ~/GitHub/horistic
npm test
```

### Python (pytest)

```bash
cd ~/GitHub/atius
pytest
# or with uv
uv run pytest
```

## Test File Naming

| Pattern | Description |
|---------|-------------|
| `test_*.test.js` | Backend unit/integration tests |
| `test_*.runtime.test.js` | Backend runtime/live tests |
| `__tests__/` | Additional test files |

## Test Configuration

ATS test reporters defined in `jest.reporters.js`.

Coverage thresholds: **not configured** (no `coverageThreshold` set).

## Playwright E2E

Playwright is used for browser automation and exchange testing (`~/GitHub/atius/backend/exchanges/mexc/automation/`).

Embedded Chromium at:
```
backend/exchanges/mexc/automation/browser/bin/chromium
```

## Test Results

Test output and reports stored in:
- `~/GitHub/atius/test-results/`
- `~/GitHub/atius/tests/`

## CI Integration

No GitHub Actions workflows detected for this project. Jenkinsfile present at `~/GitHub/atius/Jenkinsfile` for CI pipeline.
