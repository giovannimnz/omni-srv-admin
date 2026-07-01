#!/usr/bin/env node
'use strict';

const fs = require('fs');
const http = require('http');
const https = require('https');
const net = require('net');
const path = require('path');
const tls = require('tls');

const DEFAULT_CONFIG_PATH = '/etc/atius/mt5-remote-auth-proxy.json';
const DEFAULT_STATIC_ROOT = '/var/www/remote-mt5';
const MAX_AUTH_RESPONSE_BYTES = 64 * 1024;
const STATIC_PREFIXES = new Set(['app', 'core', 'include', 'utils', 'vendor']);
const STATIC_FILES = new Set(['auth.html', 'index.html', 'vnc.html', 'vnc_lite.html']);
const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

const MIME_TYPES = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.gif', 'image/gif'],
  ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.map', 'application/json; charset=utf-8'],
  ['.mp3', 'audio/mpeg'],
  ['.oga', 'audio/ogg'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml; charset=utf-8'],
  ['.ttf', 'font/ttf'],
  ['.txt', 'text/plain; charset=utf-8'],
  ['.wasm', 'application/wasm'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

function readConfig() {
  const configPath = process.env.MT5_REMOTE_AUTH_PROXY_CONFIG || process.argv[2] || DEFAULT_CONFIG_PATH;
  const rawConfig = fs.readFileSync(configPath, 'utf8');
  const config = JSON.parse(rawConfig);

  if (!config.authCheckUrl || !config.publicOrigin || !config.ssoLoginUrl) {
    throw new Error('config requires authCheckUrl, publicOrigin, and ssoLoginUrl');
  }

  if (!config.routes || typeof config.routes !== 'object' || Array.isArray(config.routes)) {
    throw new Error('config requires routes object keyed by MT5 id');
  }

  const routes = {};
  for (const [id, route] of Object.entries(config.routes)) {
    if (!/^[A-Za-z0-9_-]+$/.test(id)) {
      throw new Error(`invalid route id: ${id}`);
    }
    if (!route.upstream) {
      throw new Error(`route ${id} requires upstream`);
    }

    routes[id] = {
      basePath: normalizeBasePath(route.basePath || `/mt5/${id}`),
      requiredPermission: route.requiredPermission || null,
      staticRoot: route.staticRoot || config.staticRoot || DEFAULT_STATIC_ROOT,
      upstream: new URL(route.upstream),
    };
  }

  return {
    authCheckUrl: new URL(config.authCheckUrl),
    authCookieName: config.authCookieName || 'auth-token',
    listenHost: config.listenHost || '127.0.0.1',
    listenPort: Number(config.listenPort || 8095),
    publicOrigin: stripTrailingSlash(config.publicOrigin),
    routes,
    ssoLoginUrl: new URL(config.ssoLoginUrl),
  };
}

function normalizeBasePath(value) {
  const normalized = `/${String(value || '').replace(/^\/+|\/+$/g, '')}`;
  if (!/^\/mt5\/[A-Za-z0-9_-]+$/.test(normalized)) {
    throw new Error(`invalid MT5 basePath: ${value}`);
  }
  return normalized;
}

function stripTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function jsonResponse(res, statusCode, body) {
  const payload = Buffer.from(JSON.stringify(body));
  res.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Length': payload.length,
    'Content-Type': 'application/json; charset=utf-8',
  });
  res.end(payload);
}

function textResponse(res, statusCode, body, headers = {}) {
  const payload = Buffer.from(body);
  res.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Length': payload.length,
    'Content-Type': 'text/plain; charset=utf-8',
    ...headers,
  });
  res.end(payload);
}

function parseRequestUrl(req) {
  return new URL(req.url || '/', 'http://mt5-remote-auth.local');
}

function routeForPath(config, pathname) {
  const match = pathname.match(/^\/mt5\/([A-Za-z0-9_-]+)(?:\/|$)/);
  if (!match) {
    return null;
  }
  const id = match[1];
  const route = config.routes[id];
  return route ? { id, route } : { id, route: null };
}

function parseCookies(cookieHeader) {
  const cookies = new Map();
  for (const part of String(cookieHeader || '').split(';')) {
    const index = part.indexOf('=');
    if (index === -1) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    if (key) cookies.set(key, value);
  }
  return cookies;
}

function buildReturnTo(config, req) {
  const rawUrl = req.url || '/';
  const safeUrl = rawUrl.startsWith('/mt5/') ? rawUrl : '/mt5/';
  return `${config.publicOrigin}${safeUrl}`;
}

function buildLoginRedirect(config, req) {
  const loginUrl = new URL(config.ssoLoginUrl.toString());
  loginUrl.searchParams.set('return_to', buildReturnTo(config, req));
  return loginUrl.toString();
}

function redirectToSso(config, req, res) {
  const location = buildLoginRedirect(config, req);
  res.writeHead(302, {
    'Cache-Control': 'no-store',
    Location: location,
  });
  res.end();
}

function websocketReject(socket, statusCode, reason) {
  const payload = Buffer.from(`${reason}\n`);
  socket.write([
    `HTTP/1.1 ${statusCode} ${reason}`,
    'Connection: close',
    'Cache-Control: no-store',
    'Content-Type: text/plain; charset=utf-8',
    `Content-Length: ${payload.length}`,
    '',
    '',
  ].join('\r\n'));
  socket.write(payload);
  socket.destroy();
}

async function verifySession(config, route, req) {
  const cookies = parseCookies(req.headers.cookie);
  const token = cookies.get(config.authCookieName);
  if (!token) {
    return { ok: false, reason: 'missing_auth' };
  }

  let response;
  try {
    response = await requestJson(config.authCheckUrl, {
      Cookie: `${config.authCookieName}=${token}`,
      'X-Forwarded-For': forwardedFor(req),
      'X-Forwarded-Host': new URL(config.publicOrigin).host,
      'X-Forwarded-Proto': new URL(config.publicOrigin).protocol.replace(':', ''),
    });
  } catch (error) {
    console.error(`[mt5-auth] auth_check_failed status=error message=${error.message}`);
    return { ok: false, reason: 'auth_unavailable' };
  }

  if (response.statusCode === 401 || response.statusCode === 403) {
    return { ok: false, reason: 'invalid_auth' };
  }

  if (response.statusCode < 200 || response.statusCode > 299) {
    console.error(`[mt5-auth] auth_check_failed status=${response.statusCode}`);
    return { ok: false, reason: 'auth_unavailable' };
  }

  const user = response.body && response.body.user;
  if (!response.body || response.body.authenticated !== true || !user) {
    return { ok: false, reason: 'invalid_auth' };
  }

  const requiredPermission = route.requiredPermission;
  const isAllowed =
    !requiredPermission ||
    user.is_admin === true ||
    (user.permissions && user.permissions[requiredPermission] === true);

  if (!isAllowed) {
    return { ok: false, reason: 'forbidden', userId: user.id || null };
  }

  return { ok: true, userId: user.id || null };
}

function requestJson(targetUrl, headers) {
  return new Promise((resolve, reject) => {
    const client = targetUrl.protocol === 'https:' ? https : http;
    const req = client.request({
      headers: {
        Accept: 'application/json',
        ...headers,
      },
      hostname: targetUrl.hostname,
      method: 'GET',
      path: `${targetUrl.pathname}${targetUrl.search}`,
      port: targetUrl.port || (targetUrl.protocol === 'https:' ? 443 : 80),
      protocol: targetUrl.protocol,
      timeout: 5000,
    }, (res) => {
      const chunks = [];
      let total = 0;
      res.on('data', (chunk) => {
        total += chunk.length;
        if (total > MAX_AUTH_RESPONSE_BYTES) {
          req.destroy(new Error('auth response too large'));
          return;
        }
        chunks.push(chunk);
      });
      res.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        let body = null;
        if (raw.trim()) {
          try {
            body = JSON.parse(raw);
          } catch (error) {
            return reject(new Error(`auth response is not JSON: ${error.message}`));
          }
        }
        resolve({ body, statusCode: res.statusCode || 0 });
      });
    });

    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('auth request timeout')));
    req.end();
  });
}

function forwardedFor(req) {
  const existing = String(req.headers['x-forwarded-for'] || '').trim();
  const remote = req.socket.remoteAddress || '';
  return existing ? `${existing}, ${remote}` : remote;
}

function innerRoutePath(pathname, route) {
  if (pathname === route.basePath) return '/';
  const prefix = `${route.basePath}/`;
  if (!pathname.startsWith(prefix)) return null;
  return pathname.slice(route.basePath.length) || '/';
}

function staticRelativePath(pathname, route) {
  const innerPath = innerRoutePath(pathname, route);
  if (innerPath === null) return null;
  let relPath = innerPath.replace(/^\/+/, '');
  if (!relPath) return 'index.html';
  if (relPath === 'auth' || relPath === 'auth/') return 'auth.html';
  if (relPath.endsWith('/')) relPath = `${relPath}index.html`;

  const firstSegment = relPath.split('/', 1)[0];
  if (STATIC_PREFIXES.has(firstSegment) || STATIC_FILES.has(relPath)) {
    return relPath;
  }

  return null;
}

function safeResolve(root, relPath) {
  const normalizedRoot = path.resolve(root);
  const resolved = path.resolve(normalizedRoot, relPath);
  if (resolved !== normalizedRoot && !resolved.startsWith(`${normalizedRoot}${path.sep}`)) {
    return null;
  }
  return resolved;
}

function sendStatic(req, res, route, relPath) {
  const filePath = safeResolve(route.staticRoot, decodeURIComponent(relPath));
  if (!filePath) {
    textResponse(res, 403, 'Forbidden');
    return true;
  }

  let stat;
  try {
    stat = fs.statSync(filePath);
  } catch {
    textResponse(res, 404, 'Not Found');
    return true;
  }

  if (!stat.isFile()) {
    textResponse(res, 404, 'Not Found');
    return true;
  }

  const ext = path.extname(filePath);
  const contentType = MIME_TYPES.get(ext.toLowerCase()) || 'application/octet-stream';
  const headers = {
    'Cache-Control': relPath === 'index.html' || relPath === 'auth.html' ? 'no-store' : 'public, max-age=3600',
    'Content-Length': stat.size,
    'Content-Type': contentType,
  };

  if (relPath === 'index.html') {
    const html = fs.readFileSync(filePath, 'utf8').replaceAll('/mt5/1', route.basePath);
    const payload = Buffer.from(html);
    res.writeHead(200, {
      ...headers,
      'Cache-Control': 'no-store',
      'Content-Length': payload.length,
    });
    if (req.method === 'HEAD') {
      res.end();
    } else {
      res.end(payload);
    }
    return true;
  }

  res.writeHead(200, headers);
  if (req.method === 'HEAD') {
    res.end();
    return true;
  }

  fs.createReadStream(filePath).pipe(res);
  return true;
}

function proxyHttp(req, res, route, parsedUrl) {
  const upstreamPath = upstreamRequestPath(parsedUrl, route);
  const headers = sanitizeProxyHeaders(req.headers);
  headers.host = route.upstream.host;
  headers['x-forwarded-for'] = forwardedFor(req);
  headers['x-forwarded-host'] = req.headers['x-forwarded-host'] || req.headers.host || '';
  headers['x-forwarded-proto'] = req.headers['x-forwarded-proto'] || 'https';

  const client = route.upstream.protocol === 'https:' ? https : http;
  const proxyReq = client.request({
    headers,
    hostname: route.upstream.hostname,
    method: req.method,
    path: upstreamPath,
    port: route.upstream.port || (route.upstream.protocol === 'https:' ? 443 : 80),
    protocol: route.upstream.protocol,
    timeout: 300000,
  }, (proxyRes) => {
    const responseHeaders = rewriteResponseHeaders(proxyRes.headers, route);
    res.writeHead(proxyRes.statusCode || 502, responseHeaders);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (error) => {
    console.error(`[mt5-auth] upstream_http_error upstream=${route.upstream.origin} message=${error.message}`);
    if (!res.headersSent) {
      jsonResponse(res, 502, { error: 'upstream_error' });
    } else {
      res.destroy(error);
    }
  });
  proxyReq.on('timeout', () => proxyReq.destroy(new Error('upstream timeout')));
  req.pipe(proxyReq);
}

function upstreamRequestPath(parsedUrl, route) {
  const innerPath = innerRoutePath(parsedUrl.pathname, route) || '/';
  const normalizedPath = innerPath === '/' ? '/' : innerPath;
  return `${normalizedPath}${parsedUrl.search}`;
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

function rewriteResponseHeaders(rawHeaders, route) {
  const headers = {};
  for (const [key, value] of Object.entries(rawHeaders)) {
    const normalized = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(normalized)) continue;

    if (normalized === 'location' && typeof value === 'string') {
      headers[key] = rewriteLocation(value, route);
      continue;
    }

    if (normalized === 'set-cookie') {
      const cookies = Array.isArray(value) ? value : [value];
      headers[key] = cookies.map((cookie) => String(cookie).replace(/;\s*Path=\//i, `; Path=${route.basePath}/`));
      continue;
    }

    headers[key] = value;
  }
  return headers;
}

function rewriteLocation(location, route) {
  if (location.startsWith('/')) {
    return `${route.basePath}${location}`;
  }

  try {
    const parsed = new URL(location);
    if (parsed.origin === route.upstream.origin) {
      return `${route.basePath}${parsed.pathname}${parsed.search}`;
    }
  } catch {
    return location;
  }

  return location;
}

async function handleRequest(config, req, res) {
  const parsedUrl = parseRequestUrl(req);

  if (parsedUrl.pathname === '/healthz') {
    jsonResponse(res, 200, {
      ok: true,
      routeCount: Object.keys(config.routes).length,
    });
    return;
  }

  const matched = routeForPath(config, parsedUrl.pathname);
  if (!matched) {
    textResponse(res, 404, 'Not Found');
    return;
  }

  if (!matched.route) {
    textResponse(res, 404, `Unknown MT5 route: ${matched.id}`);
    return;
  }

  const auth = await verifySession(config, matched.route, req);
  if (!auth.ok) {
    if (auth.reason === 'missing_auth' || auth.reason === 'invalid_auth') {
      redirectToSso(config, req, res);
      return;
    }
    if (auth.reason === 'forbidden') {
      textResponse(res, 403, 'Forbidden');
      return;
    }
    jsonResponse(res, 503, { error: 'auth_unavailable' });
    return;
  }

  const relPath = staticRelativePath(parsedUrl.pathname, matched.route);
  if (relPath) {
    sendStatic(req, res, matched.route, relPath);
    return;
  }

  proxyHttp(req, res, matched.route, parsedUrl);
}

async function handleUpgrade(config, req, socket, head) {
  const parsedUrl = parseRequestUrl(req);
  const matched = routeForPath(config, parsedUrl.pathname);

  if (!matched || !matched.route) {
    websocketReject(socket, 404, 'Not Found');
    return;
  }

  const auth = await verifySession(config, matched.route, req);
  if (!auth.ok) {
    websocketReject(socket, auth.reason === 'forbidden' ? 403 : 401, auth.reason === 'forbidden' ? 'Forbidden' : 'Unauthorized');
    return;
  }

  proxyWebSocket(req, socket, head, matched.route, parsedUrl);
}

function proxyWebSocket(req, socket, head, route, parsedUrl) {
  const upstreamPath = upstreamRequestPath(parsedUrl, route);
  const port = Number(route.upstream.port || (route.upstream.protocol === 'https:' ? 443 : 80));
  const connect = route.upstream.protocol === 'https:' ? tls.connect : net.connect;
  const upstreamSocket = connect({
    host: route.upstream.hostname,
    port,
    servername: route.upstream.hostname,
  });

  upstreamSocket.once('connect', () => {
    const headers = sanitizeProxyHeaders(req.headers);
    headers.connection = 'Upgrade';
    headers.host = route.upstream.host;
    headers.upgrade = req.headers.upgrade || 'websocket';
    headers['x-forwarded-for'] = forwardedFor(req);
    headers['x-forwarded-host'] = req.headers['x-forwarded-host'] || req.headers.host || '';
    headers['x-forwarded-proto'] = req.headers['x-forwarded-proto'] || 'https';

    const headerLines = Object.entries(headers).flatMap(([key, value]) => {
      if (Array.isArray(value)) {
        return value.map((entry) => `${key}: ${entry}`);
      }
      return [`${key}: ${value}`];
    });

    upstreamSocket.write(`${req.method} ${upstreamPath} HTTP/${req.httpVersion}\r\n`);
    upstreamSocket.write(`${headerLines.join('\r\n')}\r\n\r\n`);
    if (head && head.length) upstreamSocket.write(head);
    upstreamSocket.pipe(socket);
    socket.pipe(upstreamSocket);
  });

  upstreamSocket.on('error', (error) => {
    console.error(`[mt5-auth] upstream_ws_error upstream=${route.upstream.origin} message=${error.message}`);
    if (!socket.destroyed) {
      websocketReject(socket, 502, 'Bad Gateway');
    }
  });
}

function main() {
  const config = readConfig();
  const server = http.createServer((req, res) => {
    handleRequest(config, req, res).catch((error) => {
      console.error(`[mt5-auth] request_error message=${error.message}`);
      if (!res.headersSent) {
        jsonResponse(res, 500, { error: 'internal_error' });
      } else {
        res.destroy(error);
      }
    });
  });

  server.on('upgrade', (req, socket, head) => {
    handleUpgrade(config, req, socket, head).catch((error) => {
      console.error(`[mt5-auth] upgrade_error message=${error.message}`);
      if (!socket.destroyed) {
        websocketReject(socket, 500, 'Internal Server Error');
      }
    });
  });

  server.listen(config.listenPort, config.listenHost, () => {
    console.log(`[mt5-auth] listening host=${config.listenHost} port=${config.listenPort} routes=${Object.keys(config.routes).join(',')}`);
  });
}

if (require.main === module) {
  main();
}
