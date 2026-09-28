# Omni Routine Engine: Fase 2 — Frota Multi-Host, Servidor MCP Nativo e Auto-Cura

**Data:** 2026-09-28  
**Modo:** /gsd-autonomous /tdd /caveman Full /ponytail Full  
**Objetivo:** Evoluir o Omni Routine Engine com Dispatcher Multi-Host (SSH fallback resiliente), Servidor MCP Stdio nativo registrado no Antigravity e Motor de Auto-Diagnóstico com Circuit Breaker contra loops de IA.

---

## 1. Arquitetura da Fase 2

```text
┌─────────────────────────────────────────────────────────────┐
│             ANTIGRAVITY IDE / CODEX RUNTIME                 │
│   • MCP Stdio Nativo: omni_routine_stdio                    │
│   • Ferramentas: list, run, status, diagnose                │
│   • Skill: /omni-routine                                    │
└──────────────────────────────┬──────────────────────────────┘
                               │ JSON-RPC Stdio
┌──────────────────────────────▼──────────────────────────────┐
│                  OMNI ROUTINE MCP SERVER                    │
│   • tools/list & tools/call                                 │
│   • MultiPatternRedactor (sanitização de segredos)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  ROUTINE FLEET DISPATCHER                   │
│   • Local? -> RoutineRunner (cgroups omni-builds.slice)     │
│   • Remoto? -> SSH Multi-Path Fallback (DRG -> WG -> WAN)   │
│     - ConnectTimeout=5s, ServerAliveInterval=10s x 3        │
│     - Execução remota delegada com lock e cgroup            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│              AUTO-DIAGNÓSTICO & HEALING CONTROLLER          │
│   • Classificação causal do erro                            │
│   • Rate budget: máx 3 tentativas / 15 min                  │
│   • Quarentena automática de 30 min (Anti-Loop IA)          │
│   • Gravação de anomalias no GBrain e Obsidian              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Waves de Execução TDD

- **Wave 4 (Dispatcher Multi-Host):**
  - Teste (RED): `cli/omni/tests/test_routine_dispatcher.py`
  - Código (GREEN): `cli/omni/routine_dispatcher.py`
- **Wave 5 (Servidor MCP Stdio Nativo):**
  - Teste (RED): `cli/omni/tests/test_routine_mcp_server.py`
  - Código (GREEN): `cli/omni/routine_mcp_server.py`
  - Configuração: Registro em `~/.gemini/config/mcp_config.json`
- **Wave 6 (Diagnósticos e Auto-Cura SRE):**
  - Teste (RED): `cli/omni/tests/test_routine_diagnostics.py`
  - Código (GREEN): `cli/omni/routine_diagnostics.py`
- **Wave 7 (Validação E2E e Registro Operacional):**
  - Testes de regressão completos (Pytest)
  - Registro de Fatos no GBrain e Obsidian
  - Atualização do Graphify
