export function sanitizeLogUrl(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    for (const key of ['code', 'session_state', 'token', 'access_token', 'id_token', 'refresh_token']) {
      if (parsed.searchParams.has(key)) {
        parsed.searchParams.set(key, '[REDACTED]');
      }
    }
    return parsed.toString();
  } catch {
    return rawUrl;
  }
}

export async function probeSsoEndpoint(targetUrl, { timeoutMs = 3000 } = {}) {
  const start = Date.now();
  try {
    const res = await fetch(targetUrl, {
      method: 'GET',
      redirect: 'manual',
      signal: AbortSignal.timeout(timeoutMs)
    });
    const latencyMs = Date.now() - start;
    const isHealthy = (res.status >= 200 && res.status < 400);

    return {
      url: sanitizeLogUrl(targetUrl),
      status: res.status,
      healthy: isHealthy,
      latencyMs
    };
  } catch (err) {
    return {
      url: sanitizeLogUrl(targetUrl),
      status: 0,
      healthy: false,
      latencyMs: Date.now() - start,
      error: err.name === 'TimeoutError' ? 'timeout' : err.message
    };
  }
}
