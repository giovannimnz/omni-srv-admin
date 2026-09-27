# Omni Routine Engine: Plano de Implementação TDD & Arquitetura Soberana

**Data:** 2026-09-27  
**Modo:** /gsd-autonomous /tdd /caveman Full  
**Objetivo:** Implementar motor unificado e seguro de execução de rotinas orquestradas por IA e operadores (Skill + MCP + CLI + Direct API) com guardrails de CPU <= 20%, locks idempotentes, mitigação SRE contra split-brain e auditoria persistente.

---

## 1. Arquitetura do Sistema

```text
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACES DE DISPARO                    │
│   • Skill Semântica: /omni-routine (Antigravity/Codex)      │
│   • Ferramentas MCP: omni_routine_* (Edge / Stdio Bridge)   │
│   • CLI Headless: omni routine run|list|status|cancel       │
│   • Direct API / Python: omni.routine_engine                │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    OMNI ROUTINE ENGINE                      │
│   • RoutineRegistry (catálogo estático + dinâmico)          │
│   • StateMachine (PENDING -> RUNNING -> COMPLETED/FAILED)   │
│   • LocalLockManager (fcntl / atomic lock file)             │
│   • CircuitBreaker (bloqueio temporário após 3 falhas)      │
│   • MultiPatternRedactor (PEM, Bearer, API Keys, Passwords) │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    GUARDRAILS & RUNNER                      │
│   • Linux: cgroup omni-builds.slice (CPU <= 20%) + nice 19  │
│   • Windows: Zero-UI headless launcher                      │
│   • ProcessGroup: start_new_session + killpg em timeout     │
│   • SSH Fallback: DRG (10.11.x) -> WG (10.100.x) -> WAN     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    AUDITORIA & MEMÓRIA                      │
│   • Log local em ~/.logs/routines/<run_id>.json             │
│   • GBrain (remember / timeline entry para anomalias)       │
│   • Obsidian (Second Brain log estruturado em incidentes)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Waves de Execução TDD

### Wave 1: Core Engine & Contracts (TDD)
- **Objetivo:** Definir modelos de dados, máquina de estados finita, registry de rotinas, redaction seguro de segredos e locks com timeout.
- **Teste (RED):** `cli/omni/tests/test_routine_engine.py`
  - `test_routine_registry_load_and_validate`: Valida catálogo de rotinas padrão (`backup-gdrive`, `sync-vault`, `cleanup-local`, `resource-audit`, `fleet-pki-verify`).
  - `test_state_machine_valid_transitions`: Garante transições permitidas (`PENDING` -> `RUNNING` -> `COMPLETED/FAILED`).
  - `test_state_machine_invalid_transition_raises`: Impede salto inválido de estado.
  - `test_lock_manager_mutual_exclusion`: Impede duas instâncias da mesma rotina rodando juntas.
  - `test_lock_manager_stale_lock_recovery`: Recupera lock órfão expirado.
  - `test_multipattern_redactor`: Mascara chaves PEM, tokens Bearer e senhas, mas preserva logs legítimos com palavras inofensivas.
- **Implementação (GREEN):** `cli/omni/routine_engine.py`
- **Validação (GREEN):** Pytest 100% verde.

### Wave 2: SRE Guardrails & Execution Runner (TDD)
- **Objetivo:** Executar processos com isolamento estrito de CPU (quota <= 20% via `omni-builds.slice` ou `nice`), timeout com terminação limpa de process group (`killpg`), e Circuit Breaker para evitar tempestades de retry.
- **Teste (RED):** `cli/omni/tests/test_routine_runner.py`
  - `test_runner_executes_simple_command_successfully`: Execução bem-sucedida com captura de stdout e tempo.
  - `test_runner_enforces_cpu_quota_wrapper`: Valida que rotinas com profile `builds` são envelopadas com `omni-builds.slice` ou `nice 19`.
  - `test_runner_timeout_terminates_process_group`: Valida que comando excedendo timeout é morto sem órfãos.
  - `test_runner_circuit_breaker_trips_after_failures`: Valida que 3 falhas consecutivas ativam o Circuit Breaker.
  - `test_runner_sanitizes_output_before_persistence`: Valida que a saída gravada passou pelo redactor.
- **Implementação (GREEN):** `cli/omni/routine_runner.py`
- **Validação (GREEN):** Pytest 100% verde.

### Wave 3: Omnichannel CLI & MCP Adapters + Skill Sync (TDD & E2E)
- **Objetivo:** Expor a camada CLI `omni routine`, o adapter de ferramentas MCP `omni_routine_*`, a sincronização com GBrain/Obsidian e o Skill Antigravity/Codex.
- **Teste (RED):** `cli/omni/tests/test_routine_cli_and_mcp.py`
  - `test_cli_routine_list`: Valida saída tabular e `--json` de `omni routine list`.
  - `test_cli_routine_run_dry_run`: Valida `omni routine run <id> --dry-run`.
  - `test_cli_routine_run_execute`: Valida execução real e geração de run log.
  - `test_cli_routine_status`: Valida consulta de status da última run.
  - `test_mcp_routine_handler_tools`: Valida handlers MCP para integração do agente.
- **Implementação (GREEN):**
  - `cli/omni/routine.py` (grupo click) e registro em `cli/omni/cli.py`.
  - `cli/omni/routine_mcp.py` (adapter de MCP tools).
  - Skill `.agents/skills/omni-routine/SKILL.md` e `~/.gemini/config/skills/omni-routine/SKILL.md`.
- **Validação (GREEN):** Pytest suite completa 100% verde.

---

## 3. Critérios de Parada e Aceite (/goal)
- [ ] 100% dos testes unitários e de integração aprovados no pytest.
- [ ] Zero erros de lint ou imports quebrados.
- [ ] Graphify atualizado refletindo os novos módulos do engine.
- [ ] Documentação completa no repositório, GBrain e Obsidian.
