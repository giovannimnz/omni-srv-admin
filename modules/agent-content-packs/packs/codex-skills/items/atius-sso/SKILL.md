---
name: atius-sso
description: Diretriz canônica absoluta e manual de engenharia do Atius SSO, estabelecendo o Padrão PM2 (Same-Host App-Local Login Shell) em https://<app>.<dominio>/login como modelo universal obrigatório para 100% dos serviços web da frota ATIUS.
---

<antigravity_adapter>
## Antigravity Tool Mapping (use instead of Codex tools)

| Codex / Claude Code | Antigravity |
|---|---|
| `apply_patch` / `Write` / `Edit` | `write_file` / `edit_file` |
| `exec_command` / `Bash` | `run_command` (runs Bash/sh on Linux) |
| `rg` / `grep` / `Glob` / `list_files` | `run_command` (grep, find) / `read_file` |
| `Read` / `read_file` | `read_file` |
| `spawn_agent` / `Task()` / `Agent()` | `invoke_subagent` / `browser` |
| `request_user_input` / `AskUserQuestion` | `ask_question` (prefer direct text) |
| `web_search` | `search_web` |

Paths on this host are Linux paths (`/home/ubuntu/...`).
</antigravity_adapter>

# Atius SSO — Diretriz Canônica Absoluta: O Modelo PM2 (Same-Host App-Local Login Shell)

> **Status Normativo**: **ABSOLUTO, CANÔNICO & MANDATÓRIO**  
> **Autoridade**: Equipe de Arquitetura & Governança da Frota ATIUS  
> **Referência Visual e Operacional Padrão-Ouro**: `https://pm2.atius.io/login` e `https://pm2.atius.com.br/login`

Esta skill estabelece a diretriz arquitetural definitiva para autenticação, telas de login e ciclo de vida do **Atius SSO**.  
O modelo de redirecionamento para telas centrais externas (`https://sso.atius.com.br/login?return_to=...`, `https://sso.atius.io/login` ou `https://auth.atius.com.br/realms/...`) está **terminantemente depreciado e proibido** para os fluxos interativos de aplicação da frota.

O padrão universal mandatório é o **Modelo PM2 (Same-Host App-Local Login Shell)**.

---

## 1. Princípio Fundamental: O Modelo PM2

Quando qualquer usuário não autenticado tenta acessar qualquer aplicação ou console da frota (ex: `https://<app>.atius.io` ou `https://<app>.atius.com.br`), o sistema deve:

1. **Permanecer no Host da Própria Aplicação (Zero Domain Switching):**
   - A barra de endereços do navegador deve exibir estritamente:
     ```
     https://<app>.atius.io/login        (para nós .io)
     https://<app>.atius.com.br/login    (para nós .com.br)
     ```
   - É **proibido** redirecionar o navegador para `https://sso.atius.com.br/login`, `https://sso.atius.io/login` ou URLs OIDC externas durante o fluxo normal de login.
2. **Zero Query Leak (URLs Limpas):**
   - É **proibido** expor parâmetros de redirecionamento ou credenciais na URL visível (sem `?return_to=...`, sem `?client_id=...`, sem `?redirect_uri=...`).
   - O destino pretendido é mantido exclusivamente via cookie transitório host-only (`atius_sso_login_return_to`) ou sessão interna do gateway.
3. **Shell Canônico Idêntico e Unificado:**
   - A tela servida em `https://<app>.<dominio>/login` é renderizada localmente (via Edge Gateway, Apache Rewrite, Next.js Middleware ou Facade) utilizando rigorosamente o shell HTML/CSS padronizado do PM2 (`renderCanonicalLoginShell`).
   - O campo **DESTINO SEGURO** exibe com ícone de escudo (`shield`) exatamente o hostname puro da aplicação acessada (ex: `pm2.atius.io`, `gitlab.atius.io`, `painel.atius.com.br`, `grafana.atius.io`).
   - Não há barras azuis (como a do PatternFly do Keycloak), nem elementos visuais destoantes.

---

## 2. Contrato Visual e Estrutural do Shell de Login (Padrão PM2)

A geometria e estilização do shell de login seguem com fidelidade absoluta a implementação do Edge Gateway (`atius-admin-edge-gateway.js`):

### 2.1 Especificações Métricas & Geometria
- **Card Central**: Largura máxima `448px` (`width: min(448px, 100%)`). Cantos arredondados com `border-radius: 12px`.
- **Fundo do Card**: `#171b22` / `rgba(17,24,39,.35)` com borda sutil `border: 1px solid rgba(55,65,81,.3)`.
- **Fundo da Página**: `#18191b` com gradiente suave (`linear-gradient(135deg, #1a1a1a 0%, #1f1f1f 50%, #1a1a1a 100%)`).
- **Logotipo Oficial**: Atius Mark SVG oficial (triângulo gradiente ouro/verde ou estilizado canônico) com 44px de largura e subtítulo discreto `Atius SSO` em 11px (`color: #9ca3af`).
- **Box "DESTINO SEGURO"**:
  - Background: `rgba(31,41,55,.4)` / `#1b222c`, borda `1px solid rgba(55,65,81,.4)`.
  - Label superior: `DESTINO SEGURO` em caixa alta, tamanho `11px`, peso normal, cor `#9ca3af`.
  - Linha de destino: Ícone de escudo SVG com check na cor laranja Atius (`#f97316` / `#ff7112`), seguido do hostname puro (ex: `pm2.atius.io` ou `gitlab.atius.io`) em `14px`, cor `#e5e7eb`.
- **Campos de Formulário (Inputs 44px)**:
  - Input "Email ou username": Ícone 👤 à esquerda (`icon-left`), altura 44px, placeholder `"Digite seu email ou username"`, fundo `#1f2937` / `#1a1d24`, borda `#4b5563`, texto `#ffffff`.
  - Input "Senha": Ícone 🔒 à esquerda, altura 44px, placeholder `"Digite sua senha"`, botão de olho 👁 à direita (`icon-right`) com funcionalidade nativa de toggle de visualização da senha (type="password" <-> type="text").
  - Foco: Contorno em laranja Atius (`border-color: #f97316; box-shadow: 0 0 0 1px rgba(249,115,22,.2)`).
- **Botão de Ação Primário**:
  - Altura 44px, cantos arredondados 10px, fundo laranja institucional Atius (`#f97316` / `#ff7112`), texto branco `#ffffff` em negrito (`font-weight: 500`/`600`), largura 100% (`width: 100%`).
  - Label: `"Entrar com Atius SSO"`.
  - Hover: `#ea580c` / `#e0600a`.

### 2.2 Template HTML/CSS de Referência Absoluta
O template canônico em JavaScript/Node.js que gera esta interface está consolidado em:
`/home/ubuntu/GitHub/omni-srv-admin/modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js` nas funções `renderCanonicalLoginShell` e `CANONICAL_LOGIN_CSS`.

---

## 3. Fluxo de Autenticação e Sessão Same-Host

```
[ Usuário Navega para https://<app>.<dominio>/ ]
                       │
                       ▼
        [ Possui cookie auth-token válido? ]
               ├── SIM ──► Serve a aplicação normalmente
               └── NÃO
                       │
                       ▼
        [ HTTP 302 / 307 Interno ]
        Navegador permanece em: https://<app>.<dominio>/login
        Renderiza: Shell Canônico Atius SSO (Destino Seguro: <app>.<dominio>)
                       │
                       ▼
        [ Usuário digita credenciais e clica "Entrar com Atius SSO" ]
        POST https://<app>.<dominio>/login (Action local)
                       │
                       ▼
        [ Gateway / Facade / Middleware local intercepta ]
        Valida credenciais contra API Central:
        POST http://127.0.0.1:8015/v1/token/generate (ou OIDC Backend)
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
[ Credenciais Inválidas ]   [ Autenticação Sucesso ]
Renderiza /login com erro    Injeta Set-Cookie: auth-token=<jwt>
"Não foi possível entrar.    - .atius.com.br (Domain=.atius.com.br)
 Verifique as credenciais."  - .atius.io (Domain=<hostname> ou .atius.io)
                             HTTP 302 Redirect para https://<app>.<dominio>/
```

---

## 4. Matriz Canônica de Migração dos 29 Sistemas da Frota para o Modelo PM2

| # | Sistema / Endpoint Web | Host / Nó | Padrão Atual | Padrão Alvo Canônico (Modelo PM2) | Ação de Migração para Modelo PM2 |
|---|---|---|:---:|:---:|---|
| **01** | `sso.atius.com.br`<br>`sso.atius.io` | `atius-srv-1` | Central Host | **Modelo PM2 (Raiz)** | Padrão nativo do SSO central. Opera como validador de sessão (`/v1/auth/me`) e emissor de tokens (`/v1/token/generate`). |
| **02** | `trade.atius.com.br`<br>`trade.atius.io` | `atius-srv-1` | Redireciona sso | **`https://trade.atius.com.br/login`** | Ingress Apache / Next.js middleware atende `/login` localmente renderizando o shell PM2 com Destino Seguro `trade.atius.com.br`. |
| **03** | `painel.atius.com.br`<br>`painel.atius.io` | `atius-srv-1` | Redireciona sso | **`https://painel.atius.com.br/login`** | Migrar de HTTP 307 para sso.atius.com.br para servir o shell PM2 diretamente na rota limpa `/login` do próprio painel. |
| **04** | `dashboard.atius.com.br`<br>`dashboard.atius.io` | `atius-srv-1` | Redireciona sso | **`https://dashboard.atius.com.br/login`** | Ingress atende `/login` local com Destino Seguro `dashboard.atius.com.br`. |
| **05** | `backtest.atius.com.br`<br>`backtest.atius.io` | `atius-srv-1` | Redireciona sso | **`https://backtest.atius.com.br/login`** | Ingress atende `/login` local com Destino Seguro `backtest.atius.com.br`. |
| **06** | `strategy.atius.com.br`<br>`strategy.atius.io` | `atius-srv-1` | Redireciona sso | **`https://strategy.atius.com.br/login`** | Ingress atende `/login` local com Destino Seguro `strategy.atius.com.br`. |
| **07** | `admin.atius.com.br`<br>`admin.atius.io` | `atius-srv-1` | Redireciona sso | **`https://admin.atius.com.br/login`** | Ingress atende `/login` local com Destino Seguro `admin.atius.com.br`. |
| **08** | `talk.atius.com.br`<br>`talk.atius.io` | `atius-srv-1` | Apache Facade | **`https://talk.atius.com.br/login`** | Apache Ingress renderiza shell PM2 com Destino Seguro `talk.atius.com.br` e valida sessão antes de repassar para Nextcloud upstream :3101. |
| **09** | `admin.talk.atius.com.br`<br>`admin.talk.atius.io` | `atius-srv-1` | Apache Facade | **`https://admin.talk.atius.com.br/login`** | Apache Ingress renderiza shell PM2 com Destino Seguro `admin.talk.atius.com.br`. |
| **10** | `remote.atius.com.br`<br>`remote.atius.io` | `atius-srv-1` | SSO Proxy :8095 | **`https://remote.atius.com.br/login`** | SSO Proxy :8095 renderiza shell PM2 same-host antes de abrir o túnel WebSocket/noVNC para o MetaTrader 5. |
| **11** | `oci.atius.com.br`<br>`oci.atius.io` | `atius-srv-1` | Apache Ingress | **`https://oci.atius.com.br/login`** | Ingress renderiza shell PM2 com Destino Seguro `oci.atius.com.br` e valida antes de encaminhar para OCI Admin DRG `10.13.1.13:8080`. |
| **12** | `auth.atius.com.br` | `atius-srv-1` | Keycloak Standalone | **Keycloak Tema PM2** | Remover barra azul PatternFly (`.pf-v5-c-login__main::before`) e alinhar ícones dos inputs com o padrão PM2. |
| **13** | `grafana.atius.com.br`<br>`grafana.atius.io` | `atius-srv-1` / `srv-3` | Edge Gateway :8210 | **`https://grafana.atius.io/login`** | **100% no Modelo PM2**. Gateway :8210 já renderiza o shell canônico e injeta Basic Auth upstream. |
| **14** | `portainer.atius.com.br`<br>`portainer.atius.io` | `atius-srv-1` / `srv-2` | Edge Gateway :8210 | **`https://portainer.atius.io/login`** | **100% no Modelo PM2**. Gateway :8210 renderiza shell canônico e injeta Portainer JWT upstream. |
| **15** | `docker.atius.com.br`<br>`docker.atius.io` | `atius-srv-1` / `srv-2` | Edge Gateway :8210 | **`https://docker.atius.io/login`** | **100% no Modelo PM2**. Alias direto de Portainer. |
| **16** | `pm2.atius.com.br`<br>`pm2.atius.io` | `atius-srv-1` | Edge Gateway :8210 | **`https://pm2.atius.io/login`** | **PADRÃO-OURO DE REFERÊNCIA (100% IMPLEMENTADO)**. Destino seguro dinâmico, sem troca de domínio, inputs estilizados e zero query leak. |
| **17** | `paseo.atius.com.br`<br>`paseo.atius.io` | `atius-srv-1` | Edge Gateway :8210 | **`https://paseo.atius.io/login`** | **100% no Modelo PM2**. Shell canônico integrado com allowlist de emails. |
| **18** | `ssh.atius.com.br`<br>`ssh.atius.io` | `atius-srv-1` | Casa Remote :8088 | **`https://ssh.atius.com.br/login`** | Casa Remote Auth Gateway atende `/login` com shell PM2 antes de emitir ticket efêmero para ttyd web shell. |
| **19** | `rdp.atius.com.br` | `atius-srv-1` / `W11` | Casa Remote :8196 | **`https://rdp.atius.com.br/login`** | Casa Remote Auth Gateway atende `/login` com shell PM2 antes de abrir túnel RustGuac/RDP para o Windows 11. |
| **20** | `vpn.atius.com.br` | `atius-srv-1` | Next.js Facade | **`https://vpn.atius.com.br/login`** | Portal VPN renderiza shell PM2 localmente e limpa cookies residuais. |
| **21** | `adguard.atius.com.br` | `atius-srv-1` | Node Gateway | **`https://adguard.atius.com.br/login`** | Portal AdGuard renderiza shell PM2 localmente antes de repassar chamadas para AdGuard Home. |
| **22** | `landscape.atius.com.br`<br>`landscape.atius.io` | `atius-srv-1` / `srv-3` | Standalone Exceção | **`https://landscape.atius.com.br/login`** | Ingress Apache no SRV-1 intercepta acessos anônimos e reescreve `/login` com CSS dark adaptado (autenticação local Zope preservada). |
| **23** | `vault.atius.com.br` | `atius-srv-1` / `srv-3` | Vaultwarden Nativo | **Standalone Exceção Segura** | Mantém autenticação com Master Password e criptografia Zero-Knowledge (proibido SSO por requisito de segurança criptográfica). |
| **24** | `cockpit.atius.com.br`<br>`cockpit.atius.io` | `atius-srv-1` | PAM Linux Nativo | **Standalone Exceção SO** | Mantém autenticação PAM do Kernel Linux para delegação sudo. |
| **25** | `casa.atius.com.br` | `atius-srv-1` / `BE3` | Firmware Iframe | **Standalone Exceção IoT** | Wrapper HTML institucional envelopando o roteador doméstico. |
| **26** | `plane.atius.io` | `atius-srv-1` | Plane Auth Nativa | **Alvo: Modelo PM2 via Edge Gateway** | Rota para migração: colocar Plane atrás do Edge Gateway :8210 ou Ingress com shell PM2. |
| **27** | `router.atius.com.br` | `atius-srv-1` | Router AI Nativo | **Alvo: Modelo PM2 via Ingress** | Integrar validação Atius SSO no middleware Go ou Apache Ingress com shell PM2. |
| **28** | `mcp.atius.com.br`<br>`mcp.atius.io` | `atius-srv-1` | Bearer Token API | **API Sem UI** | Endpoints de integração com agentes de IA (FastMCP). Autenticação estática via Vault Bearer Token. |
| **29** | `gitlab.atius.com.br`<br>`gitlab.atius.io` | `atius-srv-4` | OIDC Keycloak | **`https://gitlab.atius.io/login` (Modelo PM2)** | **PLANO DE TRANSIÇÃO DO GITLAB**: Substituir o redirecionamento externo para o Keycloak por fachada local em `gitlab.atius.io/login` que autentica contra o Keycloak/Atius SSO nos bastidores e completa o callback OIDC de forma transparente! |

---

## 5. Plano Detalhado de Transição do GitLab (`gitlab.atius.io` / `gitlab.atius.com.br`)

O caso de uso trazido pelo usuário ilustra a necessidade de eliminar a transição visual desarmônica no GitLab:

1. **Como está hoje (Imagens 1 e 2):**
   - Acesso a `https://gitlab.atius.io` -> redireciona para `https://gitlab.atius.io/users/sign_in`.
   - Usuário clica em "Atius SSO" -> redireciona externamente para `https://auth.atius.com.br/realms/atius/protocol/openid-connect/auth?...`.
   - Tela do Keycloak exibe barra azul no topo do card, inputs sem ícones e URL quilométrica.
2. **Como deve ser no Modelo PM2 (Imagens 3 e 4):**
   - Acesso a `https://gitlab.atius.io` sem sessão -> encaminhado para `https://gitlab.atius.io/login` (ou `/users/sign_in` estilizada).
   - A tela renderizada é o **Shell Canônico PM2**:
     - Sem barra azul!
     - Logo oficial Atius SSO.
     - **DESTINO SEGURO: `gitlab.atius.io`** com ícone de escudo laranja.
     - Inputs dark com ícone 👤 de usuário e 🔒/👁 de senha.
     - Botão primário laranja: `"Entrar com Atius SSO"`.
   - O submit do form realiza a autenticação direta, obtém os tokens de claims OIDC e entrega o usuário autenticado na dashboard do GitLab em `https://gitlab.atius.io/`.
   - A URL no navegador NUNCA exibe `auth.atius.com.br` para o operador humano.

---

## 6. Checklist de Qualidade e Conformidade para Qualquer Integração SSO

Toda nova implementação, ajuste ou migração deve validar os seguintes pontos antes de ser considerada concluída:

- [ ] **Mesmo Host na Barra de Endereços**: O navegador nunca sai de `https://<app>.<dominio>/login`.
- [ ] **Zero Redirecionamentos Externos**: Não há 302/307 visível para `sso.atius.com.br` ou `sso.atius.io`.
- [ ] **Zero Query Leak**: A URL `/login` não possui parâmetros de query expostos.
- [ ] **Destino Seguro Fiel**: Exibe estritamente o `URL.hostname` puro (ex: `pm2.atius.io`, `gitlab.atius.io`), com ícone de escudo laranja.
- [ ] **Campos com Ícones e Toggle**: Input de usuário com ícone 👤 e input de senha com ícone 🔒 e botão 👁 funcional.
- [ ] **Sem Barra Azul**: O card de login não possui borda ou barra azul no topo.
- [ ] **Botão Laranja Institucional**: Botão com fundo `#f97316` / `#ff7112` e texto `"Entrar com Atius SSO"`.
- [ ] **Dual-Domain Parity**: Comportamento idêntico em domínios `.com.br` e `.io`.
- [ ] **Encerramento de Sessão Seguro**: Logout exclusivo via `POST` com CSRF e Origin validados.
