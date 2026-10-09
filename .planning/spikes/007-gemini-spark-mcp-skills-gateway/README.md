# Spike 007: Gemini Spark MCP Gateway & Skills Integration

## 1. Contexto & Desafio
O Google Gemini Spark (`https://gemini.google.com/spark/apps`) introduziu suporte a **Apps conectados personalizados via MCP** (*Model Context Protocol*):
- O campo de cadastro aceita exclusivamente a URL pública HTTPS (`https://your-app-link.com/mcp`).
- O Gemini Spark não disponibiliza campo de injeção de cabeçalhos arbitrários (ex: `Authorization: Bearer <token>`).
- Se o servidor responder com `401 Unauthorized` ou `403 Forbidden`, o cliente do Gemini tenta acionar OAuth 2.1 (RFC 9728 / RFC 8414). Sem um provedor OAuth configurado para o Google, a conexão falha ("Cannot Complete Request").
- Se o servidor responder com `200 OK` para o handshake inicial JSON-RPC `initialize`, o Gemini Spark aceita a conexão diretamente sem exigir OAuth interativo.

## 2. Hipótese Validada
É possível expor os MCPs soberanos da infraestrutura ATIUS (`gbrain`, `obsidian`, `oci-admin`) e o catálogo de 337 skills ao Gemini Spark através de duas estratégias combinadas:

### A. Token Ingress via Path ou Query Param no Apache Edge (`mcp.atius.com.br`)
Adicionar regras de rewrite no Apache vhost (`modules/srv1-ops/apache/mcp.atius.com.br.conf`):
1. `/spark/<token>/<service>` -> traduz para `/<service>` e injeta `Authorization: Bearer <token>`.
2. `/<service>?token=<token>` -> traduz e injeta `Authorization: Bearer <token>`.

### B. Integração de Skills (Habilidades)
Na interface `gemini.google.com/spark/skills`:
1. **Upload Direto (UI):** O botão de upload `(↑)` aceita arquivos `SKILL.md` ou pacotes `.zip` contendo pastas com `SKILL.md`. Desenvolvido o script `scripts/spark-skills-packager.py` que gera pacotes categorizados (`atius-fleet-ops`, `gsd-spec-driven`, `intelligence-brain`, `devtools-automation`).
2. **Exposição Dinâmica via MCP:** O servidor `gbrain` já implementa `list_skills` e `get_skill`. Conectando o `@gbrain` no Spark, o assistente pode consultar qualquer skill em runtime sem necessidade de importar as 337 manualmente.

## 3. Topologia e Segurança
- Origem do token: HashiCorp Vault (`atius-srv-3`, path `kv/atius/atius-mcp/api`).
- Zero segredos em repositório Git ou URLs hardcoded.
- Paridade dual-domain preservada: `mcp.atius.com.br` e `mcp.atius.io`.
