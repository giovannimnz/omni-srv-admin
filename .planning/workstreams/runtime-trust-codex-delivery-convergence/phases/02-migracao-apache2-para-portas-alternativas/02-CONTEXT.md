# Phase 2: Migração Apache2 para Portas Alternativas — Context

**Phase:** 02
**Goal:** Cloudflare Origin Rules update to route :443 → origin:9444 for all 66 hostnames

## Background

Phase 1 already migrated Apache2 from ports 80/443 to 9080/9444. All 37 HTTP vhosts and 40 HTTPS vhosts are serving on the new ports. certbot 5.5.0 is working with webroot authenticator.

**What's left:** Cloudflare is still proxying port 443 to origin port 443 (which is now empty). Traffic reaching Cloudflare edge on :443 needs to be routed to origin :9444.

## User Decisions (Locked)

- **D-12:** Cloudflare Origin Rules mapearão :443 → origin:9444 para os 60+ vhosts
- **D-13:** Apache2 `Listen` alterado de 80/443 para 9080/9444 (DONE in Phase 1)
- **D-14:** Todos os 60+ vhosts atualizados com novas portas (DONE in Phase 1)
- **D-15:** Cloudflare Origin Rules atualizadas para apontar para 9444
- **D-17:** Proxy mode mantido (proxied) — Origin Rules definem porta de origem

## Requirements

- **APCH-02:** 60+ vhosts atualizados com novas portas no Cloudflare

## Success Criteria

1. Cloudflare Origin Rules configured to route :443 → origin:9444 for all 66 hostnames
2. At least 3 vhosts tested and accessible via Cloudflare (curl through Cloudflare proxy)
3. API credentials verified (CF_API_TOKEN and CF_ZONE_ID set)
4. Rollback strategy documented (how to revert Origin Rules if something breaks)

## Constraints

- Cloudflare API token with `Zone Rulesets: Edit` permission required
- If API token not available, manual dashboard update is the fallback (66 hostnames = time-consuming)
- Origin Rules API replaces entire ruleset in single PUT — must GET-modify-PUT to preserve existing rules
- Must NOT break existing Cloudflare features (SSL, caching, security rules)

## Current State (from Phase 1)

- 66 hostnames catalogued at `/tmp/03-all-hostnames.txt`
- Cloudflare API credentials status: NOT SET (need to be provided by user)
- Template script at `/tmp/03-cloudflare-update.sh` (not executable, reference only)
- Apache2 serving on 9080/9444, verified working
- Ports 80/443 free on origin
