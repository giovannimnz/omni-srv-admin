---
name: atius-fleet-login-and-sso
description: Diretrizes canônicas, árvore de decisão arquitetural, padrões de UI/UX para telas de login, contratos de SSO/Edge Gateway e governança de exceções (Landscape) na frota ATIUS.
---

<antigravity_adapter>
## Antigravity Tool Mapping (use instead of Codex tools)

| Codex / Claude Code | Antigravity |
|---|---|
| `apply_patch` / `Write` / `Edit` | `replace_file_content` or `multi_replace_file_content` |
| `exec_command` / `Bash` | `run_command` (runs Bash/sh on Linux, pwsh on Windows) |
| `rg` / `grep` / `Glob` / `list_files` | `grep_search` / `list_dir` / `find_by_name` |
| `Read` / `read_file` | `view_file` |
| `spawn_agent` / `Task()` / `Agent()` | `invoke_subagent` / `browser_subagent` |
| `request_user_input` / `AskUserQuestion` | `ask_question` |
| `web_search` | `search_web` |

Paths on this host are Linux paths (`/home/ubuntu/...`) on servers and Windows paths (`C:\Users\muniz\...`) on the Windows workstation.
</antigravity_adapter>

# Atius Fleet Login & SSO — Diretriz Canônica de Governança

Esta é a skill mestra e autoridade canônica para governança, arquitetura, construção, padronização visual e manutenção de **todas as superfícies de autenticação, telas de login e integrações SSO da frota ATIUS**.

Todas as operações de criação de novos serviços, adição de autenticação, refatoração de gateways ou auditoria de interfaces web devem obrigatoriamente seguir as diretrizes desta skill.

---

## 1. Taxonomia dos 5 Padrões de Autenticação da Frota ATIUS

A frota ATIUS opera mais de 26 serviços e endpoints web distribuídos entre servidores de produção (`atius-srv-1..4`, `horistic-srv`, `GIOVANNI-W11-PC`). Os serviços NÃO utilizam um único método homogêneo, mas sim 5 padrões arquiteturais governados e justificados:

| Padrão | Denominação | Mecanismo de Autenticação | Sessão & Tokens | Sistemas / Endpoints da Frota |
|---|---|---|---|---|
| **1** | **Atius Central SSO Nativo (ATS / Keycloak)** | Exposição de `/login` com shell canônico no próprio host. Validação de sessão em Next.js :3015 e Fastify :8015. Redirecionamento transparente sem query exposta. | Cookie `auth-token` (`Domain=.atius.com.br`, HttpOnly, Secure, Lax). Validação via `GET /v1/auth/me`. Logout central `POST /api/sso/logout` (CSRF + Origin). | `trade`, `painel`, `dashboard`, `backtest`, `strategy`, `admin`, `talk`, `admin-talk`, `remote` (MT5), `oci`, `sso`. *Em migração para Modelo PM2 same-host.* |
| **2** | **Atius Admin Edge Gateway (:8210) — MODELO PM2 (PADRÃO-OURO)** | Proxy Node.js perimetral no SRV-1. Atende `/login` no mesmo host (`same-host`), renderiza o shell canônico Atius SSO com Destino Seguro dinâmico, valida `auth-token` central via `/v1/auth/me`, checa `allowedEmails` e injeta credencial server-side upstream. | Sessão validada pelo cookie Atius SSO; usuário nunca sai do domínio da aplicação e nunca vê senhas dos upstreams. | `pm2` (**Referência Padrão-Ouro**), `grafana` (Basic Auth injetado), `portainer` / `docker` (JWT injetado via `/api/auth`), `paseo` (agent platform sem auth). |
| **3** | **Casa Remote Auth Gateway (:8088 / :8196)** | Gateway perimetral para acesso a terminais e desktops remotos. Valida `auth-token` central e emite ticket efêmero para ponte WebSocket / RustGuac. | Sessão validada pelo Atius SSO; autorização por token/ticket de curta duração. | `ssh` (`ssh.atius.com.br` / `ssh.atius.io` -> ttyd / terminal), `rdp` (`rdp.atius.com.br` -> Windows 11 host desktop). |
| **4** | **App-Local Facade Gateway** | Frontends locais que embutem middleware de validação e limpeza de cookie local antes de renderizar ou repassar requisições. | Validação em runtime local do cookie central e fallback para `/login`. | `vpn` (`vpn.atius.com.br` via `proxy.ts`), `adguard` (`adguard.atius.com.br` via `adguard-portal-gateway.cjs`). |
| **5** | **Standalone com Tela de Login Própria (Exceções Arquiteturais Governadas)** | Sistemas com isolamento de segurança estrito, backends proprietários legados ou consoles nativos do SO que NÃO usam Atius SSO. | Autenticação local proprietária / Vault AppRole / PAM Linux / Zero-Knowledge Master Password. | - **Canonical Landscape**: Zope/TwistedWeb nativo em container LXC no SRV-3. Apache Ingress no SRV-1 intercepta acessos anônimos e reescreve `/login` transparente (`next_url=/account/standalone/secrets`). CSS Dark injetado. Integração de segredos via bridge AppRole do Vault.<br>- **Vaultwarden**: Bitwarden Master Password com criptografia client-side zero-knowledge (proibido SSO por requisito de segurança).<br>- **Cockpit**: Autenticação PAM nativa do Kernel Linux (:9090).<br>- **Casa Router BE3**: Firmware Huawei embarcado envelopado em wrapper iframe HTML.<br>- **Plane / Jenkins / Cloudbeaver**: Gestão RBAC local interna. |

---

## 2. Árvore de Decisão Arquitetural para Novos Serviços

Ao conectar ou implantar qualquer novo serviço ou aplicação web na frota ATIUS, utilize rigorosamente o seguinte fluxo de decisão:

```
[Novo Serviço na Frota]
           │
           ▼
[1. O serviço exige isolamento estrito, PAM de SO, ou criptografia Zero-Knowledge?]
    ├── SIM ──► PADRÃO 5: STANDALONE EXCEÇÃO GOVERNADA
    │           (Ex: Vaultwarden, Cockpit PAM, Landscape Zope, Firmware Roteador)
    │           Requisitos: Login nativo isolado, credenciais no Vault, CSS Dark se customizável.
    └── NÃO
           │
           ▼
[2. O serviço é uma ferramenta interna de terceiros SEM suporte nativo a OIDC/SSO?]
    ├── SIM ──► PADRÃO 2: ATIUS ADMIN EDGE GATEWAY (:8210)
    │           (Ex: Grafana, Portainer, PM2 Dashboard, Ferramentas Internas)
    │           Requisitos: Validar auth-token central via /v1/auth/me, checar allowlist de emails,
    │           injetar credenciais server-side upstream via headers/Basic/JWT.
    └── NÃO
           │
           ▼
[3. O serviço entrega terminal SSH ou desktop gráfico remoto via browser?]
    ├── SIM ──► PADRÃO 3: CASA REMOTE AUTH GATEWAY (:8088 / :8196)
    │           (Ex: ttyd terminal web, noVNC desktop W11/Linux)
    │           Requisitos: Validar auth-token central e emitir ticket efêmero assinado para WebSocket.
    └── NÃO
           │
           ▼
[4. A aplicação possui backend próprio e necessita gerenciar contexto local?]
    ├── SIM ──► PADRÃO 4: APP-LOCAL FACADE GATEWAY
    │           (Ex: AdGuard Home Portal, WireGuard VPN Manager)
    │           Requisitos: Middleware de validação do cookie auth-token, proxy reverso local,
    │           limpeza de parâmetros e fallback limpo para /login.
    └── NÃO
           │
           ▼
[5. Aplicação padrão web do ecossistema ATIUS (Next.js / Node / API)]
    └─────────► PADRÃO 1: ATIUS CENTRAL SSO NATIVO
                (Ex: Painéis de negócio, Trading, Analytics, ATS)
                Requisitos: Ingress Apache com rewrite /login transparente, cookie de sessão
                compartilhado auth-token (Domain=.atius.com.br), validação /v1/auth/me,
                logout central POST /api/sso/logout com CSRF e Origin.
```

---

## 3. Especificação Canônica de Design UI/UX para Telas de Login

Toda tela de login desenvolvida, customizada ou envelopada na frota ATIUS deve aderir estritamente ao contrato visual de alta fidelidade estabelecido no repositório ATS (`sso-ssh-base-model.png` e `Diretriz-Canonica-Telas-de-Login-e-SSO.md`):

### 3.1 Geometria e Dimensões
- **Card Central de Login**: Dimensão exata de `448px` de largura máxima (`width: min(448px, 100%)`).
  - Padding interno: `28px 24px` a `32px`.
  - Border-radius: `12px`.
  - Borda: `1px solid rgba(55, 65, 81, 0.3)` / `1px solid rgba(255, 255, 255, 0.08)`.
  - Background: `#171b22` / `rgba(17, 24, 39, 0.35)`.
  - **Zero barras azuis**: Proibido qualquer artefato de cor destoante no topo do card (como a linha azul PatternFly do Keycloak).
- **Logo Atius**: Dimensão exata de `44 × 44 px`.
  - SVG vetorial canônico Atius (ouro/verde ou ciano estilizado oficial) centralizado acima do formulário com subtítulo sutil "Atius SSO" em 11px (`#9ca3af`).
  - O favicon canônico Atius deve ser servido em todos os endpoints (`/_atius/favicon.svg` ou `/favicon.ico`). É expressamente proibido o uso de favicons legados de terceiros ou emojis.

### 3.2 Tipografia e Hierarquia Visual (Padrão PM2)
- **Título da Aplicação**: `11px`, font-weight `400`, uppercase, letter-spacing `0.05em`, cor `#9aa0a6`.
- **Box "Destino seguro"**:
  - Background: `rgba(31, 41, 55, 0.4)` / `#1b222c`, borda `1px solid rgba(55, 65, 81, 0.4)`.
  - Label superior: `DESTINO SEGURO` em caixa alta, tamanho `11px`, cor `#9ca3af`.
  - Linha de destino: Ícone de escudo SVG com check na cor laranja Atius (`#f97316` / `#ff7112`), seguido do hostname puro (ex: `pm2.atius.io` ou `gitlab.atius.io`) em `14px`, cor `#e5e7eb`.
- **Labels de Formulário**: `14px`, font-weight `500`, cor `#ffffff` / `#d0d4dc`.
- **Inputs de Texto / Senha com Ícones Integrados (Padrão PM2)**:
  - Input "Email ou username": Ícone 👤 à esquerda (`icon-left`), altura `44px`, placeholder `"Digite seu email ou username"`, background `#1f2937` / `#1a1d24`, border `1px solid #4b5563`, text-color `#ffffff`, border-radius `10px`.
  - Input "Senha": Ícone 🔒 à esquerda (`icon-left`), altura `44px`, placeholder `"Digite sua senha"`, botão de olho 👁 à direita (`icon-right`) com funcionalidade nativa de toggle de visualização (password <-> text).
  - Foco: Contorno em laranja Atius (`border-color: #f97316; box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.2)`).
- **Botão Primário de Submissão**:
  - Altura `44px`, border-radius `10px`, background `#f97316` / `#ff7112` (hover `#ea580c` / `#e0600a`), text-color `#ffffff`, font-weight `500`/`600`, font-size `14px`, largura 100%.
  - Label: `"Entrar com Atius SSO"`.

### 3.3 Acessibilidade e Padrões WCAG 2.2 AA
- **Contraste de Cores**: Mínimo de `4.5:1` para textos regulares e `3:1` para componentes interativos e bordas ativas.
- **Área Mínima de Toque (Touch Target)**: Mínimo de `44 × 44 px` para todos os botões, checkboxes e links.
- **Foco e Teclado**: Todos os campos interativos devem possuir indicador de foco evidente (`outline: 2px solid #3b82f6; outline-offset: 2px`). Nenhum script pode criar armadilhas de teclado (focus trap).
- **Dark Mode**: O modo escuro (`atius-classic-dark`) é o tema padrão mandatória em toda a frota.

---

## 4. Contratos de Segurança & Lifecycle de Autenticação

Para garantir a postura de segurança perimetral contra vazamento de credenciais, phishing interno e loops de redirecionamento, os seguintes 5 contratos técnicos são obrigatórios:

### 4.1 Contrato do Campo "Destino seguro" (Host-Only)
- O campo "Destino seguro" na tela de login exibe **estritamente o `URL.hostname` puro**.
- **PROIBIDO**: Protocolo (`https://`), portas (`:8443`), barras (`/`), caminhos (`/compute`), query strings (`?tab=1`) ou fragments (`#id`).
  - Exemplo válido: `ssh.atius.com.br` ou `painel.atius.com.br`.
  - Exemplo proibido: `https://ssh.atius.com.br:8443/compute?ref=main`.
- **Login Central Neutro**: Quando o usuário acessar diretamente `https://sso.atius.com.br/login` sem nenhum aplicativo de destino informado, o campo DEVE exibir exatamente o valor neutro canônico:
  ```
  Destino seguro: Nenhum destino selecionado
  ```

### 4.2 URL Limpa no Navegador (Zero Query Leak)
- Toda tela de login na barra de endereços do usuário deve ser limpa e canônica:
  ```
  https://<app>.atius.com.br/login
  ```
- **PROIBIDO** expor `?return_to=...`, `?next=...`, deep links ou tokens de autenticação na query string da URL pública.
- **Mecanismo de Retorno Seguro**: O parâmetro de retorno de deep-link deve ser gravado exclusivamente em um cookie transitório host-only:
  - Nome: `atius_sso_login_return_to`
  - Atributos: `HttpOnly; Secure; SameSite=Lax; Max-Age=600`
  - Ciclo de vida: Criado na requisição inicial anônima, consumido e destruído (`Max-Age=0`) imediatamente após o primeiro redirecionamento bem-sucedido.

### 4.3 Prevenção de Enumeração de Credenciais
- Mensagens de erro de autenticação devem ser rigorosamente genéricas:
  ```
  "Credenciais inválidas. Verifique seu usuário e senha."
  ```
- Proibido informar se o erro foi de usuário inexistente ou de senha incorreta.
- Respostas de falha de login devem aplicar taxa limite de tentativas (Rate Limiting) e tempo constante de hashing para evitar ataques de temporização (timing attacks).

### 4.4 Prevenção do Loop 302
- Se um backend upstream rejeitar ou invalidar o token de sessão, o proxy reverso ou gateway **NUNCA** deve responder com redirecionamento 302 cíclico para `/login`.
- Em caso de falha de credencial upstream, o gateway deve renderizar uma página amigável de erro HTTP 401/403 ou 502/503 com código de correlação interno (ex: `GATEWAY_UPSTREAM_AUTH_REJECTED`), permitindo intervenção do operador ou logout limpo.

### 4.5 Logout Seguro POST-Only
O processo de encerramento de sessão na frota deve seguir estritamente o contrato seguro:
- **Endpoint Central**: `POST https://sso.atius.com.br/api/sso/logout`
- **Headers Obrigatórios**:
  - `Content-Type: application/json`
  - `Origin`: Validado contra a allowlist de domínios permitidos (`*.atius.com.br`, `*.atius.io`).
  - `X-CSRF-Token`: Token de uso único amarrado à sessão criptográfica do usuário.
- **Rejeição Estrita de GET**: Requisições de logout via `GET /logout` são proibidas para impedir logout inadvertido por pre-fetching de navegadores, spiders ou ataques de CSRF simples via tags `<img src="/logout">`.
- **Invalidação em Cascata**: O servidor deve invalidar a sessão no Redis/Keycloak e emitir cabeçalho de expiração de cookie:
  ```http
  Set-Cookie: auth-token=; Path=/; Domain=.atius.com.br; Max-Age=0; HttpOnly; Secure; SameSite=Lax
  ```

---

## 5. Invariante Dual-Domain RFC 6265 (.com.br vs .io)

A frota ATIUS opera em arquitetura de paridade dual-domain (`atius.com.br` e `atius.io`). No entanto, as equipes devem respeitar as leis fundamentais de isolamento de cookies da web:

1. **Isolamento de TLD no RFC 6265**:
   - Um cookie configurado com `Domain=.atius.com.br` **NUNCA** é enviado pelo navegador para requisições direcionadas a `*.atius.io`.
   - "Logou em um, logou em tudo" é nativo **apenas** dentro do mesmo TLD (`*.atius.com.br`).
2. **Requisitos Obrigatórios para Serviços sob `.atius.io`**:
   - **CORS Allowlist**: Configuração explícita de `allowedOrigins` nos backends (ex: Fastify/Express) incluindo ambas as origens.
   - **Ingress Apache Paritário**: Todo VirtualHost configurado no Apache para `app.atius.com.br` deve possuir bloco idêntico para `app.atius.io` com certificados TLS Origin CA válidos.
   - **Edge Gateway Transparent Session Resolution**: Gateways como o `:8210` e `:8088` devem resolver a sessão individualmente no domínio acessado sem assumir compartilhamento automático de cookie inter-TLD.

---

## 6. Governança do Canonical Landscape Standalone (Exceção Homologada)

O **Canonical Landscape** (gerenciador central de controle e automação da frota Linux) é uma **Exceção Arquitetural Homologada (Padrão 5)** e NÃO deve ser integrado ao Atius SSO.

### 6.1 Justificativa Arquitetural
- **Monolito Zope/TwistedWeb**: O Landscape Server opera sobre um runtime Python/Zope legado em container LXC isolado no servidor `atius-srv-3` (`10.13.1.13:80`).
- **Incompatibilidade OIDC**: Não possui suporte nativo a OIDC/OAuth2 moderno nem autenticação baseada em cabeçalhos HTTP confiáveis sem risco de quebra do protocolo do agente `landscape-client`.
- **Segurança de Controle Soberano**: Por ser o plano de controle de execução remota de scripts em todos os servidores, o Landscape deve permanecer independente da disponibilidade do serviço de SSO central (ATS/Keycloak).

### 6.2 Implementação do Ingress e Reescrita Transparente
- O tráfego público acessa `https://landscape.atius.com.br` e `https://landscape.atius.io`.
- No Apache Ingress do `atius-srv-1`, requisições anônimas são reescritas de forma limpa:
  ```apache
  # Regra canônica de reescrita transparente do Landscape
  RewriteEngine On
  RewriteCond %{REQUEST_URI} ^/login/?$
  RewriteRule ^/login/?$ /+login?next_url=%2Faccount%2Fstandalone%2Fsecrets [R=302,L]
  ```
- O tráfego do agente cliente (`http://landscape.atius.com.br/ping`) é preservado em HTTP puro sem redirecionamento para HTTPS, garantindo a conectividade de todos os nós da frota.

### 6.3 Skin e Tema Dark Injetado
- Para eliminar defeitos de contraste visual (texto branco em fundo branco nos modais `.cookie-policy` e cards de login), o container LXC no SRV-3 possui override de CSS dark em:
  `/opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt`
  com o bloco de estilo `<style id="atius-classic-dark">`.

### 6.4 Gestão de Segredos via Vault
- As credenciais de acesso ao Landscape são gerenciadas centralmente no HashiCorp Vault em `kv/atius/landscape/*` via autenticação AppRole, mantendo conformidade com a política de zero segredos expostos.

---

## 7. Procedimentos de Emergência / Break-Glass

Em situações de indisponibilidade severa da infraestrutura de SSO central (ex: queda do ATS, banco de dados de autenticação ou rede interna), os operadores devem seguir os procedimentos de Break-Glass homologados:

1. **Plano de Controle Soberano (Landscape CLI)**:
   - Executar automações e comandos simultaneamente na frota sem depender de UI web:
     ```bash
     omni landscape run <script-id> --hosts all --wait --yes
     ```
2. **SSH Nativo Direto (Fallback Multi-Porta)**:
   - Se o WireGuard ou o gateway web `ssh.atius.com.br` estiverem indisponíveis, utilizar as portas SSH públicas diretas:
     - Windows 11 Host: `ssh -p 8122 muniz@ssh-giovanni-w11-pc.atius.com.br`
     - WSL Ubuntu: `ssh -p 8222 muniz@ssh-giovanni-wsl-pc.atius.com.br`
     - S23 Termux: `ssh -p 8322 termux@ssh-giovanni-s23.atius.com.br`
     - Servidores Linux: Acesso via IP privado OCI DRG (`10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.14.1.14`, `10.21.1.21`).
3. **OCI Serial Console**:
   - Para recuperação em nível de boot de instâncias Oracle Cloud ARM64, utilizar os scripts de console serial via `oci-admin` sem tráfego TCP/IP.
4. **Credenciais de Emergência no Vault**:
   - Credenciais break-glass residem em `kv/atius/breakglass/emergency-creds` e só devem ser acessadas mediante justificativa operacional e auditoria pós-incidente.

---

## 8. Referências Cruzadas Completas

A governança de Login e SSO da frota ATIUS é sustentada por documentação cruzada mantida nos três pilares de conhecimento do ecossistema:

### 8.1 Obsidian Vault (`AiSecondBrain/Operations/Autenticacao-e-SSO/`)
- `00-INDEX-Autenticacao-e-SSO.md`: Índice mestre, taxonomia e navegação de autenticação da frota.
- `Diretriz-Canonica-Telas-de-Login-e-SSO.md`: Especificação milimétrica de UI/UX, geometria, tipografia, segurança e acessibilidade.
- `Matriz-Sistemas-Login-Frota-Atius.md`: Matriz exaustiva dos 29 endpoints web da frota com mapeamento de hosts, backends, portas e padrões.
- `Arquitetura-Dual-Domain-Cookies-e-CORS.md`: Invariantes de cookies RFC 6265, CORS e paridade `.com.br` vs `.io`.
- `Excecoes-Arquiteturais-Landscape-e-Breakglass.md`: Justificativa do Canonical Landscape Standalone e procedimentos de contingência Break-Glass.

### 8.2 Memória Operacional GBrain
- **Fato #765**: Taxonomia dos 5 padrões arquiteturais de autenticação da frota ATIUS.
- **Fato #766**: Governança e arquitetura do Canonical Landscape Standalone (Zope LXC SRV-3, reescrita Ingress Apache /login, CSS dark, Vault AppRole).
- **Fato #767**: Padrão visual UI/UX de telas de login (card 448x454.25 px, logo 44x44 px, URL limpa sem query, Destino seguro host-only).
- **Fato #768**: Invariante RFC 6265 Dual-Domain e regras de isolamento de cookies entre `.com.br` e `.io`.
- **Fato #769**: Logout seguro POST-only com CSRF token e cabeçalho Origin.
- **Fato #770**: Detalhamento dos gateways perimetrais Edge Gateway :8210, Casa Remote Gateway :8088/:8196 e App-Local Facade.
- **Timeline #300** na página mãe: `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`.

### 8.3 Documentação no Repositório `omni-srv-admin`
- `docs/domain/atius-fleet-login-and-sso-governance.md`: Guia canônico completo de governança para auditoria e esteira de CI/CD.
- `docs/domain/atius-sso-lifecycle-matrix.md`: Matriz de ciclo de vida e testes de aceitação automatizados.
- `docs/domain/atius-wide-sso.md`: Arquitetura do SSO central no ATS.
- `docs/domain/atius-sso-manual-index.md`: Índice operacional de integrações SSO.

### 8.4 Skills Relacionadas
- `atius-sso`: Implementação técnica, montagem, inclusão e validação de ciclo de vida de integrações SSO.
- `atius-dual-domain`: Operação e provisionamento paritário de serviços em `atius.com.br` e `atius.io`.
- `atius-sso-governed-release-closeout`: Fechamento de releases e promoção governada de autenticação.
