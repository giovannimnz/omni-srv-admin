# ATIUS-SRV-1 — Full Server Audit Report
**Server:** ATIUS-SRV-1 (10.1.1.1)  
**Generated:** $(date -u)  
**Project:** atius-srv (commit 2b244ac)  

---

## Executive Summary

| Category | Status |
|---|---|
| Phase 1 (Host Prep) | ⚠️ PARTIAL — certbot quebrado, chrony OK |
| Phase 2 (Apache2 migração) | ❌ NOT EXECUTED — Apache2 ainda em 80/443 |
| Phase 3 (FreeIPA) | ❌ NOT STARTED — container não existe |
| Phase 4-7 | ○ NOT STARTED |
| Undocumented services | 🔴 CRÍTICO — 30+ temuanhos |
| Cloudflare credentials | ❌ INVÁLIDAS — token curto demais |

---

## Phase 1 — Preparação do Host

### ✅ Chrony/NTP — OK
- `/etc/chrony/chrony.conf` correto: `server 169.254.169.254 iburst prefer`
- Synced, Stratum 4, offset <1ms
- Documentado e verificado

### ❌ Certbot — BREAKN
- `certbot --version` chama `/home/ubuntu/.local/bin/certbot` (pip) → `ModuleNotFoundError: configargparse`
- Snap certbot funciona: `/snap/bin/certbot --version` → `certbot 5.5.0`
- **Causa:** `.local/bin` no PATH antes de `/snap/bin` (shadow)
- **Origem:** `.bashrc` linha 122 → source `~/.local/bin/env` → prepends `~/.local/bin` ao PATH
- **Quando:** pip certbot instalado em `/home/ubuntu/.local/bin/` em `abr 22 03:19`
- **Verificação Phase 1** rodou `certbot --version` no contexto do snap (quando PATH era diferente ou chamou snap diretamente), não detectou que o comando default `certbot` agora está quebrado

### ✅ FQDN /etc/hosts — OK
- `ipa.atius.com.br` → 10.1.1.1
- hostname -f = ipa.atius.com.br

### ❌ Port 80/443 — AINDA OCUPADOS POR APACHE2
- Phase 1 Plan 01-01 diz: "Apache2 migrated to 9080/9444"
- Phase 1 Verification diz: "10/10 truths verified"
- **REALIDADE:** Apache2 escuta em 80, 443, 9080, 8443, 8081, 8084 SIMULTANEAMENTE
- portas.conf: `Listen 80`, `Listen 0.0.0.0:443` (duplicado), `Listen 8443`, `Listen 8081`, `Listen 9080`
- 71 vhosts em sites-enabled, muitos em :443

---

## Phase 2 — Migração Apache2 para Portas Alternativas

### ❌ NÃO EXECUTADO
- Plan 02-01 existe mas nunca foi executado
- Artefatos `/tmp/02-cloudflare-origin-rules-report.txt` e `/tmp/02-cloudflare-rollback.sh` NÃO EXISTEM
- **Gate bloqueador:** `CF_API_TOKEN` = 13 caracteres (placeholder inválido)
- `CF_ZONE_ID` = 32 chars (formato real, mas sem token não funciona)

### Estado atual Apache2
```
Listen ports:   80, 443, 9080, 8443, 8081, 8084
:80  vhosts:    nenhum ativo (apenas .bak)
:443 vhosts:    panel, gsd, cockpit, + outros
:9080 vhosts:   admin, agent, api-dev, api, atius, backtest-dev, + ~30
:8443 vhosts:   (mesmos que 443)
:8081 vhosts:   aion, hermes (duplicados)
:8084 vhosts:   paperclip (HTTP)
```

### Documento diz vs Realidade

| Item | Doc (01-VERIFICATION) | Realidade |
|---|---|---|
| Apache2 em 9080/9444 | ✓ 10/10 verified | ✓ escutando em 9080/8443 |
| Portas 80/443 livres | ✓ 0 on :80, 0 on :443 | ❌ ainda em 80/443 |
| Todos vhosts migrados | ✓ 37 on :9080, 40 on :9444 | ❌ muitos ainda em :443 |
| Apache2 serve nas novas portas | ✓ curl localhost:9080 → 200 | ✓ funcionando |

**Conclusão:** Phase 1 migrou Apache2 para 9080/9444 ADICIONANDO novas portas, mas NÃO removeu 80/443. A verificação foi feita só nas novas portas, sem checar se as antigas foram desativadas.

---

## Phase 3 — FreeIPA Server Container

### ❌ NÃO INSTALADO
- Zero containers FreeIPA
- Zero imagens freeipa
- 3 planos em `.planning/phases/03-freeipa-server-container/` não executados
- Phase 3 marcada como "Planned" no ROADMAP

---

## Undocumented Services (NOT in atius-srv project)

### 🔴 Docker Containers (não documentados)

| Container | Portas | Função | Network | Status |
|---|---|---|---|---|
| new-api | :3301→3000 | Atius AI Router (New-API) | atius + newapi-internal | Up 6h |
| model-detailed | :3300→3001 | router-ai-atius-model-detailed | atius + newapi-internal | Up 2d |
| db-newapi | :5432 | PostgreSQL do New-API | newapi-internal | Up 2d |
| hermes-pers | (sem porta) | Hermes persistent memory (Postgres) | ? | Up 7d healthy |
| pm2web-backend | (sem porta exposta) | Backend pm2web | 172.18.0.2 | Up 7d |
| pm2web-dashboard | :3000 | pm2web dashboard | 172.18.0.3 | Up 7d |
| open-webui | localhost:3001→8080 | Open WebUI (LLM interface) | 192.168.0.4 | Up 7d |
| cloudbeaver | :8000→8978 | CloudBeaver (DB IDE) | 172.23.0.2 | Up 7d |
| jenkins | :8085, :50000 | Jenkins CI/CD | 192.168.160.14 | Up 7d |
| portainer | :9001, :9443 | Portainer Docker management | 172.19.0.2 | Up 7d |
| angry_yonath | :8000 | ??? (nome aleatório docker) | docker0 (172.17.0.5) | Up 2d |
| mystifying_poincare | :8000 | ??? | docker0 (172.17.0.4) | Up 2d |
| pedantic_tharp | :8000 | ??? | docker0 (172.17.0.3) | Up 7d |
| upbeat_wiles | :8000 | ??? | docker0 (172.17.0.2) | Up 7d |

**Problema:** Containers `angry_yonath`, `mystifying_poincare`, `pedantic_tharp`, `upbeat_wiles` têm nomes aleatórios (Docker default adjective_noun) — nunca foram renomeados ou documentados. Parece que alguém rodou `docker run` sem `--name`.

### 🔴 Host Services (não documentados)

| Serviço | Porta | Processo | Nota |
|---|---|---|---|
| AnyDesk | 7070 | anydesk (PID 1469) | Remote desktop |
| Webmin | 10000 | miniserv.pl (PID 2200) | System admin panel |
| qBittorrent | 6889 | qbittorrent-nox (PID 1083631) | Torrent client |
| noVNC | 6080 | websockify → localhost:5900 | VNC web proxy |
| NoMachine | 12001+ | nxnode.bin | Remote desktop |
| MongoDB | 27017 | mongod (PID 9449) | Native (não Docker) |
| Cockpit | 9090 | systemd | System admin web UI |
| Hermes adapter | 8100 | node /opt/hermes/adapter-server.mjs | Hermes integration |
| Hermes dashboard | 8082 | hermes dashboard --port 8082 | Hermes web UI |
| Paperclip Vhost | 8084 | Apache2 vhost | paperclip.atius.com.br |

### 🔴 PM2 Processes (atius-srv vs atius-srv project)

| Processo | Portas | Namespace | Status |
|---|---|---|---|
| aionui-web | — | aionui | online |
| atius-api | 8015 | default | online |
| atius-divap-indicator | — | default | online |
| atius-strategy-builder | — | default | online |
| atius-unified-bot-launcher | — | default | waiting |
| atius-web | — | atius | online |
| atius-webhook-signals | 8199 | default | online |
| gsd-ac-web | — | default | stopped |
| gsd-web | — | default | online |
| horistic-api | 8050 | default | online |
| horistic-divap-indicator | — | default | online |
| horistic-unified-bot-launcher | — | default | waiting |
| horistic-web | — | horistic | online |
| horistic-webhook-signals | 8099 | default | online |

**Nota:** "horistic" e "aionui" são projetos separados de atius-srv. Não há documentação cruzando esses projetos.

---

## iptables State

### ✅ Regraz Documentadas
- `/home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf` existe (118 linhas, jan 23 2025)
- BACKUP ANTIGO — não reflete estado atual

### Regras Ativas (não documentadas)
```
INPUT:
  multiport 4000,5353 UDP → ACCEPT
  tcp 4000 → ACCEPT
  tcp 27017 from 127.0.0.1 → ACCEPT (MongoDB localhost)
  tcp 27017 from 10.1.1.2 → ACCEPT (MongoDB VPN host)
  tcp 27017 from 10.1.1.0/24 → ACCEPT (MongoDB VPN range)
  MAILCOW chain → 3 regras (não inspecionadas)

FORWARD:
  DOCKER-USER → DOCKER-FORWARD → ACCEPT
  -i wg0 → ACCEPT (WireGuard)
  MAILCOW chain → 3 regras

OUTPUT:
  tcp 25 → ACCEPT (SMTP out)
  tcp 443 → ACCEPT (HTTPS out)
```

**Problema:** 
- Backup iptables é de jan 2025 — 4 meses desatualizado
- Regras atuais (MongoDB, MAILCOW, WireGuard) NÃO estão no projeto atius-srv
- WireGuard (`wg0`) está no FORWARD chain mas Phase 5 (WireGuard migration) não começou

---

## Network Summary

### Redes Docker ativas
| Network | Subnet | Containers |
|---|---|---|
| atius (bridge) | ? | new-api, model-detailed |
| atius-shared (bridge) | ? | ? |
| paperclip-atius_default | ? | paperclip-atius-db |
| router-ai-atius_newapi-internal | ? | db-newapi, new-api, model-detailed |
| docker0 | 172.17.0.0/24 | 4 containers anônimos |
| br-cc5440fb4e16 (atius) | 192.168.160.0/24 | Plane stack + Jenkins |
| br-7cedbd84cf3e (atius-shared) | 192.168.0.0/24 | new-api, model-detailed, open-webui |
| br-8cbffb33c1ac | 172.18.0.0/24 | pm2web stack |
| br-1bac6fbca871 | 172.19.0.0/24 | portainer |
| br-97e9ea0515db | 172.21.0.0/24 | db-newapi, new-api, model-detailed |
| br-7e488c14feea | 172.22.0.0/24 | paperclip-atius-db |
| br-798605a3dfb4 | 172.23.0.0/24 | cloudbeaver |
| br-83f37cfb99ff | 172.26.0.0/24 | paperclip-pers-db |
| br-7013f1b720f5 | 192.168.64.0/24 | open-webui |

---

## Resumo de Lacunas

### CRÍTICO (impede progresso)
1. **CF_API_TOKEN inválido** — Phase 2 bloqueada, Cloudflare não pode ser configurado
2. **Certbot quebrado** — Let's Encrypt não funciona até corrigir PATH ou desinstalar pip certbot
3. **Apache2 em 80/443** — Phase 1 prometeu livrar, não cumpriram

### ALTO (degrada segurança/operação)
4. **MongoDB exposto em 10.1.1.1:27017** — acesso completo da rede VPN sem autenticação documentada
5. **4 containers com nomes aleatórios** — angry_yonath, mystifying_poincare, pedantic_tharp, upbeat_wiles
6. **Backup iptables desatualizado** (jan 2025)
7. **.anydesk em servidor** — software de acesso remoto não documentado
8. **qBittorrent** em servidor — uso não documentado
9. **Webmin** em porta 10000 — painel administrativo exposto

### MÉDIO (inconsistência documentação)
10. WireGuard em `wg0` existe mas Phase 5 não começou
11. hermes-pers (Postgres memory) não documentado
12. pm2web stack (backend + dashboard) não documentado
13. CloudBeaver não documentado
14. NoMachine não documentado
15. open-webui não documentado

---

## Recommendations

### 1. Corrigir Certbot (bloqueador)
```bash
# Opção A: remover pip certbot do PATH
# Remover linha 122 do .bashrc ou editar ~/.local/bin/env para não prependar

# Opção B: chamar snap certbot explicitamente
sudo snap refresh certbot
/usr/bin/certbot --version  # deve mostrar 5.5.0
```

### 2. Fornecer Cloudflare API Token (bloqueador Phase 2)
- Token atual (`CF_API_TOKEN`) tem 13 chars — inválido
- Necessário: `Zone Rulesets: Edit` permission
- Depois de obter token válido: executar Phase 2

### 3. Apache2 — desativar 80/443 ou documentar reason
- Se 80/443 são necessários temporariamente, documentar por quê
- Se não são: `sudo a2dissite` nos vhosts em :80 e :443

### 4. Identificar containers anônimos
```bash
docker rename angry_yonath <nome-significativo>
# fazer para todos 4
```

### 5. Documentar serviços não-no-projeto
- AnyDesk, Webmin, qBittorrent, NoMachine, MongoDB nativo
- Decidir: removê-los ou documentá-los

### 6. Atualizar backup iptables
```bash
sudo iptables-save > /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4-$(date +%Y%m%d).conf
```

### 7. Atualizar STATE.md do projeto
