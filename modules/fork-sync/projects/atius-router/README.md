# Fork Sync — Atius Router

Fork-sync configuration for the Atius Router fork (`giovannimnz/atius-ai-router`).

## Purpose

This directory stores the `sync.yaml` used by fork-sync to synchronize the Atius Router fork with upstream `QuantumNous/new-api`.

Current production worktree on this host: `/home/ubuntu/GitHub/containers/router-ai-atius`.
The older `/home/ubuntu/docker/Atius/router-ai-atius` symlink points at `/home/ubuntu/GitHub/containers/Atius/router-ai-atius` and should be treated as legacy unless the inventory is intentionally changed.

The `sync.yaml` defines:
- **protected_paths**: files customized in the fork that must not be overwritten during upstream merges
- **merge_strategy**: `theirs` (prefer upstream on conflict, then restore protected files)
- **version_scheme**: `v{upstream_version}-rf{N}` for fork releases
- **notification_level**: `all`

## Structure

```
fork-sync/
└── projects/
    └── atius-router/
        ├── sync.yaml          # Main config
        ├── README.md          # This file
        ├── UPSTREAM-SYNC-GUARDS.md # Current fork-specific merge guards
        ├── PROTECTED.md       # Detailed protected files documentation
        └── VERSIONS.md        # Release history
```

## Updating sync.yaml

When a new customization is added to the fork:

1. Edit `sync.yaml` in this directory
2. Add the file path to `protected_paths`
3. Commit and push

The fork-sync GitHub Action reads from this directory on the `sync` branch.

## Protected Files Summary

### Retired Middleware and Containers
- `integration/middleware/` — historical middleware assets; do not restore as canonical `/v1/` owner
- `runtime/model-detailed/` — legacy FastAPI middleware source retained only as history/fallback reference; not runtime
- `Dockerfile.fastapi` — retired local container customization

### Infrastructure
- `docker-compose.yml` / `podman-compose.yml` — protected infra definitions; production `/v1/` is Go-only on port `3000`

### i18n — Portuguese Translation
- `i18n/locales/pt.yaml` — Brazilian Portuguese backend translations (278 keys)
- `i18n/i18n.go` — added `LangPt`, `normalizeLang("pt")`, `SupportedLanguages()` includes `pt`

### Frontend i18n
- `web/default/src/i18n/locales/*.json` — locale updates required by fork-specific channel UX
- `web/default/src/i18n/config.ts` — added `pt` to `supportedLngs` and `resources`
- `web/default/src/i18n/languages.ts` — exposes `Português` and normalizes `pt-BR`/`pt_BR` to `pt`
- `web/classic/src/i18n/` and both classic selectors — keep PT-BR available if the classic theme is enabled
- `scripts/smoke-pt-br-i18n.sh` — blocks sync when locale files, registrations, keys or placeholders regress

### Codex channel integration
- `controller/codex_*.go`, `service/codex_*.go` — OAuth/device/model flows
- `relay/channel/codex/` — Codex adaptor
- `service/openaicompat/policy.go` — chat-to-responses routing
- `dto/channel_settings.go`, `router/api-router.go` — API/router deltas
- `web/default/src/features/channels/` — fork-specific channel UI

### Go-native model catalog, Codex embeddings and provider consolidation
- `.dockerignore` — keeps runtime `backups/`, `data/`, `logs/`, `runtime/` out of build context
- `controller/model.go`, `controller/model_list_test.go` — public `/v1/models` contract and regression tests
- `service/modelcatalog/` — deterministic model catalog projection and ordering
- `relay/common/relay_utils.go`, `relay/common/relay_utils_test.go` — base URL normalization, including trailing `/v1`
- `relay/embedding_handler.go`, `service/embeddinggovernor/` — local TEI embeddings governor inside the Go router, with no Python sidecar
- `relay/channel/codex/`, `service/codex_*.go` — Codex OAuth chat/responses/embeddings, sharing the same OAuth credential
- `common/endpoint_type.go`, `dto/embedding.go`, `relay/channel/minimax/`, `relay/channel/deepseek/` — single-channel MiniMax/DeepSeek routing across OpenAI/Anthropic/embeddings where supported
- `constant/channel.go`, frontend channel constants and i18n locale files — canonical label `OpenAI - Codex`
- `tools/clianything.py`, `tests/test_clianything.py` — legacy `phase19-apply` now consolidates channels and `clone-keyed` blocks split-channel recreation by default

See `UPSTREAM-SYNC-GUARDS.md` before any upstream merge.

### Documentation (fork-specific, PT-BR primary)
- `README.md` — Portuguese (BR) README — primary language
- `README.en.md` — English README — copy of main README
- `docs/` — documentation folder (ARCHITECTURE, GETTING-STARTED, DEVELOPMENT, TESTING, CONFIGURATION)

### Planning
- `.planning/` — planning artifacts tied to the fork roadmap

### Versioning
- `VERSION` — fork version file (`0.12.14.2`)

## Merge Flow

```
1. git fetch upstream
2. verify working tree is clean or checkpoint locally first
3. snapshot protected files from the fork branch
4. git merge --no-commit -X theirs upstream/main
5. restore protected files from the local snapshot
6. abort if any conflict remains outside protected paths
7. git commit the merge once the tree is clean
```

## Versioning Scheme

Fork uses `X.Y.Z.N`:
- `X.Y.Z` = upstream NewAPI base version
- `N` = fork suffix (incremented on each sync)

Example: `0.12.14.2` — based on upstream `0.12.14`, fork suffix `.2`

## Upstream Differences (vs QuantumNous/new-api)

| Feature | Upstream (new-api) | Fork (atius-ai-router) |
|---------|-------------------|----------------------|
| Primary language | English / Chinese | Portuguese (BR) |
| Default models | Various | MiniMax + DeepSeek focused |
| Middleware | None | Runtime `/v1/` is full-Go; legacy Python/FastAPI helper is retired history |
| Codex embeddings | None | `text-embedding-3-*` routed through channel 5 `OpenAI - Codex` |
| MiniMax/DeepSeek routing | Provider-specific defaults | One active channel per provider, with Go selecting OpenAI/Anthropic/embeddings paths automatically |
| Documentation | EN/ZH | PT-BR primary, EN copy |
| Version scheme | Standard semver | `X.Y.Z.N` fork suffix |
| Docker Compose | Basic | Podman/Docker stack with Go router only for canonical `/v1/` |
