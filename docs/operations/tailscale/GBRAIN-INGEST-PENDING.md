# gbrain Embeddings - Registro historico superado

Este arquivo preserva apenas o contexto operacional de 2026-06-16. A configuracao antiga via MiniMax/`embo-01` foi superada e nao deve ser usada como runbook ativo.

## Estado atual

- Endpoint publico: `https://router.atius.com.br/v1`
- Modelo de embeddings ativo: `embedding-gte-v1`
- Provider GBrain: `openai:embedding-gte-v1`
- Dimensoes: `768`
- Backend interno: TEI `text-embeddings-inference` servindo `Alibaba-NLP/gte-multilingual-base`
- Governor: obrigatorio no Go router; batch via `X-Embedding-Workload: batch`

## Historico removido

O caminho antigo usava MiniMax/`embo-01` com 1536 dimensoes e chegou a conter token operacional em texto neste documento. Esse material foi removido. Nao reintroduzir chaves, Bearer tokens, Authorization headers ou exemplos com segredo real em docs, `.planning`, Obsidian, logs ou tickets.

## Runbook ativo

Use os documentos atuais:

- `docs/operations/local-ai-embeddings.md`
- `docs/operations/gbrain-embedding-migration.md`

Smoke recomendado:

```bash
/home/ubuntu/.local/bin/gbrain doctor
/home/ubuntu/.local/bin/gbrain embed --stale --dry-run --batch-size 4
/home/ubuntu/.local/bin/graphify-embed --text "Graphify retrieval smoke" --pretty
```
