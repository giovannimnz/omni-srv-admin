# Fork Sync — Atius Router

Fork-sync configuration for the Atius Router fork (`giovannimnz/atius-ai-router`).

## Purpose

This directory stores the `sync.yaml` used by fork-sync to synchronize the Atius Router fork with upstream `QuantumNous/new-api`.

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

### Middleware and containers
- `integration/middleware/` — FastAPI/Go middleware assets and build files
- `Dockerfile.fast` — local container customization

### Infrastructure
- `docker-compose.yml` — Docker Compose with `model-detailed` Python service

### i18n — Portuguese Translation
- `i18n/locales/pt.yaml` — Brazilian Portuguese backend translations (278 keys)
- `i18n/i18n.go` — added `LangPt`, `normalizeLang("pt")`, `SupportedLanguages()` includes `pt`

### Frontend i18n
- `web/default/src/i18n/locales/*.json` — locale updates required by fork-specific channel UX
- `web/default/src/i18n/config.ts` — added `pt` to `supportedLngs` and `resources`

### Codex channel integration
- `controller/codex_*.go`, `service/codex_*.go` — OAuth/device/model flows
- `relay/channel/codex/` — Codex adaptor
- `service/openaicompat/policy.go` — chat-to-responses routing
- `dto/channel_settings.go`, `router/api-router.go` — API/router deltas
- `web/default/src/features/channels/` — fork-specific channel UI

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
| Middleware | None | Python FastAPI enrichment layer |
| Documentation | EN/ZH | PT-BR primary, EN copy |
| Version scheme | Standard semver | `X.Y.Z.N` fork suffix |
| Docker Compose | Basic | With `model-detailed` Python service |
