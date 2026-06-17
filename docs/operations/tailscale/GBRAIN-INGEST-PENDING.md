# gbrain Embeddings — Atius Router config (validated 2026-06-16)

**Path confirmado:** `gbrain → https://router.atius.com.br/v1/embeddings → new-api Go (giovanni) → channel id=6 (MiniMax) → upstream api.minimax.io`.

## Configuração aplicada

**Arquivo:** `~/.gbrain/config.json` (file plane, NÃO `gbrain config` que escreve no DB plane).

```json
{
  "embedding_model": "openai:embo-01",
  "embedding_dimensions": 1536,
  "provider_base_urls": {
    "minimax": "https://api.minimax.io/v1",
    "openai": "https://router.atius.com.br/v1",
    "anthropic": "https://api.minimax.io/anthropic"
  },
  "openai_api_key": "pil5K2AMTE3brIL6wBGJGF0DfJd156CO2TpCg3t7GT9judOP"
}
```

`openai_api_key` = subscriber token `gbrain-embed-2026-06-09` (Atius Router tokens.id=8, group=default).

## Validação

| Model | Status | Notes |
|---|---|---|
| `embo-01` (MiniMax) | ✅ 200 | 1536 dims, RPM 1 (slow) |
| `text-embedding-3-small` | ❌ 503 | canal 8 (OpenAI) desabilitado, klen=3 |
| `text-embedding-3-large` | ❌ 503 | mesmo canal 8 |

## Pendência (operador)

Habilitar canal 8 (`OpenAI - Embeddings`) com uma OpenAI key real, no admin UI do Atius Router. Após isso:

1. Atualizar `~/.gbrain/config.json`:
   - `embedding_model: "openai:text-embedding-3-small"` (ou large)
   - `embedding_dimensions: 1536` (ou 3072)
2. Testar com `python3 /tmp/test_all_embeds.py` — todos devem retornar 200.

## Runbook

```bash
# Health check do canal 6 (MiniMax)
sleep 60 && python3 /tmp/test_all_embeds.py

# Capture no gbrain (vai dar 429 até RPM zerar)
gbrain capture --file /tmp/gbrain-tailscale-content.md --slug inbox/2026-06-16-tailscale-acl-closed
```

## Notas

- `gbrain` está em `~/.bun/install/global/node_modules/gbrain/` (Bun, não npm). Version 0.42.36.0.
- DB: PostgreSQL via PgBouncer (`127.0.0.1:6432/gbrain`, prepare=false).
- Embedding_dimensions 1536 bate com `embo-01` (MiniMax Embedding v1). Se trocar pra `text-embedding-3-large` (3072), precisa `UPDATE config SET value='3072' WHERE key='embedding_dimensions'` no DB plane também, senão vetor armazenado tem dim errada.
