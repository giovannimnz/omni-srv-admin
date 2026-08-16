#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { mkdtempSync, rmSync, writeFileSync } = require('node:fs');
const { handleRequest, injectLogoutBridge, redirectToSso } = require('./mt5-remote-auth-proxy.js');

function responseCapture() {
  return {
    ended: false,
    headers: null,
    statusCode: null,
    end() { this.ended = true; },
    writeHead(statusCode, headers) {
      this.statusCode = statusCode;
      this.headers = headers;
    },
  };
}

const config = { publicOrigin: 'https://remote.atius.com.br' };
const req = { url: '/mt5/1/' };
const res = responseCapture();
redirectToSso(config, req, res);

assert.equal(res.statusCode, 302);
assert.equal(res.headers.Location, '/login');
assert.match(res.headers['Set-Cookie'], /^atius_sso_login_return_to=https%3A%2F%2Fremote\.atius\.com\.br%2Fmt5%2F1%2F;/);
assert.match(res.headers['Set-Cookie'], /Max-Age=600; Secure; HttpOnly; SameSite=Lax$/);
assert.equal(res.ended, true);

console.log('mt5_remote_sso_url_contract=PASS');

async function testDefaultRoute() {
  const defaultResponse = responseCapture();
  await handleRequest({
    defaultRouteId: '1',
    routes: { '1': { basePath: '/mt5/1' } },
  }, { url: '/', headers: {} }, defaultResponse);
  assert.equal(defaultResponse.statusCode, 302);
  assert.equal(defaultResponse.headers.Location, '/mt5/1/');
  assert.equal(defaultResponse.ended, true);
  console.log('mt5_remote_default_route_contract=PASS');
}

testDefaultRoute().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

const bridged = injectLogoutBridge('<html><body><main>noVNC</main></body></html>');
assert.match(bridged, /data-atius-sso-logout/);
assert.match(bridged, /Sair do Atius SSO/);

async function testLogout() {
  const logoutResponse = responseCapture();
  await handleRequest({ routes: {} }, { url: '/logout', headers: {} }, logoutResponse);
  assert.equal(logoutResponse.statusCode, 302);
  assert.equal(logoutResponse.headers.Location, '/login');
  assert.match(String(logoutResponse.headers['Set-Cookie']), /auth-token=.*Max-Age=0/);
  console.log('mt5_remote_logout_contract=PASS');
}

testLogout().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

function asyncResponseCapture() {
  let resolveDone;
  const done = new Promise((resolve) => { resolveDone = resolve; });
  return {
    body: [],
    done,
    ended: false,
    headers: null,
    statusCode: null,
    end(chunk) {
      if (chunk) this.body.push(Buffer.from(chunk));
      this.ended = true;
      resolveDone(this);
    },
    write(chunk) { if (chunk) this.body.push(Buffer.from(chunk)); },
    writeHead(statusCode, headers) {
      this.statusCode = statusCode;
      this.headers = headers;
    },
  };
}

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
  });
}

async function close(server) {
  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}

async function testSessionCacheCoalescing() {
  let authHits = 0;
  const authServer = http.createServer((authReq, authRes) => {
    authHits += 1;
    setTimeout(() => {
      authRes.writeHead(200, { 'Content-Type': 'application/json' });
      authRes.end(JSON.stringify({
        authenticated: true,
        user: { id: 42, is_admin: true, permissions: {} },
      }));
    }, 50);
  });
  const staticRoot = mkdtempSync(path.join(os.tmpdir(), 'mt5-remote-auth-test-'));
  writeFileSync(path.join(staticRoot, 'index.html'), '<html><body>noVNC</body></html>');

  try {
    const port = await listen(authServer);
    const token = `shared-token-${Date.now()}`;
    const cachedConfig = {
      authCheckUrl: new URL(`http://127.0.0.1:${port}/v1/auth/me`),
      authCookieName: 'auth-token',
      defaultRouteId: '1',
      publicOrigin: 'https://remote.atius.com.br',
      routes: {
        1: {
          basePath: '/mt5/1',
          requiredPermission: null,
          staticRoot,
        },
      },
    };
    const req = () => ({
      headers: { cookie: `auth-token=${token}` },
      socket: { remoteAddress: '127.0.0.1' },
      url: '/mt5/1/',
    });

    const first = asyncResponseCapture();
    const second = asyncResponseCapture();
    await Promise.all([
      handleRequest(cachedConfig, req(), first),
      handleRequest(cachedConfig, req(), second),
    ]);
    await Promise.all([first.done, second.done]);
    assert.equal(first.statusCode, 200);
    assert.equal(second.statusCode, 200);
    assert.equal(authHits, 1);

    const third = asyncResponseCapture();
    await handleRequest(cachedConfig, req(), third);
    await third.done;
    assert.equal(third.statusCode, 200);
    assert.equal(authHits, 1);

    const logout = asyncResponseCapture();
    await handleRequest(cachedConfig, {
      headers: { cookie: `auth-token=${token}` },
      socket: { remoteAddress: '127.0.0.1' },
      url: '/logout',
    }, logout);
    await logout.done;

    const afterLogout = asyncResponseCapture();
    await handleRequest(cachedConfig, req(), afterLogout);
    await afterLogout.done;
    assert.equal(afterLogout.statusCode, 200);
    assert.equal(authHits, 2);
    console.log('mt5_remote_auth_cache_coalescing=PASS');
  } finally {
    await close(authServer);
    rmSync(staticRoot, { force: true, recursive: true });
  }
}

testSessionCacheCoalescing().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});