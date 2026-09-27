---
name: omni-routine
description: Orquestração e execução de rotinas operacionais soberanas na frota ATIUS (SRV-1..4, Horistic, W11) via IA, CLI ou MCP, com contenção de CPU (<=20%), locks idempotentes e auditoria contínua.
---

# omni-routine

Motor de execução de rotinas operacionais intermediadas por IA, CLI ou MCP para a frota ATIUS.

## Quando usar
- Executar backups periódicos (`srv1:backup-gdrive`, `fleet-backup`).
- Sincronizar Obsidian vault e base do GBrain (`srv1:sync-vault`).
- Realizar limpezas de disco e retenção de logs (`srv1:cleanup-local`).
- Auditar limites de cgroups e uso de CPU da frota (`srv1:resource-audit`).
- Validar certificados TLS e PKI da frota (`fleet:pki-verify`).
- Disparar rotinas automatizadas com segurança fail-closed e sem tempestade de comandos.

## Comandos CLI (`omni routine`)

```bash
# Listar todas as rotinas disponíveis
omni routine list
omni routine list --json

# Ver detalhes de uma rotina
omni routine show srv1:backup-gdrive

# Simular execução (dry-run)
omni routine run srv1:backup-gdrive --dry-run

# Executar de fato (apply)
omni routine run srv1:backup-gdrive --apply

# Consultar status de uma execução anterior
omni routine status <run_id>
```

## Ferramentas MCP (`RoutineMcpHandler`)
Disponíveis para o agente via bridge MCP stdio/HTTP:
- `omni_routine_list(host_id)`: Retorna catálogo de rotinas cadastradas.
- `omni_routine_trigger(routine_id, dry_run)`: Planeja ou executa a rotina imediatamente.
- `omni_routine_status(run_id)`: Consulta o estado, exit code e tail de logs da run.

## Guardrails Invioláveis
1. **CPU Guardrail:** Rotinas de perfil `builds` executam restritas a 20% do host via cgroup `omni-builds.slice` e `nice -n 19`.
2. **Circuit Breaker:** 3 falhas consecutivas bloqueiam automaticamente novas execuções da rotina por 60 segundos, evitando tempestades de retry (command storm).
3. **Locks Atômicos:** Bloqueio mútuo por rotina com recuperação de locks obsoletos (stale lease recovery).
4. **Sanitização Determinística:** Chaves privadas PEM, tokens Bearer e credenciais são mascarados automaticamente nos logs sem cegar termos operacionais inofensivos.
5. **Zero-UI no Windows:** Processos executam com `CREATE_NO_WINDOW`, sem piscar consoles na tela.
