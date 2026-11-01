# Governança Canônica de Login, SSO e Autenticação da Frota ATIUS

**Documento Canônico de Arquitetura e Engenharia de Frota**  
**Data**: 2026-11-01  
**Status**: Vigente / Homologado  
**Repositório**: `omni-srv-admin`  
**Autoridade**: Diretrizes de Governança ATIUS  

---

## 1. Sumário Executivo & Finalidade

Este documento estabelece a política soberana de autenticação, telas de login, Single Sign-On (SSO), proxies perimetrais e exceções governadas para todos os serviços web operados na frota ATIUS (`atius-srv-1..4`, `horistic-srv`, `GIOVANNI-W11-PC`, `WSL`, `S23`).

O ecossistema ATIUS engloba mais de 26 serviços web críticos (sistemas de negociação algorítmica, painéis analíticos, orquestração de containers, terminais SSH/RDP web, plataformas de agentes autônomos, VPN e controle de frota). Esta diretriz elimina inconsistências arquiteturais, impede desvios de design em telas de autenticação e formaliza os limites de segurança perimetral entre autenticação centralizada, proxies de injeção de credenciais e exceções isoladas.

---

## 2. Escopo & Topologia de Ingress da Frota

A infraestrutura de rede da frota ATIUS opera em camadas hierárquicas conectadas via Cloudflare Edge, malha privada OCI DRG (`10.11.1.11` a `10.14.1.14` e `10.21.1.21`) e túneis WireGuard (`10.100.100.0/24`):

```
                                  [ Navegador / Usuário ]
                                             │
                                             ▼
                        [ Cloudflare Edge (DNS Proxied + TLS) ]
                                  │                     │
                     *.atius.com.br                     *.atius.io
                                  │                     │
                                  ▼                     ▼
               [ Apache Ingress TLS (atius-srv-1: 10.11.1.11:443) ]
                     │                   │                   │
         ┌───────────┴──────────┐        │        ┌──────────┴──────────┐
         ▼                      ▼        ▼        ▼                     ▼
   [ ATS / Keycloak ]    [ Edge Gateway ]  [ Ingress LXC ]    [ Remote Gateway ]
   Next :3015/Fast :8015     (:8210)          SRV-3: Landscape     (:8088 / :8196)
     Padrão 1                Padrão 2         Padrão 5             Padrão 3
```

- **Ponto de Entrada Canônico**: Todo tráfego HTTP/HTTPS público ingressa pelo proxy Apache no nó primário `atius-srv-1`.
- **Certificados TLS**: Emitidos pelo Cloudflare Origin CA ou Let's Encrypt em paridade dual-domain estrita (`*.atius.com.br` e `*.atius.io`).
- **Comunicação Interna**: Encaminhamento upstream ocorre exclusivamente pela malha privada interna OCI DRG de alta velocidade e sub-milissegundo (~0.6 ms), sem exposição de portas de backends para a Internet pública.

---

## 3. Taxonomia Canônica: Os 5 Padrões de Autenticação da Frota

A frota ATIUS classifica todos os seus serviços em 5 padrões arquiteturais mutuamente exclusivos e governados:

### Padrão 1: Atius Central SSO Nativo (ATS / Keycloak)
- **Mecanismo**: A aplicação expõe externamente `/login`, que é reescrito ou roteado de forma transparente pelo Ingress Apache para o shell central do ATS (Next.js :3015 e Fastify :8015).
- **Gestão de Sessão**: Cookie compartilhado `auth-token` com escopo `Domain=.atius.com.br`, `Path=/`, `HttpOnly`, `Secure` e `SameSite=Lax`.
- **Validação de Sessão**: O backend consulta `GET /v1/auth/me` na API central.
- **Encerramento**: Logout centralizado via `POST /api/sso/logout` exigindo cabeçalho `Origin` validado e token criptográfico `X-CSRF-Token`.
- **Aplicações Típicas**: Plataformas proprietárias desenvolvidas internamente (`trade`, `painel`, `dashboard`, `backtest`, `strategy`, `admin`, `talk`, `admin-talk`, `remote`, `oci`, `sso`).

### Padrão 2: Atius Admin Edge Gateway (:8210)
- **Mecanismo**: Proxy perimetral em Node.js residente no `atius-srv-1`. Intercepta rotas desprotegidas e solicitações de login, valida o cookie `auth-token` contra `GET /v1/auth/me`, verifica se o email do usuário consta na lista de acesso permitida (`allowedEmails`) e injeta credenciais administrativas upstream no cabeçalho da requisição enviada ao backend.
- **Gestão de Sessão**: O usuário final não conhece e não gerencia as credenciais do upstream; a sessão é autenticada puramente pelo SSO central.
- **Aplicações Típicas**: Ferramentas de infraestrutura de terceiros que não possuem suporte nativo ou viável a OIDC (`grafana` com Basic Auth injetado, `portainer`/`docker` com JWT administrativo injetado via `/api/auth`, `pm2` dashboard de processos, `paseo` plataforma de agentes).

### Padrão 3: Casa Remote Auth Gateway (:8088 / :8196)
- **Mecanismo**: Gateway de autenticação perimetral dedicado a sessões remotas e terminais interativos em tempo real. Valida o cookie `auth-token` central e gera um ticket de curta duração assinado criptograficamente para handshake com os bridges WebSocket (ttyd para terminal Linux e RustGuac/noVNC para desktops gráficos).
- **Gestão de Sessão**: Sessão primária no Atius SSO; autorização na camada de transporte via ticket efêmero.
- **Aplicações Típicas**: `ssh` (`ssh.atius.com.br` / `ssh.atius.io` apontando para terminais web ttyd) e `rdp` (`rdp.atius.com.br` conectando ao desktop do Windows 11 host).

### Padrão 4: App-Local Facade Gateway
- **Mecanismo**: Aplicações com backends dedicados que embutem middleware local em seu próprio servidor web/proxy para validar a presença e integridade do cookie `auth-token`.
- **Gestão de Sessão**: Validação local no gateway da aplicação com limpeza de parâmetros e fallback gracioso para `/login` central em caso de ausência de sessão.
- **Aplicações Típicas**: `vpn` (`vpn.atius.com.br` via `proxy.ts` do portal WireGuard) e `adguard` (`adguard.atius.com.br` via `adguard-portal-gateway.cjs`).

### Padrão 5: Standalone com Tela de Login Própria (Exceções Arquiteturais Governadas)
- **Mecanismo**: Aplicações com isolamento estrito de segurança, consoles nativos do sistema operacional ou ferramentas com backends legados monolíticos que **NÃO** utilizam o Atius SSO.
- **Gestão de Sessão**: Autenticação local isolada, senhas mestras com criptografia client-side zero-knowledge, autenticação PAM do kernel Linux ou credenciais gerenciadas via Vault AppRole.
- **Aplicações Típicas**:
  - **Canonical Landscape**: Zope/TwistedWeb nativo em container LXC no `atius-srv-3`. Ingress Apache intercepta `/login` e reescreve transparente para `next_url=/account/standalone/secrets`. CSS Dark injetado (`atius-classic-dark`). Segredos via HashiCorp Vault AppRole.
  - **Vaultwarden**: Servidor Bitwarden com criptografia zero-knowledge (proibido SSO por requisito de não-custódia de chaves de criptografia).
  - **Cockpit**: Console administrativo do SO com autenticação PAM nativa no nó Linux (:9090).
  - **Casa Router BE3**: Firmware de roteador Huawei embarcado protegido em iframe local.
  - **Plane / Jenkins / Cloudbeaver**: Ferramentas com RBAC interno dedicado.

---

## 4. Matriz Exaustiva dos Sistemas da Frota ATIUS

A tabela abaixo documenta o inventário oficial e a classificação de todos os 29 endpoints web da frota:

| # | Endpoint / Subdomínio | Host Primário | Porta/Backend Upstream | Padrão | Mecanismo de Autenticação & Sessão | Observações de Governança |
|---|---|---|---|---|---|---|
| 1 | `sso.atius.com.br` | atius-srv-1 | 10.11.1.11:3015 | Padrão 1 | ATS Central SSO / Keycloak OIDC | Ponto focal de login e emissão de `auth-token`. |
| 2 | `trade.atius.com.br` | atius-srv-1 | 10.11.1.11:3000 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Painel de trading institucional. |
| 3 | `painel.atius.com.br` | atius-srv-1 | 10.11.1.11:3001 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Gestão corporativa Atius. |
| 4 | `dashboard.atius.com.br` | atius-srv-1 | 10.11.1.11:3002 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Métricas e analytics de execução. |
| 5 | `backtest.atius.com.br` | atius-srv-1 | 10.11.1.11:3003 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Motor de backtesting quantitativo. |
| 6 | `strategy.atius.com.br` | atius-srv-1 | 10.11.1.11:3004 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Gestão de algoritmos de negociação. |
| 7 | `admin.atius.com.br` | atius-srv-1 | 10.11.1.11:3005 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Console administrativo do ATS. |
| 8 | `talk.atius.com.br` | atius-srv-1 | 10.11.1.11:3006 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Interface conversacional de IA. |
| 9 | `admin-talk.atius.com.br` | atius-srv-1 | 10.11.1.11:3007 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Gestão administrativa do Talk. |
| 10 | `remote.atius.com.br` | atius-srv-1 | 10.11.1.11:3008 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Conector de instâncias MT5 remotas. |
| 11 | `oci.atius.com.br` | atius-srv-1 | 10.11.1.11:3009 | Padrão 1 | ATS SSO (`auth-token` + `/v1/auth/me`) | Portal de visualização da nuvem OCI. |
| 12 | `grafana.atius.com.br` | atius-srv-1 | 10.11.1.11:3030 | Padrão 2 | Edge Gateway :8210 (Injeção Basic Auth) | Observabilidade Prometheus/Loki. |
| 13 | `portainer.atius.com.br` | atius-srv-1 | 10.11.1.11:9000 | Padrão 2 | Edge Gateway :8210 (Injeção JWT `/api/auth`) | Gestão de containers Docker/Podman. |
| 14 | `docker.atius.com.br` | atius-srv-1 | 10.11.1.11:9000 | Padrão 2 | Edge Gateway :8210 (Injeção JWT `/api/auth`) | Alias canônico para Portainer. |
| 15 | `pm2.atius.com.br` | atius-srv-1 | 10.11.1.11:9615 | Padrão 2 | Edge Gateway :8210 (Proxy Perimetral) | Monitoramento de daemons Node.js. |
| 16 | `paseo.atius.com.br` | atius-srv-1 | 10.11.1.11:8080 | Padrão 2 | Edge Gateway :8210 (Proxy Perimetral) | Plataforma de agentes autônomos. |
| 17 | `ssh.atius.com.br` | atius-srv-1 | 10.11.1.11:8088 | Padrão 3 | Remote Gateway :8088 (Ticket WebSocket) | Shell web ttyd para servidores da frota. |
| 18 | `ssh.atius.io` | atius-srv-1 | 10.11.1.11:8088 | Padrão 3 | Remote Gateway :8088 (Ticket WebSocket) | Paridade dual-domain para terminal web. |
| 19 | `rdp.atius.com.br` | atius-srv-1 | 10.11.1.11:8196 | Padrão 3 | Remote Gateway :8196 (Ticket RustGuac) | Acesso visual ao desktop GIOVANNI-W11-PC. |
| 20 | `vpn.atius.com.br` | atius-srv-1 | 10.11.1.11:51821 | Padrão 4 | App-Local Facade (`proxy.ts`) | Portal de administração WireGuard. |
| 21 | `adguard.atius.com.br` | atius-srv-1 | 10.11.1.11:3003 | Padrão 4 | App-Local Facade (`adguard-portal-gateway`) | Resolução de DNS e filtro de anúncios. |
| 22 | `landscape.atius.com.br` | atius-srv-3 | 10.65.172.253:80 | Padrão 5 | Standalone Zope / Reescrita Apache Ingress | Plano de controle soberano da frota Linux. |
| 23 | `landscape.atius.io` | atius-srv-3 | 10.65.172.253:80 | Padrão 5 | Standalone Zope / Reescrita Apache Ingress | Paridade dual-domain para Landscape. |
| 24 | `vault.atius.com.br` | atius-srv-3 | 10.13.1.13:8200 | Padrão 5 | Standalone Vault (Token / AppRole) | Cofre autoritativo de segredos da frota. |
| 25 | `vaultwarden.atius.com.br` | atius-srv-1 | 10.11.1.11:8085 | Padrão 5 | Standalone Zero-Knowledge Master Password | Gerenciador de senhas Bitwarden. |
| 26 | `cockpit.atius.com.br` | atius-srv-1 | 10.11.1.11:9090 | Padrão 5 | Standalone Linux Kernel PAM Auth | Console de administração do host Ubuntu. |
| 27 | `router.atius.com.br` | local-be3 | 192.168.1.1:80 | Padrão 5 | Standalone Firmware Huawei Embarcado | Interface do roteador de borda residencial. |
| 28 | `plane.atius.com.br` | atius-srv-2 | 10.12.1.12:8091 | Padrão 5 | Standalone RBAC Local / Plane Auth | Gestão de tarefas e projetos de engenharia. |
| 29 | `cloudbeaver.atius.com.br` | atius-srv-1 | 10.11.1.11:8978 | Padrão 5 | Standalone RBAC Local / DBeaver Auth | Console web de administração PostgreSQL. |

---

## 5. Árvore de Decisão Arquitetural para Novos Serviços

Para integrar qualquer novo serviço, microserviço ou aplicação de terceiros na frota, a equipe de engenharia DEVE seguir a seguinte árvore de decisão estrita:

```
[Início: Novo Serviço na Frota]
           │
           ▼
[Questão 1: O serviço possui requisito estrito de segurança que proíbe SSO?]
   (Exemplos: Zero-Knowledge client-side, PAM nativo do SO, firmware embarcado,
    ou plano de controle de execução soberana isolado de falhas como Landscape).
    ├── SIM ──► APLICAR PADRÃO 5 (STANDALONE GOVERNADO)
    │           - Proteger rota com HTTPS e TLS Origin CA.
    │           - Credenciais administrativas estritamente registradas no Vault.
    │           - Injetar tema dark (atius-classic-dark) se houver suporte a templates.
    └── NÃO
           │
           ▼
[Questão 2: O serviço é ferramenta web de terceiros sem suporte a OIDC?]
    ├── SIM ──► APLICAR PADRÃO 2 (EDGE GATEWAY :8210)
    │           - Configurar entrada no Ingress Apache apontando para :8210.
    │           - Registrar aplicação no array de rotas do Edge Gateway.
    │           - Configurar checagem de auth-token via /v1/auth/me e allowedEmails.
    │           - Injetar credencial administrativa upstream via cabeçalho HTTP server-side.
    └── NÃO
           │
           ▼
[Questão 3: O serviço entrega terminal SSH ou desktop gráfico interativo?]
    ├── SIM ──► APLICAR PADRÃO 3 (CASA REMOTE AUTH GATEWAY)
    │           - Integrar com o gateway perimetral :8088/:8196.
    │           - Validar auth-token central e emitir tickets efêmeros assinados.
    └── NÃO
           │
           ▼
[Questão 4: O serviço possui backend próprio e gerencia sessão local?]
    ├── SIM ──► APLICAR PADRÃO 4 (APP-LOCAL FACADE GATEWAY)
    │           - Implementar middleware local de validação de cookie.
    │           - Garantir limpeza de parâmetros transitórios e fallback para /login.
    └── NÃO
           │
           ▼
[Caso Padrão: Aplicação Web Interna / Ecossistema ATS]
    └─────────► APLICAR PADRÃO 1 (ATIUS CENTRAL SSO NATIVO)
                - Ingress Apache com rewrite transparente de /login para Next :3015.
                - Herança automática do cookie auth-token (Domain=.atius.com.br).
                - Validação central via /v1/auth/me.
                - Logout central via POST /api/sso/logout com CSRF e Origin.
```

---

## 6. Especificação Canônica de Design UI/UX para Telas de Login

Toda interface de login da frota ATIUS deve aderir ao padrão geométrico, tipográfico e de acessibilidade homologado:

### 6.1 Geometria e Grid
- **Container / Card Central**:
  - Largura: `448px`.
  - Altura padrão de referência: `454.25px`.
  - Padding: `32px` em todos os lados.
  - Border-Radius: `12px`.
  - Border: `1px solid rgba(255, 255, 255, 0.08)`.
  - Background: `#121418` (Surface Dark).
  - Box-Shadow: `0 8px 32px rgba(0, 0, 0, 0.45)`.
- **Logotipo Atius**:
  - Dimensão: `44 × 44px`.
  - Posição: Centralizado no topo do card, margem inferior de `24px`.
  - Favicon: Favicon oficial Atius (`/favicon.ico`). Expressamente proibidos favicons legados ou emojis em abas de navegação.

### 6.2 Tipografia e Escala
- **Título do Sistema**: `11px`, peso `400`, uppercase, letter-spacing `0.05em`, cor `#9aa0a6`.
- **Hostname / Destino Seguro**: `14px`, peso `400`, fonte monoespaçada (`font-family: monospace`), cor `#f0f2f5`.
- **Labels de Campos**: `14px`, peso `500`, cor `#d0d4dc`.
- **Campos de Entrada (Inputs)**: `14px`, altura `44px`, background `#1a1d24`, border `1px solid rgba(255, 255, 255, 0.12)`, border-radius `8px`, cor `#f0f2f5`.
- **Botão Primário de Ação**: `14px`, peso `500`, altura `44px`, background `#2563eb` (hover `#1d4ed8`), text-color `#ffffff`, border-radius `8px`.

### 6.3 Acessibilidade & WCAG 2.2 AA
- **Contraste de Cores**: Todo texto informativo deve manter relação de contraste de no mínimo `4.5:1` contra o fundo. Elementos interativos e bordas ativas devem satisfazer `3:1`.
- **Tamanho de Alvo de Toque (Touch Target)**: Mínimo de `44 × 44px` para botões e links de navegação.
- **Navegação por Teclado**: Ordem de tabulação lógica (`tabindex="0"`), sem armadilhas de foco (`focus traps`). Indicador de foco evidente: `outline: 2px solid #3b82f6; outline-offset: 2px`.
- **Modo Escuro (Dark Mode)**: Tema dark (`atius-classic-dark`) obrigatório como padrão.

---

## 7. Contratos Técnicos de Segurança & Lifecycle

Para mitigar riscos de engenharia reversa, phishing e bypass de autenticação, aplicam-se cinco contratos técnicos rígidos:

### 7.1 Contrato do Campo "Destino seguro" (Host-Only)
- O campo "Destino seguro" deve renderizar **estritamente o valor de `URL.hostname` puro**.
- **PROIBIDO**: Protocolo (`https://`), portas (`:8443`), barras (`/`), caminhos (`/compute`), query strings (`?tab=1`) ou fragments (`#id`).
  - *Correto*: `painel.atius.com.br`
  - *Incorreto*: `https://painel.atius.com.br:443/home?user=1`
- **Fallback Neutro**: Quando a tela central for carregada sem um destino válido pré-configurado, o valor do campo deve ser exatamente:
  ```
  Destino seguro: Nenhum destino selecionado
  ```

### 7.2 URL Limpa no Navegador (Zero Query Leak)
- A URL exibida ao usuário deve ser limpa e canônica:
  ```
  https://<app>.atius.com.br/login
  ```
- **PROIBIDO**: Exposição de parâmetros transitórios na barra de endereços (`?return_to=...`, `?next=...`, tokens ou segredos).
- **Cookie de Transporte Transitório**: Redirecionamentos de retorno devem utilizar cookie temporário host-only:
  - Nome: `atius_sso_login_return_to`
  - Flags: `HttpOnly; Secure; SameSite=Lax; Max-Age=600`
  - Comportamento: O cookie deve ser lido e destruído (`Max-Age=0`) no primeiro redirecionamento pós-login.

### 7.3 Prevenção de Enumeração de Usuários
- Em caso de falha de login, a mensagem de erro retornada deve ser rigorosamente genérica:
  ```
  "Credenciais inválidas. Verifique seu usuário e senha."
  ```
- Proibido indicar se o usuário existe ou se apenas a senha estava incorreta. Respostas devem possuir tempo de processamento padronizado contra ataques de temporização.

### 7.4 Prevenção do Loop 302
- Em cenários onde a autenticação no backend upstream falha ou é revogada, proxies e gateways **NUNCA** devem disparar redirecionamento HTTP 302 em loop contínuo para `/login`.
- O gateway deve renderizar página de erro HTTP 401/403 com código de diagnóstico transparente (ex: `AUTH_UPSTREAM_SESSION_REJECTED`), permitindo ao operador realizar logout limpo ou reiniciar a sessão.

### 7.5 Logout Seguro POST-Only
- **Endpoint Central**: `POST https://sso.atius.com.br/api/sso/logout`
- **Validação Estrita**:
  - O método `GET /logout` é expressamente bloqueado para evitar encerramento acidental de sessão por prefetching ou ataques de CSRF simples.
  - O cabeçalho `Origin` deve bater com a allowlist oficial de domínios (`*.atius.com.br`, `*.atius.io`).
  - A requisição deve conter o cabeçalho `X-CSRF-Token` associado criptograficamente à sessão atual.
- **Invalidação**: O servidor purga a sessão no Redis/Keycloak e instrui o navegador a deletar o cookie:
  ```http
  Set-Cookie: auth-token=; Path=/; Domain=.atius.com.br; Max-Age=0; HttpOnly; Secure; SameSite=Lax
  ```

---

## 8. Invariante Dual-Domain RFC 6265 (.com.br vs .io)

A frota ATIUS opera os domínios `atius.com.br` (produção primária) e `atius.io` (espelho de paridade internacional). No entanto, o padrão de isolamento de cookies da web (RFC 6265) impõe restrições incontornáveis:

1. **Isolamento de TLD**: Um cookie configurado com `Domain=.atius.com.br` jamais é enviado por nenhum navegador moderno para um host sob `.atius.io`.
2. **Implicação Arquitetural**: O conceito "logou em um, logou em tudo" é nativo **somente** dentro do mesmo TLD (`*.atius.com.br`).
3. **Requisitos de Paridade para `.atius.io`**:
   - Os backends Fastify/Node.js devem registrar explicitamente ambos os domínios em `allowedOrigins` para CORS.
   - O Apache Ingress no `atius-srv-1` deve manter blocos de `VirtualHost` perfeitamente espelhados para ambos os domínios com certificados TLS válidos.
   - Os Edge Gateways (:8210 e :8088) resolvem sessões de forma isolada e segura em cada TLD.

---

## 9. Governança do Canonical Landscape Standalone (Exceção Homologada)

O **Canonical Landscape** é o sistema central de gerenciamento de pacotes, monitoramento e execução de scripts na frota de servidores Linux. Por decisão arquitetural deliberada, ele opera como **Padrão 5 (Standalone)**.

### 9.1 Justificativa de Isolamento
- **Monolito Zope/TwistedWeb**: O Landscape Server é baseado em um runtime Python legado executado em container LXC isolado no nó `atius-srv-3` (`10.65.172.253`).
- **Incompatibilidade de Header-Auth**: Modificações no fluxo de autenticação do Landscape quebrem a comunicação nativa do protocolo cliente-servidor do `landscape-client`.
- **Independência Operacional Soberana**: Em caso de falha total do SSO central (ATS/Keycloak), o administrador precisa continuar apto a disparar comandos e scripts via Landscape para restabelecer os serviços.

### 9.2 Reescrita Transparente no Apache Ingress
O nó `atius-srv-1` intercepta acessos web públicos ao Landscape e executa reescrita limpa:
```apache
# Ingress Apache atius-srv-1 para Landscape
RewriteEngine On
RewriteCond %{REQUEST_URI} ^/login/?$
RewriteRule ^/login/?$ /+login?next_url=%2Faccount%2Fstandalone%2Fsecrets [R=302,L]
```
O tráfego de comunicação de clientes (`http://landscape.atius.com.br/ping`) trafega em HTTP puro conforme exigido pelo protocolo do agente.

### 9.3 Injeção de Tema Dark
O container LXC no SRV-3 possui personalização de estilo injetada em:
`/opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt`
com o bloco `<style id="atius-classic-dark">`, corrigindo anomalias de texto branco sobre fundo branco em modais e formulários.

---

## 10. Procedimentos de Emergência / Break-Glass

Na eventualidade de colapso ou indisponibilidade do sistema de autenticação central, as operações da frota são mantidas através de 4 vetores de emergência:

1. **Landscape CLI Soberano**:
   - Disparo direto de comandos e scripts em todos os nós da frota sem depender de interfaces web:
     ```bash
     omni landscape run <script-id> --hosts all --wait --yes
     ```
2. **OpenSSH Nativo Direto (Portas Canônicas)**:
   - Se o túnel WireGuard ou o gateway `ssh.atius.com.br` falharem, utilizar as rotas públicas OpenSSH diretas:
     - Windows 11 Host: `ssh -p 8122 muniz@ssh-giovanni-w11-pc.atius.com.br`
     - WSL Ubuntu: `ssh -p 8222 muniz@ssh-giovanni-wsl-pc.atius.com.br`
     - S23 Termux: `ssh -p 8322 termux@ssh-giovanni-s23.atius.com.br`
     - Horistic Server: `ssh -p 22 horistic@ssh-horistic-srv.atius.com.br`
3. **OCI Serial Console**:
   - Para instâncias Oracle Cloud inacessíveis via rede IP, conectar via console serial nativo através do CLI `oci-admin` ou painel OCI.
4. **Cofre de Credenciais de Emergência**:
   - Credenciais de contingência administrativa residem no cofre HashiCorp Vault no caminho `kv/atius/breakglass/emergency-creds`.

---

## 11. Referências Cruzadas & Mapeamento de Conhecimento

Esta governança é mantida de forma sincronizada entre os pilares de documentação da ATIUS:

### 11.1 Obsidian Vault (`AiSecondBrain/Operations/Autenticacao-e-SSO/`)
- `00-INDEX-Autenticacao-e-SSO.md`: Índice geral e taxonomia de autenticação.
- `Diretriz-Canonica-Telas-de-Login-e-SSO.md`: Especificação geométrica, visual e de segurança.
- `Matriz-Sistemas-Login-Frota-Atius.md`: Matriz completa dos 29 endpoints da frota.
- `Arquitetura-Dual-Domain-Cookies-e-CORS.md`: Regras de isolamento RFC 6265 e CORS.
- `Excecoes-Arquiteturais-Landscape-e-Breakglass.md`: Governança do Landscape e protocolos de emergência.

### 11.2 Memória Operacional GBrain
- **Fato #765**: Os 5 padrões arquiteturais de autenticação da frota ATIUS.
- **Fato #766**: Canonical Landscape Standalone (Zope LXC SRV-3, Ingress /login, CSS dark, Vault AppRole).
- **Fato #767**: Padrão visual UI/UX de telas de login (card 448x454.25 px, logo 44x44 px, URL limpa, Destino seguro host-only).
- **Fato #768**: Invariante RFC 6265 Dual-Domain (.com.br vs .io).
- **Fato #769**: Logout seguro POST-only com CSRF e Origin allowlist.
- **Fato #770**: Gateways perimetrais Edge Gateway :8210, Casa Remote :8088/:8196 e App-Local Facade.
- **Timeline #300** na página mãe: `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`.

### 11.3 Skills Canônicas
- `atius-fleet-login-and-sso`: Governança e diretrizes de login da frota.
- `atius-sso`: Integração, montagem e validação de ciclo de vida SSO.
- `atius-dual-domain`: Operação de paridade dual-domain `.com.br` e `.io`.
- `atius-sso-governed-release-closeout`: Promoção governada de releases e auditoria.
