import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { probeSsoEndpoint, sanitizeLogUrl } from '../src/sso.mjs';

test('Wave 4: SSO Sentinel sanitizes sensitive query params and tokens', () => {
  const dirty = 'https://sso.atius.com.br/login?code=SECRET123&session_state=ABC&return_to=https://trade.atius.io';
  const clean = sanitizeLogUrl(dirty);
  assert.ok(!clean.includes('SECRET123'), 'Must redact authorization code');
  assert.ok(!clean.includes('ABC'), 'Must redact session state');
  assert.ok(clean.includes('trade.atius.io'), 'Preserves safe destination');
});

test('Wave 4: SSO Sentinel probes endpoint and measures latency', async () => {
  const mockServer = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'UP' }));
    } else if (req.url === '/login') {
      res.writeHead(302, { 'Location': 'https://auth.atius.com.br/realms/atius/auth' });
      res.end();
    }
  });

  await new Promise((resolve) => mockServer.listen(0, '127.0.0.1', resolve));
  const port = mockServer.address().port;

  try {
    const healthResult = await probeSsoEndpoint(`http://127.0.0.1:${port}/health`);
    assert.equal(healthResult.status, 200);
    assert.equal(healthResult.healthy, true);
    assert.ok(healthResult.latencyMs >= 0);

    const loginResult = await probeSsoEndpoint(`http://127.0.0.1:${port}/login`);
    assert.equal(loginResult.status, 302);
    assert.equal(loginResult.healthy, true, '302 redirect to OIDC is healthy');
  } finally {
    mockServer.close();
  }
});
