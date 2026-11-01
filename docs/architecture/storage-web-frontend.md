# Arquitetura e Engenharia do Frontend Web de Storage (`storage.atius.io`)

**Módulo:** `modules/fleet-gdrive` & `modules/atius-admin-edge-sso`  
**Data:** 2026-11-01  
**Autor:** Web Storage Frontend Architect  
**Status:** Especificação Aprovada para Produção  

---

## 1. Comparativo Arquitetural: `storage.atius.io` vs `https://omni.atius.io/storage`

A disponibilização de uma interface web para gestão de arquivos corporativos da frota ATIUS (Google Drive montado em `/mnt/gdrive`) foi analisada sob duas abordagens de exposição externa: **Subdomínio Dedicado** (`storage.atius.io`) e **Subcaminho Integrado** (`https://omni.atius.io/storage`).

A tabela a seguir apresenta o comparativo técnico aprofundado em 6 dimensões críticas de infraestrutura, segurança e governança:

| Dimensão Técnica | Opção A: `storage.atius.io` (Recomendado) | Opção B: `https://omni.atius.io/storage` (Desaconselhado) | Vencedor e Justificativa Técnica |
| :--- | :--- | :--- | :--- |
| **1. Isolamento de Origem (SOP, CORS & Cookies)** | **Totalmente isolado.** Origem web independente (`https://storage.atius.io:443`). Cookies de sessão, tokens JWT e `localStorage` não colidem com a aplicação Omni Admin. Zero risco de vazamento de credenciais cruzadas ou contaminação de contexto. | **Compartilhado.** Sob a mesma origem `https://omni.atius.io`, scripts e workers do frontend de storage compartilham cookies e armazenamento local com o portal administrativo principal, violando o princípio do menor privilégio. | **Opção A (Subdomínio):** Isolamento de segurança canônico via *Same-Origin Policy*. |
| **2. Roteamento de Assets Estáticos & Base URLs** | **Nativo na raiz (`/`).** O frontend carrega assets (`/assets/...`, `/static/...`, fontes, ícones, sourcemaps e bundles Vite/Webpack) diretamente na raiz. Nenhuma reescrita de cabeçalhos HTML ou parâmetros complexos de compilação é necessária. | **Frágil e propenso a quebras.** Exige reescrita dinâmica de caminhos (`baseURL: /storage/`), flags de proxy reverso e manipulação de cabeçalhos `Location` e HTML de resposta. Alto índice de falhas em carregamento de chunks assíncronos. | **Opção A (Subdomínio):** Elimina 100% dos problemas de asset bundling e path rewrite. |
| **3. WebSockets & Transferência em Streaming** | **Transparente.** Proxy reverso direto para `ws://127.0.0.1:8082/` sem prefixos. Uploads chunked de arquivos de vários gigabytes e download em streaming ocorrem sem buffering intermediário. | **Complexo.** Conexões de transferência de longa duração dividem threads e buffers com as chamadas de API transacionais do Omni Admin. Requer regras intrincadas de multiplexação WebSocket no mesmo endpoint. | **Opção A (Subdomínio):** Sem concorrência de sockets; preserva I/O do portal administrativo. |
| **4. Alinhamento com Atius Admin Edge Gateway** | **Compatibilidade Nativa 1:1.** O daemon do Atius Admin Edge Gateway (`127.0.0.1:8210`) roteia requisições exclusivamente com base no VirtualHost (`req.headers.host`), conforme padronizado em toda a frota. | **Incompatível.** O Edge Gateway não possui motor de roteamento baseado em prefixos de path (`pathname`). Exigiria refatoração profunda no core do gateway para suportar prefixos de URL. | **Opção A (Subdomínio):** Integração perfeita com o contrato existente do Edge Gateway. |
| **5. Paridade Visual e Padrão da Frota** | **Consistência Total.** Segue exatamente o padrão institucional adotado em 100% dos consoles e serviços da frota: `grafana.atius.io`, `portainer.atius.io`, `cockpit.atius.io`, `pm2.atius.io`, `paseo.atius.io`. | **Quebra de Padrão.** Criaria uma anomalia na governança de nomes da infraestrutura, onde apenas o storage operaria como subcaminho, enquanto todos os demais serviços operam em subdomínios. | **Opção A (Subdomínio):** Mantém identidade operacional limpa e previsível. |
| **6. Gestão de Certificados TLS e Borda** | **Cobertura Automática.** O certificado wildcard gerenciado via Cloudflare / Let's Encrypt para `*.atius.io` e `*.atius.com.br` já cobre o hostname sem custo operacional ou emissão de novos certificados. | **Reaproveitamento simples.** Utiliza o mesmo certificado do domínio base, sem ganho adicional. | **Empate:** Ambas as opções usam o mesmo plano de terminação TLS. |

**Decisão Arquitetural:** Adota-se de forma mandatória e exclusiva a **Opção A: `storage.atius.io`** (com espelho idêntico `storage.atius.com.br`). Para atender à experiência unificada do usuário no portal Omni, será adicionado um link na barra de navegação do Omni apontando para `https://storage.atius.io`.

---

## 2. Topologia de Ponta a Ponta

A cadeia de comunicação entre o navegador do usuário e o sistema de arquivos distribuído é estruturada em 6 camadas estritamente governadas:

```text
[ Usuário / Navegador ]
         │
         │ 1. HTTPS / WSS (Porta 443)
         ▼
[ Borda Cloudflare (CDN / WAF / Proxy Laranja) ]
         │  - Terminação TLS Wildcard (*.atius.io / *.atius.com.br)
         │  - Proteção contra DDoS e Pacing de conexões externas
         │  - Repasse com Host Header preservado
         ▼
[ Servidor Apache vhost (atius-srv-1:443) ]
         │  - VirtualHost: storage.atius.io.conf / storage.atius.com.br.conf
         │  - ProxyPreserveHost On
         │  - Rewrite de WebSocket (Upgrade: websocket -> ws://127.0.0.1:8210)
         │  - ProxyPass / http://127.0.0.1:8210/
         ▼
[ Atius Admin Edge Gateway (Node.js - 127.0.0.1:8210) ]
         │  - Resolução de Host Header (`storage.atius.io`)
         │  - Inspeção do cookie `auth-token`
         │  ├─ [Ausente/Inválido] ──► 302 Redirect para https://storage.atius.io/login
         │  │                         (Exibe tela Atius SSO corporativa com paridade visual)
         │  │
         │  ├─ [Validação de Sessão] ──► GET http://127.0.0.1:8015/v1/auth/me
         │  │                            Valida token, allowedEmails e requireAdmin
         │  │
         │  └─ [Sessão Válida] ──► Injeta Header `X-Forwarded-User: <email>`
         │                         Encaminha requisição HTTP/WS para o Upstream
         ▼
[ Backend Filebrowser (Go Single Binary - 127.0.0.1:8082) ]
         │  - Modo Proxy Auth (`auth.method="proxy"`, `auth.header="X-Forwarded-User"`)
         │  - Reconhece o email do usuário sem solicitação de credenciais locais
         │  - Operação restrita ao diretório raiz `/mnt/gdrive`
         │  - Governança de recursos: CPUQuota=40% (10% do host), Nice=10
         ▼
[ Ponto de Montagem Local: /mnt/gdrive ]
         │  - Gerenciado por `gdrive-mount.service` (rclone FUSE)
         │  - Full VFS Cache em `/var/cache/rclone-gdrive` (com cotas por host)
         │  - Credenciais OAuth efêmeras em tmpfs (`/run/rclone/rclone.conf`, mode 0600)
         ▼
[ Google Workspace API (API Google Drive) ]
```

### 2.1 Detalhamento de Cada Salto

1. **Borda Cloudflare:** Fornece terminação SSL na borda, mitigação de ataques volumétricos e resolução de DNS unificada para `storage.atius.io` e `storage.atius.com.br`. As requisições são encaminhadas diretamente para a porta 443 do `atius-srv-1`.
2. **Apache VirtualHost (`/etc/apache2/sites-available/`):**
   - Configurado com certificados Cloudflare Origin CA (`/etc/ssl/cloudflare/atius.com.br.pem`).
   - Mantém `ProxyPreserveHost On` para que o Edge Gateway saiba exatamente qual site está sendo requisitado.
   - Encaminha tráfego HTTP para `http://127.0.0.1:8210/` e conexões WebSocket para `ws://127.0.0.1:8210/`.
3. **Atius Admin Edge Gateway (`127.0.0.1:8210`):**
   - Executa como daemon Node.js governado sob systemd (`atius-admin-edge-gateway.service`).
   - Roteia a requisição pelo objeto de configuração `sites["storage.atius.com.br"]` (com alias `storage.atius.io`).
   - Intercepta requisições não autenticadas e exibe a tela de login corporativo local (`/login`), com paridade visual 1:1 ao contrato do `ssh.atius.com.br/login`.
4. **Micro-serviço ATS SSO (`127.0.0.1:8015`):**
   - Recebe a sonda `GET /v1/auth/me` enviada pelo Edge Gateway.
   - Valida o token JWT contido no cookie corporativo `auth-token`.
   - Retorna os dados do usuário (`email`, `is_admin`, `permissions`).
5. **Backend Filebrowser (`127.0.0.1:8082`):**
   - Escuta exclusivamente na interface de loopback (`127.0.0.1`).
   - Recebe o cabeçalho `X-Forwarded-User` injetado com segurança pelo Edge Gateway.
   - Aplica permissões de leitura, escrita, streaming e download direto sobre `/mnt/gdrive`.
6. **Filesystem FUSE (`/mnt/gdrive`):**
   - Rclone mount governado por `gdrive-mount.service`.
   - Lê credenciais hidratadas em tempo de execução via Vault a partir de tmpfs efêmero em `/run/rclone/rclone.conf`.

---

## 3. Contrato de Autenticação Atius SSO

### 3.1 Ciclo de Vida do Cookie `auth-token`

- **Nome do Cookie:** `auth-token`
- **Atributos Canônicos:** `Path=/; HttpOnly; Secure; SameSite=Lax`
- **Escopo Dual-Domain:**
  - Para `*.atius.com.br`: O cookie é emitido com `Domain=.atius.com.br`, permitindo navegação transparente (Single Sign-On verdadeiro) entre todos os serviços do domínio corporativo.
  - Para `*.atius.io`: O cookie é emitido no escopo de host (`Domain=storage.atius.io` ou sem domínio para cookie host-only), garantindo que navegadores modernos não rejeitem o cookie por restrições de terceiros.
- **Duração de Sessão:** 30 dias com renovação automática por atividade.

### 3.2 Validação de Sessão no ATS SSO

Toda requisição HTTP recebida pelo Edge Gateway (exceto assets públicos estáticos como `/_atius/favicon.svg` e a rota `/login`) é submetida à validação:

```http
GET /v1/auth/me HTTP/1.1
Host: 127.0.0.1:8015
Cookie: auth-token=<jwt_token_recebido>
X-Forwarded-For: 203.0.113.195
X-Forwarded-Host: storage.atius.io
X-Forwarded-Proto: https
Accept: application/json
```

**Payload de Sucesso (HTTP 200 OK):**
```json
{
  "authenticated": true,
  "user": {
    "id": 1,
    "email": "giovannimunizds@gmail.com",
    "name": "Giovanni Muniz",
    "is_admin": true,
    "permissions": {
      "storage_access": true,
      "admin_console": true
    }
  }
}
```

### 3.3 Regras de Autorização e Injeção de Cabeçalhos

O Edge Gateway avalia os dados recebidos:
1. `response.authenticated === true`: Caso falso, retorna HTTP 302 para `/login`.
2. `allowedEmails`: Verifica se o email normalizado em minúsculas está na allowlist declarada (`["giovannimunizds@gmail.com"]`). Se não constar, retorna HTTP 403 Forbidden.
3. `requireAdmin: true`: Verifica se `user.is_admin === true`. Se não for admin, retorna HTTP 403 Forbidden.
4. **Injeção de Cabeçalhos Upstream:**
   - O Edge Gateway remove qualquer tentativa externa de envio do cabeçalho `X-Forwarded-User` para prevenir spoofing de identidade.
   - Injeta o cabeçalho autenticado:
     ```http
     X-Forwarded-User: giovannimunizds@gmail.com
     X-Forwarded-For: <client_ip>, 127.0.0.1
     X-Forwarded-Host: storage.atius.io
     X-Forwarded-Proto: https
     ```

### 3.4 Reconhecimento no Filebrowser (Proxy Auth Mode)

No backend Filebrowser, a configuração `auth.method: "proxy"` com `auth.header: "X-Forwarded-User"` instrui o serviço a aceitar a identidade declarada no cabeçalho.
- No primeiro acesso, o Filebrowser provisiona automaticamente o registro do usuário no banco SQLite interno (`filebrowser.db`), associando as permissões padrão (upload, download, rename, delete, share).
- Nenhuma tela de senha secundária é solicitada ao usuário.

### 3.5 Fluxo de Logout

1. O usuário clica no controle de saída ou acessa `https://storage.atius.io/logout`.
2. O Edge Gateway intercepta o path `/logout`.
3. Executa a limpeza determinística dos cookies corporativos:
   - `auth-token=; Path=/; Domain=.atius.com.br; Max-Age=0; HttpOnly; Secure; SameSite=Lax`
   - `auth-token=; Path=/; Domain=storage.atius.io; Max-Age=0; HttpOnly; Secure; SameSite=Lax`
   - `auth-token=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`
4. Devolve HTTP 302 Redirection para `https://storage.atius.io/login`.

---

## 4. Governança de Recursos Institucional (Regra de CPU <= 20%)

A infraestrutura da frota ATIUS segue a diretriz institucional expressa em `modules/srv1-ops/configs/resource-governor.env`: **nenhum processo auxiliar pode comprometer a capacidade de processamento do host, mantendo-se rigorosamente em CPU <= 20% total.**

### 4.1 Métricas de Desempenho do Filebrowser

| Métrica | Filebrowser (Go) | Nextcloud (PHP + MySQL + Redis) | Rclone RC WebGUI |
| :--- | :--- | :--- | :--- |
| **Consumo de CPU em Repouso** | **0.0% a 0.1%** | 3.5% a 8.0% (cron jobs em background) | 0.0% a 0.2% |
| **Consumo de CPU em Transferência** | **< 1.0%** | 25.0% a 70.0% (processamento de chunks em PHP) | < 2.0% |
| **Pegada de Memória (RSS)** | **< 20 MB** | > 450 MB (PHP-FPM pools + Redis + MySQL) | < 35 MB |
| **Varredura Periódica de Disco** | **Zero.** Consulta em tempo real sob demanda. | **Pesada.** `occ files:scan` causa 100% CPU. | Zero. |
| **Arquitetura de Binário** | Single Binary Go estático (~25MB). | Pilha complexa LAMP/LEMP. | Integrado no rclone. |

### 4.2 Eliminação de Indexação Pesada sobre FUSE

Um dos problemas mais graves em servidores de storage é o travamento do kernel (`D state`) decorrente de crawlers de banco de dados varrendo pontos de montagem FUSE.
- Softwares como Nextcloud e ownCloud tentam sincronizar metadados continuamente, gerando centenas de milhares de chamadas `getattr` e `readdir` na API do Google Drive, o que provoca erros HTTP 429 (Rate Limit Exceeded) e saturação de I/O.
- O Filebrowser **não realiza indexação prévia nem background crawl**. As leituras de diretórios ocorrem estritamente quando o usuário abre uma pasta na interface web, aproveitando o cache VFS local (`--dir-cache-time 72h` configurado no `gdrive-mount.service`).

### 4.3 Contenção por CGroup e Systemd Slice

A unit `modules/fleet-gdrive/systemd/filebrowser.service` implementa travas rígidas de governança de recursos:

```ini
# Em hosts de 4 vCPUs (Ampere Altra), CPUQuota=40% equivale a 10% da capacidade total do host.
# Isso garante que o serviço fique 50% abaixo do teto institucional de 20%.
CPUQuota=40%
Nice=10
CPUSchedulingPolicy=other
IOSchedulingClass=best-effort
IOSchedulingPriority=7

# Limites estritos de memória para evitar vazamento
LimitNOFILE=65536
MemoryMax=512M
MemoryHigh=256M
```

---

## 5. Paridade Dual-Domain (`storage.atius.com.br` e `storage.atius.io`)

Em cumprimento rigoroso à diretriz `atius-dual-domain`:
1. **Domínio Primário:** `storage.atius.com.br` (produção nacional).
2. **Domínio Internacional:** `storage.atius.io` (paridade 1:1).

### 5.1 Registro no Edge Gateway

O arquivo de configuração do Edge Gateway define o site canônico e o alias com paridade completa:

```json
{
  "storage.atius.com.br": {
    "publicOrigin": "https://storage.atius.com.br",
    "appName": "Storage",
    "authMode": "none",
    "upstream": "http://127.0.0.1:8082",
    "allowedEmails": ["giovannimunizds@gmail.com"],
    "requireAdmin": true
  },
  "storage.atius.io": {
    "aliasOf": "storage.atius.com.br",
    "publicOrigin": "https://storage.atius.io",
    "appName": "Storage",
    "allowedEmails": ["giovannimunizds@gmail.com"],
    "requireAdmin": true
  }
}
```

### 5.2 Configuração dos VirtualHosts Apache

Dois arquivos de VirtualHost idênticos são mantidos em `/etc/apache2/sites-available/`:
- `storage.atius.com.br.conf`
- `storage.atius.io.conf`

**Conteúdo Canônico do VirtualHost (`storage.atius.io.conf`):**
```apache
<VirtualHost *:9080>
    ServerName storage.atius.io
    RewriteEngine On
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</VirtualHost>

<VirtualHost *:443>
    ServerName storage.atius.io

    ProxyPreserveHost On
    ProxyRequests Off

    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader unset Authorization

    # Suporte transparente a WebSockets do Filebrowser
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule /(.*) ws://127.0.0.1:8210/$1 [P,L]

    # Encaminhamento para o Atius Admin Edge Gateway
    ProxyPass / http://127.0.0.1:8210/
    ProxyPassReverse / http://127.0.0.1:8210/

    # Certificados TLS Cloudflare Origin CA
    SSLEngine on
    SSLCertificateFile /etc/ssl/cloudflare/atius.io.pem
    SSLCertificateKeyFile /etc/ssl/cloudflare/atius.io.key
    SSLStrictSNIVHostCheck off
    Include /etc/letsencrypt/options-ssl-apache.conf

    ErrorLog ${APACHE_LOG_DIR}/storage.atius.io-error.log
    CustomLog ${APACHE_LOG_DIR}/storage.atius.io-access.log combined
</VirtualHost>
```

---

## 6. Runbook de Deploy e Validação Operacional

### 6.1 Pré-Requisitos

1. `gdrive-mount.service` ativo e com ponto de montagem validado em `/mnt/gdrive`.
2. HashiCorp Vault acessível em `https://10.13.1.13:8202` com o perfil `omni-storage` hidratado.
3. Porta interna `8082` livre na interface `127.0.0.1`.
4. Módulos Apache habilitados: `proxy`, `proxy_http`, `proxy_wstunnel`, `rewrite`, `headers`, `ssl`.

### 6.2 Procedimento Passo a Passo de Instalação

```bash
# 1. Download do binario Filebrowser (v2.30.0 ARM64 para servidores OCI Ubuntu 22.04)
curl -fsSL https://github.com/filebrowser/filebrowser/releases/download/v2.30.0/linux-arm64-filebrowser.tar.gz | tar -xz -C /tmp
sudo mv /tmp/filebrowser /usr/local/bin/filebrowser
sudo chmod 755 /usr/local/bin/filebrowser

# 2. Criacao da estrutura de diretorios de configuracao e banco
sudo mkdir -p /etc/filebrowser /var/lib/filebrowser

# 3. Instalacao do arquivo de configuracao governado
sudo cp modules/fleet-gdrive/configs/filebrowser.json /etc/filebrowser/filebrowser.json
sudo chmod 644 /etc/filebrowser/filebrowser.json

# 4. Inicializacao do banco SQLite com modo proxy auth ativo
sudo /usr/local/bin/filebrowser config init -c /etc/filebrowser/filebrowser.json
sudo /usr/local/bin/filebrowser config set --auth.method=proxy --auth.header=X-Forwarded-User -c /etc/filebrowser/filebrowser.json

# 5. Instalacao e ativacao da unit systemd
sudo cp modules/fleet-gdrive/systemd/filebrowser.service /etc/systemd/system/filebrowser.service
sudo systemctl daemon-reload
sudo systemctl enable --now filebrowser.service

# 6. Merge do snippet no Atius Admin Edge Gateway
# Em /etc/atius/atius-admin-edge-gateway.json, mesclar o snippet:
# modules/atius-admin-edge-sso/configs/storage-edge-gateway-snippet.json
sudo systemctl restart atius-admin-edge-gateway.service

# 7. Provisionamento dos VirtualHosts Apache e reload
sudo a2ensite storage.atius.com.br.conf storage.atius.io.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 6.3 Probes de Verificação e Validação de Saúde

Execute os 5 testes sintéticos abaixo para certificar a integridade do deployment:

#### Probe 1: Estado da Unit e CGroup de CPU
```bash
systemctl is-active filebrowser.service
# Resposta esperada: active

systemctl show filebrowser.service -p CPUQuota,Nice,MemoryMax
# Resposta esperada: CPUQuotaPerSecUSec=400ms (40%), Nice=10, MemoryMax=536870912 (512M)
```

#### Probe 2: Listener Local de Loopback
```bash
ss -tulpn | grep 8082
# Resposta esperada: tcp LISTEN 0 4096 127.0.0.1:8082
```

#### Probe 3: Teste HTTP Direto no Backend com Simulação de Proxy Auth
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "X-Forwarded-User: giovannimunizds@gmail.com" http://127.0.0.1:8082/
# Resposta esperada: 200
```

#### Probe 4: Teste de Redirecionamento 302 em Acesso Anônimo (Edge Gateway)
```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" -H "Host: storage.atius.io" http://127.0.0.1:8210/
# Resposta esperada: 302 https://storage.atius.io/login
```

#### Probe 5: Teste Headless com Cookie Corporativo Válido
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: storage.atius.io" \
  -H "Cookie: auth-token=<TOKEN_VALIDO_DO_VAULT>" \
  http://127.0.0.1:8210/
# Resposta esperada: 200
```

---

## 7. Troubleshooting e Incidentes Conhecidos

### A. HTTP 502 Bad Gateway ao Acessar `storage.atius.io`
- **Causa 1:** O daemon do Filebrowser caiu ou a porta 8082 está travada.
  - **Ação:** Verificar logs com `journalctl -u filebrowser.service -n 50 --no-pager`. Reiniciar o serviço.
- **Causa 2:** O Edge Gateway não consegue conectar no upstream.
  - **Ação:** Verificar se `127.0.0.1:8082` responde com `curl -I http://127.0.0.1:8082/`.

### B. Loop Infinito de Redirecionamento 302 para `/login`
- **Causa:** O micro-serviço ATS SSO (`127.0.0.1:8015`) está inativo ou o email do usuário logado não está cadastrado em `allowedEmails` no arquivo de configuração do Edge Gateway.
  - **Ação:** Testar a saúde do SSO com `curl http://127.0.0.1:8015/v1/healthz`. Confirmar que `giovannimunizds@gmail.com` consta no array `allowedEmails`.

### C. Erro `Permission denied` ao Navegar ou Fazer Upload no Filebrowser
- **Causa:** O rclone foi montado sem a opção `allow-other`, ou `/etc/fuse.conf` não possui a diretiva `user_allow_other`.
  - **Ação:** Conferir `/etc/fuse.conf`. Verificar se `gdrive-mount.service` contém a flag `--allow-other`.

### D. Upload de Arquivos Grandes Falha por Timeout
- **Causa:** O proxy reverso do Apache ou o Edge Gateway atinge timeout antes da conclusão do envio.
  - **Ação:** Assegurar que no Edge Gateway o timeout HTTP esteja configurado em `300000ms` (5 minutos) e que no Apache a diretiva `ProxyTimeout 600` esteja ativa para o VirtualHost do storage.
