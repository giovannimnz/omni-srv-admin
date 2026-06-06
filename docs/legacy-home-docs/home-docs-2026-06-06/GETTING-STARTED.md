<!-- generated-by: gsd-doc-writer -->
# Getting Started — Atius Home Server

**Server:** atius-srv-1 (Oracle Cloud, Ubuntu 22.04, ARM64)
**Access:** SSH via WireGuard VPN `10.1.1.0/24`

## Prerequisites

| Requirement | Value |
|-------------|-------|
| WireGuard VPN | Client configured for `10.1.1.0/24` network |
| SSH key | Key-based auth for `ubuntu@10.1.1.11` |
| Sudo password | `REDACTED` (do not store sudo passwords in repo docs) |

## Initial Access

### 1. Connect to WireGuard VPN

Ensure your WireGuard client is active and you have an IP in the `10.1.1.0/24` range.

### 2. SSH to the server

```bash
ssh ubuntu@10.1.1.11
```

### 3. Verify services are running

```bash
pm2 list
```

Expected processes: `atius-api`, `atius-web`, `atius-webhook-signals`, `atius-bot-launcher`

### 4. Check Docker containers

```bash
docker ps
```

Expected: Plane stack containers (plane-mq, plane-db, plane-webl).

## Quick Start for ATS Development

### Clone/pull the project

```bash
cd ~/GitHub/atius
git pull
```

### Install dependencies

```bash
npm install
```

### Start services

```bash
./start.sh
```

### Stop services

```bash
./stop.sh
```

## Common Setup Issues

| Issue | Solution |
|-------|----------|
| SSH connection refused | Verify WireGuard VPN is active; try public IP instead |
| PM2 process not starting | Check `pm2 logs atius-api` for startup errors |
| Database connection failed | Verify PostgreSQL is running on port 8745 |
| `JWT_SECRET` not set | Set in `~/GitHub/atius/config/.env` before starting API |

## Next Steps

- See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for local development setup
- See [`docs/TESTING.md`](docs/TESTING.md) for testing infrastructure
- See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for environment variables
