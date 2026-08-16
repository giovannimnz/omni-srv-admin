import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import http from 'node:http';
import test from 'node:test';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { injectLogoutBridge, logoutBridgeScript, verifySession } = require('./atius-admin-edge-gateway.js');
const gatewaySource = readFileSync(new URL('./atius-admin-edge-gateway.js', import.meta.url), 'utf8');

function listen(server) {
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
}

test('injects the host-local logout bridge before body close', () => {
  const result = injectLogoutBridge('<html><body><main>app</main></body></html>');
  assert.match(result, /<script src="\/_atius\/logout-bridge\.js" defer><\/script><\/body>/);
});

test('does not inject the bridge twice', () => {
  const once = injectLogoutBridge('<html><body>app</body></html>');
  assert.equal(injectLogoutBridge(once), once);
});

test('bridge exposes a visible app logout control targeting local /logout', () => {
  const script = logoutBridgeScript();
  assert.match(script, /link\.href = '\/logout'/);
  assert.match(script, /data-atius-sso-logout/);
  assert.match(script, /Sair do Atius SSO/);
  assert.match(script, /a\[href="#!\/logout"\]/);
  assert.match(script, /link\.addEventListener\('click'/);
  assert.match(script, /window\.location\.assign\('\/logout'\)/);
  assert.doesNotMatch(script, /sso\.atius\.com\.br/);
});

test('compatibility /sso redirects to clean app-local /login', () => {
  assert.match(gatewaySource, /parsed\.pathname === '\/sso'/);
  assert.match(gatewaySource, /redirect\(res, 308, `\$\{site\.publicOrigin\}\$\{site\.loginPath\}`\)/);
  assert.doesNotMatch(gatewaySource, /parsed\.pathname === site\.loginPath \|\| parsed\.pathname === '\/sso'/);
});

test('login typography matches the canonical Atius SSO weights and sizes', () => {
  assert.match(gatewaySource, /\.dest small\{[^}]*font-size:11px;[^}]*font-weight:400;[^}]*line-height:16\.5px;[^}]*letter-spacing:normal/);
  assert.match(gatewaySource, /\.dest-row\{[^}]*font-size:14px;[^}]*font-weight:400;[^}]*line-height:20px/);
  assert.match(gatewaySource, /label\{[^}]*font-size:14px;[^}]*font-weight:500;[^}]*line-height:20px/);
  assert.doesNotMatch(gatewaySource, /\.dest-row\{[^}]*font-weight:600|label\{[^}]*font-weight:650/);
});

test('active login renderer matches the SSH SSO visual contract and serves Atius favicon', () => {
  const canonical = gatewaySource.slice(gatewaySource.indexOf('const CANONICAL_LOGIN_CSS ='));
  assert.match(gatewaySource, /return renderCanonicalLoginShell/);
  assert.match(canonical, /linear-gradient\(135deg,#1a1a1a 0%,#1f1f1f 50%,#1a1a1a 100%\)/);
  assert.match(canonical, /\.card\{width:min\(448px,100%\)/);
  assert.match(canonical, /\.brand-mark\{display:block;width:44px;height:44px/);
  assert.match(canonical, /\.control\{position:relative;margin-top:8px\}/);
  assert.match(canonical, /\.submit\{[^}]*font-size:14px;font-weight:500;line-height:20px/);
  assert.match(canonical, /<link rel="icon" href="\/_atius\/favicon\.svg"/);
  assert.match(canonical, /parsed\.pathname === '\/_atius\/favicon\.svg'/);
  assert.doesNotMatch(canonical, /👤|🔒|👁/);
});

test('reuses a short positive session validation cache for the same token and site', async () => {
  let requests = 0;
  const auth = http.createServer((_req, res) => {
    requests += 1;
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ authenticated: true, user: { email: 'owner@example.test', is_admin: true } }));
  });
  const port = await listen(auth);
  try {
    const config = { authCheckUrl: new URL(`http://127.0.0.1:${port}/v1/auth/me`), authCookieName: 'auth-token' };
    const site = { allowedEmails: ['owner@example.test'], publicOrigin: 'https://grafana.atius.com.br', requireAdmin: true, requiredPermission: null };
    const req = { headers: { cookie: 'auth-token=cache-test-token' }, socket: { remoteAddress: '127.0.0.1' } };
    assert.equal((await verifySession(config, site, req)).ok, true);
    assert.equal((await verifySession(config, site, req)).ok, true);
    assert.equal(requests, 1);
  } finally {
    await new Promise((resolve) => auth.close(resolve));
  }
});

test('accepts a valid domain session when a duplicate legacy host-only cookie is also present', async () => {
  const seen = [];
  const auth = http.createServer((req, res) => {
    seen.push(req.headers.cookie);
    const valid = req.headers.cookie === 'auth-token=valid-domain-token';
    res.writeHead(valid ? 200 : 401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(valid
      ? { authenticated: true, user: { email: 'owner@example.test', is_admin: true } }
      : { error: 'unauthorized' }));
  });
  const port = await listen(auth);
  try {
    const config = { authCheckUrl: new URL(`http://127.0.0.1:${port}/v1/auth/me`), authCookieName: 'auth-token' };
    const site = { allowedEmails: ['owner@example.test'], publicOrigin: 'https://grafana.atius.com.br', requireAdmin: true, requiredPermission: null };
    const req = { headers: { cookie: 'auth-token=valid-domain-token; auth-token=stale-host-token' }, socket: { remoteAddress: '127.0.0.1' } };
    assert.equal((await verifySession(config, site, req)).ok, true);
    assert.deepEqual(seen, ['auth-token=valid-domain-token']);
  } finally {
    await new Promise((resolve) => auth.close(resolve));
  }
});

test('accepts a valid domain session when a duplicate stale host-only cookie appears first', async () => {
  const seen = [];
  const auth = http.createServer((req, res) => {
    seen.push(req.headers.cookie);
    const valid = req.headers.cookie === 'auth-token=valid-domain-token';
    res.writeHead(valid ? 200 : 401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(valid
      ? { authenticated: true, user: { email: 'owner@example.test', is_admin: true } }
      : { error: 'unauthorized' }));
  });
  const port = await listen(auth);
  try {
    const config = { authCheckUrl: new URL(`http://127.0.0.1:${port}/v1/auth/me`), authCookieName: 'auth-token' };
    const site = { allowedEmails: ['owner@example.test'], publicOrigin: 'https://grafana.atius.com.br', requireAdmin: true, requiredPermission: null };
    const req = { headers: { cookie: 'auth-token=stale-host-token; auth-token=valid-domain-token' }, socket: { remoteAddress: '127.0.0.1' } };
    assert.equal((await verifySession(config, site, req)).ok, true);
    assert.deepEqual(seen, ['auth-token=stale-host-token', 'auth-token=valid-domain-token']);
  } finally {
    await new Promise((resolve) => auth.close(resolve));
  }
});

