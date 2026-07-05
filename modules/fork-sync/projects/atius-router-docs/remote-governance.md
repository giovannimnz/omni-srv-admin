# Governança do Remote Separado `atius-router-docs`

**Decisão (Phase 09 — Docs Convergence Main Repo):**

O remote `giovannimnz/new-api-docs-v1` continua como fork/origin do worktree em
`/home/ubuntu/GitHub/containers/router-ai-atius/docs/atius-router-docs`. O
upstream de comparação é `QuantumNous/new-api-docs-v1`.

Em 2026-07-05, os checkouts legados sob `/home/ubuntu/GitHub/containers/Atius`
foram movidos para backup/quarentena. O único path operacional ativo é o
worktree canônico dentro do fork `router-ai-atius`.

## Papéis

| Componente | Papel | Destino |
|------------|-------|---------|
| `giovannimnz/new-api-docs-v1` | Fork/origin | Mantido |
| `QuantumNous/new-api-docs-v1` | Upstream | Somente comparação/merge |
| `/home/ubuntu/GitHub/containers/router-ai-atius/docs/atius-router-docs` | Source canônico operacional | Permanente |
| `/home/ubuntu/GitHub/containers/Atius/*atius-router-docs*` | Checkouts legados | Quarentena/backup |

## Critério de Remoção do Standalone

1. Sync via fork-script funcionando no worktree por >=2 ciclos consecutivos
2. Build + deploy via systemd validado em produção
3. Nenhuma referência funcional ao path legado em scripts ou automações
4. Rollback documentado e testado

## Rollback

Se algo quebrar, o rollback é:
1. Parar `atius-router-docs.service`
2. Restaurar o último backup validado para o path canônico
3. `systemctl --user daemon-reload && systemctl --user start atius-router-docs.service`
4. Verificar rotas
5. Registrar o backup usado e o smoke resultante neste manual
