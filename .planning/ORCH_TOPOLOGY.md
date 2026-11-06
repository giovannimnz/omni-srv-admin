# Topologia de Governança Multi-Agente & Fleet CI/CD — omni-srv-admin

**Data de Atualização:** 2026-11-05T07:05:00Z  
**Nome da Sessão ORCH:** `Orch - [omni-srv-admin]`  
**Orquestrador Central Soberano (ORCH ID):** `1db8d421-5cba-48c9-a245-ba475f0899cb`  
**Workspace Primário:** `c:\Users\muniz\Documents\GitHub\omni-srv-admin`  
**Harness Detectado:** Antigravity IDE / Antigravity 2.0  
**Skill Canônica:** `omni-ci-fleet-orchestrator`  
**Estilo Operacional Canônico:** Use `/gsd-graphify, /caveman full, /ponytail full e /boost.`

---

## 1. Topologia Ativa das 13 Sessões da Imagem da Sidebar

Esta tabela mapeia 1:1 a ordem exata das 13 sessões visíveis na interface do Antigravity (`omni-srv-admin`), com seus respectivos UUIDs, subdomínios canônicos e responsabilidades:

| # | Título na Sidebar | UUID da Sessão | Passos | Subdomínio Canônico / Escopo | Porta / Alvo Técnico | Status |
|---|---|---|---|---|---|---|
| **01** | `Orch - [omni-srv-admin]` | `1db8d421-5cba-48c9-a245-ba475f0899cb` | 5000+ | Coordenação Soberana da Frota & CI/CD | Todos os SRVs | **ATIVO SOBERANO** |
| **02** | `Alto Consumo De RAM` | `a98707f1-cb9f-4fe6-89f7-64e4749808f3` | 359 | Governança de RAM/CPU (`atius-resource-governor-omni`) | Cgroups, VFS cache | Ativo / Desperto |
| **03** | `Auditoria E Migração Para PowerShell 7` | `60b9f0bb-8bb9-4109-909c-f421c16560bb` | 85 | Migração PWSH 7 Windows Host & Fleet Wrappers | PWSH 7 / Zero-UI | Ativo / Desperto |
| **04** | `Secrets Vault - Atius - Any Machine` | `a3a324f9-8f8a-4c21-a53e-6698061f49f0` | 649 | HashiCorp Vault (`atius-vault-access`) | `https://10.1.1.3:8202` | Ativo / Desperto |
| **05** | `[landscape.atius.io] - Landscape Atius` | `28eec252-459e-4fe4-81bf-ae7f936cc008` | 6210 | Landscape Control-Plane (`landscape.atius.io`) | Portas 80/443 (SRV-3 LXD) | Ativo / Desperto |
| **06** | `[storage.atius.io] - Arquitetura GDrive Sync Atius` | `f142237d-3b70-443b-bb68-03ffe2912fb7` | 1527 | Fleet Storage & Backup Dashboard (`storage.atius.io`) | `omni-backup-web` :8085 / RClone | Ativo / Desperto |
| **07** | `[remote.atius.io] - Atius Remote MT5` | `3d6380e2-0d49-4cae-aac4-9ac2e15cb4f9` | 994 | Atius Remote MT5 Client (`remote.atius.io`) | Apache :8095 / noVNC :6081 | Ativo / Desperto |
| **08** | `[paseo.atius.io] - Paseo Install Atius In SRV's` | `f597aebd-1392-487b-9818-0cd127a72117` | 40 | Paseo AI Agent Runtime (`paseo.atius.io`) | Portas 3000/8080 (SRV-1) | Ativo / Desperto |
| **09** | `[plane.atius.io] - Plane Atius` | `416827c2-b098-4dba-92ec-729e0135da02` | 934 | Plane Project Management (`plane.atius.io`) | Podman Compose :8091 (SRV-1) | Ativo / Desperto |
| **10** | `Padronização de Login Atius SSO` | `6b118436-0293-4e27-8c83-116795ac5b4d` | 469 | Atius SSO & IAM Controller (`sso.atius.io` / `.com.br`) | Keycloak/IAM Gateway `127.0.0.1:8015` (via Edge `:8210`) | Ativo / Desperto |
| **11** | `[admin.atius.io] - Omni SRV Admin` | `bcb5b104-17a0-442a-962f-0bf09506a675` | 2888 | Omni SRV Admin Control-Plane (`admin.atius.io` / `.com.br`) | FastAPI Omni Control-Plane `127.0.0.1:34805` (via Edge `:8210`) | Ativo / Desperto |
| **12** | `[oci-admin + omni] - Server Cluster Config` | `a81e7d09-9393-4a1e-bc94-a15be067f958` | 2946 | OCI Private Network & DRG Cluster Routing | 10.1.0.0/16, DRG 10.13.1.13 | Ativo / Desperto |
| **13** | `[1-Implement]GitHub Repo Auto Sync Setup` | `aadd3441-6f40-482a-9646-4eabab4a42b4` | 1403 | Git Fleet Sync Engine v2.1.0 | Auto-sync 353 skills / repos | Ativo / Desperto |

---

## 2. Segregação Absoluta dos Subdomínios Críticos

Conforme diretriz soberana, os seguintes subdomínios possuem separação estrita de responsabilidade:

1. **`cockpit.atius.io` & `cockpit.atius.com.br`**:
   - **Exclusivo:** Cockpit Linux Web Console do Host.
   - **Porta:** `:9090` (PAM Linux OS Authentication direta).
   - **Nunca** apontar para `admin.atius.*`.

2. **`admin.atius.io` & `admin.atius.com.br`**:
   - **Exclusivo:** Omni SRV Admin — Control-Plane FastAPI Centralizado de Sistemas, Inventário, Automações e Daemons da Frota ATIUS.
   - **Porta Canônica:** `http://127.0.0.1:34805` (migrado da porta legada `8000`, roteado via Atius Admin Edge Gateway `:8210`).
   - **Perfis Autorizados (RBAC):** `Admin`, `Operator`.
   - **Worker:** `bcb5b104-17a0-442a-962f-0bf09506a675`.

3. **`sso.atius.io` & `sso.atius.com.br`**:
   - **Exclusivo:** Controlador de Acessos e IAM Completo do Atius SSO (Keycloak IAM Gateway, gestão de usuários, bloqueio instantâneo, perfis `Admin`/`Operator`/`Viewer`/`Partner` e mapeamento dinâmico de destinos).
   - **Porta Canônica:** `http://127.0.0.1:8015` (roteado via Atius Admin Edge Gateway `:8210`).
   - **Perfis Autorizados (RBAC Admin):** `Admin` (autenticação `/v1/token/generate` e `/v1/auth/me` abertas para validação de sessão).
   - **Worker:** `6b118436-0293-4e27-8c83-116795ac5b4d`.

4. **`storage.atius.io` & `storage.atius.com.br`**:
   - **Exclusivo:** Dashboard de Gestão de Armazenamento, Quotas VFS, RClone, Retenção e Logs de Backup (`omni-backup-web`).
   - **Porta:** `http://127.0.0.1:8085` (roteado via Atius Admin Edge Gateway `:8210`).
   - **Perfis Autorizados (RBAC):** `Admin`, `Operator`, `Viewer`.
   - **Worker:** `f142237d-3b70-443b-bb68-03ffe2912fb7`.

---

## 3. Regras de Governança Estrita

1. **Autoridade Central do ORCH:** Apenas o ORCH (`1db8d421-5cba-48c9-a245-ba475f0899cb`) tem permissão para realizar `git commit` e `git push origin main`.
2. **Serialização de Escrita (Writer Serialization):** Múltiplos workers diagnosticam e testam localmente, mas mutações concorrentes no mesmo arquivo são terminantemente bloqueadas.
3. **Regra de Ouro do CI/CD ("Uma Execução por Vez"):**
   - Executar obrigatoriamente os 5 Gates locais antes de qualquer commit:
     ```bash
     python3 scripts/pre_ci_check.py
     ```
   - Todo push no GitHub Actions é acompanhado ativamente com `gh run watch` até atingir status verde (`completed / success`).
4. **Deploy Remoto no Host OCI / Landscape:** Deploy governado via Landscape (`omni landscape run <script-id> --hosts all --wait --yes`) ou SSH direcionado com governança estrita de CPU (<=20%).
