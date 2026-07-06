# GBrain Embedding Migration

## Target

Target router, using our public `router-ai-atius` / New API deployment:

```text
https://router.atius.com.br/v1
```

Target model:

```text
openai:embedding-gte-v1
```

Target dimensions:

```yaml
embedding_dimensions: 768
```

The public alias `embedding-gte-v1` resolves through our `router-ai-atius` / New API gateway to the private TEI upstream `http://10.1.1.4:3000`, which serves `Alibaba-NLP/gte-multilingual-base` directly as `embedding-gte-v1`.

## Non-Negotiable Rule

Do not mix vectors from different embedding spaces.

Historical GBrain embeddings on this host used a 1536-dimensional provider path. The current `embedding-gte-v1` contract is 768-dimensional. Those stores are incompatible. Migrating requires one of these paths:

1. Create a fresh vector store or schema for 768-dimensional vectors.
2. Back up the current store, truncate only the approved vector tables, then reembed all chunks.
3. Implement a retrieval-upgrade path that can query old and new stores separately without mixing vectors in the same index.

Changing model, revision or digest, quantization, dimension, normalization, or chunking later also requires reembedding and reindexing.

## Backup First

Before changing config or stored vectors, create a timestamped backup:

```bash
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$HOME/.backups/gbrain-embeddings-${TS}"
mkdir -p "$BACKUP_DIR"

cp -a "/var/lib/gbrain-home/.gbrain/config.json" "$BACKUP_DIR/config.json"
gbrain stats > "$BACKUP_DIR/gbrain-stats-before.txt"
gbrain config list > "$BACKUP_DIR/gbrain-config-before.txt" 2>&1 || true
```

Also back up the PostgreSQL database or the specific GBrain schema/table set using the approved database credential path for this host. Do not place database passwords in shell history, Git, `.planning`, Obsidian, or logs.

Record the backup location before any destructive vector operation:

```text
~/.backups/gbrain-embeddings-<timestamp>/
```

## File-Plane Config

The active `/home/ubuntu/.local/bin/gbrain` wrapper uses `GBRAIN_HOME=/var/lib/gbrain-home`, so the active file-plane config is `/var/lib/gbrain-home/.gbrain/config.json`. Keep model and dimension aligned:

```json
{
  "embedding_model": "openai:embedding-gte-v1",
  "embedding_dimensions": 768,
  "provider_base_urls": {
    "openai": "https://router.atius.com.br/v1"
  }
}
```

Do not put the API key in this doc. Load the key through the approved runtime path, such as a prompt, Vault, or a local secret file with restricted permissions.

Interactive token load for one-off testing:

```bash
read -rsp "New API key: " NEW_API_KEY
export NEW_API_KEY
echo
```

## DB-Plane Config Check

If the GBrain DB plane also stores embedding configuration, update it only after the file-plane backup and DB backup exist.

Expected values after migration:

```text
embedding_model=openai:embedding-gte-v1
embedding_dimensions=768
provider_base_urls.openai=https://router.atius.com.br/v1
```

Verify the DB-plane value with the local GBrain tooling first. If the tooling cannot show the value, query PostgreSQL read-only before writing anything.

On 2026-06-26 the public alias was renamed from `embedding-pt-v1` to `embedding-gte-v1` without changing the backend embedding space. The DB-plane `config.embedding_model` was updated, and `pages.embedding_signature` was migrated from `openai:embedding-pt-v1:768` to `openai:embedding-gte-v1:768` to avoid reembedding identical vectors. Backup table: `migration_backup_embedding_gte_20260626`.

## Reindex Flow

Do this only after the router smoke test passes with `dimensoes: 768`.

1. Confirm the current backup path.
2. Confirm the current vector dimension and row counts.
3. Stop any watcher or background embed job that writes to the old store.
4. Switch GBrain config to `openai:embedding-gte-v1` and `embedding_dimensions: 768`.
5. Reimport or reembed from source Markdown/docs.
6. Run stats and semantic query checks.
7. Keep the old backup until the new search path is accepted.

Example verification target:

```bash
gbrain stats
gbrain query "router.atius.com.br embedding-gte-v1" --no-expand
```

The exact destructive command for clearing or replacing vectors is intentionally not documented here. Choose it only after confirming the current GBrain schema and backup restore path.

## Obsidian Contract

Obsidian remains the Markdown source of truth. Use an external indexer that scans the vault, chunks Markdown, calls `embedding-gte-v1`, and stores vectors outside the vault.

Do not install or configure an Obsidian plugin that silently chooses a different embedding model behind the same index.

## Graphify Contract

Graphify remains graph-first. Embeddings can be an auxiliary retrieval layer for docs and semantic search, but they do not replace Graphify's structural code graph, relationships, or GSD routing.

Before relying on updated graph context, run:

```bash
node "$HOME/.Codex/gsd-core/bin/gsd-tools.cjs" graphify status
```

Configured local bridge:

```text
LLM backend:      ~/.graphify/providers.json -> atius-router-gpt
LLM model:        gpt-5.4-mini via https://router.atius.com.br/v1
Streaming patch:  ~/.local/share/graphify-patches/graphify_atius_router_patch.py
Embedding config: ~/.graphify/embeddings.json
Embedding helper: ~/.local/bin/graphify-embed
Embedding model:  embedding-gte-v1
Dimensions:       768
Batch cap:        4
Governor header:  X-Embedding-Workload: batch
```

Use the bridge only for auxiliary retrieval/indexing until upstream Graphify has a native embeddings store:

```bash
graphify-embed --text "Graphify retrieval smoke" --pretty
```

If Graphify later gains native embeddings for retrieval, keep its vector store separate from legacy 1536-dimensional vectors and record the model contract used to generate it.

## Secret Hygiene

Do not write New API keys, Bearer tokens, Authorization headers, database passwords, Kubernetes Secret values, or historical router/GBrain token values to Git, `.planning`, Obsidian, logs, shell history, saved curl output, or screenshots.

Historical notes and runbooks may contain old token material. Treat them as sensitive read-only evidence and do not copy those values into any new artifact.
