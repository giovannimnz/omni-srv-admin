# Multi-stage build for the new-api-docs-v1 (Atius-branded) documentation site.
#
# ATIUS: This Dockerfile is part of the Atius fork. It uses bun for
# faster install + build, and adds custom healthcheck + env vars for
# the Atius deployment. The atius-router-docs-rebrand.sh script
# (in fork-sync) drops this file when the upstream doesn't have it.
#
# Stage 1: install deps + run prebuild + build (multi-stage, bun)
# Stage 2: minimal runtime with next start (non-standalone since
#          upstream doesn't enable `output: 'standalone'`)
#
# Build context: the docs site repo (cloned from upstream)
# Image:    localhost/router-ai-atius-docs:local

# ---- Stage 1: deps + build ----
FROM docker.io/library/node:20-bookworm-slim AS builder

# Install Bun (the official install script uses $HOME/.bun, NOT
# /usr/local/bun which is what the older docs say).
ENV BUN_INSTALL=/root/.bun
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && curl -fsSL https://bun.sh/install | bash \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.bun/bin:${PATH}"

WORKDIR /app

# Install deps with bun (lockfile-friendly, faster than npm).
# Use --ignore-scripts because fumadocs-mdx postinstall tries to import
# ESM modules with relative paths that fail in a clean container — the
# same step runs in the prebuild script below with proper resolution.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --ignore-scripts

# Copy source + content
COPY . .

# Build the standalone bundle
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_NEW_API_URL="https://router.atius.com.br"
RUN bun run prebuild && bun run build

# ---- Stage 2: minimal runtime ----
FROM docker.io/library/node:20-bookworm-slim AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3003
ENV HOSTNAME=0.0.0.0

# Install production-only deps (no devDependencies, no postinstall scripts).
COPY package.json bun.lock ./
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && curl -fsSL https://bun.sh/install | bash \
    && rm -rf /var/lib/apt/lists/* \
    && export PATH="/root/.bun/bin:${PATH}" \
    && bun install --omit=dev --frozen-lockfile --ignore-scripts

# Copy full build output (build/ is .next/, public/ is user uploads).
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/public ./public

USER node
EXPOSE 3003

# Healthcheck: GET / via the standalone server (always 200 for Next.js).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:3003/ || exit 1

CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3003", "-H", "0.0.0.0"]
