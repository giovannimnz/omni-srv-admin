# Gemini Spark MCP Cloudflare OAuth Proxy

Worker Cloudflare para integração autorizada de servidores MCP (Model Context Protocol) no **Google Gemini Spark** (`https://gemini.google.com/spark/apps`).

## Especificação de Autenticação Atendida
O Gemini Spark implementa a especificação oficial de autorização MCP baseada em OAuth 2.1:
1. **RFC 9728 (OAuth 2.0 Protected Resource Metadata):**
   - Endpoint: `/.well-known/oauth-protected-resource`
   - Retorna o identificador do recurso protegido e aponta para o servidor de autorização.
2. **RFC 8414 (OAuth 2.0 Authorization Server Metadata):**
   - Endpoint: `/.well-known/oauth-authorization-server`
   - Retorna os endpoints `authorization_endpoint`, `token_endpoint`, `registration_endpoint` e suporte a PKCE `S256`.
3. **Desafio HTTP 401 (WWW-Authenticate):**
   - Ao receber requisição não autenticada no endpoint MCP, responde com:
     `WWW-Authenticate: Bearer resource_metadata="https://<host>/.well-known/oauth-protected-resource"`
4. **Proxy & Injeção de Segredo:**
   - Troca o token temporário do cliente pelo `ATIUS_MCP_TOKEN` injetado pelo Cloudflare Secrets e encaminha a chamada para `https://mcp.atius.com.br/<service>`.

## URLs Prontas para o Gemini Spark
Insira no campo *"Apps personalizados para o Spark"*:

- **GBrain (Memória, Grafos e Skills - 115 ferramentas):**
  `https://spark-oauth-proxy.giovanni-account.workers.dev/mcp`
  *(ou: `https://spark-oauth-proxy.giovanni-account.workers.dev/gbrain`)*

- **Obsidian Vault (AiSecondBrain - 16 ferramentas):**
  `https://spark-oauth-proxy.giovanni-account.workers.dev/obsidian`

- **OCI Admin (Controle Cloud OCI - 12 ferramentas):**
  `https://spark-oauth-proxy.giovanni-account.workers.dev/oci-admin`
