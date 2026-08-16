#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';

const hosts = Object.freeze([
  'ssh.atius.com.br',
  'rdp.atius.com.br',
  'oci.atius.com.br',
  'grafana.atius.com.br',
  'portainer.atius.com.br',
  'docker.atius.com.br',
  'vpn.atius.com.br',
  'adguard.atius.com.br',
  'remote.atius.com.br',
  'talk.atius.com.br',
  'admin.talk.atius.com.br',
]);

const activeSources = Object.freeze([
  '/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts',
  '/home/ubuntu/GitHub/vpn-atius/home-proxy/modules/casa-remote-gateway/scripts/casa-remote-auth-gateway.js',
  '/home/ubuntu/GitHub/vpn-atius/home-proxy/modules/casa-remote-gateway/configs/casa-remote-gateway.json',
  '/home/ubuntu/GitHub/vpn-atius/home-proxy/modules/casa-remote-gateway/configs/rdp-remote-gateway.json',
  '/home/ubuntu/GitHub/omni-srv-admin/modules/mt5-remote-auth/scripts/mt5-remote-auth-proxy.js',
  '/home/ubuntu/GitHub/omni-srv-admin/modules/mt5-remote-auth/configs/mt5-remote-auth-proxy.json',
  '/home/ubuntu/GitHub/omni-srv-admin/modules/mt5-remote-auth/apache/remote.atius.com.br.sso.conf',
  '/home/ubuntu/GitHub/omni-srv-admin/modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js',
  '/home/ubuntu/GitHub/vpn-atius/web/frontend/src/proxy.ts',
  '/home/ubuntu/GitHub/vpn-atius/home-proxy/modules/home-router-be3/scripts/adguard-portal-gateway.cjs',
]);

const read = (file) => fs.readFileSync(file, 'utf8');
const source = Object.fromEntries(activeSources.map((file) => [file, read(file)]));

const atsMiddleware = source[activeSources[0]];
assert.match(atsMiddleware, /APP_LOCAL_SSO_DEFAULT_DESTINATIONS/);
assert.match(atsMiddleware, /pathname === '\/sso'/);
assert.match(atsMiddleware, /SSO_LOGIN_RETURN_TO_COOKIE/);
assert.match(atsMiddleware, /NextResponse\.redirect\(loginUrl, 307\)/);
assert.match(atsMiddleware, /NextResponse\.redirect\(loginUrl, 308\)/);
assert.match(atsMiddleware, /response\.cookies\.set\(SSO_LOGIN_RETURN_TO_COOKIE/);

for (const file of [activeSources[1], activeSources[2], activeSources[3], activeSources[4], activeSources[5], activeSources[6]]) {
  const content = source[file];
  assert.doesNotMatch(
    content,
    /\/sso\?return_to=|function buildLoginRedirect\b/,
    `${file} still generates a browser-facing return_to query`,
  );
}

const casaConfig = JSON.parse(source[activeSources[2]]);
assert.equal(casaConfig.ssoLoginUrl, 'https://ssh.atius.com.br/login');
const rdpConfig = JSON.parse(source[activeSources[3]]);
assert.equal(rdpConfig.ssoLoginUrl, 'https://rdp.atius.com.br/login');
assert.equal(Object.hasOwn(rdpConfig, 'ssoReturnTo'), false);
const mt5Config = JSON.parse(source[activeSources[5]]);
assert.equal(mt5Config.ssoLoginUrl, 'https://remote.atius.com.br/login');
assert.doesNotMatch(source[activeSources[6]], /sso\.atius\.com\.br\/login\?return_to=/);

if (process.argv.includes('--live')) {
  for (const host of hosts) {
    const login = await fetch(`https://${host}/login`, { redirect: 'manual' });
    assert.ok([200, 302, 303, 307, 308].includes(login.status), `${host}/login status=${login.status}`);
    if (login.status >= 300 && login.status < 400) {
      const location = new URL(login.headers.get('location'), `https://${host}`);
      assert.equal(location.origin, `https://${host}`, `${host}/login crossed origin`);
      assert.equal(location.search, '', `${host}/login exposed query state`);
    }

    const compatibility = await fetch(
      `https://${host}/sso?return_to=${encodeURIComponent(`https://${host}/`)}`,
      { redirect: 'manual' },
    );
    assert.ok([307, 308].includes(compatibility.status), `${host}/sso status=${compatibility.status}`);
    const location = new URL(compatibility.headers.get('location'), `https://${host}`);
    assert.equal(location.origin, `https://${host}`, `${host}/sso crossed origin`);
    assert.equal(location.pathname, '/login', `${host}/sso did not canonicalize to /login`);
    assert.equal(location.search, '', `${host}/sso retained query state`);
  }
}

console.log(`atius_sso_url_contract=PASS hosts=${hosts.length}`);
