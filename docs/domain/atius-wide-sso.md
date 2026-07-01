# Atius-wide SSO em `sso.atius.com.br`

## Objetivo

Publicar `https://sso.atius.com.br` como host canonico de login/logout do ATS sem vazar segredo, sem abrir redirect arbitrario e sem perder rollback de Apache/DNS/Cloudflare/Keycloak.

O fluxo primario do SSO usa as credenciais do banco ATS: a tela `sso.atius.com.br/login` chama `/v1/token/generate`, recebe o cookie `auth-token` em `.atius.com.br` e redireciona para o `return_to` permitido. Keycloak/OIDC fica disponivel apenas para rotas auxiliares e rollback controlado, nao como caminho visual padrao para `remote.atius.com.br/mt5/*`.

## Escopo desta fase

- Preparar o vhost Apache `sso.atius.com.br` para a facade SSO do ATS em `ATIUS-SRV-1:3015`.
- Tornar explícito o contrato `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-Port` e `X-Forwarded-For` para:
  - `trade.atius.com.br`
  - `painel.atius.com.br`
  - `dashboard.atius.com.br`
  - `backtest.atius.com.br`
  - `strategy.atius.com.br`
  - `admin.atius.com.br`
- Incluir `remote.atius.com.br/mt5/*` no mesmo SSO usando o cookie `auth-token` e verificação server-side em `/v1/auth/me`.
- Inventariar e assertar o cliente Keycloak `sso.atius.com.br` sem imprimir client secret, mantendo OIDC como fallback/integração opcional.
- Definir gate manual para publicação Cloudflare/DNS/TLS, enable/reload do Apache e smoke live do ATS.

## Artefatos e scripts

- `scripts/sso-edge-smoke.sh`
  - `--dry-run --assert-status --assert-headers`: checklist de publicação sem mutação live.
  - `--local --assert-status --assert-headers --assert-app-hosts trade.atius.com.br,...`: smoke local quando o vhost `sso` já estiver enabled/reloaded por gate humano.
- `scripts/keycloak-sso-client-check.sh`
  - `inventory`: inventário real via `kcadm.sh` quando autenticado; fallback para checklist do dashboard quando não autenticado.
  - `render-apply-plan`: payload exato sem segredo para create/update do cliente.
  - `assert`: exige `kcadm.sh` autenticado e falha fechado se não houver acesso admin aprovado.
- `scripts/sso-secret-hygiene-scan.sh`
  - Escaneia os artefatos da fase e o worklog Obsidian.
- `modules/mt5-remote-auth/`
  - Proxy local fail-closed para proteger `remote.atius.com.br/mt5/<id>` via SSO antes de liberar assets noVNC/WebSocket.

## Contrato Apache

### `sso.atius.com.br`

- Host canônico: `https://sso.atius.com.br`
- Backend alvo: `http://ATIUS-SRV-1:3015`
- Headers obrigatórios:
  - `ProxyPreserveHost On`
  - `RequestHeader set X-Forwarded-Host "sso.atius.com.br"`
  - `RequestHeader set X-Forwarded-Proto "https"`
  - `RequestHeader set X-Forwarded-Port "443"`
  - `RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s`

### Hosts ATS protegidos

Todos os seis hosts acima devem sobrescrever explicitamente:

```apache
RequestHeader set X-Forwarded-Host "<host-exato>"
RequestHeader set X-Forwarded-Proto "https"
RequestHeader set X-Forwarded-Port "443"
RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s
```

Não usar `setifempty` para esses campos.

### `remote.atius.com.br/mt5/*`

- Host publico: `https://remote.atius.com.br`
- Gate local: `http://127.0.0.1:8095`
- Verificador de sessao: `http://127.0.0.1:8015/v1/auth/me`
- Cookie exigido: `auth-token`
- Permissao inicial: `can_access_trade`; `is_admin` tambem passa
- Primeira rota: `/mt5/1 -> http://10.1.1.3:6081`
- Rotas futuras: adicionar novo id em `/etc/atius/mt5-remote-auth-proxy.json`; nao criar novo Basic Auth no Apache
- O proxy nao repassa `Cookie` nem `Authorization` ao container MT5/noVNC
- `/login` em `remote.atius.com.br` deve redirecionar para `https://sso.atius.com.br/login?return_to=https://remote.atius.com.br/mt5/1/`

## Contrato de login ATS SSO

- Host: `https://sso.atius.com.br/login`
- Entrada: `return_to` com allowlist em `frontend/src/lib/sso/redirects.ts`
- URL publica: qualquer entrada `https://sso.atius.com.br/login?return_to=...` deve redirecionar imediatamente para `https://sso.atius.com.br/login`, sem query visivel na barra.
- Preservacao do destino: o `return_to` normalizado e permitido fica somente no cookie httpOnly `atius_sso_login_return_to`, `Secure`, `SameSite=Lax`, `Max-Age=600`, e e reinjetado apenas no rewrite interno `/login -> /sso/login`.
- Autenticacao primaria: `POST /v1/token/generate`
- Credenciais aceitas: `email` ou `username` da tabela ATS `"user"` + senha ATS
- Cookie emitido: `auth-token` com dominio `.atius.com.br` em producao
- Sessao emitida: JWT/cookie `auth-token` com validade de 1 hora (`expiresIn=3600`, `Max-Age=3600`)
- Renovacao ativa: a aba aberta e visivel renova via `POST /v1/auth/refresh` a cada 5 minutos quando a sessao entra na janela de 15 minutos antes de expirar e houve atividade recente na aba.
- Sessao ociosa: se a aba nao estiver visivel ou sem atividade recente, nao ha silent refresh; ao expirar, `/v1/auth/me` retorna 401 e a sessao deve desconectar.
- Pos-login: redirecionar para o `return_to` normalizado; para `/mt5/1`, `https://remote.atius.com.br/mt5/1/`
- CORS do `atius-api` deve permitir `Origin: https://sso.atius.com.br`; se faltar, o login falha como `Internal Server Error` antes de validar senha.
- O middleware do host `sso.atius.com.br` deve preservar a query string ao fazer `/login -> /sso/login`; sem isso, a tela cai no destino default `trade.atius.com.br/`
- A rota `/api/sso/login` ainda inicia OIDC/Keycloak, mas nao deve ser o botao primario do shell SSO enquanto o contrato exigir credenciais do banco ATS.

## Contrato Keycloak

Estado atual: opcional/fallback. Nao usar como fluxo principal de login do `remote.atius.com.br/mt5/*` enquanto o requisito for autenticar usuarios ATS do banco.

- Realm: `atius`
- Client ID: `sso.atius.com.br`
- Protocol: `openid-connect`
- Redirect URI: `https://sso.atius.com.br/api/sso/callback`
- Web origin: `https://sso.atius.com.br`
- Valid post logout redirect URI: `https://sso.atius.com.br/login?logout=complete`
- Sem wildcard em `webOrigins`
- Default: client type `confidential`
- Exceção: `public` só com decisão explícita do operador e justificativa do fluxo
- Se `confidential`: armazenar apenas em `/etc/keycloak/sso.atius.com.br-client.env`, fora do Git.
- No runtime PM2 atual, o arquivo fica `root:ubuntu` e `0640` para permitir leitura por `atius-web` e `atius-api` sem colocar secret em repo, `.planning/`, Obsidian, shell history ou logs.
- Nunca imprimir, fazer diff ou copiar o valor do secret para Git, `.planning/`, Obsidian, shell history ou logs

### Referência operacional

- `kcadm.sh get clients -r atius -q clientId=sso.atius.com.br`
- Em Keycloak 26.x, `Valid Post Logout Redirect URIs` fica em `attributes["post.logout.redirect.uris"]`
- Em logout RP-initiated, `post_logout_redirect_uri` exige `client_id` ou `id_token_hint`

## Env OIDC opcional no ATS

- `SSO_OIDC_ISSUER=https://auth.atius.com.br/realms/atius`
- `SSO_OIDC_DISCOVERY_URL=http://127.0.0.1:8180/realms/atius/.well-known/openid-configuration`
- `SSO_OIDC_CLIENT_ID=sso.atius.com.br`
- `SSO_OIDC_CLIENT_SECRET_FILE=/etc/keycloak/sso.atius.com.br-client.env` quando confidential
- `SSO_OIDC_REDIRECT_URI=https://sso.atius.com.br/api/sso/callback`
- `SSO_OIDC_POST_LOGOUT_REDIRECT_URI=https://sso.atius.com.br/login?logout=complete`

`SSO_OIDC_DISCOVERY_URL` usa loopback para evitar que `atius-web`/`atius-api` dependam do retorno via Cloudflare no proprio SRV-1. O documento discovery ainda anuncia issuer e endpoints publicos `https://auth.atius.com.br/...`.

Para habilitar handoff de logout para Keycloak, defina explicitamente `SSO_OIDC_LOGOUT_ENABLED=true`. Sem essa flag, logout limpa o cookie ATS e volta para `https://sso.atius.com.br/login?logout=complete`.

## Cookie e logout global

- O bridge ATS continua emitindo só `auth-token`
- `auth-token` deve ser temporario, nao infinito: validade de 1 hora e renovacao condicionada a aba ativa/visivel com atividade recente.
- O logout global deve:
  - limpar `auth-token` com domínio `.atius.com.br`
  - limpar `auth-token` sem domínio explícito
  - voltar para `https://sso.atius.com.br/login?logout=complete`
  - redirecionar para o end-session endpoint do Keycloak somente se `SSO_OIDC_LOGOUT_ENABLED=true`
  - não entrar em loop de auto-login

## Sequência obrigatória de publicação

1. Capturar before-state de Cloudflare:
   - DNS de `sso.atius.com.br`
   - proxy on/off
   - modo TLS aplicável
   - estado atual dos seis hosts ATS relacionados
2. Confirmar backups Apache existentes:
   - `~/.backups/phase42-apache-20260628T084851Z`
3. Rodar:
   - `apache2ctl configtest`
   - `bash scripts/sso-edge-smoke.sh --dry-run --assert-status --assert-headers`
   - `bash scripts/keycloak-sso-client-check.sh inventory --realm atius --client-id sso.atius.com.br`
   - `bash scripts/keycloak-sso-client-check.sh assert --realm atius --client-id sso.atius.com.br --redirect-uri https://sso.atius.com.br/api/sso/callback --web-origin https://sso.atius.com.br --post-logout-redirect-uri 'https://sso.atius.com.br/login?logout=complete'`
   - `bash scripts/sso-secret-hygiene-scan.sh`
4. Confirmar gate humano:
   - tipo de client no Keycloak
   - before-state Cloudflare/DNS/TLS
   - comandos de rollback Apache
   - disponibilidade de env live `SSO_TEST_EMAIL` e `SSO_TEST_PASSWORD`
5. Só depois do gate:
   - enable/reload do Apache para ativar `sso.atius.com.br`
   - publicação DNS/proxy/TLS
   - primeiro smoke live de login/logout ATS

## Rollback

- Restaurar os vhosts de app a partir de `~/.backups/phase42-apache-20260628T084851Z`
- Remover o vhost novo se a publicação for abortada:
  - `sudo rm -f /etc/apache2/sites-available/sso.atius.com.br.conf`
- Reverter cada vhost alterado:
  - `sudo cp ~/.backups/phase42-apache-20260628T084851Z/<arquivo>.conf /etc/apache2/sites-available/<arquivo>.conf`
- Depois do gate humano, o rollback operacional inclui disable/reload e reversão do before-state Cloudflare/DNS/TLS

## Evidência permitida

Registrar apenas:

- timestamp
- host alvo
- comando executado
- status pass/block
- caminho de backup/artefato

Nunca registrar:

- client secret
- cookie value
- password
- token
- screenshot com segredo
- shell history com credencial
