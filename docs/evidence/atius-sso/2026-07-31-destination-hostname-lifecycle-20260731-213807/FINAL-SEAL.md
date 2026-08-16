# Selo final — Destino seguro hostname-only

- Data: 2026-07-31 BRT
- Runtime ATS build: `atius-1785544475988`
- PM2 `atius-web`: PID `2089505`, online
- Regra: `Destino seguro = URL.hostname`
- Navegação/segurança: URL completa validada preservada
- Scan anônimo: `12/12 PASS`, 12 screenshots
- Lifecycle: `12/12` sites, `24/24` ciclos, `96/96` screenshots
- Revisão visual: `12/12 PASS`
- Failures: `0`
- Contrato documental: `8/8` surfaces, `20/20` checks
- ATS target test: `18/18 PASS`
- `atius-sso` core/auth-web: `15/15 PASS`, typechecks PASS, dist rebuild PASS
- Source manifest: `29/29 PASS`
- Legacy `hostname + pathname` display pattern: absent from source and dist
- Runtime health: PM2 online, local `307`, public `/login=200`
- GBrain: slug canônico atualizado; readback dos três markers PASS
- Graphify `atius-sso`: `1.009` nodes, `1.116` edges, `stale=false`; queries
  `safeLabel` e `destinationLabel` presentes
- Graphify ATS: `32.050` nodes, `48.520` edges, `stale=false`; query
  `safeDisplayReturnTo` presente
- Graphify omni: `12.626` nodes, `18.682` edges, `stale=false`,
  `commit_stale=false`
- Graphify rebuilds: user-owned em `omni-builds.slice`, swap `0B`
- Evidence scan: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-destination-hostname-only-20260731-213651`
- Evidence lifecycle: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-destination-hostname-lifecycle-20260731-213807`
- Backup pré-mudança: `/home/ubuntu/backups/atius-sso-destination-hostname-pre-20260731-212540`
- Restore drill: PASS
- Commit/push: nenhum
