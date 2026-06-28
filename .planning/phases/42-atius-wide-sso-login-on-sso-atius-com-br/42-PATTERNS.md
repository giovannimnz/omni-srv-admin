# Phase 42: Atius-wide SSO Login on sso.atius.com.br - Pattern Map

**Mapped:** 2026-06-28
**Files classified:** 17 candidate new/modified files
**Analogs found:** 15 / 17
**Source analogs read:** Phase 42 artifacts, Phase 36 artifacts, ATS auth/session/RBAC/middleware/tests/UI files, and Apache vhost inventory.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `/etc/apache2/sites-available/sso.atius.com.br.conf` | config | request-response | `/etc/apache2/sites-available/auth.atius.com.br.conf` + `/etc/apache2/sites-enabled/painel.atius.com.br.conf` | role-match |
| `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-wide-sso.md` | docs/config | batch | `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/keycloak-freeipa-coexistence.md` | role-match |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts` | utility | transform/request-response | `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/api.js` + `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/login/page.tsx` | partial |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/oidc.ts` | utility | request-response | Phase 36 OIDC docs only | no exact source analog |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/state.ts` | utility | request-response/session | `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/auth/logout/route.ts` | partial |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/sso/login/page.tsx` | component/page | request-response | `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/components/auth/login-form.tsx` + `frontend/src/app/login/page.tsx` | exact visual, divergent auth |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/callback/route.ts` | route | request-response | `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js` + `backend/server/routes/token/index.js` | partial |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/logout/route.ts` | route | request-response/session | `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/auth/logout/route.ts` | exact |
| `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js` | route | request-response/session | same file | exact |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts` | middleware | request-response | same file | exact |
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/contexts/auth-context.tsx` | provider | event-driven/request-response | same file | exact |
| `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/middleware/permissions.js` | middleware | request-response/RBAC | same file | exact |
| `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_redirect_allowlist.test.js` | test | transform/request-response | `backend/server/api.js` redirect helpers + Phase 42 research allowlist matrix | partial |
| `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_oidc_bridge.test.js` | test | request-response/session | `tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` + `test_auth_rbac_api.runtime.test.js` | role-match |
| `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` | test | request-response/runtime | same file | exact, must be hardened |
| `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/e2e/test_sso_global_logout.spec.ts` | test | browser request-response | `tests/frontend/e2e/test_sso_regression.spec.ts` | exact |
| `/home/ubuntu/GitHub/omni-srv-admin/scripts/sso-edge-smoke.sh` or phase runbook | utility/test | request-response/file-I/O | Phase 36 `curl --resolve` evidence + `/etc/apache2/sites-available/auth.atius.com.br.conf` | role-match |

## Pattern Assignments

### Apache / Keycloak / FreeIPA Planning

**Targets:** `sso.atius.com.br` vhost, Keycloak client/runbook, edge smoke script.

**Analogs:**
- `/etc/apache2/sites-available/auth.atius.com.br.conf`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/keycloak-freeipa-coexistence.md`

**Copy:**
- Keep Keycloak private behind Apache, using `127.0.0.1:8180`.
- Use Apache local smoke before public exposure.
- Keep FreeIPA federation read-first and root-only secrets out of docs.
- Use the same wildcard certificate path only after checking live DNS/proxy blast radius.

**Existing Apache reverse proxy shape** (`/etc/apache2/sites-available/auth.atius.com.br.conf` lines 8-20):

```apache
<VirtualHost *:443>
    ServerName auth.atius.com.br
    SSLEngine on
    SSLCertificateFile /etc/ssl/cloudflare/atius.com.br.pem
    SSLCertificateKeyFile /etc/ssl/cloudflare/atius.com.br.key
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s
    ProxyPass / http://127.0.0.1:8180/ retry=0 timeout=120
    ProxyPassReverse / http://127.0.0.1:8180/
```

**Existing Phase 36 baseline** (`docs/domain/keycloak-freeipa-coexistence.md` lines 6-18, 20-31, 64-73):

```text
Keycloak version: 26.6.3
Private listener: 127.0.0.1:8180
Public smoke hostname: auth.atius.com.br via Apache reverse proxy
Realm used for smoke: atius
LDAP source: FreeIPA on ldap://10.1.1.3:389
LDAP bind DN: root-only in /etc/keycloak/freeipa-bind.env
Federation: READ_ONLY, importEnabled=true, UUID attribute ipaUniqueID
Root-only paths: /etc/keycloak/keycloak.env, /etc/keycloak/freeipa-bind.env, /etc/keycloak/recovery-admin.env
```

**Avoid:**
- Do not copy Phase 36 password-grant smoke as the user-facing SSO flow. Phase 36 used it only as smoke evidence.
- Do not write Keycloak client secrets, JWT secrets, FreeIPA bind secrets, passwords, bearer tokens, or smoke credentials into Git, `.planning`, Obsidian, logs, or shell history.
- Do not publish `sso.atius.com.br` before `apache2ctl configtest`, local `curl --resolve`, and rollback inventory.

**Phase 42 divergence:**
- `sso.atius.com.br` should be an SSO facade, not only a Keycloak alias, because ATS still needs an `auth-token` bridge and DB-backed RBAC.
- Add an explicit `X-Forwarded-Host` contract for `sso` and ATS app vhosts. Prefer `RequestHeader set`, not `setifempty`, for headers that must not be spoofed or inherited.
- Add Cloudflare/DNS/TLS state capture before mutation. No `sso.atius.com.br` vhost currently exists in `/etc/apache2/sites-enabled` or `/etc/apache2/sites-available`.

### ATS Middleware / Subdomain Routing

**Target:** `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts`

**Analog:** same file.

**Copy:**
- Keep the host-to-app routing model and static asset bypass.
- Keep frontend middleware as UX/routing guard only.
- Continue to rely on backend RBAC for final authorization.

**Host and permission map** (`frontend/src/middleware.ts` lines 5-28):

```typescript
const SUBDOMAIN_PERMISSIONS: Record<string, string> = {
  'backtest.atius.com.br': 'can_access_backtest',
  'dashboard.atius.com.br': 'can_access_dashboard',
  'painel.atius.com.br': 'is_admin',
  'strategy.atius.com.br': 'can_access_lc',
  'admin.atius.com.br': 'is_admin',
}

const VALID_HOSTNAMES = [
  'api.atius.com.br',
  'trade.atius.com.br',
  'backtest.atius.com.br',
  'admin.atius.com.br',
  'dashboard.atius.com.br',
  'painel.atius.com.br',
  'strategy.atius.com.br',
  'localhost',
  '127.0.0.1',
  '0.0.0.0',
]
```

**Forwarded host dependency** (`frontend/src/middleware.ts` lines 43-52):

```typescript
const forwardedHostRaw = request.headers.get('x-forwarded-host')
const forwardedHost = forwardedHostRaw ? forwardedHostRaw.split(',')[0].trim() : null
const hostHeader = request.headers.get('host')
const rawHostname = forwardedHost || hostHeader || request.nextUrl.hostname
const hostname = rawHostname.split(':')[0]
```

**Current app-local login redirect** (`frontend/src/middleware.ts` lines 183-200):

```typescript
const checkAuthAndRedirect = (redirectPath?: string) => {
  const token = request.cookies.get('auth-token')

  if (!token) {
    const isLocal = hostname === 'localhost' || hostname.startsWith('127.0.0.1') || hostname === '0.0.0.0'
    const protocol = isLocal ? 'http' : 'https'
    const requestHost = request.headers.get('host')
    const hostWithPort = isLocal ? (requestHost ?? hostname) : hostname

    const loginUrl = new URL(`${protocol}://${hostWithPort}/login`)
    const finalRedirectPath = redirectPath ?? getExternalRedirectPath()
    loginUrl.searchParams.set('redirect', finalRedirectPath)
    return NextResponse.redirect(loginUrl)
  }
  return null
}
```

**Avoid:**
- Do not keep redirecting protected production hosts to app-local `/login` as the canonical path after SSO facade is ready.
- Do not trust `x-forwarded-host` unless Apache/Cloudflare overwrites it in a documented contract.
- Do not rely on middleware token decoding for RBAC; current comments explicitly leave enforcement to backend.

**Phase 42 divergence:**
- Change unauthenticated production redirects to `https://sso.atius.com.br/login?return_to=<allowlisted absolute target>`.
- Normalize return targets server-side. Reject external, protocol-relative, userinfo, non-HTTPS, subdomain-confusion, encoded-host, and unknown path targets.
- Add tests for missing/wrong `x-forwarded-host` and direct `Host` fallback behavior.

### ATS Auth Cookie / Session Bridge

**Targets:** backend auth route modifications and OIDC callback bridge.

**Analogs:**
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/token/index.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/users/index.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/contexts/auth-context.tsx`

**Copy:**
- Keep `auth-token` httpOnly cookie semantics.
- Keep production `Domain=.atius.com.br`, `Secure`, `SameSite=Lax`, `Path=/`.
- Keep `/v1/auth/me` as session hydration and `/v1/auth/refresh` as legacy refresh.
- Keep active-user lookup from the ATS `"user"` table.

**Central cookie options** (`backend/server/routes/auth/index.js` lines 7-17):

```javascript
const isProd = process.env.NODE_ENV === 'production';

const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: isProd,
  sameSite: 'lax',
  maxAge: 7 * 24 * 60 * 60,
  path: '/',
  domain: isProd ? '.atius.com.br' : undefined
};
```

**Session hydration** (`backend/server/routes/auth/index.js` lines 31-47, 61-80):

```javascript
const token = request.cookies['auth-token'];
if (!token) {
  return reply.status(401).send({ authenticated: false, error: 'Nao autenticado' });
}

const decoded = jwt.verify(token, process.env.JWT_SECRET);
const db = await getDatabaseInstance();
const result = await db.query(
  `SELECT id, nome, sobrenome, email, is_admin,
          can_access_backtest, can_access_dashboard,
          can_access_automation, can_access_trade,
          can_access_lc, bybit_uid, affiliate
   FROM "user" WHERE id = $1 AND ativa = true`,
  [decoded.id]
);

reply.send({
  authenticated: true,
  user: {
    id: user.id,
    email: user.email,
    is_admin: user.is_admin,
    permissions: {
      can_access_backtest: user.can_access_backtest,
      can_access_dashboard: user.can_access_dashboard,
      can_access_automation: user.can_access_automation,
      can_access_trade: user.can_access_trade,
      can_access_lc: user.can_access_lc
    }
  },
  expiresIn
});
```

**Legacy login token issuance** (`backend/server/routes/token/index.js` lines 54-70):

```javascript
const isProd = process.env.NODE_ENV === 'production';

const token = jwt.sign(
  { id: user.id, email: user.email, nome: user.nome, sobrenome: user.sobrenome },
  process.env.JWT_SECRET,
  { expiresIn: '7d' }
);

reply.setCookie('auth-token', token, {
  httpOnly: true,
  secure: isProd,
  sameSite: 'lax',
  maxAge: 7 * 24 * 60 * 60,
  path: '/',
  domain: isProd ? '.atius.com.br' : undefined
});
```

**Frontend hydration/refresh/logout contract** (`frontend/src/contexts/auth-context.tsx` lines 49-67, 80-99, 152-178):

```typescript
const response = await fetch('/v1/auth/me', {
  method: 'GET',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' }
});

const response = await fetch('/v1/auth/refresh', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' }
});

await fetch('/api/auth/logout', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' }
});
setUser(null);
window.location.href = '/login?logout=true';
```

**Avoid:**
- Do not expose the `auth-token` in JSON response bodies.
- Do not bypass ATS DB active-user and permissions checks after OIDC callback.
- Do not add a second parallel cookie name unless the plan also migrates every consumer and test.

**Phase 42 divergence:**
- OIDC callback must exchange Keycloak code server-side, map Keycloak identity to an ATS active user, then issue the existing ATS-compatible `auth-token`.
- If using Keycloak tokens directly later, keep ATS DB lookup authoritative until role/claim mapping is verified.

### ATS RBAC

**Target:** `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/middleware/permissions.js`

**Analog:** same file.

**Copy:**
- Keep backend `authenticate`, `requirePermission`, `requireAnyPermission`, `requireAdmin`, and `assertAccountOwnership`.
- Keep admin bypass behavior only where existing code already allows it.
- Keep permission flags in ATS DB: `is_admin`, `can_access_backtest`, `can_access_dashboard`, `can_access_automation`, `can_access_trade`, `can_access_lc`.

**Auth middleware** (`backend/server/middleware/permissions.js` lines 27-42):

```javascript
async function authenticate(request, reply) {
  try {
    const token = request.cookies['auth-token'];

    if (!token) {
      return reply.status(401).send({ error: 'Nao autenticado' });
    }

    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    request.user = decoded;
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return reply.status(401).send({ error: 'Sessao expirada. Faca login novamente.' });
    }
    return reply.status(401).send({ error: 'Token invalido.' });
  }
}
```

**Permission check** (`backend/server/middleware/permissions.js` lines 55-99):

```javascript
function requirePermission(permission) {
  return async (request, reply) => {
    try {
      const userId = request.user?.id;
      if (!userId) return reply.status(401).send({ error: 'Nao autenticado' });

      const db = await getDatabaseInstance();
      const result = await db.query(
        `SELECT is_admin, can_access_backtest, can_access_dashboard,
                can_access_automation, can_access_trade, can_access_lc
         FROM "user" WHERE id = $1 AND ativa = true`,
        [userId]
      );

      if (result.rows.length === 0) {
        return reply.status(403).send({ error: 'Usuario nao encontrado ou inativo' });
      }

      const userPerms = result.rows[0];
      if (userPerms.is_admin) {
        request.userPermissions = userPerms;
        return;
      }

      if (!userPerms[permission]) {
        return reply.status(403).send({
          error: 'Sem permissao para acessar este recurso',
          requiredPermission: permission
        });
      }

      request.userPermissions = userPerms;
    } catch (error) {
      request.log?.error?.('Erro ao verificar permissao:', error);
      return reply.status(500).send({ error: 'Erro interno ao verificar permissao' });
    }
  };
}
```

**Avoid:**
- Do not migrate trading access to Keycloak claims in Phase 42.
- Do not treat frontend denial copy or middleware redirects as security enforcement.

**Phase 42 divergence:**
- Add tests proving OIDC-bridged users still hit the same RBAC middleware and the same `"user"` permission flags.

### Logout

**Targets:** SSO logout route, ATS compatibility logout, login page logout state.

**Analogs:**
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/auth/logout/route.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/login/page.tsx`

**Copy:**
- Use a Next server-side route to send Set-Cookie headers directly to the browser.
- Use multiple `Set-Cookie` headers when clearing same-name cookies with different domains.
- Call backend logout best-effort, but do not block client cookie cleanup on backend failure.
- Preserve login page `logout=true` behavior to avoid auto-redirect loops.

**Next logout route** (`frontend/src/app/api/auth/logout/route.ts` lines 12-45):

```typescript
export async function POST() {
  const isProd = process.env.NODE_ENV === 'production'
  const apiPort = isProd ? (process.env.API_PORT || 8015) : (process.env.API_PORT || 8075)

  try {
    await fetch(`http://localhost:${apiPort}/v1/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
  } catch {
  }

  const response = NextResponse.json({ message: 'Logout realizado com sucesso' })

  if (isProd) {
    response.headers.append('Set-Cookie',
      'auth-token=; Path=/; Domain=.atius.com.br; Max-Age=0; HttpOnly; Secure; SameSite=Lax'
    )
  }

  response.headers.append('Set-Cookie',
    `auth-token=; Path=/; Max-Age=0; HttpOnly;${isProd ? ' Secure;' : ''} SameSite=Lax`
  )

  return response
}
```

**Backend logout route** (`backend/server/routes/auth/index.js` lines 160-184):

```javascript
fastify.post('/auth/logout', { schema: { tags: ['Auth'] } }, async (request, reply) => {
  reply.clearCookie('auth-token', {
    path: '/',
    domain: COOKIE_OPTIONS.domain,
    httpOnly: true,
    secure: COOKIE_OPTIONS.secure,
    sameSite: COOKIE_OPTIONS.sameSite
  });

  reply.clearCookie('auth-token', {
    path: '/',
    httpOnly: true,
    secure: COOKIE_OPTIONS.secure,
    sameSite: COOKIE_OPTIONS.sameSite
  });

  reply.send({ message: 'Logout realizado com sucesso' });
});
```

**Login page logout-loop guard** (`frontend/src/app/login/page.tsx` lines 52-82):

```typescript
const isLogout = urlParams.get('logout') === 'true'

if (isLogout) {
  didLogoutRef.current = true
  fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
  }).catch(() => {})
  window.history.replaceState({}, '', window.location.pathname)
}

if (didLogoutRef.current) return

if (!isLoading && user) {
  performRedirect()
}
```

**Avoid:**
- Do not use only one cookie clear. Domain and no-domain variants both matter.
- Do not use `response.cookies.set()` for two same-name clears where one can overwrite the other.
- Do not auto-login-loop after logout if Keycloak still has a browser session.

**Phase 42 divergence:**
- Add Keycloak RP-initiated logout after ATS cookie clears.
- `post_logout_redirect_uri` must be allowlisted and should land on `https://sso.atius.com.br/logged-out`.
- E2E must verify Keycloak session plus ATS `.atius.com.br` and no-domain cookie cleanup.

### Redirect Validation / Open Redirect

**Targets:** `frontend/src/lib/sso/redirects.ts`, SSO login/callback/logout routes, Swagger/docs compatibility.

**Analogs:**
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/api.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/login/page.tsx`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/components/auth/login-form.tsx`

**Copy:**
- Use `new URL()` parsing and host/path normalization.
- Preserve query only if explicitly allowed and redacted in UI/evidence.
- Tests should cover current app hosts from Phase 42: `trade`, `painel`, `dashboard`, `backtest`, `strategy`, `admin`.

**Forwarded origin helper** (`backend/server/api.js` lines 187-198):

```javascript
const resolveRequestOrigin = (request) => {
  const forwardedProto = String(request.headers?.['x-forwarded-proto'] || '').split(',', 1)[0].trim();
  const forwardedHost = String(request.headers?.['x-forwarded-host'] || '').split(',', 1)[0].trim();
  const host = forwardedHost || String(request.headers?.host || '').trim();
  const protocol = forwardedProto || (request.protocol === 'https' ? 'https' : 'http');

  if (host) {
    return `${protocol}://${host}`;
  }

  return BASE_URL;
};
```

**Current docs login URL pattern** (`backend/server/api.js` lines 200-210):

```javascript
const docsLoginUrl = (request) => {
  const normalizedSwaggerUrl = normalizeSwaggerPath(request);
  const [normalizedPath] = normalizedSwaggerUrl.split('?', 1);
  const isSwaggerEntryPath = /^\/v1\/docs(?:\/|\/index\.html)?$/i.test(normalizedPath);

  const nextTarget = isSwaggerEntryPath
    ? `${resolveRequestOrigin(request)}/v1/docs#/`
    : `${resolveRequestOrigin(request)}${normalizedSwaggerUrl}`;

  return `${SWAGGER_LOGIN_BASE_URL}/login?redirect=${encodeURIComponent(nextTarget)}`;
};
```

**Current app redirect pattern to avoid copying raw** (`frontend/src/app/login/page.tsx` lines 37-48; `frontend/src/components/auth/login-form.tsx` lines 138-146):

```typescript
const redirectUrl = urlParams.get('redirect')
if (redirectUrl) {
  window.location.href = redirectUrl
}
```

**Avoid:**
- Do not propagate `redirect`, `return_to`, `next`, or `post_logout_redirect_uri` without a strict allowlist.
- Do not allow `//evil.example`, `https://trade.atius.com.br.evil.example`, URLs with username/password, non-HTTPS URLs, encoded host confusion, or unknown paths.
- Do not rely on Apache rewrite allowlisting alone; SSO facade must validate server-side.

**Phase 42 divergence:**
- Implement an exact allowlist utility for scheme, hostname, and path prefixes.
- Default missing `return_to` to `https://trade.atius.com.br/`.
- Render invalid redirect state instead of redirecting.

### UI Login Shell

**Targets:** SSO login page/component.

**Analogs:**
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/components/auth/login-form.tsx`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/login/page.tsx`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-UI-SPEC.md`

**Copy:**
- Use existing shadcn components, `lucide-react`, `bg-dark-gradient`, compact centered shell, `mono-atius-horizontal.svg`, orange CTA/focus.
- Keep utility auth surface, not a hero/marketing page.
- Keep spinner/loading state shape from login page.

**Imports and UI library pattern** (`frontend/src/components/auth/login-form.tsx` lines 3-11):

```typescript
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useAuth } from '@/contexts/auth-context';
import { Mail, Lock, Eye, EyeOff, User, CheckCircle, XCircle, Loader2, ShieldCheck, ShieldX, Info, ExternalLink } from 'lucide-react';
```

**Login shell visual pattern** (`frontend/src/components/auth/login-form.tsx` lines 238-324):

```tsx
<div className="min-h-screen flex items-center justify-center bg-dark-gradient px-4 py-4 sm:py-6 lg:py-2">
  <div className="w-full max-w-md space-y-3 lg:space-y-2 min-h-[62vh] sm:min-h-[64vh] lg:min-h-[68vh] bg-gray-900/35 border border-gray-700/30 rounded-xl p-4 sm:p-5">
    <Card className="bg-transparent border-0 shadow-none">
      <div className="text-center pt-2 pb-0.5 lg:pt-1 lg:pb-0">
        <img
          src="/mono-atius-horizontal.svg"
          alt="Atius Capital"
          className="h-8 sm:h-9 mx-auto mb-0.5"
        />
        <p className="text-[11px] text-gray-500 leading-tight">Plataforma de Trading Profissional</p>
      </div>
      <CardHeader className="space-y-0.5 px-6 py-1.5 lg:py-1">
        <CardTitle className="text-xl text-center text-white">Entrar</CardTitle>
        <CardDescription className="text-center text-gray-400 text-xs">
          Digite suas credenciais para acessar sua conta de trading
        </CardDescription>
      </CardHeader>
      <CardContent className="px-6 py-2 lg:py-1.5">
        <Button
          type="submit"
          className="w-full bg-orange-500 hover:bg-orange-600 text-white font-medium transition-colors shadow-soft"
          disabled={isLoading}
        >
          {isLoading ? "Entrando..." : "Entrar"}
        </Button>
      </CardContent>
    </Card>
  </div>
</div>
```

**Loading state pattern** (`frontend/src/app/login/page.tsx` lines 84-104):

```tsx
<div className="min-h-screen bg-dark-gradient flex items-center justify-center p-4">
  <div className="flex flex-col items-center gap-4">
    <div className="w-8 h-8 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
    <p className="text-gray-400 text-sm">Redirecionando...</p>
  </div>
</div>
```

**Avoid:**
- Do not copy the local credential form as the primary SSO flow.
- Do not show raw redirect, state, code, token, client ID, stack trace, or secret placeholders.
- Do not keep trading-only copy. UI-SPEC requires Atius-wide copy such as `Entrar na Atius` and `Entrar com Atius SSO`.

**Phase 42 divergence:**
- Replace username/password fields with safe destination row, SSO CTA, OIDC handoff/loading, invalid redirect, auth error, already-authenticated redirect, and logout complete states.
- Keep shell width, gradient, logo, and orange CTA/focus.

### Runtime Tests

**Targets:**
- `tests/backend/auth/test_sso_redirect_allowlist.test.js`
- `tests/backend/auth/test_sso_oidc_bridge.test.js`
- `tests/backend/auth/test_sso_auth_endpoints.runtime.test.js`
- `tests/frontend/e2e/test_sso_global_logout.spec.ts`
- edge smoke script/runbook

**Analogs:**
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_auth_rbac_api.runtime.test.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/e2e/test_sso_regression.spec.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/playwright.config.js`
- `/home/ubuntu/GitHub/Atius-Capital/ats/jest.backend.runtime.config.js`

**Copy:**
- Use `RUN_LIVE_API_TESTS=1` gating for live backend runtime tests.
- Use Axios with `validateStatus: () => true`.
- Extract `auth-token` from `Set-Cookie` headers without logging its value.
- Keep Playwright `workers: 1` for SSO tests because cookies share `.atius.com.br`.
- Assert cookie attributes and cross-subdomain login/logout behavior.

**Runtime gating shape** (`tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` lines 1-6, 10-35):

```javascript
const axios = require('axios');

const runLive = process.env.RUN_LIVE_API_TESTS === '1';
const testLive = runLive ? test : test.skip;

const API_URL = process.env.BACKEND_API_URL || process.env.API_URL || 'http://localhost:8015';

function extractAuthCookie(setCookieHeader) {
  const raw = Array.isArray(setCookieHeader)
    ? setCookieHeader.join(';')
    : String(setCookieHeader || '');
  const match = raw.match(/auth-token=([^;]+)/);
  return match ? match[1] : null;
}
```

**RBAC runtime shape** (`tests/backend/auth/test_auth_rbac_api.runtime.test.js` lines 55-66, 92-146, 148-166):

```javascript
describe('Auth + RBAC API runtime', () => {
  beforeAll(async () => {
    if (!runLive) return;
    adminToken = await loginToken(ADMIN_EMAIL, ADMIN_PASSWORD);
  });

  testLive('cria usuario restrito e valida RBAC 403', async () => {
    const created = await apiPost('/v1/admin/users', adminToken, {
      ativa: true,
      is_admin: false
    });
    testUserId = created.data.userId;

    const permsOff = await apiPut(`/v1/admin/users/${testUserId}`, adminToken, {
      can_access_backtest: false,
      can_access_dashboard: false,
      can_access_automation: false,
      can_access_trade: false
    });

    const restrictedToken = await loginToken(testUserEmail, testUserPassword);
    const backtestRes = await apiGet('/v1/backtests/list-backtest', restrictedToken);
    const dashboardRes = await apiGet('/v1/dashboard/account/1', restrictedToken);
    const adminRes = await apiGet('/v1/admin/users', restrictedToken);

    expect(backtestRes.status).toBe(403);
    expect(dashboardRes.status).toBe(403);
    expect(adminRes.status).toBe(403);
  });
});
```

**Playwright one-worker config** (`playwright.config.js` lines 4-18):

```javascript
module.exports = defineConfig({
  testDir: './tests/frontend/e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3015',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
});
```

**E2E SSO assertions** (`tests/frontend/e2e/test_sso_regression.spec.ts` lines 139-146, 274-310, 312-327):

```typescript
const cookies = await context.cookies();
const authCookie = cookies.find(c => c.name === 'auth-token');
expect(authCookie).toBeDefined();
expect(authCookie!.domain).toBe('.atius.com.br');
expect(authCookie!.httpOnly).toBe(true);
expect(authCookie!.secure).toBe(true);
expect(authCookie!.sameSite).toBe('Lax');

await logoutViaUI(page, SITES.trade);

for (const [name, url] of Object.entries(SITES) as [SiteName, string][]) {
  await expectUnauthenticatedViaUI(page, url, `Pos-logout ${name}`);
}
```

**Avoid:**
- Do not copy the hardcoded fallback credentials currently present in runtime auth tests (`test_sso_auth_endpoints.runtime.test.js` lines 7-8 and `test_auth_rbac_api.runtime.test.js` lines 7-8). Replace with env-only and fail closed when missing.
- Do not log raw cookie/token values.
- Do not run live DNS/Cloudflare mutations from tests.

**Phase 42 divergence:**
- Add no-open-redirect unit matrix before implementation.
- Add OIDC bridge unit/runtime tests that can run with mocked Keycloak responses and separate live smoke env.
- Add global logout E2E that verifies Keycloak logout redirect and both ATS cookie deletion variants.
- Add edge smoke with `apache2ctl configtest` and `curl --resolve sso.atius.com.br:443:127.0.0.1 -I https://sso.atius.com.br/login`.

## Shared Patterns

### Auth Boundary

**Apply to:** SSO callback, middleware, backend routes, tests.

Copy the current separation:
- Keycloak authenticates the browser.
- ATS backend issues/validates the legacy `auth-token`.
- ATS DB remains authorization source of truth.
- Frontend middleware is UX/routing only.

### Cookie Attributes

**Source:** `backend/server/routes/auth/index.js` lines 7-17, `frontend/src/app/api/auth/logout/route.ts` lines 29-43.

Required production attributes:

```text
Name: auth-token
Domain: .atius.com.br
Path: /
HttpOnly: true
Secure: true
SameSite: Lax
Max-Age: 7 days for login/refresh; Max-Age=0 for logout
```

### Header Contract

**Source:** `frontend/src/middleware.ts` lines 43-52, `.planning/codebase/CONCERNS.md` lines 196-204, Apache vhost grep across ATS hosts.

Phase 42 must make these explicit:

```apache
ProxyPreserveHost On
RequestHeader set X-Forwarded-Host "sso.atius.com.br"
RequestHeader set X-Forwarded-Proto "https"
RequestHeader set X-Forwarded-Port "443"
```

For app vhosts, set each concrete app host (`trade`, `painel`, `dashboard`, `backtest`, `strategy`, `admin`) and test that middleware sees the intended hostname. Current vhosts are inconsistent: `painel` sets `X-Forwarded-Host`, while `trade`, `dashboard`, `backtest`, `strategy`, `admin`, and `api` do not set it explicitly.

### Secret Hygiene

**Sources:** `42-CONTEXT.md` lines 64-67, `docs/domain/keycloak-freeipa-coexistence.md` lines 64-73, `backend/server/api.js` lines 4-10, runtime tests lines 7-8.

Rules:
- Root-only paths may be named, but values must never be copied.
- Live smoke credentials must come from env/secret store and tests must fail closed if absent.
- Do not include token/cookie values in logs, test output, screenshots, `.planning`, or Obsidian.

### Error Handling

**Sources:** `backend/server/routes/auth/index.js` lines 81-92, 147-154; `backend/server/middleware/permissions.js` lines 96-99; `backend/server/api.js` lines 275-279.

Copy:
- JWT errors return 401 and clear cookies where appropriate.
- Permission failures return 403.
- Unexpected errors are logged server-side and return generic 500.

Avoid:
- Do not expose Keycloak, token exchange, client, secret, realm, stack trace, or raw upstream error details to browser UI.

## Risk Notes

### `x-forwarded-host`

Current middleware prefers `x-forwarded-host` over `host`. This is correct only if Apache/Cloudflare overwrites it. A client-controlled or missing value can make middleware route or guard the wrong subdomain. Phase 42 must include Apache contracts, local header smoke, and tests for absent/wrong/multiple forwarded host values.

### Cookie `Domain` / `Secure` / `SameSite`

The legacy ATS SSO depends on production cookies being `Domain=.atius.com.br`, `Secure`, `HttpOnly`, and `SameSite=Lax`. `NODE_ENV` controls `Secure` and `Domain`; PM2/build/runtime drift can make login work on one host and fail cross-subdomain. Phase 42 must inspect real `Set-Cookie` headers with `curl -D -` and Playwright.

### Open Redirects

Existing ATS code has raw `redirect` usage in app login paths. Phase 42 cannot copy that behavior into `sso.atius.com.br`. All return targets and post-logout redirects must be parsed and allowlisted by exact scheme, host, and path prefix. Reject protocol-relative URLs, userinfo, non-HTTPS, host confusion, encoded bypasses, and unknown hosts.

### Secret Hygiene

Phase 36 documents root-only paths, and current ATS runtime tests contain hardcoded fallback credentials. The planner must include a Wave 0 task to remove fallback credentials before live reuse. Planning artifacts should use placeholders only.

### Live DNS / Proxy Blast Radius

No `sso.atius.com.br` Apache vhost exists now. Adding one touches production edge, wildcard TLS, Cloudflare/DNS, Apache reload, Keycloak redirect URI correctness, and ATS cookie behavior. Execution must snapshot current DNS/proxy/vhost state, create backup, run `apache2ctl configtest`, run local `--resolve` smoke, and keep rollback steps before live publication.

## No Analog Found

| File / Concern | Role | Data Flow | Reason |
|----------------|------|-----------|--------|
| `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/oidc.ts` | utility | request-response | ATS has no existing OIDC Authorization Code client implementation. Use Keycloak docs and Phase 36 baseline; do not copy password-grant smoke. |
| Keycloak production client creation/apply script | config/tooling | request-response/batch | Phase 36 used manual/runtime configuration and docs. Phase 42 should plan a no-secrets inventory/export/apply gate, but there is no existing repo script to clone directly. |

## Metadata

**Analog search scope:**
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/phases/36-keycloak-sso-and-coexistence`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/codebase/CONCERNS.md`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src`
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server`
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests`
- `/etc/apache2/sites-enabled`
- `/etc/apache2/sites-available`

**Graphify:** status was fresh on 2026-06-28 (`commit_stale: false`), but task-specific query returned no direct Phase 42 nodes.
**GBrain:** queried for Phase 42/SSO/Keycloak/FreeIPA/ATS; no SSO-specific prior entry was used as an implementation source.
**Pattern extraction date:** 2026-06-28
