// spark-oauth-proxy
// Canonical Model Context Protocol (MCP) OAuth 2.1 & Resource Proxy for Gemini Spark

const MOCK_ACCESS_TOKEN = "spark_atiuz_bearer_token";
const ORIGIN_BASE = "https://mcp.atius.com.br";

function json(data, init = {}) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "Content-Type, Authorization, Accept, mcp-session-id, mcp-protocol-version",
      ...(init.headers || {}),
    },
  });
}

function handleCors() {
  return new Response(null, {
    status: 204,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "Content-Type, Authorization, Accept, mcp-session-id, mcp-protocol-version",
      "access-control-max-age": "86400",
    },
  });
}

// 1. RFC 9728: Protected Resource Metadata
function handleProtectedResource(url) {
  const origin = url.origin;
  return json({
    resource: `${origin}/mcp`,
    authorization_servers: [origin],
    scopes_supported: ["mcp:tools", "mcp:read", "mcp:write"],
    bearer_methods_supported: ["header"],
    resource_documentation: "https://mcp.atius.com.br"
  });
}

// 2. RFC 8414: OAuth 2.0 Authorization Server Metadata
function handleAuthServerMetadata(url) {
  const origin = url.origin;
  return json({
    issuer: origin,
    authorization_endpoint: `${origin}/authorize`,
    token_endpoint: `${origin}/token`,
    registration_endpoint: `${origin}/register`,
    response_types_supported: ["code"],
    grant_types_supported: ["authorization_code", "refresh_token"],
    token_endpoint_auth_methods_supported: ["none", "client_secret_post", "client_secret_basic"],
    code_challenge_methods_supported: ["S256", "plain"],
    scopes_supported: ["mcp:tools", "mcp:read", "mcp:write"]
  });
}

// 3. Dynamic Client Registration (RFC 7591) fallback
function handleRegister(req, url) {
  return json({
    client_id: "gemini-spark-client",
    client_secret: "gemini-spark-secret",
    client_id_issued_at: Math.floor(Date.now() / 1000),
    grant_types: ["authorization_code", "refresh_token"],
    response_types: ["code"],
    redirect_uris: ["https://gemini.google.com/oauth/callback", "https://gemini.google.com/spark/oauth/callback"]
  }, { status: 201 });
}

// 4. Authorize Endpoint (RFC 6749)
async function handleAuthorize(req) {
  const url = new URL(req.url);
  const redirectUri = url.searchParams.get("redirect_uri");
  const state = url.searchParams.get("state") ?? "";
  const code = "spark_code_" + Math.random().toString(36).substring(2, 10);
  
  if (!redirectUri) {
    return json({ error: "missing_redirect_uri" }, { status: 400 });
  }

  const target = new URL(redirectUri);
  target.searchParams.set("code", code);
  if (state) target.searchParams.set("state", state);
  return Response.redirect(target.toString(), 302);
}

// 5. Token Endpoint
async function handleToken(req) {
  return json({
    access_token: MOCK_ACCESS_TOKEN,
    token_type: "Bearer",
    expires_in: 315360000,
    scope: "mcp:tools"
  });
}

// 6. MCP Proxy Handler
async function handleProxy(req, env) {
  const incomingUrl = new URL(req.url);
  
  let targetPath = incomingUrl.pathname;
  if (targetPath === "/mcp" || targetPath === "/mcp/") {
    targetPath = "/gbrain";
  }

  // Verifica desafio OAuth se for rota MCP e faltar o header de autorização
  const authHeader = req.headers.get("authorization");
  if (!authHeader && (targetPath.startsWith("/gbrain") || targetPath.startsWith("/obsidian") || targetPath.startsWith("/oci-admin"))) {
    return new Response(JSON.stringify({ error: "unauthorized", message: "Authentication required via OAuth 2.1" }), {
      status: 401,
      headers: {
        "content-type": "application/json",
        "WWW-Authenticate": `Bearer resource_metadata="${incomingUrl.origin}/.well-known/oauth-protected-resource"`,
        "access-control-allow-origin": "*"
      }
    });
  }

  const targetUrl = new URL(ORIGIN_BASE);
  targetUrl.pathname = targetPath;
  targetUrl.search = incomingUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("authorization");
  headers.set("authorization", `Bearer ${env.ATIUS_MCP_TOKEN}`);
  headers.set("host", targetUrl.host);

  const init = {
    method: req.method,
    headers,
    redirect: "manual"
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half";
  }

  const upstream = await fetch(targetUrl.toString(), init);
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-length");
  responseHeaders.set("access-control-allow-origin", "*");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders
  });
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return handleCors();
    const url = new URL(req.url);
    const path = url.pathname;

    if (path === "/.well-known/oauth-protected-resource") {
      return handleProtectedResource(url);
    }
    if (path === "/.well-known/oauth-authorization-server") {
      return handleAuthServerMetadata(url);
    }
    if (path === "/register" && req.method === "POST") {
      return handleRegister(req, url);
    }
    if ((path === "/authorize" || path === "/oauth/authorize") && req.method === "GET") {
      return handleAuthorize(req);
    }
    if ((path === "/token" || path === "/oauth/token") && req.method === "POST") {
      return handleToken(req);
    }

    return handleProxy(req, env);
  }
};
