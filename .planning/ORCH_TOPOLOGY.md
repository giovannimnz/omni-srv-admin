# Topologia de Governança Multi-Agente & Fleet CI/CD — omni-srv-admin

**Data de Atualização:** 2026-11-01T23:16:30Z  
**Nome da Sessão ORCH:** `Orch - [omni-srv-admin]`  
**Orquestrador Central Soberano (ORCH ID):** `1db8d421-5cba-48c9-a245-ba475f0899cb`  
**Workspace Primário:** `omni-srv-admin` (`c:\Users\muniz\Documents\GitHub\omni-srv-admin`)  
**Harness Detectado:** Antigravity IDE / Antigravity 2.0  
**Estilo Operacional Canônico:** Use `/gsd-graphify, /caveman full, /ponytail full e /boost.`

---

## 1. Topologia de Sessões & Status de Handshake dos Workers

| # | Sessão / Worker Label | Sessão ID (UUID) | Escopo / Especialidade Canônica | Status & Entregas Homologadas |
|---|---|---|---|---|
| **ORCH** | `Orch - [omni-srv-admin]` | `1db8d421-5cba-48c9-a245-ba475f0899cb` | Coordenação central, controle exclusivo de commit/push main, CI/CD watch e deploy OCI | **ATIVO SOBERANO** |
| **W1** | `[remote.atius.io] - Atius Remote MT5` | `3d6380e2-0d49-4cae-aac4-9ac2e15cb4f9` | Dual-domain Apache (8095), fix display :31 na porta 6081 (livre de lockscreen VM), SSO Keycloak | **Homologado / Standby Ativo** |
| **W2** | `[plane.atius.io] - Plane Atius` | `416827c2-b098-4dba-92ec-729e0135da02` | Plane Project Management, Podman Compose SRV-1, MinIO SSL, alinhamento frota | **Homologado / Standby Ativo** |
| **W3** | `[1-Implement] GitHub Repo Auto Sync Setup` | `aadd3441-6f40-482a-9646-4eabab4a42b4` | Auto-sync v2.0.0, isolamento repos confidenciais, skills sync (353) e symlinks frota | **Homologado / Standby Ativo** |
| **W4** | `[admin.atius.io] - Omni SRV Admin` | `bcb5b104-17a0-442a-962f-0bf09506a675` | Landscape LXD, Phase 51 script 13, Horistic 10.41.0.0/16, Qwen3 cutover SRV-4 | **Phase 47.1 100% Concluída (39/39 testes) / Standby Ativo** |
| **W5** | `[oci-admin + omni] - Server Cluster Config` | `a81e7d09-9393-4a1e-bc94-a15be067f958` | Topologia cluster OCI, rotas DRG 10.13.1.13, integração aln-srv e Horistic | **Homologado / Standby Ativo** |
| **W6** | `[storage.atius.io] - Arquitetura GDrive Sync Atius` | `f142237d-3b70-443b-bb68-03ffe2912fb7` | /mnt/gdrive FUSE SRV-1..4, backup diário DBs 14d, autoclean 8GB recuperados, frontend spec | **Homologado / Standby Ativo** |
| **W7** | `Alto Consumo De RAM` | `a98707f1-cb9f-4fe6-89f7-64e4749808f3` | RAM 83%->50%, CPU 32%, eliminação de git sprawl em $PROFILE, guardrail CPUQuota=20% | **Homologado / Standby Ativo** |
| **W8** | `Secrets Vault - Atius - Any Machine` | `a3a324f9-8f8a-4c21-a53e-6698061f49f0` | atius-vault-access (34 profiles), runtime-repo (353 skills), sync v2.1.0, probe storage | **Homologado / Standby Ativo** |
| **W9** | `[landscape.atius.io] - Landscape Atius` | `28eec252-459e-4fe4-81bf-ae7f936cc008` | Landscape Server LXD SRV-3, rota DRG 10.13.1.13, scripts frota, ingress dual-domain | **Homologado / Standby Ativo** |

---

## 2. Regras de Governança Estrita

1. **Autoridade Central do ORCH:** Apenas o ORCH tem permissão para realizar `git commit` e `git push origin main`.
2. **Serialização de Escrita (Writer Serialization):** Múltiplos workers diagnosticam e testam localmente, mas mutações concorrentes no mesmo arquivo são bloqueadas.
3. **Regra de Ouro do CI/CD:** Todo push no GitHub Actions é acompanhado ativamente com `gh run watch` até ficar 100% verde ("uma execução por vez").
4. **Deploy Remoto no Host OCI:** Deploy governado via SSH no servidor OCI com `git fetch origin main && git reset --hard origin/main`, build sob governança de CPU (<=20%) e reinício dos serviços afetados.
5. **Cadeia Canônica de Dependência:**
   `Secrets Vault (W8)` -> `OCI Cluster Config (W5)` -> `Landscape Control-Plane (W9)` -> `Auto-Sync / Storage (W3 / W6)` -> `Aplicações & Web (W4 / W2 / W1)` com `Higiene de RAM/CPU (W7)` transversal.
