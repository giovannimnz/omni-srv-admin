# Phase 29: Cloudflare DNS Evidence for Landscape Self-hosted

**Generated:** 2026-06-25T03:21:16Z
**Zone:** `atius.com.br`
**Record:** `landscape.atius.com.br`
**Purpose:** Landscape self-hosted endpoint for the v1.2 governance track.

## DNS record

| Field | Value |
| --- | --- |
| action | `created` |
| type | `A` |
| name | `landscape.atius.com.br` |
| content | `137.131.190.161` |
| proxied | `false` |
| ttl | `300` |

## Operational note

The record is intentionally DNS-only (`proxied=false`) so Landscape web/API/client traffic reaches the origin directly. Cloudflare proxying can be evaluated later only after Landscape ports, TLS mode, client enrollment, and callbacks are proven compatible.

No Cloudflare credentials are stored in this artifact.
