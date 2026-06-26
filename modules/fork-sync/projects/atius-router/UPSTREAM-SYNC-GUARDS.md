# Atius Router upstream sync guards

Updated: 2026-06-26

This file is the operational warning for upstream sync maintainers. The Atius Router fork has production-only behavior that must survive merges from `QuantumNous/new-api`.

## Do not overwrite these behaviors

- `GET /v1/models` is owned by the Go backend, not by Python/model-detailed or another service.
- Public `/v1/models` returns root `{"data":[...]}` only for model-list modes.
- Public `/v1/models` must not expose `pricing_source`, `pricing_estimated` or `pricing_version`.
- Model ordering must keep text before embeddings, MiniMax before DeepSeek before OpenAI/Codex, higher numeric versions first, `-highspeed` above standard, and `pro` above `flash`.
- Codex embeddings use channel 5 `OpenAI - Codex` and the same OAuth credential used by Codex chat/responses.
- Do not activate a separate OpenAI-key embeddings channel as the default route for `text-embedding-3-*`.
- MiniMax must remain a single active provider channel: `MiniMax`, type `35`, base `https://api.minimax.io`, covering OpenAI-compatible chat, Anthropic-compatible messages and `embo-01` embeddings.
- DeepSeek must remain a single active provider channel: `DeepSeek`, type `43`, base `https://api.deepseek.com`, covering OpenAI-compatible chat and Anthropic-compatible messages.
- Provider base URLs may be stored either at provider root or with trailing `/v1`; Go must normalize both forms and must not produce duplicated `/v1/v1` paths. MiniMax/DeepSeek must strip a trailing `/v1` before appending Anthropic/native paths.
- Do not reintroduce active split channels named `MiniMax - OpenAI-Compatible`, `MiniMax - Anthropic-Compatible`, `MiniMax - Embeddings`, `DeepSeek - OpenAI-Compatible`, `DeepSeek - Anthropic-Compatible`, `OpenAI - Embeddings`, or `Codex - Embeddings`.
- Do not add or reactivate a Python/container sidecar as the canonical owner for `/v1/`, detailed models, or Codex embeddings.
- Local TEI embeddings must remain governed inside the Go router through `service/embeddinggovernor/` and `relay/embedding_handler.go`; do not move this path back to Python/model-detailed or a separate sidecar/container. Default governed models are `embedding-pt-v1` and `embedding-pt-v1-batch`.
- Runtime directories must stay excluded from image build context through `.dockerignore`: `/backups`, `/data`, `/logs`, `/runtime`.

## Protected paths that carry this behavior

- `.dockerignore`
- `controller/model.go`
- `controller/model_list_test.go`
- `service/modelcatalog/`
- `relay/common/relay_utils.go`
- `relay/common/relay_utils_test.go`
- `relay/embedding_handler.go`
- `service/embeddinggovernor/`
- `common/endpoint_type.go`
- `common/endpoint_type_test.go`
- `constant/channel.go`
- `dto/embedding.go`
- `relay/channel/codex/`
- `relay/channel/minimax/`
- `relay/channel/deepseek/`
- `service/codex_*.go`
- `tools/clianything.py`
- `tests/test_clianything.py`
- `docs/`
- `.planning/`

## Required post-sync checks

Run from `/home/ubuntu/GitHub/containers/router-ai-atius` after any upstream sync:

```bash
go test ./common ./controller ./service/modelcatalog ./relay/common ./relay/channel/minimax ./relay/channel/deepseek ./relay/channel/codex ./service ./service/embeddinggovernor ./relay -count=1
python3 -m py_compile tools/clianything.py scripts/smoke-provider-consolidation.py scripts/smoke-embeddings.py
python3 -m unittest discover -s tests -p 'test_clianything*.py'
bin/clianything status --strict
bin/clianything providers --all
```

With an operational token in the environment, also verify:

```bash
curl -sS -H "Authorization: Bearer $ATIUS_ROUTER_TOKEN" http://127.0.0.1:3000/v1/models | jq '.data[0].id, any(.data[]; has("pricing_version"))'
```

Expected result: first value should be the most recent/capable visible MiniMax text model, currently `MiniMax-M3` when enabled; second value must be `false`.

## Current production notes

- Production image validated on 2026-06-18: `ghcr.io/giovannimnz/router-ai-atius:latest` at image id `e389110f98fb8e3fce80ac8cf691a04c1c74b6268d91d5fb304bb6f574344151`.
- Rollback image tag: `ghcr.io/giovannimnz/router-ai-atius:rollback-before-baseurl-v1-normalize-20260618122124`.
- Current active provider channels: `MiniMax` and `OpenAI - Codex`. `DeepSeek` is intentionally disabled until its upstream key stops returning `401 invalid api key`.
- `Codex - Embeddings` may exist disabled as a historical/manual fallback channel. It is not the active default route.
- Codex embeddings can route locally and still return upstream `429 insufficient_quota`; that is quota/licensing, not proof of local channel-selection failure. Keep `text-embedding-3-*` out of `/v1/models` until strict smoke passes.
- Current active embeddings route: `Local TEI - GTE Embeddings` with public model `embedding-pt-v1`, upstream `http://10.1.1.4:3000`, dimension `768`, protected by the Go-native governor.
- Active Apache `/v1/` and `/health` route directly to Go on `127.0.0.1:3000`; do not restore `127.0.0.1:3300`, `127.0.0.1:3399`, or pod port `3001`.
