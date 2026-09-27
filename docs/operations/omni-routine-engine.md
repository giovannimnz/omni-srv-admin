# Omni Routine Engine — Motor Soberano de Rotinas Operacionais

O **Omni Routine Engine** é o subsistema unificado do `omni-srv-admin` para execução, agendamento e monitoramento de rotinas operacionais nos servidores da frota ATIUS (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv` e hosts Windows/WSL).

## 1. Arquitetura em 4 Camadas Interoperáveis

1. **Camada Skill Semântica (`/omni-routine`):** Permite invocação natural e declarativa pelos agentes de IA (Antigravity IDE e Codex).
2. **Camada MCP (`RoutineMcpHandler`):** Expõe as ferramentas `omni_routine_list`, `omni_routine_trigger` e `omni_routine_status` para o bridge stdio/HTTP de IA.
3. **Camada CLI (`omni routine`):** Comandos headless para operadores e terminais (`list`, `show`, `run`, `status`).
4. **Camada Direct API:** Módulos Python `omni.routine_engine` e `omni.routine_runner` utilizáveis diretamente por daemons e endpoints.

## 2. Guardrails Invioláveis e Mitigações SRE

- **Contenção de CPU (<= 20%):** Comandos com profile `builds` são automaticamente envelopados em cgroup `omni-builds.slice` com `nice -n 19`, respeitando a quota máxima de 0.8 vCPU na frota ARM64 OCI.
- **Circuit Breaker Anti-Storm:** Após 3 falhas consecutivas, a rotina é bloqueada por 60 segundos com retorno de erro estruturado, eliminando loops de retry do modelo.
- **Process Group Isolation:** Em sistemas Unix/Linux, execuções usam `start_new_session=True`. Em caso de timeout, `os.killpg` garante terminação limpa de todo o grupo de processos (sem processos zumbis).
- **Sanitização Determinística de Segredos:** Chaves PEM, tokens de autorização Bearer e senhas são mascarados antes de qualquer persistência em disco ou retorno para a IA.
- **Zero-UI no Windows:** No Windows host, processos são iniciados com `subprocess.CREATE_NO_WINDOW`.

## 3. Catálogo de Rotinas Padrão

| ID | Host | Profile | Descrição |
|---|---|---|---|
| `srv1:backup-gdrive` | `atius-srv-1` | `builds` | Backup rclone completo para o Google Drive com verificação |
| `srv1:sync-vault` | `atius-srv-1` | `transfers` | Sincronização git do Obsidian vault e dump incremental do GBrain |
| `srv1:cleanup-local` | `atius-srv-1` | `interactive` | Cleanup semanal e retenção de 15 dias em `~/.logs` |
| `srv1:resource-audit` | `atius-srv-1` | `interactive` | Auditoria de hotspots de CPU, limites de cgroup e disco |
| `fleet:pki-verify` | `atius-srv-1` | `interactive` | Verificação de integridade dos certificados TLS internos da frota |
