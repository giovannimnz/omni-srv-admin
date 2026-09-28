---
name: omni-routine
description: Orquestração e execução de rotinas operacionais soberanas na frota ATIUS (SRV-1..4, Horistic, W11) via IA, CLI ou MCP, com contenção de CPU (<=20%), locks idempotentes, dispatcher SSH resiliente e auto-cura governada.
---

# omni-routine

Motor de execução de rotinas operacionais intermediadas por IA, CLI ou MCP para a frota ATIUS.

## Quando usar
- Executar backups periódicos (`srv1:backup-gdrive`, `fleet-backup`).
- Sincronizar Obsidian vault e base do GBrain (`srv1:sync-vault`).
- Realizar limpezas de disco e retenção de logs (`srv1:cleanup-local`).
- Auditar limites de cgroups e uso de CPU da frota (`srv1:resource-audit`).
- Validar certificados TLS e PKI da frota (`fleet:pki-verify`).
- Disparar rotinas automatizadas com segurança fail-closed, multi-host SSH e sem tempestade de comandos.
- Diagnosticar falhas e respeitar limites de auto-cura de agentes de IA.

## Comandos CLI (`omni routine`)

```bash
# Listar todas as rotinas disponíveis
omni routine list
omni routine list --host atius-srv-1
omni routine list --json

# Ver detalhes de uma rotina
omni routine show srv1:backup-gdrive

# Simular execução (dry-run)
omni routine run srv1:backup-gdrive --dry-run

# Executar de fato no host alvo configurado via SSH multi-caminho (ou local)
omni routine run srv1:backup-gdrive --apply

# Forçar execução no host local (ignora target_host do inventário)
omni routine run srv1:backup-gdrive --apply --local

# Sobrescrever host de destino
omni routine run srv1:backup-gdrive --apply --host atius-srv-2

# Consultar status de uma execução anterior
omni routine status <run_id>

# Diagnosticar falhas, circuit breaker e rate-budget de auto-cura
omni routine diagnose srv1:backup-gdrive
omni routine diagnose --run <run_id>
omni routine diagnose srv1:backup-gdrive --json
```

## Ferramentas MCP Nativas (`omni-routine`)
Registrado no runtime MCP do Antigravity IDE (`omni-routine` via stdio):
- `omni_routine_list(host_id)`: Retorna catálogo de rotinas cadastradas.
- `omni_routine_trigger(routine_id, target_host, dry_run)`: Planeja ou executa a rotina imediatamente via dispatcher multi-rota.
- `omni_routine_status(run_id)`: Consulta o estado, exit code, rota SSH utilizada e tail de logs da run.
- `omni_routine_diagnose(routine_id, run_id)`: Realiza análise causal de erros (ex: `NETWORK_TIMEOUT`, `BINARY_NOT_FOUND`, `LOCK_HELD`) e avalia rate budget de auto-cura (`PERMITTED` vs `BLOCKED_AUTO_HEAL`).

## Guardrails Invioláveis
1. **CPU Guardrail:** Rotinas de perfil `builds` executam restritas a 20% do host via cgroup `omni-builds.slice` e `nice -n 19`.
2. **Dispatcher Multi-Host Resiliente:** Execuções remotas utilizam fallback estrito de 3 vias:
   - Rota 1: OCI DRG / Rede Privada
   - Rota 2: WireGuard VPN (`10.100.100.x`)
   - Rota 3: Casa WAN / NAT com porta dedicada (ex: `8122`, `8222`, `8322`)
   - Flags SSH invioláveis: `BatchMode=yes ConnectTimeout=5 ServerAliveInterval=10 ServerAliveCountMax=3 StrictHostKeyChecking=accept-new TCPKeepAlive=no`.
3. **Prevenção de Loop Infinito de IA (Auto-Heal Governor):**
   - Rate budget: máximo de 3 tentativas de remediação / 15 minutos por rotina.
   - Quarentena automática de 30 minutos em caso de esgotamento (`BLOCKED_AUTO_HEAL`).
4. **Circuit Breaker:** 3 falhas consecutivas bloqueiam automaticamente novas execuções da rotina por 60 segundos, evitando tempestades de retry (command storm).
5. **Locks Atômicos:** Bloqueio mútuo por rotina com recuperação de locks obsoletos (stale lease recovery).
6. **Sanitização Determinística:** Chaves privadas PEM, tokens Bearer e credenciais são mascarados automaticamente nos logs sem cegar termos operacionais inofensivos.
7. **Zero-UI no Windows:** Processos executam com `CREATE_NO_WINDOW`, sem piscar consoles na tela.
