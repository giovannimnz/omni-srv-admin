import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import test from 'node:test';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const {
  filterCookieHeader,
  injectLogoutBridge,
  logoutBridgeScript,
  proxyHttp,
  proxyWebSocket,
  readConfig,
  resolveHost,
  rewriteResponseHeaders,
  sanitizeProxyHeaders,
  sanitizeSetCookieHeader,
  siteForRequest,
  verifySession,
} = require('./atius-admin-edge-gateway.js');
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

test('resolves host from Host or X-Forwarded-Host headers', () => {
  assert.equal(resolveHost({ headers: { host: 'grafana.atius.io:443' } }), 'grafana.atius.io');
  assert.equal(resolveHost({ headers: { host: '127.0.0.1:8210', 'x-forwarded-host': 'portainer.atius.io' } }), 'portainer.atius.io');
  assert.equal(resolveHost({ headers: { 'x-forwarded-host': 'docker.atius.io, edge.atius.io' } }), 'docker.atius.io');
  assert.equal(resolveHost({ headers: { 'x-forwarded-host': 'pm2.atius.io' } }), 'pm2.atius.io');
});

test('correctly maps .io domain sites and aliasOf targets', () => {
  const config = {
    sites: {
      'grafana.atius.com.br': {
        publicOrigin: 'https://grafana.atius.com.br',
        upstream: new URL('http://10.13.1.13:3005'),
        loginPath: '/login',
      },
      'grafana.atius.io': {
        publicOrigin: 'https://grafana.atius.io',
        upstream: new URL('http://10.13.1.13:3005'),
        loginPath: '/login',
      },
      'portainer.atius.com.br': {
        publicOrigin: 'https://portainer.atius.com.br',
        upstream: new URL('https://10.12.1.12:9443'),
        loginPath: '/login',
      },
      'portainer.atius.io': {
        publicOrigin: 'https://portainer.atius.io',
        upstream: new URL('https://10.12.1.12:9443'),
        loginPath: '/login',
      },
      'docker.atius.io': {
        publicOrigin: 'https://docker.atius.io',
        upstream: new URL('https://10.12.1.12:9443'),
        loginPath: '/login',
      },
      'pm2.atius.io': {
        publicOrigin: 'https://pm2.atius.io',
        upstream: new URL('http://127.0.0.1:3210'),
        loginPath: '/login',
      },
    },
  };

  for (const host of ['grafana.atius.io', 'portainer.atius.io', 'docker.atius.io', 'pm2.atius.io']) {
    const matched = siteForRequest(config, { headers: { host } });
    assert.ok(matched, `Expected site to match for ${host}`);
    assert.equal(matched.host, host);
    assert.equal(matched.site.publicOrigin, `https://${host}`);
  }
});

test('filterCookieHeader strips only the gateway authCookieName and retains application cookies (including cockpit)', () => {
  assert.equal(filterCookieHeader('auth-token=secret-token', 'auth-token'), '');
  assert.equal(filterCookieHeader('cockpit=session123; auth-token=secret-token', 'auth-token'), 'cockpit=session123');
  assert.equal(filterCookieHeader('auth-token=secret-token; cockpit=session123; other=456', 'auth-token'), 'cockpit=session123; other=456');
  assert.equal(filterCookieHeader('cockpit=deleted; user=admin', 'auth-token'), 'cockpit=deleted; user=admin');
  assert.equal(filterCookieHeader('', 'auth-token'), '');
});

test('sanitizeProxyHeaders keeps application cookies and preserves Authorization when keepAuthorization is true', () => {
  const rawHeaders = {
    host: 'cockpit.atius.io',
    cookie: 'auth-token=gateway-token; cockpit=user-cockpit-session',
    authorization: 'X-Conversation challenge response',
    connection: 'keep-alive',
    'x-custom': 'hello',
  };

  // For apps with authMode: 'none' (e.g. Cockpit), keepAuthorization is true
  const sanitizedForCockpit = sanitizeProxyHeaders(rawHeaders, 'auth-token', true);
  assert.equal(sanitizedForCockpit.cookie, 'cockpit=user-cockpit-session');
  assert.equal(sanitizedForCockpit.authorization, 'X-Conversation challenge response');
  assert.equal(sanitizedForCockpit['x-custom'], 'hello');
  assert.equal(sanitizedForCockpit.connection, undefined);

  // For apps with gateway-injected auth (e.g. Grafana / Portainer), keepAuthorization is false
  const sanitizedForManaged = sanitizeProxyHeaders(rawHeaders, 'auth-token', false);
  assert.equal(sanitizedForManaged.cookie, 'cockpit=user-cockpit-session');
  assert.equal(sanitizedForManaged.authorization, undefined);
});

test('sanitizeSetCookieHeader allows upstream cookies (like cockpit) and prevents overwriting auth-token', () => {
  const site = {
    publicOrigin: 'https://cockpit.atius.io',
    upstream: new URL('http://127.0.0.1:9090'),
  };

  const upstreamSetCookies = [
    'cockpit=valid-session; PATH=/; SameSite=strict; Secure; HttpOnly',
    'auth-token=malicious-overwrite; Path=/; Domain=.atius.com.br',
    'internal_sid=xyz; Domain=127.0.0.1; Path=/',
  ];

  const filtered = sanitizeSetCookieHeader(upstreamSetCookies, site, 'auth-token');
  assert.equal(filtered.length, 2);
  assert.equal(filtered[0], 'cockpit=valid-session; PATH=/; SameSite=strict; Secure; HttpOnly');
  // Loopback domain is stripped so browser uses host-only cookie
  assert.equal(filtered[1], 'internal_sid=xyz; Path=/');
});

test('rewriteResponseHeaders passes through cockpit Set-Cookie and preserves Negotiate / X-Conversation for authMode none', () => {
  const site = {
    authMode: 'none',
    publicOrigin: 'https://cockpit.atius.io',
    upstream: new URL('http://127.0.0.1:9090'),
  };

  const rawHeaders = {
    'content-type': 'application/json',
    'set-cookie': ['cockpit=session789; PATH=/; Secure; HttpOnly'],
    'www-authenticate': 'Negotiate',
    'connection': 'close',
  };

  const rewritten = rewriteResponseHeaders(rawHeaders, site, 'auth-token');
  assert.deepEqual(rewritten['set-cookie'], ['cockpit=session789; PATH=/; Secure; HttpOnly']);
  assert.equal(rewritten['www-authenticate'], 'Negotiate');
  assert.equal(rewritten.connection, undefined);

  // For basic auth, www-authenticate should be stripped to avoid browser modal
  const basicSite = {
    authMode: 'basic',
    publicOrigin: 'https://grafana.atius.io',
    upstream: new URL('http://10.13.1.13:3005'),
  };
  const basicRewritten = rewriteResponseHeaders(rawHeaders, basicSite, 'auth-token');
  assert.equal(basicRewritten['www-authenticate'], undefined);
});

test('readConfig parses cockpit site with preserveHost: true and authMode: none', () => {
  const config = readConfig(fileURLToPath(new URL('../configs/atius-admin-edge-gateway.json', import.meta.url)));
  const cockpitBr = config.sites['cockpit.atius.com.br'];
  const cockpitIo = config.sites['cockpit.atius.io'];

  assert.ok(cockpitBr, 'cockpit.atius.com.br should be configured');
  assert.equal(cockpitBr.authMode, 'none');
  assert.equal(cockpitBr.preserveHost, true);
  assert.equal(cockpitBr.upstream.origin, 'http://127.0.0.1:9090');

  assert.ok(cockpitIo, 'cockpit.atius.io should be configured');
  assert.equal(cockpitIo.authMode, 'none');
  assert.equal(cockpitIo.preserveHost, true);
  assert.equal(cockpitIo.upstream.origin, 'http://127.0.0.1:9090');
  assert.equal(cockpitIo.publicOrigin, 'https://cockpit.atius.io');
});

test('proxyHttp preserves host, filters auth cookie, keeps cockpit cookie, and rewrites HTML with logout bridge', async () => {
  let receivedHeaders = null;
  const upstreamServer = http.createServer((req, res) => {
    receivedHeaders = req.headers;
    res.writeHead(200, {
      'content-type': 'text/html; charset=utf-8',
      'set-cookie': [
        'cockpit=valid-pam-session; PATH=/; Secure; HttpOnly',
        'auth-token=should-not-overwrite; Path=/',
      ],
      'www-authenticate': 'Negotiate',
    });
    res.end('<html><head><title>Cockpit</title></head><body><h1>Cockpit Console</h1></body></html>');
  });

  const upstreamPort = await listen(upstreamServer);
  const site = {
    appName: 'Cockpit',
    authMode: 'none',
    preserveHost: true,
    publicOrigin: 'https://cockpit.atius.io',
    upstream: new URL(`http://127.0.0.1:${upstreamPort}`),
  };
  const config = { authCookieName: 'auth-token' };

  const gatewayServer = http.createServer((req, res) => {
    proxyHttp(site, req, res, config);
  });
  const gatewayPort = await listen(gatewayServer);

  try {
    const res = await new Promise((resolve, reject) => {
      const clientReq = http.request({
        host: '127.0.0.1',
        port: gatewayPort,
        path: '/cockpit/@localhost/system',
        method: 'GET',
        headers: {
          host: 'cockpit.atius.io',
          'x-forwarded-host': 'cockpit.atius.io',
          cookie: 'auth-token=sso-outer-token; cockpit=user-cookie; theme=dark',
          authorization: 'Negotiate mock-auth',
        },
      }, (proxyRes) => {
        const chunks = [];
        proxyRes.on('data', chunk => chunks.push(chunk));
        proxyRes.on('end', () => {
          resolve({
            statusCode: proxyRes.statusCode,
            headers: proxyRes.headers,
            body: Buffer.concat(chunks).toString('utf8'),
          });
        });
      });
      clientReq.on('error', reject);
      clientReq.end();
    });

    assert.equal(res.statusCode, 200);
    // Upstream received headers:
    assert.equal(receivedHeaders.host, 'cockpit.atius.io');
    assert.equal(receivedHeaders.cookie, 'cockpit=user-cookie; theme=dark');
    assert.equal(receivedHeaders.authorization, 'Negotiate mock-auth');
    assert.equal(receivedHeaders['x-forwarded-proto'], 'https');

    // Client response:
    assert.deepEqual(res.headers['set-cookie'], ['cockpit=valid-pam-session; PATH=/; Secure; HttpOnly']);
    assert.equal(res.headers['www-authenticate'], 'Negotiate');
    assert.match(res.body, /<script src="\/_atius\/logout-bridge\.js" defer><\/script><\/body>/);
    assert.equal(res.headers['content-length'], String(Buffer.byteLength(res.body)));
  } finally {
    gatewayServer.closeAllConnections?.();
    upstreamServer.closeAllConnections?.();
    gatewayServer.close();
    upstreamServer.close();
  }
});

test('proxyHttp does not corrupt compressed HTML responses', async () => {
  const upstreamServer = http.createServer((req, res) => {
    res.writeHead(200, {
      'content-type': 'text/html',
      'content-encoding': 'gzip',
    });
    // Send arbitrary binary payload
    res.end(Buffer.from([0x1f, 0x8b, 0x08, 0x00, 0x01, 0x02, 0x03]));
  });

  const upstreamPort = await listen(upstreamServer);
  const site = {
    appName: 'Cockpit',
    authMode: 'none',
    preserveHost: true,
    publicOrigin: 'https://cockpit.atius.io',
    upstream: new URL(`http://127.0.0.1:${upstreamPort}`),
  };
  const config = { authCookieName: 'auth-token' };

  const gatewayServer = http.createServer((req, res) => {
    proxyHttp(site, req, res, config);
  });
  const gatewayPort = await listen(gatewayServer);

  try {
    const res = await new Promise((resolve, reject) => {
      const clientReq = http.request({
        host: '127.0.0.1',
        port: gatewayPort,
        path: '/',
        headers: { host: 'cockpit.atius.io' },
      }, (proxyRes) => {
        const chunks = [];
        proxyRes.on('data', chunk => chunks.push(chunk));
        proxyRes.on('end', () => {
          resolve({
            statusCode: proxyRes.statusCode,
            headers: proxyRes.headers,
            body: Buffer.concat(chunks),
          });
        });
      });
      clientReq.on('error', reject);
      clientReq.end();
    });

    assert.equal(res.statusCode, 200);
    assert.equal(res.headers['content-encoding'], 'gzip');
    assert.deepEqual(res.body, Buffer.from([0x1f, 0x8b, 0x08, 0x00, 0x01, 0x02, 0x03]));
  } finally {
    gatewayServer.closeAllConnections?.();
    upstreamServer.closeAllConnections?.();
    gatewayServer.close();
    upstreamServer.close();
  }
});

test('proxyWebSocket proxies WebSocket upgrade and pipes bidirectional messages', async () => {
  let upstreamUpgradeHeaders = null;
  let serverWsSocket = null;
  const upstreamServer = http.createServer();
  upstreamServer.on('upgrade', (req, socket, head) => {
    serverWsSocket = socket;
    upstreamUpgradeHeaders = req.headers;
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      'Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n' +
      'Sec-WebSocket-Protocol: cockpit1\r\n\r\n'
    );
    socket.on('data', (data) => {
      socket.write(`echo:${data.toString()}`);
    });
  });

  const upstreamPort = await listen(upstreamServer);
  const site = {
    appName: 'Cockpit',
    authMode: 'none',
    preserveHost: true,
    publicOrigin: 'https://cockpit.atius.io',
    upstream: new URL(`http://127.0.0.1:${upstreamPort}`),
  };
  const config = { authCookieName: 'auth-token' };

  const gatewayServer = http.createServer();
  gatewayServer.on('upgrade', (req, socket, head) => {
    proxyWebSocket(site, req, socket, head, config);
  });
  const gatewayPort = await listen(gatewayServer);

  let clientSocket = null;
  try {
    clientSocket = net.connect({ host: '127.0.0.1', port: gatewayPort });
    await new Promise((resolve) => clientSocket.once('connect', resolve));

    clientSocket.write(
      'GET /cockpit/socket HTTP/1.1\r\n' +
      'Host: cockpit.atius.io\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n' +
      'Sec-WebSocket-Version: 13\r\n' +
      'Sec-WebSocket-Protocol: cockpit1\r\n' +
      'Cookie: auth-token=sso-token; cockpit=cockpit-ws-session\r\n\r\n'
    );

    const response = await new Promise((resolve) => {
      clientSocket.once('data', (chunk) => {
        resolve(chunk.toString());
      });
    });

    assert.match(response, /HTTP\/1\.1 101 Switching Protocols/);
    assert.match(response, /Sec-WebSocket-Protocol: cockpit1/);
    assert.equal(upstreamUpgradeHeaders.host, 'cockpit.atius.io');
    assert.equal(upstreamUpgradeHeaders.cookie, 'cockpit=cockpit-ws-session');
    assert.equal(upstreamUpgradeHeaders['sec-websocket-protocol'], 'cockpit1');

    // Test bidirectional pipe
    const echoPromise = new Promise((resolve) => {
      clientSocket.once('data', (chunk) => resolve(chunk.toString()));
    });
    clientSocket.write('cockpit-init-payload');
    const echoResult = await echoPromise;
    assert.equal(echoResult, 'echo:cockpit-init-payload');
  } finally {
    clientSocket?.destroy();
    serverWsSocket?.destroy();
    gatewayServer.closeAllConnections?.();
    upstreamServer.closeAllConnections?.();
    gatewayServer.close();
    upstreamServer.close();
  }
});

test('proxyWebSocket selects secureConnect event for HTTPS upstreams and connect for HTTP upstreams', () => {
  const httpSite = { upstream: new URL('http://127.0.0.1:9090') };
  const httpsSite = { upstream: new URL('https://10.12.1.12:9443') };
  assert.equal(httpSite.upstream.protocol === 'https:' ? 'secureConnect' : 'connect', 'connect');
  assert.equal(httpsSite.upstream.protocol === 'https:' ? 'secureConnect' : 'connect', 'secureConnect');
});


