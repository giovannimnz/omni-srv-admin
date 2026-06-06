<!-- generated-by: gsd-doc-writer -->
# Development — Atius Home Server

## Project Structure

The home server contains multiple projects. The primary development targets are:

| Project | Location | Stack |
|---------|----------|-------|
| Atius Trade System | `~/GitHub/atius/` | Node.js/Fastify + Next.js + Python |
| Horistic | `~/GitHub/horistic/` | Node.js + Next.js + Python |
| Atius AI Router | `~/docker/Atius/router-ai-atius/` | Go (New-API fork) |

## Atius Trade System (ATS)

### Local Setup

```bash
# Clone/pull
cd ~/GitHub/atius
git pull

# Install dependencies
npm install

# Copy environment config
cp config/.env.example config/.env
# Edit config/.env with your values

# Build (if needed)
npm run build

# Start services
./start.sh
```

### Build Commands

| Command | Description |
|---------|-------------|
| `npm run build` | Build Next.js frontend |
| `npm run dev` | Development server with hot reload |
| `npm run lint` | ESLint check |
| `npm run lint:fix` | Auto-fix ESLint issues |
| `npm run format` | Prettier formatting |
| `npm run test` | Run Jest test suite |

### Code Style

| Tool | Config | Run |
|------|--------|-----|
| ESLint | `.eslintrc*`, `eslint.config.*` | `npm run lint` |
| Prettier | `.prettierrc*` | `npm run format` |

### Branch Conventions

No formal convention documented. Recent branches suggest:
- `feat/*` — new features
- `fix/*` — bug fixes
- `refactor/*` — refactoring

### Key Files

| File | Purpose |
|------|---------|
| `ecosystem.config.js` | PM2 process definitions |
| `jest.config.js` | Jest test configuration |
| `backend/server/api.js` | Fastify API entry point |
| `backend/exchanges/` | Exchange adapter implementations |
| `config/.env` | Environment variables |

## Horistic

| Command | Description |
|---------|-------------|
| `npm run dev` | Development server |
| `npm run build` | Build |
| `npm test` | Run tests |

## Atius AI Router

Location: `~/docker/Atius/router-ai-atius/`

Managed via Docker Compose. Rebuild after config changes:

```bash
cd ~/docker/Atius/router-ai-atius
docker compose build
docker compose up -d
```

## Scripts

| Script | Location | Purpose |
|--------|----------|---------|
| `start.sh` | `~/GitHub/atius/` | ATS service orchestration |
| `setup.sh` | `~/atius-srv/` | Server initial setup |
| `restart-containers.sh` | `~/atius-srv/` | Docker container restart |
| `install-chromium.sh` | `~/atius-srv/` | Browser automation setup |

## VS Code Remote Development

The server has a `.code-workspace` file at `~/GitHub/atius/atius.code-workspace` for VS Code remote SSH development.

Launch config at `~/GitHub/atius/launch.json` for debugger attachment.
