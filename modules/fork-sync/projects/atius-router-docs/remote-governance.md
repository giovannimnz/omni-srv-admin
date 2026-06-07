# Governança do Remote Separado `atius-router-docs`

**Decisão (Phase 09 — Docs Convergence Main Repo):**

O remote `giovannimnz/new-api-docs-v1` continua como remote do submodule em
`router-ai-atius/docs/atius-router-docs/`. Ele é a fonte `origin` do submodule
e não muda.

O checkout standalone em `/home/ubuntu/docker/Atius/atius-router-docs` será
mantido como mirror transitório até o fim do milestone v2.15, depois removido.

## Papéis

| Componente | Papel | Destino |
|------------|-------|---------|
| `giovannimnz/new-api-docs-v1` | Remote do submodule (origin) | Mantido como está |
| `docs/atius-router-docs/` (submodule) | Source canônico operacional | Permanente |
| `/home/ubuntu/docker/Atius/atius-router-docs` | Checkout standalone legado | Removido após validação |

## Critério de Remoção do Standalone

1. Sync via fork-script funcionando no submodule por ≥2 ciclos consecutivos
2. Build + deploy via systemd validado em produção
3. Nenhuma referência funcional ao path legado em scripts ou automações
4. Rollback documentado e testado

## Rollback

Se algo quebrar, o rollback é:
1. Parar service apontando para submodule
2. Restaurar `WorkingDirectory` no unit file para o path legado
3. Restart service
4. Verificar rotas
5. Submodule fica preservado para próxima tentativa
