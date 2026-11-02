#!/usr/bin/env node
'use strict';

const http = require('http');
const querystring = require('querystring');
const { URL } = require('url');

const LISTEN_HOST = process.env.GITLAB_FACADE_LISTEN_HOST || '127.0.0.1';
const LISTEN_PORT = Number(process.env.GITLAB_FACADE_LISTEN_PORT || 8930);
const GITLAB_UPSTREAM_HOST = process.env.GITLAB_UPSTREAM_HOST || '10.14.1.14';
const GITLAB_UPSTREAM_PORT = Number(process.env.GITLAB_UPSTREAM_PORT || 8929);
const KEYCLOAK_UPSTREAM_HOST = process.env.KEYCLOAK_UPSTREAM_HOST || '127.0.0.1';
const KEYCLOAK_UPSTREAM_PORT = Number(process.env.KEYCLOAK_UPSTREAM_PORT || 8180);

const ATIUS_MARK_SVG = `<svg class="brand-mark" width="512" height="512" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><defs><linearGradient id="goldGradient" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#D4AF37;stop-opacity:1"/><stop offset="100%" style="stop-color:#AA8A26;stop-opacity:1"/></linearGradient><linearGradient id="greenGradient" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" style="stop-color:#1A4D2E;stop-opacity:1"/><stop offset="100%" style="stop-color:#0F2B1A;stop-opacity:1"/></linearGradient></defs><path d="M256 50 L460 450 H360 L256 220 L152 450 H52 L256 50Z" fill="url(#greenGradient)"/><path d="M340 380 A 90 90 0 1 1 340 280 L 300 300 A 45 45 0 1 0 300 360 Z" fill="url(#goldGradient)" transform="translate(-44, 20)"/><path d="M190 400 L320 400" stroke="#1A4D2E" stroke-width="5"/></svg>`;

const CANONICAL_LOGIN_CSS = `*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji";background:linear-gradient(135deg,#1a1a1a 0%,#1f1f1f 50%,#1a1a1a 100%);color:#fafafa;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0;padding:24px 16px}.card{width:min(448px,100%);background:rgba(17,24,39,.35);border:1px solid rgba(55,65,81,.3);border-radius:12px;padding:24px}.brand{text-align:center;padding-bottom:16px}.brand-mark{display:block;width:44px;height:44px;margin:0 auto 8px}.brand-name{font-size:11px;font-weight:400;line-height:13.75px;color:#9ca3af;margin:0}.dest{margin-top:16px;padding:12px;border-radius:12px;background:rgba(31,41,55,.4);border:1px solid rgba(55,65,81,.4)}.dest small{display:block;color:#9ca3af;font-size:11px;font-weight:400;line-height:16.5px;letter-spacing:normal;text-transform:uppercase;margin:0}.dest-row{display:flex;align-items:flex-start;gap:8px;margin-top:8px;color:#e5e7eb;font-size:14px;font-weight:400;line-height:20px}.icon{display:block;width:16px;height:16px;color:#9ca3af;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.shield{margin-top:2px;color:#f97316;flex:none}.form{margin-top:16px}.field+.field{margin-top:12px}.label-line{height:24px}label{color:#fff;font-size:14px;font-weight:500;line-height:20px}.control{position:relative;margin-top:8px}.icon-left,.icon-right{position:absolute;top:50%;transform:translateY(-50%);z-index:1}.icon-left{left:12px}.icon-right{right:0;width:44px;height:44px;display:flex;align-items:center;justify-content:center;border:0;background:transparent;padding:0;color:#9ca3af;cursor:pointer}input{display:block;width:100%;height:44px;border-radius:10px;border:1px solid #4b5563;background:#1f2937;color:#fff;padding:8px 12px 8px 40px;font-family:inherit;font-size:14px;font-weight:400;line-height:20px;outline:none}input[type=password],input[data-password]{padding-right:44px}input::placeholder{color:#b3b3b3}input:focus{border-color:#f97316;box-shadow:0 0 0 1px rgba(249,115,22,.2)}.submit{height:44px;border:0;border-radius:10px;background:#f97316;color:#fff;font-family:inherit;font-size:14px;font-weight:500;line-height:20px;width:100%;margin-top:12px;padding:8px 16px;cursor:pointer}.submit:hover{background:#ea580c}.submit:focus-visible,.icon-right:focus-visible{outline:2px solid #f97316;outline-offset:2px}.error{margin:16px 0 0;padding:12px;border:1px solid rgba(239,68,68,.4);background:rgba(69,10,10,.3);border-radius:12px;color:#fecaca;font-size:14px;line-height:20px}@media(max-width:639px){body{padding:16px}.card{padding:16px}.brand-mark{width:40px;height:40px}}`;

function renderCanonicalLoginShell({ destination, action = '/login', error = '', redirectTo = '' }) {
  const errorHtml = error ? `<div class="error" role="alert">${error}</div>` : '';
  const redirectInput = redirectTo ? `<input type="hidden" name="redirect_to" value="${escapeHtml(redirectTo)}">` : '';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Atius SSO</title><meta name="description" content="Atius SSO login for authorized apps"><link rel="icon" href="/_atius/favicon.svg" type="image/svg+xml"><style>${CANONICAL_LOGIN_CSS}</style></head><body><main class="card"><div class="brand">${ATIUS_MARK_SVG}<p class="brand-name">Atius SSO</p></div><h1 hidden>Entrar na Atius</h1><div class="dest"><small>Destino seguro</small><div class="dest-row"><svg class="icon shield" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg><span>${destination}</span></div></div>${errorHtml}<form class="form" method="post" action="${action}">${redirectInput}<div class="field"><div class="label-line"><label for="login">Email ou username</label></div><div class="control"><svg class="icon icon-left" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><input id="login" name="login" autocomplete="username" placeholder="Digite seu email ou username" required autofocus></div></div><div class="field"><div class="label-line"><label for="senha">Senha</label></div><div class="control"><svg class="icon icon-left" viewBox="0 0 24 24" aria-hidden="true"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg><input id="senha" name="senha" type="password" data-password autocomplete="current-password" placeholder="Digite sua senha" required><button class="icon-right" type="button" aria-label="Mostrar senha" onclick="const i=this.previousElementSibling;const show=i.type==='password';i.type=show?'text':'password';this.setAttribute('aria-label',show?'Ocultar senha':'Mostrar senha')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg></button></div></div><button class="submit" type="submit">Entrar com Atius SSO</button></form></main></body></html>`;
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function resolveDestination(req) {
  const forwarded = String(req.headers['x-forwarded-host'] || '').split(',')[0].trim();
  const host = forwarded || String(req.headers.host || '').split(',')[0].trim();
  const hostname = host.split(':')[0].toLowerCase();
  if (hostname.includes('gitlab.atius.com.br')) return 'gitlab.atius.com.br';
  return 'gitlab.atius.io';
}

function httpRequest(options, postData = null) {
  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode || 0,
          headers: res.headers,
          body: Buffer.concat(chunks).toString('utf8')
        });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('upstream timeout')));
    if (postData) req.write(postData);
    req.end();
  });
}

function readBody(req, maxBytes = 16384) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > maxBytes) return reject(new Error('request body too large'));
      chunks.push(chunk);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

async function performHandshake(destination, username, password) {
  // 1. Fetch sign_in page to acquire CSRF and session
  const signRes = await httpRequest({
    hostname: GITLAB_UPSTREAM_HOST,
    port: GITLAB_UPSTREAM_PORT,
    path: '/users/sign_in',
    method: 'GET',
    headers: {
      'Host': destination,
      'X-Forwarded-Proto': 'https'
    },
    timeout: 10000
  });

  if (signRes.statusCode !== 200) {
    throw new Error(`GitLab sign_in failed with status ${signRes.statusCode}`);
  }

  const gitlabCookies = (signRes.headers['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
  const csrfMatch = signRes.body.match(/name="csrf-token" content="([^"]+)"/);
  if (!csrfMatch) {
    throw new Error('CSRF token not found in GitLab sign_in page');
  }
  const csrfToken = csrfMatch[1];

  // 2. Initiate OIDC request
  const oidcPostData = querystring.stringify({ authenticity_token: csrfToken });
  const oidcRes = await httpRequest({
    hostname: GITLAB_UPSTREAM_HOST,
    port: GITLAB_UPSTREAM_PORT,
    path: '/users/auth/openid_connect',
    method: 'POST',
    headers: {
      'Host': destination,
      'X-Forwarded-Proto': 'https',
      'Cookie': gitlabCookies,
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(oidcPostData)
    },
    timeout: 10000
  }, oidcPostData);

  if (oidcRes.statusCode !== 302 || !oidcRes.headers.location) {
    throw new Error(`GitLab OIDC initiation failed: status=${oidcRes.statusCode}`);
  }
  const keycloakAuthUrl = new URL(oidcRes.headers.location);

  // 3. Fetch Keycloak Auth Page
  const kcPageRes = await httpRequest({
    hostname: KEYCLOAK_UPSTREAM_HOST,
    port: KEYCLOAK_UPSTREAM_PORT,
    path: keycloakAuthUrl.pathname + keycloakAuthUrl.search,
    method: 'GET',
    headers: {
      'Host': 'auth.atius.com.br',
      'X-Forwarded-Proto': 'https'
    },
    timeout: 10000
  });

  if (kcPageRes.statusCode !== 200) {
    throw new Error(`Keycloak auth page failed: status=${kcPageRes.statusCode}`);
  }

  const kcCookies = (kcPageRes.headers['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
  const actionMatch = kcPageRes.body.match(/action="([^"]+login-actions[^"]+)"/);
  if (!actionMatch) {
    throw new Error('Keycloak form action not found in auth page');
  }
  const kcActionUrl = new URL(actionMatch[1].replace(/&amp;/g, '&'));

  // 4. Submit Credentials to Keycloak (allow up to 15s for Keycloak brute-force/password hash guard)
  const kcPostData = querystring.stringify({ username, password });
  const kcLoginRes = await httpRequest({
    hostname: KEYCLOAK_UPSTREAM_HOST,
    port: KEYCLOAK_UPSTREAM_PORT,
    path: kcActionUrl.pathname + kcActionUrl.search,
    method: 'POST',
    headers: {
      'Host': 'auth.atius.com.br',
      'X-Forwarded-Proto': 'https',
      'Cookie': kcCookies,
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(kcPostData)
    },
    timeout: 15000
  }, kcPostData);

  // Keycloak returns 302 with callback URL on success
  if (kcLoginRes.statusCode === 302 && kcLoginRes.headers.location) {
    const callbackUrl = new URL(kcLoginRes.headers.location);

    // 5. Complete Callback on GitLab
    const cbRes = await httpRequest({
      hostname: GITLAB_UPSTREAM_HOST,
      port: GITLAB_UPSTREAM_PORT,
      path: callbackUrl.pathname + callbackUrl.search,
      method: 'GET',
      headers: {
        'Host': destination,
        'X-Forwarded-Proto': 'https',
        'Cookie': gitlabCookies
      },
      timeout: 15000
    });

    return {
      ok: true,
      cookies: cbRes.headers['set-cookie'] || [],
      location: cbRes.headers.location || '/'
    };
  }

  // Keycloak returned 200 or 401 with login page => credentials rejected
  const isInvalid = kcLoginRes.statusCode === 401 ||
                    kcLoginRes.statusCode === 200 ||
                    kcLoginRes.body.includes('inválid') ||
                    kcLoginRes.body.includes('Invalid');
  return {
    ok: false,
    reason: isInvalid ? 'invalid_credentials' : 'login_failed'
  };
}

const server = http.createServer(async (req, res) => {
  const parsed = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
  const destination = resolveDestination(req);

  // Healthcheck endpoint
  if (parsed.pathname === '/healthz' || parsed.pathname === '/_atius/healthz') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ status: 'ok', service: 'gitlab-login-facade', destination }));
  }

  // Favicon
  if (parsed.pathname === '/_atius/favicon.svg') {
    res.writeHead(200, { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=86400' });
    return res.end(ATIUS_MARK_SVG);
  }

  // Login page GET / HEAD
  if (parsed.pathname === '/login' && (req.method === 'GET' || req.method === 'HEAD')) {
    const redirectTo = parsed.searchParams.get('redirect_to') || '';
    const html = renderCanonicalLoginShell({ destination, action: '/login', redirectTo });
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store, private',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'SAMEORIGIN'
    });
    if (req.method === 'HEAD') return res.end();
    return res.end(html);
  }

  // Login POST
  if (parsed.pathname === '/login' && req.method === 'POST') {
    let body;
    try {
      const rawBody = await readBody(req);
      body = querystring.parse(rawBody);
    } catch {
      res.writeHead(400, { 'Content-Type': 'text/plain' });
      return res.end('Invalid request');
    }

    const login = String(body.login || '').trim();
    const senha = String(body.senha || '');
    const redirectTo = String(body.redirect_to || '').trim();

    if (!login || !senha) {
      const html = renderCanonicalLoginShell({
        destination,
        action: '/login',
        error: 'Informe email ou username e senha.',
        redirectTo
      });
      res.writeHead(400, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store, private'
      });
      return res.end(html);
    }

    try {
      const result = await performHandshake(destination, login, senha);
      if (result.ok) {
        // Successful login
        const headers = {
          'Location': redirectTo && redirectTo.startsWith('/') ? redirectTo : '/',
          'Cache-Control': 'no-store, private'
        };
        if (result.cookies && result.cookies.length) {
          headers['Set-Cookie'] = result.cookies;
        }
        res.writeHead(302, headers);
        return res.end();
      }

      // Credentials rejected
      const html = renderCanonicalLoginShell({
        destination,
        action: '/login',
        error: 'Não foi possível entrar. Verifique as credenciais.',
        redirectTo
      });
      res.writeHead(401, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store, private'
      });
      return res.end(html);
    } catch (err) {
      console.error(`[gitlab-login-facade] handshake_error dest=${destination}:`, err.message);
      const html = renderCanonicalLoginShell({
        destination,
        action: '/login',
        error: 'O serviço de autenticação está temporariamente indisponível.',
        redirectTo
      });
      res.writeHead(503, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store, private'
      });
      return res.end(html);
    }
  }

  // Fallback for other paths
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

server.listen(LISTEN_PORT, LISTEN_HOST, () => {
  console.log(`[gitlab-login-facade] Listening on http://${LISTEN_HOST}:${LISTEN_PORT}`);
});
