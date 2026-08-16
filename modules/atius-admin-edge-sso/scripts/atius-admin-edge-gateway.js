#!/usr/bin/env node
'use strict';

const fs = require('fs');
const crypto = require('crypto');
const http = require('http');
const https = require('https');
const net = require('net');
const tls = require('tls');
const querystring = require('querystring');

const DEFAULT_CONFIG = '/etc/atius/atius-admin-edge-gateway.json';
const HOP_BY_HOP_HEADERS = new Set([
  'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade'
]);
const MAX_AUTH_RESPONSE_BYTES = 64 * 1024;
const MAX_PROXY_HTML_BYTES = 8 * 1024 * 1024;
const PORTAINER_TOKEN_TTL_MS = 10 * 60 * 1000;
const SESSION_CACHE_TTL_MS = 30 * 1000;
const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', 'localhost']);

function readConfig(configPath = process.env.ATIUS_ADMIN_EDGE_GATEWAY_CONFIG || process.argv[2] || DEFAULT_CONFIG) {
  const raw = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  for (const key of ['authCheckUrl', 'centralLoginUrl', 'listenHost', 'listenPort', 'sites']) {
    if (!raw[key]) throw new Error(`config requires ${key}`);
  }
  if (!LOOPBACK_HOSTS.has(String(raw.listenHost))) throw new Error('listenHost must be loopback');
  const authCheckUrl = new URL(raw.authCheckUrl);
  if (!LOOPBACK_HOSTS.has(authCheckUrl.hostname)) throw new Error('authCheckUrl must be loopback');
  const sites = {};
  const raws = raw.sites || {};
  for (const [host, cfg] of Object.entries(raws)) {
    const base = cfg.aliasOf ? raws[cfg.aliasOf] : cfg;
    if (!base) throw new Error(`alias target missing for ${host}`);
    if (!base.publicOrigin && !cfg.publicOrigin) throw new Error(`site ${host} requires publicOrigin`);
    const site = {
      appName: cfg.appName || base.appName || host,
      authMode: cfg.authMode || base.authMode,
      loginPath: cfg.loginPath || base.loginPath || '/login',
      logoutPath: cfg.logoutPath || base.logoutPath || '/logout',
      publicOrigin: cfg.publicOrigin || base.publicOrigin,
      requiredPermission: cfg.requiredPermission || base.requiredPermission || null,
      requireAdmin: Object.prototype.hasOwnProperty.call(cfg, 'requireAdmin') ? cfg.requireAdmin : (Object.prototype.hasOwnProperty.call(base, 'requireAdmin') ? base.requireAdmin : true),
      upstream: new URL(cfg.upstream || base.upstream),
      upstreamUsernameEnv: cfg.upstreamUsernameEnv || base.upstreamUsernameEnv || '',
      upstreamPasswordEnv: cfg.upstreamPasswordEnv || base.upstreamPasswordEnv || '',
      upstreamAuthUrl: cfg.upstreamAuthUrl || base.upstreamAuthUrl || '/api/auth',
      allowedEmails: (cfg.allowedEmails || base.allowedEmails || []).map(v => String(v).trim().toLowerCase()),
    };
    sites[host] = site;
  }
  return {
    authCheckUrl,
    authCookieName: raw.authCookieName || 'auth-token',
    centralLoginUrl: new URL(raw.centralLoginUrl),
    listenHost: raw.listenHost,
    listenPort: Number(raw.listenPort),
    sites,
  };
}

function parseCookies(header) {
  const cookies = new Map();
  for (const part of String(header || '').split(';')) {
    const idx = part.indexOf('=');
    if (idx < 1) continue;
    cookies.set(part.slice(0, idx).trim(), part.slice(idx + 1).trim());
  }
  return cookies;
}

function cookieValues(header, name, limit = 4) {
  const values = [];
  for (const part of String(header || '').split(';')) {
    const idx = part.indexOf('=');
    if (idx < 1 || part.slice(0, idx).trim() !== name) continue;
    const value = part.slice(idx + 1).trim();
    if (value && !values.includes(value)) values.push(value);
    if (values.length >= limit) break;
  }
  return values;
}

function forwardedFor(req) {
  const existing = String(req.headers['x-forwarded-for'] || '').trim();
  const remote = req.socket.remoteAddress || '';
  return existing ? `${existing}, ${remote}` : remote;
}

function resolveHost(req) {
  const forwarded = String(req.headers['x-forwarded-host'] || '').split(',')[0].trim();
  const host = forwarded || String(req.headers.host || '').split(',')[0].trim();
  return host.split(':')[0];
}

function siteForRequest(config, req) {
  const host = resolveHost(req);
  return config.sites[host] ? { host, site: config.sites[host] } : null;
}

function buildReturnTo(site, req) {
  const path = '/';
  return `${site.publicOrigin}${path}`;
}

function buildCentralLogin(config, site, req) {
  const url = new URL(config.centralLoginUrl.toString());
  url.searchParams.set('return_to', buildReturnTo(site, req));
  return url.toString();
}

function redirect(res, statusCode, location, extraHeaders = {}) {
  res.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    Location: location,
    ...extraHeaders,
  });
  res.end();
}

function clearAtiusCookies() {
  return [
    'auth-token=; Path=/; Domain=.atius.com.br; Max-Age=0; HttpOnly; Secure; SameSite=Lax',
    'auth-token=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax',
  ];
}

function clearHostOnlyAuthCookie() {
  return 'auth-token=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax';
}

function sendJson(res, statusCode, body, extraHeaders = {}) {
  const payload = Buffer.from(JSON.stringify(body));
  res.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': payload.length,
    ...extraHeaders,
  });
  res.end(payload);
}

function sendHtml(res, statusCode, html, extraHeaders = {}) {
  const payload = Buffer.from(html);
  res.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Type': 'text/html; charset=utf-8',
    'Content-Length': payload.length,
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    ...extraHeaders,
  });
  res.end(payload);
}

function logoutBridgeScript() {
  return `(() => {
  const id = '__atius_sso_logout';
  if (document.getElementById(id)) return;
  const wireVendorLogout = () => {
    for (const control of document.querySelectorAll('a[href="#!/logout"], a[href="/logout"], [data-cy="userMenu-logOut"]')) {
      if (control.id === id || control.dataset.atiusSsoWired === 'true') continue;
      control.dataset.atiusSsoWired = 'true';
      control.setAttribute('href', '/logout');
      control.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.location.assign('/logout');
      }, true);
    }
  };
  const link = document.createElement('a');
  link.id = id;
  link.href = '/logout';
  link.textContent = 'Sair do Atius SSO';
  link.setAttribute('aria-label', 'Sair do Atius SSO');
  link.setAttribute('data-atius-sso-logout', 'true');
  link.style.cssText = [
    'position:fixed', 'z-index:2147483646', 'right:16px', 'bottom:16px',
    'display:inline-flex', 'align-items:center', 'min-height:36px',
    'padding:8px 12px', 'border:1px solid #f97316', 'border-radius:8px',
    'background:#171b22', 'color:#fff', 'font:600 13px/1.2 system-ui,sans-serif',
    'text-decoration:none', 'box-shadow:0 4px 16px rgba(0,0,0,.35)'
  ].join(';');
  link.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    window.location.assign('/logout');
  }, true);
  document.body.appendChild(link);
  wireVendorLogout();
  new MutationObserver(wireVendorLogout).observe(document.documentElement, { childList: true, subtree: true });
})();`;
}

function sendJavaScript(res, body) {
  const payload = Buffer.from(body);
  res.writeHead(200, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/javascript; charset=utf-8',
    'Content-Length': payload.length,
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(payload);
}

function sendSvg(res, body) {
  const payload = Buffer.from(body);
  res.writeHead(200, {
    'Cache-Control': 'public, max-age=86400',
    'Content-Type': 'image/svg+xml; charset=utf-8',
    'Content-Length': payload.length,
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(payload);
}

function injectLogoutBridge(html) {
  const tag = '<script src="/_atius/logout-bridge.js" defer></script>';
  if (html.includes('/_atius/logout-bridge.js')) return html;
  if (/<\/body>/i.test(html)) return html.replace(/<\/body>/i, `${tag}</body>`);
  return `${html}${tag}`;
}

const ATIUS_MARK_SVG = `<svg class="brand-mark" width="512" height="512" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><defs><linearGradient id="goldGradient" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#D4AF37;stop-opacity:1"/><stop offset="100%" style="stop-color:#AA8A26;stop-opacity:1"/></linearGradient><linearGradient id="greenGradient" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" style="stop-color:#1A4D2E;stop-opacity:1"/><stop offset="100%" style="stop-color:#0F2B1A;stop-opacity:1"/></linearGradient></defs><path d="M256 50 L460 450 H360 L256 220 L152 450 H52 L256 50Z" fill="url(#greenGradient)"/><path d="M340 380 A 90 90 0 1 1 340 280 L 300 300 A 45 45 0 1 0 300 360 Z" fill="url(#goldGradient)" transform="translate(-44, 20)"/><path d="M190 400 L320 400" stroke="#1A4D2E" stroke-width="5"/></svg>`;

function renderLoginShell({ destination, action, error = '' }) {
  const errorHtml = error ? `<div class="error" role="alert">${error}</div>` : '';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Atius SSO</title><style>*{box-sizing:border-box}body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#18191b;color:#f8fafc;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0;padding:24px}.card{width:min(448px,100%);background:#171b22;border:1px solid #25303d;border-radius:12px;padding:28px 24px}.brand{text-align:center}.brand-mark{display:block;width:72px;height:72px;margin:0 auto 6px}.brand-name{font-size:12px;color:#a7b0aa;margin:0}.dest{margin-top:28px;padding:14px 16px;border-radius:12px;background:#1b222c;border:1px solid #25303d}.dest small{display:block;color:#a7b0aa;font-size:11px;font-weight:400;line-height:16.5px;letter-spacing:normal;text-transform:uppercase;margin-bottom:8px}.dest-row{display:flex;align-items:center;gap:10px;color:#fff;font-size:14px;font-weight:400;line-height:20px}.shield{width:18px;height:18px;color:#ff7112;flex:none}.field{display:flex;flex-direction:column;gap:9px;margin-top:18px}label{color:#fff;font-size:14px;font-weight:500;line-height:20px}.control{position:relative;margin-top:8px}.icon-left,.icon-right{position:absolute;top:50%;transform:translateY(-50%);color:#94a3b8;line-height:1}.icon-left{left:14px}.icon-right{right:14px}input{width:100%;height:44px;border-radius:11px;border:1px solid #40536b;background:#1e2a39;color:#fff;padding:0 42px;font-size:14px}input::placeholder{color:#cbd5e1}button{height:44px;border:none;border-radius:11px;background:#ff7112;color:#fff;font-weight:700;width:100%;margin-top:18px;font-size:14px}.error{margin:18px 0 0;padding:12px;border:1px solid #7f1d1d;background:#450a0a;border-radius:12px;color:#fecaca}</style></head><body><main class="card"><div class="brand">${ATIUS_MARK_SVG}<p class="brand-name">Atius SSO</p></div><div class="dest"><small>DESTINO SEGURO</small><div class="dest-row"><svg class="shield" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 19 6v5c0 4.7-2.8 8.1-7 10-4.2-1.9-7-5.3-7-10V6l7-3Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg><span>${destination}</span></div></div>${errorHtml}<form method="post" action="${action}"><div class="field"><label for="login">Email ou username</label><div class="control"><span class="icon-left">👤</span><input id="login" name="login" autocomplete="username" placeholder="Digite seu email ou username" required></div></div><div class="field"><label for="senha">Senha</label><div class="control"><span class="icon-left">🔒</span><input id="senha" name="senha" type="password" autocomplete="current-password" placeholder="Digite sua senha" required><span class="icon-right">👁</span></div></div><button type="submit">Entrar com Atius SSO</button></form></main></body></html>`;
}

const CANONICAL_LOGIN_CSS = `*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji";background:linear-gradient(135deg,#1a1a1a 0%,#1f1f1f 50%,#1a1a1a 100%);color:#fafafa;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0;padding:24px 16px}.card{width:min(448px,100%);background:rgba(17,24,39,.35);border:1px solid rgba(55,65,81,.3);border-radius:12px;padding:24px}.brand{text-align:center;padding-bottom:16px}.brand-mark{display:block;width:44px;height:44px;margin:0 auto 8px}.brand-name{font-size:11px;font-weight:400;line-height:13.75px;color:#9ca3af;margin:0}.dest{margin-top:16px;padding:12px;border-radius:12px;background:rgba(31,41,55,.4);border:1px solid rgba(55,65,81,.4)}.dest small{display:block;color:#9ca3af;font-size:11px;font-weight:400;line-height:16.5px;letter-spacing:normal;text-transform:uppercase;margin:0}.dest-row{display:flex;align-items:flex-start;gap:8px;margin-top:8px;color:#e5e7eb;font-size:14px;font-weight:400;line-height:20px}.icon{display:block;width:16px;height:16px;color:#9ca3af;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.shield{margin-top:2px;color:#f97316;flex:none}.form{margin-top:16px}.field+.field{margin-top:12px}.label-line{height:24px}label{color:#fff;font-size:14px;font-weight:500;line-height:20px}.control{position:relative;margin-top:8px}.icon-left,.icon-right{position:absolute;top:50%;transform:translateY(-50%);z-index:1}.icon-left{left:12px}.icon-right{right:0;width:44px;height:44px;display:flex;align-items:center;justify-content:center;border:0;background:transparent;padding:0;color:#9ca3af;cursor:pointer}input{display:block;width:100%;height:44px;border-radius:10px;border:1px solid #4b5563;background:#1f2937;color:#fff;padding:8px 12px 8px 40px;font-family:inherit;font-size:14px;font-weight:400;line-height:20px;outline:none}input[type=password],input[data-password]{padding-right:44px}input::placeholder{color:#b3b3b3}input:focus{border-color:#f97316;box-shadow:0 0 0 1px rgba(249,115,22,.2)}.submit{height:44px;border:0;border-radius:10px;background:#f97316;color:#fff;font-family:inherit;font-size:14px;font-weight:500;line-height:20px;width:100%;margin-top:12px;padding:8px 16px;cursor:pointer}.submit:hover{background:#ea580c}.submit:focus-visible,.icon-right:focus-visible{outline:2px solid #f97316;outline-offset:2px}.error{margin:16px 0 0;padding:12px;border:1px solid rgba(239,68,68,.4);background:rgba(69,10,10,.3);border-radius:12px;color:#fecaca;font-size:14px;line-height:20px}@media(max-width:639px){body{padding:16px}.card{padding:16px}.brand-mark{width:40px;height:40px}}`;

function renderCanonicalLoginShell({ destination, action, error = '' }) {
  const errorHtml = error ? `<div class="error" role="alert">${error}</div>` : '';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Atius SSO</title><meta name="description" content="Atius SSO login for authorized apps"><link rel="icon" href="/_atius/favicon.svg" type="image/svg+xml"><style>${CANONICAL_LOGIN_CSS}</style></head><body><main class="card"><div class="brand">${ATIUS_MARK_SVG}<p class="brand-name">Atius SSO</p></div><h1 hidden>Entrar na Atius</h1><div class="dest"><small>Destino seguro</small><div class="dest-row"><svg class="icon shield" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg><span>${destination}</span></div></div>${errorHtml}<form class="form" method="post" action="${action}"><div class="field"><div class="label-line"><label for="login">Email ou username</label></div><div class="control"><svg class="icon icon-left" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><input id="login" name="login" autocomplete="username" placeholder="Digite seu email ou username" required></div></div><div class="field"><div class="label-line"><label for="senha">Senha</label></div><div class="control"><svg class="icon icon-left" viewBox="0 0 24 24" aria-hidden="true"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg><input id="senha" name="senha" type="password" data-password autocomplete="current-password" placeholder="Digite sua senha" required><button class="icon-right" type="button" aria-label="Mostrar senha" onclick="const i=this.previousElementSibling;const show=i.type==='password';i.type=show?'text':'password';this.setAttribute('aria-label',show?'Ocultar senha':'Mostrar senha')"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg></button></div></div><button class="submit" type="submit">Entrar com Atius SSO</button></form></main></body></html>`;
}

function loginPage(site, error = '') {
  const destination = new URL(site.publicOrigin).hostname;
  return renderCanonicalLoginShell({ destination, action: site.loginPath, error });
}

function readRequestBody(req, maxBytes = 16384) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > maxBytes) {
        reject(new Error('request body too large'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function requestJson(targetUrl, headers) {
  return new Promise((resolve, reject) => {
    const client = targetUrl.protocol === 'https:' ? https : http;
    const req = client.request({
      protocol: targetUrl.protocol,
      hostname: targetUrl.hostname,
      port: targetUrl.port || (targetUrl.protocol === 'https:' ? 443 : 80),
      path: `${targetUrl.pathname}${targetUrl.search}`,
      method: 'GET',
      headers: { Accept: 'application/json', ...headers },
      timeout: 5000,
      rejectUnauthorized: false,
    }, (res) => {
      const chunks = []; let total = 0;
      res.on('data', (chunk) => { total += chunk.length; if (total > MAX_AUTH_RESPONSE_BYTES) { req.destroy(new Error('auth response too large')); return; } chunks.push(chunk); });
      res.on('end', () => {
        let body = null;
        const raw = Buffer.concat(chunks).toString('utf8');
        if (raw.trim()) {
          try { body = JSON.parse(raw); } catch (e) { return reject(new Error(`auth response is not JSON: ${e.message}`)); }
        }
        resolve({ statusCode: res.statusCode || 0, body, headers: res.headers });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('auth request timeout')));
    req.end();
  });
}

function postJson(targetUrl, payload) {
  return new Promise((resolve, reject) => {
    const raw = Buffer.from(JSON.stringify(payload));
    const client = targetUrl.protocol === 'https:' ? https : http;
    const req = client.request({
      protocol: targetUrl.protocol,
      hostname: targetUrl.hostname,
      port: targetUrl.port || (targetUrl.protocol === 'https:' ? 443 : 80),
      path: `${targetUrl.pathname}${targetUrl.search}`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': raw.length, Accept: 'application/json' },
      timeout: 10000,
      rejectUnauthorized: false,
    }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const bodyText = Buffer.concat(chunks).toString('utf8');
        let body = null;
        if (bodyText.trim()) {
          try { body = JSON.parse(bodyText); } catch {}
        }
        resolve({ statusCode: res.statusCode || 0, body, bodyText, headers: res.headers });
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('upstream post timeout')));
    req.write(raw); req.end();
  });
}

const sessionCache = new Map();
const sessionRequests = new Map();

function sessionCacheKey(config, site, token) {
  const digest = crypto.createHash('sha256').update(token).digest('hex');
  return `${config.authCheckUrl.href}|${site.publicOrigin}|${digest}`;
}

function pruneSessionCache(now = Date.now()) {
  for (const [key, entry] of sessionCache) {
    if (entry.expiresAt <= now) sessionCache.delete(key);
  }
}

async function verifySessionUncached(config, site, req, token) {
  let response;
  try {
    response = await requestJson(config.authCheckUrl, {
      Cookie: `${config.authCookieName}=${token}`,
      'X-Forwarded-For': forwardedFor(req),
      'X-Forwarded-Host': new URL(site.publicOrigin).host,
      'X-Forwarded-Proto': 'https',
    });
  } catch (error) {
    console.error(`[admin-edge-sso] auth_check_failed reason=${error.message}`);
    return { ok: false, reason: 'auth_unavailable' };
  }
  if (response.statusCode === 401 || response.statusCode === 403) return { ok: false, reason: 'invalid_auth' };
  if (response.statusCode < 200 || response.statusCode > 299 || !response.body || response.body.authenticated !== true || !response.body.user) return { ok: false, reason: 'auth_unavailable' };
  const user = response.body.user;
  const email = String(user.email || '').trim().toLowerCase();
  if (site.allowedEmails.length && !site.allowedEmails.includes(email)) return { ok: false, reason: 'forbidden' };
  if (site.requireAdmin && user.is_admin !== true) return { ok: false, reason: 'forbidden' };
  if (site.requiredPermission && !(user.is_admin === true || (user.permissions && user.permissions[site.requiredPermission] === true))) return { ok: false, reason: 'forbidden' };
  return { ok: true, email };
}

async function verifySessionToken(config, site, req, token) {
  const now = Date.now();
  const cacheKey = sessionCacheKey(config, site, token);
  const cached = sessionCache.get(cacheKey);
  if (cached && cached.expiresAt > now) return cached.session;
  pruneSessionCache(now);
  if (sessionRequests.has(cacheKey)) return sessionRequests.get(cacheKey);
  const pending = verifySessionUncached(config, site, req, token);
  sessionRequests.set(cacheKey, pending);
  try {
    const session = await pending;
    if (session.ok) sessionCache.set(cacheKey, { expiresAt: now + SESSION_CACHE_TTL_MS, session });
    return session;
  } finally {
    sessionRequests.delete(cacheKey);
  }
}

async function verifySession(config, site, req) {
  const tokens = cookieValues(req.headers.cookie, config.authCookieName);
  if (!tokens.length) return { ok: false, reason: 'missing_auth' };
  const failures = new Set();
  for (const token of tokens) {
    const session = await verifySessionToken(config, site, req, token);
    if (session.ok) return session;
    failures.add(session.reason);
  }
  if (failures.has('auth_unavailable')) return { ok: false, reason: 'auth_unavailable' };
  if (failures.has('forbidden')) return { ok: false, reason: 'forbidden' };
  return { ok: false, reason: 'invalid_auth' };
}

const tokenCache = new Map();
async function getPortainerJwt(site) {
  const cacheKey = site.publicOrigin;
  const now = Date.now();
  const cached = tokenCache.get(cacheKey);
  if (cached && cached.expiresAt > now) return cached.token;
  const username = process.env[site.upstreamUsernameEnv] || '';
  const password = process.env[site.upstreamPasswordEnv] || '';
  if (!username || !password) throw new Error(`missing upstream credentials for ${site.publicOrigin}`);
  const authUrl = new URL(site.upstreamAuthUrl || '/api/auth', site.upstream);
  const res = await postJson(authUrl, { username, password });
  const token = res.body && res.body.jwt;
  if (res.statusCode !== 200 || !token) throw new Error(`portainer auth failed status=${res.statusCode}`);
  tokenCache.set(cacheKey, { token, expiresAt: now + PORTAINER_TOKEN_TTL_MS });
  return token;
}
function clearPortainerJwt(site) { tokenCache.delete(site.publicOrigin); }

async function injectAuthHeaders(site, headers) {
  const next = { ...headers };
  delete next.cookie;
  delete next.authorization;
  if (site.authMode === 'basic') {
    const username = process.env[site.upstreamUsernameEnv] || '';
    const password = process.env[site.upstreamPasswordEnv] || '';
    if (!username || !password) throw new Error(`missing upstream basic credentials for ${site.publicOrigin}`);
    next.Authorization = `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}`;
    return next;
  }
  if (site.authMode === 'portainer-jwt') {
    next.Authorization = `Bearer ${await getPortainerJwt(site)}`;
    return next;
  }
  throw new Error(`unsupported authMode ${site.authMode}`);
}

function sanitizeProxyHeaders(rawHeaders) {
  const headers = {};
  for (const [key, value] of Object.entries(rawHeaders)) {
    const normalized = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(normalized)) continue;
    if (normalized === 'authorization' || normalized === 'cookie') continue;
    headers[key] = value;
  }
  return headers;
}
function rewriteLocation(location, site) {
  if (location.startsWith('/')) return `${site.publicOrigin}${location}`;
  try {
    const parsed = new URL(location);
    if (parsed.origin === site.upstream.origin) return `${site.publicOrigin}${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {}
  return location;
}
function rewriteResponseHeaders(rawHeaders, site) {
  const headers = {};
  for (const [key, value] of Object.entries(rawHeaders)) {
    const normalized = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(normalized)) continue;
    if (normalized === 'set-cookie' || normalized === 'www-authenticate') continue;
    if (normalized === 'location' && typeof value === 'string') { headers[key] = rewriteLocation(value, site); continue; }
    headers[key] = value;
  }
  return headers;
}

async function proxyHttp(site, req, res, retry = false) {
  const parsed = new URL(req.url || '/', site.publicOrigin);
  let headers = sanitizeProxyHeaders(req.headers);
  headers.host = site.upstream.host;
  headers['x-forwarded-for'] = forwardedFor(req);
  headers['x-forwarded-host'] = resolveHost(req);
  headers['x-forwarded-proto'] = 'https';
  headers['accept-encoding'] = 'identity';
  headers = await injectAuthHeaders(site, headers);
  const client = site.upstream.protocol === 'https:' ? https : http;
  const proxyReq = client.request({
    protocol: site.upstream.protocol,
    hostname: site.upstream.hostname,
    port: site.upstream.port || (site.upstream.protocol === 'https:' ? 443 : 80),
    path: `${parsed.pathname}${parsed.search}`,
    method: req.method,
    headers,
    timeout: 300000,
    rejectUnauthorized: false,
  }, async (proxyRes) => {
    if (site.authMode === 'portainer-jwt' && proxyRes.statusCode === 401 && !retry) {
      clearPortainerJwt(site);
      proxyRes.resume();
      return proxyHttp(site, req, res, true);
    }
    const responseHeaders = rewriteResponseHeaders(proxyRes.headers, site);
    const contentType = String(responseHeaders['content-type'] || '');
    if ((proxyRes.statusCode || 0) === 200 && /^text\/html(?:;|$)/i.test(contentType)) {
      const chunks = [];
      let total = 0;
      proxyRes.on('data', (chunk) => {
        total += chunk.length;
        if (total > MAX_PROXY_HTML_BYTES) {
          proxyRes.destroy(new Error('upstream HTML response too large'));
          return;
        }
        chunks.push(chunk);
      });
      proxyRes.on('end', () => {
        if (res.headersSent || res.destroyed) return;
        const payload = Buffer.from(injectLogoutBridge(Buffer.concat(chunks).toString('utf8')));
        delete responseHeaders['content-encoding'];
        delete responseHeaders.etag;
        delete responseHeaders['last-modified'];
        responseHeaders['content-length'] = payload.length;
        res.writeHead(proxyRes.statusCode || 502, responseHeaders);
        res.end(payload);
      });
      proxyRes.on('error', (error) => {
        console.error(`[admin-edge-sso] upstream_html_error upstream=${site.upstream.origin} message=${error.message}`);
        if (!res.headersSent) sendJson(res, 502, { error: 'upstream_error' });
        else res.destroy(error);
      });
      return;
    }
    res.writeHead(proxyRes.statusCode || 502, responseHeaders);
    proxyRes.pipe(res);
  });
  proxyReq.on('error', (error) => {
    console.error(`[admin-edge-sso] upstream_http_error upstream=${site.upstream.origin} message=${error.message}`);
    if (!res.headersSent) sendJson(res, 502, { error: 'upstream_error' });
    else res.destroy(error);
  });
  proxyReq.on('timeout', () => proxyReq.destroy(new Error('upstream timeout')));
  req.pipe(proxyReq);
}

async function proxyWebSocket(site, req, socket, head, retry = false) {
  let headers = sanitizeProxyHeaders(req.headers);
  headers.connection = 'Upgrade';
  headers.host = site.upstream.host;
  headers.upgrade = req.headers.upgrade || 'websocket';
  headers['x-forwarded-for'] = forwardedFor(req);
  headers['x-forwarded-host'] = resolveHost(req);
  headers['x-forwarded-proto'] = 'https';
  headers = await injectAuthHeaders(site, headers);
  const upstreamPath = req.url || '/';
  const port = Number(site.upstream.port || (site.upstream.protocol === 'https:' ? 443 : 80));
  const connect = site.upstream.protocol === 'https:' ? tls.connect : net.connect;
  const upstreamSocket = connect({ host: site.upstream.hostname, port, servername: site.upstream.hostname, rejectUnauthorized: false });
  upstreamSocket.once('connect', () => {
    const headerLines = Object.entries(headers).flatMap(([key, value]) => Array.isArray(value) ? value.map((entry) => `${key}: ${entry}`) : [`${key}: ${value}`]);
    upstreamSocket.write(`${req.method} ${upstreamPath} HTTP/${req.httpVersion}\r\n`);
    upstreamSocket.write(`${headerLines.join('\r\n')}\r\n\r\n`);
    if (head && head.length) upstreamSocket.write(head);
    upstreamSocket.pipe(socket);
    socket.pipe(upstreamSocket);
  });
  upstreamSocket.on('error', (error) => {
    console.error(`[admin-edge-sso] upstream_ws_error upstream=${site.upstream.origin} message=${error.message}`);
    if (!socket.destroyed) {
      socket.write('HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n');
      socket.destroy();
    }
  });
}

async function handleLogin(config, site, req, res) {
  if (req.method === 'GET') {
    const session = await verifySession(config, site, req);
    if (session.ok) return redirect(res, 302, `${site.publicOrigin}/`);
    return sendHtml(res, 200, loginPage(site));
  }
  if (req.method !== 'POST') {
    res.writeHead(405, { Allow: 'GET, POST' });
    return res.end();
  }
  const rawBody = await readRequestBody(req);
  const body = querystring.parse(rawBody);
  const login = String(body.login || '').trim();
  const senha = String(body.senha || '');
  if (!login || !senha) return sendHtml(res, 400, loginPage(site, 'Informe email ou username e senha.'));
  const tokenUrl = new URL('http://127.0.0.1:8015/v1/token/generate');
  const upstream = await postJson(tokenUrl, { login, senha });
  if (upstream.statusCode === 401 || upstream.statusCode === 403) {
    return sendHtml(res, 401, loginPage(site, 'Não foi possível entrar. Verifique as credenciais.'));
  }
  if (upstream.statusCode !== 200) return sendHtml(res, 503, loginPage(site, 'O serviço de autenticação está temporariamente indisponível.'));
  const setCookies = upstream.headers['set-cookie'];
  const cookieHeaders = [];
  if (Array.isArray(setCookies)) cookieHeaders.push(...setCookies);
  else if (setCookies) cookieHeaders.push(setCookies);
  cookieHeaders.push(clearHostOnlyAuthCookie());
  return redirect(res, 302, `${site.publicOrigin}/`, cookieHeaders.length ? { 'Set-Cookie': cookieHeaders } : {});
}

async function handleLogout(site, res) {
  return redirect(res, 302, `${site.publicOrigin}/login`, { 'Set-Cookie': clearAtiusCookies() });
}

function healthz(res, config) {
  return sendJson(res, 200, { ok: true, sites: Object.keys(config.sites) });
}

async function handleRequest(config, req, res) {
  if (req.url === '/_atius/healthz') return healthz(res, config);
  const resolved = siteForRequest(config, req);
  if (!resolved) return sendJson(res, 404, { error: 'unknown_host' });
  const { site } = resolved;
  const parsed = new URL(req.url || '/', site.publicOrigin);
  if (parsed.pathname === '/_atius/favicon.svg') return sendSvg(res, ATIUS_MARK_SVG);
  if (parsed.pathname === '/_atius/logout-bridge.js') return sendJavaScript(res, logoutBridgeScript());
  if (parsed.pathname === '/sso') return redirect(res, 308, `${site.publicOrigin}${site.loginPath}`);
  if (parsed.pathname === site.loginPath) return handleLogin(config, site, req, res);
  if (parsed.pathname === site.logoutPath) return handleLogout(site, res);
  const session = await verifySession(config, site, req);
  if (!session.ok) {
    if (session.reason === 'auth_unavailable') return sendJson(res, 503, { error: 'atius_sso_unavailable' });
    if (session.reason === 'forbidden') return sendJson(res, 403, { error: 'forbidden' });
    return redirect(res, 302, `${site.publicOrigin}${site.loginPath}`);
  }
  return proxyHttp(site, req, res);
}

async function handleUpgrade(config, req, socket, head) {
  const resolved = siteForRequest(config, req);
  if (!resolved) {
    socket.write('HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n');
    return socket.destroy();
  }
  const { site } = resolved;
  const session = await verifySession(config, site, req);
  if (!session.ok) {
    socket.write(`HTTP/1.1 ${session.reason === 'forbidden' ? '403 Forbidden' : '401 Unauthorized'}\r\nConnection: close\r\n\r\n`);
    return socket.destroy();
  }
  return proxyWebSocket(site, req, socket, head);
}

function main() {
  const config = readConfig();
  const server = http.createServer((req, res) => {
    handleRequest(config, req, res).catch((error) => {
      console.error(`[admin-edge-sso] request_error message=${error.message}`);
      if (!res.headersSent) sendJson(res, 500, { error: 'internal_error' });
      else res.destroy(error);
    });
  });
  server.on('upgrade', (req, socket, head) => {
    handleUpgrade(config, req, socket, head).catch((error) => {
      console.error(`[admin-edge-sso] upgrade_error message=${error.message}`);
      if (!socket.destroyed) {
        socket.write('HTTP/1.1 500 Internal Server Error\r\nConnection: close\r\n\r\n');
        socket.destroy();
      }
    });
  });
  server.listen(config.listenPort, config.listenHost, () => {
    console.log(`[admin-edge-sso] listening=${config.listenHost}:${config.listenPort} sites=${Object.keys(config.sites).join(',')}`);
  });
}

if (require.main === module) main();
module.exports = { injectLogoutBridge, logoutBridgeScript, readConfig, verifySession };
