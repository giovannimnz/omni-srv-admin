<!-- generated-by: gsd-doc-writer -->
# Server Architecture

**Host:** atius-srv-1 (Oracle Cloud Infrastructure, Ubuntu 22.04, ARM64/aarch64)
**Access:** SSH to `ubuntu@10.1.1.11` via WireGuard VPN `10.1.1.0/24`

## System Overview

Atius-srv-1 is a personal home server hosting multiple projects, primarily the Atius Trade System (ATS) and Horistic automated trading platforms. The server runs on Oracle Cloud Infrastructure with a public IP fronted by Cloudflare, and internal services accessed via WireGuard VPN.

```
Internet (Cloudflare) --> atius-srv-1 (Apache reverse proxy)
                              |
                         WireGuard VPN (10.1.1.0/24)
                              |
                    +---------+---------+
                    |                   |
              Services              Internal API
              (80/443)              (10.1.1.x)
```

## Component Diagram

```
atsius-srv-1 (Oracle Cloud / Ubuntu 22.04 / ARM64)
|
+-- Apache 2.4.52 (reverse proxy, ports 80/443 + alt 8080/8443)
|       |-- Cloudflare SSL origin certs (/etc/ssl/cloudflare/)
|       |-- Virtual hosts: atius.com.br, horistic.com
|
+-- Docker (containerd)
|       |-- Plane (project management) — plane-app-*, plane-mq, plane-db
|       |-- FreeIPA (planned) — AlmaLinux 9 container for LDAP/SSO
|
+-- PostgreSQL 17 (port 8745)
|       |-- atius_prd, signals, horistic databases
|
+-- MongoDB (port 27017)
|       |-- PM2 web replica set
|
+-- PM2 (namespace: atius)
|       |-- atius-api (Fastify, port 8015)
|       |-- atius-web (Next.js, port 3015)
|       |-- atius-webhook-signals
|       |-- atius-bot-launcher (multi-exchange)
|       |-- Python workers via uv bridge
|
+-- Node.js (NVM) + Python (uv)
|       |-- Node.js v24.13.1
|       |-- Python 3.10.12 / 3.11
|
+-- Hermes Agent (this instance)
        |-- Telegram bot for Atius Capital Group
        |-- Atius AI Router management
        |-- PostgreSQL memory provider
```

## Data Flow

1. **External request** arrives via Cloudflare → Apache reverse proxy
2. **Apache** routes to internal service (Next.js frontend or Fastify API)
3. **Fastify API** (port 8015) handles trading logic, exchange adapters, database ops
4. **PostgreSQL** (port 8745) stores users, accounts, positions, orders, signals
5. **PM2** manages all Node.js and Python processes with systemd wrapper
6. **Telegram bot** receives trading signals and sends alerts via Hermes Agent
7. **WebSocket** streams price and position updates to dashboard

## Key Abstractions

| Component | Type | Location |
|-----------|------|----------|
| Fastify API server | Node.js HTTP server | `~/GitHub/atius/backend/server/api.js` |
| Next.js frontend | React SSR | `~/GitHub/atius/frontend/` |
| Exchange adapters | CCXT-based | `~/GitHub/atius/backend/exchanges/{exchange}/` |
| Signal processor | Python | `~/GitHub/atius/backend/` |
| PM2 ecosystem | Process config | `~/GitHub/atius/ecosystem.config.js` |
| Atius AI Router | New-API fork | `~/docker/Atius/router-ai-atius/` |

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `~/GitHub/atius/` | Atius Trade System — main trading platform |
| `~/GitHub/horistic/` | Horistic — futures trading platform |
| `~/GitHub/caveman/` | Caveman CLI compression tools |
| `~/GitHub/agent/` | Hermes Agent PostgreSQL memory provider |
| `~/GitHub/forks/` | Forked third-party repositories |
| `~/docker/Atius/` | Atius AI Router Docker deployment |
| `~/atius-srv/` | Server setup scripts and documentation |
| `~/.hermes/` | Hermes Agent configuration and skills |
| `~/.agents/` | Claude Code agent configurations |
| `~/bruno/` | Bruno API collection for testing |

## Network

| Endpoint | Port | Description |
|----------|------|-------------|
| atius-srv-1 (public) | 22 | SSH (key-based) |
| atius-srv-1 (internal) | 10.1.1.11 | WireGuard VPN interface |
| Apache (alt) | 8080/8443 | Alternative ports (coexist with FreeIPA) |
| atius-api | 8015 | Fastify API |
| atius-web | 3015 | Next.js frontend |
| PostgreSQL | 8745 | Database |
| MongoDB | 27017 | PM2 web replica set |

## Services

### Running Services (PM2)

```
atius-api           Fastify REST API
atius-web           Next.js frontend
atius-webhook-signals  Webhook processor
atius-bot-launcher   Multi-exchange bot orchestration
```

### Docker Containers

```
plane-app-plane-mq-1      RabbitMQ message broker
plane-app-plane-db-1     PostgreSQL for Plane
plane-app-plane-webl-1   Plane frontend
```

### Planned

- **FreeIPA** via Docker (AlmaLinux 9) — LDAP/SSO for Linux machine login
- **Keycloak** direct install — identity provider
