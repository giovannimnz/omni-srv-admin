# Atius SSO host-local lifecycle recovery

Status: live e revalidado em 2026-07-30 após correção funcional, paridade visual, logout real e proteção contra rate limit.

## Escopo

| Site | Serviço/gateway | Contrato humano final |
|---|---|---|
| `grafana.atius.com.br` | `atius-admin-edge-gateway.service` | `/` → `/login`; login → app; logout → `/login` |
| `portainer.atius.com.br` | `atius-admin-edge-gateway.service` | `/` → `/login`; login → app; logout → `/login` |
| `docker.atius.com.br` | `atius-admin-edge-gateway.service` | `/` → `/login`; login → app; logout → `/login` |
| `vpn.atius.com.br` | `vpn-frontend.service` | `/` → `/login`; login → app; logout → `/login` |
| `adguard.atius.com.br` | `adguard-portal-gateway.service` | browser `/` → `/login`; login → app; logout → `/login` |

## Contrato obrigatório

- O hostname visível continua `https://<site>.atius.com.br`.
- O caminho humano canônico é `/login`.
- O control plane `https://sso.atius.com.br` não aparece no fluxo humano dos apps.
- Logout de cada site termina em `https://<site>.atius.com.br/login`.
- O `auth-token` é emitido após login e removido após logout.
- A tela app-local `/login` segue o modelo visual `ssh.atius.com.br/login`: fundo escuro, card central, logo Atius, texto `Atius SSO`, bloco `DESTINO SEGURO`, campos `Email ou username`/`Senha` e botão `Entrar com Atius SSO`.

## Causa da regressão

1. A VPN usava redirects públicos para o control plane central em vez de uma facade app-local.
2. O layout do frontend VPN envolvia `/login` com `AuthGuard`, criando loop/limpeza indevida de sessão.
3. O logout do AdGuard dependia de metadados opcionais (`Origin`/`Referer`/`Sec-Fetch-Site`) que podem ser omitidos pelo caminho Cloudflare/Apache/headless, mesmo com CSRF one-shot correto.
4. A validação anterior cobria login/redirect parcial, não dois ciclos completos com logout e relogin.
5. A revalidação visual estrita encontrou drift de UI: admin-edge e AdGuard usavam template compacto sem logo; VPN apontava para asset inexistente `/mono-atius-horizontal.svg`.
6. O ATS API aplica rate limit global de `100/min`; validações `/v1/auth/me` por asset esgotavam o budget e faziam novos logins receberem `429`, apresentado incorretamente como credencial inválida.
7. O harness antigo navegava diretamente para `/logout` e aceitava UI protegida ainda em loading; isso produzia PASS sem provar o controle real de saída nem o app pronto.

## Correções aplicadas

### VPN

- `web/frontend/src/proxy.ts` agora redireciona anônimos para `/login` local.
- `web/frontend/src/app/login/page.tsx` implementa a tela local de login.
- `web/frontend/src/app/api/auth/login/route.ts` autentica server-side contra o backend Atius e emite cookie local.
- `web/frontend/src/app/api/auth/logout/route.ts` limpa a sessão e redireciona para `/login` local.
- `web/frontend/src/app/logout/route.ts` dá caminho humano `/logout` → `/login` sem expor endpoint API.
- `web/frontend/src/components/ProtectedAppShell.tsx` mantém `/login` fora do `AuthGuard`.
- `web/frontend/tests/phase09-sso-contract.mjs` cobre o contrato app-local.

### AdGuard

- `home-proxy/modules/home-router-be3/scripts/adguard-portal-gateway.cjs` mantém POST+CSRF one-shot e aceita ausência de metadados opcionais quando não há evidência estrangeira.
- Origem estrangeira explícita continua falhando fechada.
- `home-proxy/modules/home-router-be3/test/dns-casa/adguard-portal-gateway.test.mjs` cobre o caso real de metadados omitidos.

### Admin edges

- `modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js` permanece como gateway local para Grafana, Portainer e Docker e agora renderiza o template canônico `Atius SSO` compatível com o modelo SSH.
- O gateway aplica cache positivo/coalescing de sessão por `30s` e expõe `Sair do Atius SSO` host-local; o logout vendor do Portainer é redirecionado para `/logout`.
- `modules/atius-admin-edge-sso/scripts/validate-atius-sites-sso-lifecycle.mjs` clica no controle visível e espera marcador de UI pronta específico por site.

### Rate limit e erros de autenticação

- Admin-edge, AdGuard e VPN coalescem validações concorrentes e reutilizam sessão positiva por `30s`.
- `401/403`: credencial ou sessão inválida.
- `429/5xx/timeout`: autenticação temporariamente indisponível; nunca apresentar como senha errada.
- Não aumentar nem desabilitar o rate limit central para mascarar fan-out dos adapters.

### UI parity

- `home-proxy/modules/home-router-be3/scripts/adguard-portal-gateway.cjs` renderiza o mesmo template canônico do admin-edge.
- `web/frontend/src/app/login/page.tsx` usa o asset real `/atius-mark.svg` e removeu a referência quebrada a `/mono-atius-horizontal.svg`.
- `web/frontend/tests/phase09-sso-contract.mjs` aceita `Location: /login` relativo e valida o conteúdo app-local.

## Evidência final

Evidência final pós-rate-limit, UI pronta e logout visível:

`docs/evidence/atius-sso/2026-07-30-rate-limit-real-ui-final/`

Evidência funcional anterior preservada:

`docs/evidence/atius-sso/2026-07-30-host-local-lifecycle-per-site/`

Arquivos principais:

- `combined-report.json`
- `SHA256SUMS`
- `README.md`
- `visual-review/login-parity-contact-sheet.png`
- `visual-review/<site>-contact-sheet.png`
- `<site>/report.json`

Resultado:

| Site | Ciclos | Screenshots | Verdict |
|---|---:|---:|---|
| Grafana | 2 | 8 | PASS |
| Portainer | 2 | 8 | PASS |
| Docker alias | 2 | 8 | PASS |
| VPN | 2 | 8 | PASS |
| AdGuard | 2 | 8 | PASS |

Total: 10 ciclos, 40 screenshots.

## Validação executada

```text
python report parser -> TOTAL cycles=10 screenshots=40
node --test adguard-portal-gateway.test.mjs -> 22/22 PASS
node --test atius-admin-edge-gateway.test.mjs -> 4/4 PASS
node tests/phase09-sso-contract.mjs -> PASS
node tests/phase09-sso-contract.mjs --live -> PASS
npm run typecheck -> PASS
Next build via omni srv1-ops resources run builds -> PASS
sudo apache2ctl configtest -> Syntax OK
systemctl is-active atius-admin-edge-gateway.service adguard-portal-gateway.service vpn-frontend.service apache2.service -> active/active/active/active
vision login parity -> PASS nos cinco sites
```

HTTP browser/document check com `Accept: text/html`:

| Host | Resultado |
|---|---|
| `grafana.atius.com.br/` | `302 https://grafana.atius.com.br/login` |
| `portainer.atius.com.br/` | `302 https://portainer.atius.com.br/login` |
| `docker.atius.com.br/` | `302 https://docker.atius.com.br/login` |
| `vpn.atius.com.br/` | `307 https://vpn.atius.com.br/login` |
| `adguard.atius.com.br/` | `302 https://adguard.atius.com.br/login` |

Observação: bare non-browser `curl /` no AdGuard retorna `401` por fail-closed API behavior. Browser/document request redireciona para `/login` e passou no E2E.

## Backup e rollback

Backup verificado antes do apply:

`/home/ubuntu/backups/atius-sso-recovery-20260730-181233`

Backup adicional antes do patch visual:

`/home/ubuntu/backups/atius-sso-ui-parity-20260730-220117`

Backup antes do logout real/cache de sessão:

`/home/ubuntu/backups/atius-sso-real-ui-logout-20260730-224943`

Ambos têm manifesto `SHA256SUMS` validado.

Rollback rápido:

1. Restaurar arquivos do backup correspondente.
2. Rebuildar VPN frontend se necessário.
3. `sudo systemctl restart vpn-frontend.service adguard-portal-gateway.service atius-admin-edge-gateway.service`
4. `sudo systemctl reload apache2`
5. Rodar o harness por site novamente.

## Operação futura

Use o harness por site quando o host estiver sob carga alta:

```bash
E2E_TARGETS=grafana node modules/atius-admin-edge-sso/scripts/validate-atius-sites-sso-lifecycle.mjs docs/evidence/atius-sso/<run>/grafana-pass
```

Alvos válidos: `grafana`, `portainer`, `docker`, `vpn`, `adguard`.

## Ownership Apache e gate anti-drift

Em 2026-07-31, uma auditoria assíncrona tardia encontrou cópias standalone em
`/etc/apache2/sites-enabled/` diferentes das fontes em
`/etc/apache2/sites-available/`. O runtime estava correto, mas um próximo
`a2ensite`, reprovisionamento ou restore poderia reintroduzir Basic Auth,
upstream direto ou a porta legada `9444`.

Contrato final:

- `sites-available` é a fonte live canônica;
- `sites-enabled` contém symlinks, nunca cópias divergentes;
- os vhosts de Grafana, Portainer e Docker são versionados em
  `modules/atius-admin-edge-sso/configs/apache/`;
- o vhost da VPN é versionado em
  `vpn-atius/web/configs/apache/vpn.atius.com.br.conf`;
- `verify-apache-drift.sh` compara source, `sites-available`, symlink habilitado
  e executa `apache2ctl -t`.

Validação pós-normalização:

```text
5/5 fontes versionadas byte-exact com sites-available
5/5 sites-enabled como symlink
apache2ctl -t -> Syntax OK
Grafana, Portainer, Docker e VPN -> 4/4 sites, 8/8 ciclos, 32 screenshots
revisão visual independente -> 4/4 PASS
```

Evidence complementar:

`docs/evidence/atius-sso/2026-07-31-apache-source-live-reconcile-20260731-221849/`

Rollback: restaurar
`/home/ubuntu/backups/atius-sso-apache-source-live-drift-pre-20260731-221646`,
rodar `apache2ctl -t` e somente então `systemctl reload apache2`.
