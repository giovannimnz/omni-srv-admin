# Phase 56 — Instalação, Configuração Multi-Host e Publicação do Paseo na Frota ATIUS (srv-1 a 4)

**Phase:** 56  
**Status:** COMPLETE  
**Date:** 2026-11-02  
**Goal:** Distribuir o runtime Paseo (CLI + Server + ACP) em todos os 4 servidores da frota ATIUS com portas dedicadas por host, daemon systemd, e publicação dual-domain via Apache Edge Gateway no atius-srv-1.  
**Autoridade:** Orquestrador Central Soberano (`2251a1d9-3260-4bde-88e2-490063470338`)  
**Worker Executor:** Worker 1 (`7c2b86c3-8747-4b7f-a04c-a06b167fc806`)  
**Domínios Alvo:** `https://paseo.atius.io` e `https://paseo.atius.com.br`  
**Hub Central:** `atius-srv-4` (`10.14.1.14:37845`)

---

## 1. Topologia de Rede e Matriz de Portas Dedicadas

| Host | IP DRG Primário | IP Legado | IP Público | Porta Paseo | Papel |
|---|---|---|---|---|---|
| `atius-srv-1` | `10.1.0.11` | `10.11.1.11` | `137.131.190.161` | `37815` | Node Local + Edge Gateway Apache (Proxy Reverso / TLS / WebSocket) |
| `atius-srv-2` | `10.2.0.12` | `10.12.1.12` | `129.148.47.32` | `37825` | Node Local / Compute Host |
| `atius-srv-3` | `10.3.0.13` | `10.13.1.13` | `150.230.71.10` | `37835` | Node Local / Control Host (Vault & Landscape) |
| `atius-srv-4` | `10.14.1.14` | `10.14.1.14` | `164.152.48.22` | `37845` | **Paseo Central Hub (Backend / Relay)** |

### Invariantes de Rede
- Todo tráfego inter-nó Paseo usa exclusivamente a rota privada OCI DRG (latência ~0.6ms, zero egress).
- O Apache Edge Gateway no `atius-srv-1` faz ProxyPass para `10.14.1.14:37845` (Hub Central).
- DNS Cloudflare já provisionado: `paseo.atius.io` e `paseo.atius.com.br` ambos resolvem via proxy Cloudflare para o IP público de `atius-srv-1`.

---

## 2. Constraints & Security

- **CPU Guardrail:** ≤20% total host CPU para qualquer operação de build/install (`nice -n 19`, `CPUQuota=20%`).
- **Node.js Runtime:** Usar `nvm` existente (Node.js v24.22.2 já instalado fleet-wide via `fleet-runtimes-upgrade`). NÃO instalar `fnm` — evitar segundo gerenciador de versão.
- **Sem segredos em disco:** Credenciais Landscape e Vault carregadas via `atius-vault-env` em runtime.
- **Rollback por nó:** Cada Wave tem procedimento de reversão atômico documentado.
- **Writer Serialization:** Este Worker NÃO faz commit/push. Alterações homologadas pelo ORCH.

---

## 3. Waves de Execução

### Wave 1: Pré-Requisitos, Governança & Verificação de Portas
**Dependências:** Nenhuma  
**Escopo:** Todos os 4 hosts (srv-1..4)  
**Risco:** read-only  

| # | Task | Comando / Ação | Verificação |
|---|---|---|---|
| 1.1 | Verificar Node.js v24+ em todos os hosts | `ssh atius-srv-{1,2,3,4} 'source ~/.nvm/nvm.sh && node --version'` | Output: `v24.x.x` em cada host |
| 1.2 | Verificar portas Paseo livres | `ssh atius-srv-{1,2,3,4} 'ss -tlnp \| grep -E "378[0-9]{2}"'` | Output vazio (nenhum listener) |
| 1.3 | Verificar conectividade DRG inter-nó | `ssh atius-srv-4 'ping -c 2 -W 1 10.1.0.11 && ping -c 2 -W 1 10.2.0.12 && ping -c 2 -W 1 10.3.0.13'` | RTT < 2ms em todas as rotas |
| 1.4 | Verificar DNS Cloudflare | `dig +short paseo.atius.io && dig +short paseo.atius.com.br` | IPs Cloudflare proxy retornados |
| 1.5 | Verificar Landscape Control-Plane | `/home/ubuntu/.local/bin/omni landscape computers` | Lista de hosts retornada |

**Rollback Wave 1:** Nenhuma mutação; diagnóstico puro.

---

### Wave 2: Instalação de Pacotes Paseo via Landscape (srv-1 a 4)
**Dependências:** Wave 1 verde  
**Escopo:** Todos os 4 hosts  
**Risco:** reconcile (install de pacotes npm globais)

| # | Task | Detalhes |
|---|---|---|
| 2.1 | Criar script `fleet-paseo-install.sh` | Script versionado em `modules/landscape-control-plane/scripts/fleet-paseo-install.sh` |
| 2.2 | Registrar no `manifest.json` | ID: `fleet-paseo-install`, risk: `reconcile`, username: `ubuntu`, time_limit: 600 |
| 2.3 | Sincronizar script via Landscape | `omni landscape scripts push fleet-paseo-install --yes` |
| 2.4 | Executar em lote | `omni landscape run fleet-paseo-install --hosts atius-srv-1,atius-srv-2,atius-srv-3,atius-srv-4 --wait --yes` |

#### Conteúdo do script `fleet-paseo-install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

# CPU Guardrail
renice -n 19 $$ 2>/dev/null || true

# Carregar nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

echo "[paseo-install] Node: $(node --version), npm: $(npm --version)"

# Instalar pacotes globais (idempotente)
npm install -g @getpaseo/cli@0.14.0 @getpaseo/server@0.14.0 paseo-agy-acp@2.7.2 2>&1 | tail -5

# Verificar instalação
echo "[paseo-install] CLI: $(paseo --version 2>/dev/null || echo 'FAIL')"
echo "[paseo-install] Packages:"
npm ls -g @getpaseo/cli @getpaseo/server paseo-agy-acp --depth=0 2>/dev/null || true

# Criar diretórios base
mkdir -p ~/.paseo ~/.config/systemd/user

# Symlink de skills (se ainda não existe)
if [ ! -L "$HOME/.paseo/skills" ] && [ -d "$HOME/.gemini/config/skills" ]; then
  ln -sf "$HOME/.gemini/config/skills" "$HOME/.paseo/skills"
  echo "[paseo-install] Skills symlink criado"
fi

echo "[paseo-install] DONE on $(hostname)"
```

**Verificação Wave 2:**
- Cada host reporta `[paseo-install] DONE` com versões corretas.
- `paseo --version` retorna `0.14.0` em todos os hosts.

**Rollback Wave 2:**
```bash
npm uninstall -g @getpaseo/cli @getpaseo/server paseo-agy-acp
rm -rf ~/.paseo
```

---

### Wave 3: Parametrização dos Daemons & Systemd Units
**Dependências:** Wave 2 verde  
**Escopo:** Cada host individualmente (config por porta)  
**Risco:** targeted-config

| # | Task | Host | Porta | Config Especial |
|---|---|---|---|---|
| 3.1 | Config `~/.paseo/config.json` srv-1 | atius-srv-1 | 37815 | — |
| 3.2 | Config `~/.paseo/config.json` srv-2 | atius-srv-2 | 37825 | — |
| 3.3 | Config `~/.paseo/config.json` srv-3 | atius-srv-3 | 37835 | — |
| 3.4 | Config `~/.paseo/config.json` srv-4 | atius-srv-4 | 37845 | CORS: `paseo.atius.io`, `paseo.atius.com.br`, `app.paseo.sh`; hub: true |
| 3.5 | Aplicar patches v0.14.0 | Todos | — | `sessions.ts`, `identity.js`, `proxy.js` |
| 3.6 | Criar unit systemd `paseo-daemon.service` | Todos | — | User-level, `RestartSec=5`, `Restart=on-failure` |
| 3.7 | Habilitar e iniciar daemon | Todos | — | `systemctl --user enable --now paseo-daemon.service` |

#### Template `~/.paseo/config.json` (srv-4 / Hub):
```json
{
  "server": {
    "port": 37845,
    "host": "0.0.0.0",
    "hub": true,
    "cors": {
      "origins": [
        "https://paseo.atius.io",
        "https://paseo.atius.com.br",
        "https://app.paseo.sh"
      ]
    }
  },
  "skills": {
    "directory": "~/.paseo/skills"
  }
}
```

#### Template `~/.paseo/config.json` (nós locais srv-1/2/3):
```json
{
  "server": {
    "port": {{PORT}},
    "host": "127.0.0.1",
    "hub": false,
    "upstream": "http://10.14.1.14:37845"
  },
  "skills": {
    "directory": "~/.paseo/skills"
  }
}
```

#### Template `~/.config/systemd/user/paseo-daemon.service`:
```ini
[Unit]
Description=Paseo Daemon (Fleet Node)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=NVM_DIR=%h/.nvm
ExecStart=/bin/bash -c 'source $NVM_DIR/nvm.sh && exec paseo daemon run --home %h/.paseo'
Restart=on-failure
RestartSec=5
CPUQuota=20%%
Nice=19

[Install]
WantedBy=default.target
```

**Verificação Wave 3:**
- `systemctl --user status paseo-daemon.service` → `active (running)` em cada host.
- `curl -s http://127.0.0.1:{{PORT}}/health` → HTTP 200 em cada host.
- `curl -s http://10.14.1.14:37845/health` → HTTP 200 (Hub acessível via DRG).

**Rollback Wave 3:**
```bash
systemctl --user disable --now paseo-daemon.service
rm ~/.config/systemd/user/paseo-daemon.service
rm ~/.paseo/config.json
```

---

### Wave 4: Edge Gateway Apache & Paridade Dual-Domain (atius-srv-1)
**Dependências:** Wave 3 verde (Hub no srv-4 respondendo)  
**Escopo:** atius-srv-1 apenas  
**Risco:** targeted-config (Apache vhost)

| # | Task | Detalhes |
|---|---|---|
| 4.1 | Habilitar módulos Apache | `sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers ssl` |
| 4.2 | Criar vhost `paseo.atius.io.conf` | `/etc/apache2/sites-available/paseo.atius.io.conf` |
| 4.3 | Habilitar vhost | `sudo a2ensite paseo.atius.io.conf` |
| 4.4 | Testar configuração | `sudo apachectl configtest` |
| 4.5 | Reload Apache | `sudo systemctl reload apache2` |

#### Conteúdo de `/etc/apache2/sites-available/paseo.atius.io.conf`:
```apache
<VirtualHost *:443>
    ServerName paseo.atius.io
    ServerAlias paseo.atius.com.br

    # TLS via Cloudflare Origin Certificate (wildcard)
    SSLEngine on
    SSLCertificateFile /etc/apache2/ssl/atius.io.pem
    SSLCertificateKeyFile /etc/apache2/ssl/atius.io.key

    # Headers canônicos
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader set Origin "paseo://app"

    # Proxy HTTP para Hub Central (atius-srv-4 via DRG)
    ProxyPreserveHost On
    ProxyPass / http://10.14.1.14:37845/
    ProxyPassReverse / http://10.14.1.14:37845/

    # WebSocket upgrade
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/?(.*) ws://10.14.1.14:37845/$1 [P,L]

    # Logging
    ErrorLog ${APACHE_LOG_DIR}/paseo-error.log
    CustomLog ${APACHE_LOG_DIR}/paseo-access.log combined
</VirtualHost>

<VirtualHost *:80>
    ServerName paseo.atius.io
    ServerAlias paseo.atius.com.br
    RewriteEngine On
    RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
</VirtualHost>
```

**Verificação Wave 4:**
- `sudo apachectl configtest` → `Syntax OK`
- `curl -sI https://paseo.atius.io/health` → HTTP 200
- `curl -sI https://paseo.atius.com.br/health` → HTTP 200
- WebSocket: `curl -sI -H "Upgrade: websocket" -H "Connection: Upgrade" https://paseo.atius.io/` → HTTP 101

**Rollback Wave 4:**
```bash
sudo a2dissite paseo.atius.io.conf
sudo systemctl reload apache2
sudo rm /etc/apache2/sites-available/paseo.atius.io.conf
```

---

### Wave 5: Verificação E2E, Homologação & Documentação
**Dependências:** Wave 4 verde  
**Escopo:** Todos os hosts + endpoints públicos  
**Risco:** read-only

| # | Task | Comando | Critério de Sucesso |
|---|---|---|---|
| 5.1 | Health check local srv-1 | `curl -s http://127.0.0.1:37815/health` | HTTP 200 |
| 5.2 | Health check local srv-2 | `ssh atius-srv-2 'curl -s http://127.0.0.1:37825/health'` | HTTP 200 |
| 5.3 | Health check local srv-3 | `ssh atius-srv-3 'curl -s http://127.0.0.1:37835/health'` | HTTP 200 |
| 5.4 | Health check local srv-4 | `curl -s http://10.14.1.14:37845/health` | HTTP 200 |
| 5.5 | E2E paseo.atius.io | `curl -sI https://paseo.atius.io/health` | HTTP 200, TLS válido |
| 5.6 | E2E paseo.atius.com.br | `curl -sI https://paseo.atius.com.br/health` | HTTP 200, TLS válido |
| 5.7 | CLI validation | `paseo status && paseo provider ls` | Output sem erros |
| 5.8 | WebSocket probe | `websocat wss://paseo.atius.io/ --ping-interval 5 -1` | Conexão estabelecida |
| 5.9 | Registrar fato GBrain | `gbrain remember --fact "..." --provenance "phase-56"` | Fato registrado |
| 5.10 | Criar runbook Obsidian | Documento em `AiSecondBrain/Operations/` | Persistido e commitado |

**Rollback Wave 5:** Nenhuma mutação; apenas validação.

---

## 4. Threat Model

| Ameaça | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Hub (srv-4) offline → todas as sessões Paseo caem | Média | Alto | Monitorar via Landscape healthcheck; restart automático via systemd |
| Porta 378xx em uso por outro serviço | Baixa | Médio | Wave 1 verifica explicitamente antes de qualquer install |
| Apache misconfiguration derruba outros vhosts | Baixa | Alto | `apachectl configtest` mandatório; rollback atômico |
| npm install consome >20% CPU | Média | Baixo | `nice -n 19` + `CPUQuota=20%` no script |
| WebSocket não faz upgrade através do Apache | Média | Médio | `proxy_wstunnel` + `RewriteCond` explícitos |
| Patches v0.14.0 incompatíveis com versão instalada | Baixa | Alto | Verificar hash/versão antes de aplicar; rollback = reinstall |

---

## 5. Done Condition (Critério de Conclusão)

A fase está **DONE** quando TODOS os seguintes são verdadeiros:

1. ✅ `paseo --version` retorna `0.14.0` nos 4 hosts (srv-1..4).
2. ✅ `paseo-daemon.service` está `active (running)` nos 4 hosts.
3. ✅ `curl -s http://127.0.0.1:{{PORT}}/health` retorna HTTP 200 em cada host na porta dedicada.
4. ✅ Hub Central (`10.14.1.14:37845`) acessível de todos os nós via DRG.
5. ✅ `https://paseo.atius.io/health` retorna HTTP 200 com TLS válido.
6. ✅ `https://paseo.atius.com.br/health` retorna HTTP 200 com TLS válido.
7. ✅ WebSocket upgrade funcional em ambos os domínios.
8. ✅ Script `fleet-paseo-install` registrado no `manifest.json` e sincronizado no Landscape.
9. ✅ Fato registrado no GBrain; runbook no Obsidian.
10. ✅ Zero regressão em serviços existentes (Apache, Landscape, Vault, K3s).
