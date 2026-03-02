# [TASK010] - Migração Infra/PM2/Postgres para Atius

**Status:** Completed  
**Added:** 16/02/2026  
**Updated:** 16/02/2026

## Original Request

Atualizar documentação de infraestrutura com rebranding completo, corrigir naming/portas em PM2 e configs, reconstruir scripts PostgreSQL, executar backup completo de `horistic`, validar integridade, restaurar em `AtiusPrd` e `AtiusDev`, e subir ATS em PM2 usando `AtiusPrd`.

## Thought Process

1. Rebranding e portas precisavam ser consistentes entre `.env`, `ecosystem*.js`, scripts PM2 e docs de infraestrutura.
2. Scripts de Postgres anteriores eram frágeis (sem checksum, sem validação de TOC, sem validação pós-restore).
3. Era necessário validar paridade de dados entre origem e destinos com contagem exata por tabela.
4. O frontend PM2 usava `npm start` hardcoded em `3050`; foi necessário forçar `next start -p 3015` no ecosystem.

## Implementation Plan

- [x] Ajustar `.env` para portas de produção (`8015/3015`)
- [x] Atualizar `ecosystem.config.js` e `ecosystem.testnet.config.js`
- [x] Rebrand e ajuste de paths em `scripts/pm2/*.desktop`
- [x] Rebuild completo de `scripts/postgres/*`
- [x] Atualizar docs em `docs/infrastructure/*` e renomear arquivos com `ATIUS`
- [x] Executar backup de `horistic` com validações
- [x] Restaurar em `AtiusPrd` e `AtiusDev`
- [x] Validar integridade (estrutura + contagem exata)
- [x] Subir PM2 do ATS e remover processos legados `horistic-*`

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks

| ID | Description | Status | Updated | Notes |
|----|-------------|--------|---------|-------|
| 10.1 | Patch de config e ports | Complete | 16/02 | `.env`, `ecosystem*.js` |
| 10.2 | Rebrand PM2 scripts | Complete | 16/02 | `scripts/pm2/*.desktop` |
| 10.3 | Rebuild scripts postgres | Complete | 16/02 | backup/restore/vacuum robustos |
| 10.4 | Rebrand docs infraestrutura | Complete | 16/02 | arquivos renomeados para `ATIUS` |
| 10.5 | Backup horistic | Complete | 16/02 | dump + toc + sha256 + meta |
| 10.6 | Restore AtiusPrd | Complete | 16/02 | sucesso, 34 tabelas públicas no restore log |
| 10.7 | Restore AtiusDev | Complete | 16/02 | sucesso, 34 tabelas públicas no restore log |
| 10.8 | Validação de paridade | Complete | 16/02 | `ROW_COUNT_PARITY=OK` |
| 10.9 | PM2 start ATS | Complete | 16/02 | stack `atius-*` online |

## Progress Log

### 16/02/2026
- Atualizadas portas de produção para `8015/3015` em configs principais
- Corrigido naming PM2 legado (`starboy/horistic` -> `atius`)
- Scripts de Postgres reconstruídos com `set -Eeuo pipefail`, checksum e validação de TOC
- Backup criado: `horistic-20260216-200537.dump`
- Restore concluído com sucesso em `AtiusPrd` e `AtiusDev`
- Integridade validada com contagem exata por tabela (`ROW_COUNT_PARITY=OK`)
- PM2 iniciado com ecosystem atualizado; processos legados `horistic-*` removidos
- Ajuste final do `atius-web` para subir em `3015` via `next start -p 3015`

## Arquivos Relevantes

- `config/.env`
- `ecosystem.config.js`
- `ecosystem.testnet.config.js`
- `scripts/pm2/*.desktop`
- `scripts/postgres/*.sh`
- `docs/infrastructure/apache/APACHE_CONFIG_TRADE_ATIUS_FINAL.conf`
- `docs/infrastructure/apache/CONFIGURACAO_APACHE_REVERSE_PROXY_TRADE_ATIUS.md`
- `docs/infrastructure/domains/CONFIGURACAO_DOMINIOS_ATIUS_FINAL.md`
- `docs/infrastructure/domains/MIGRACAO_DOMINIO_ATIUS_UNICO.md`
