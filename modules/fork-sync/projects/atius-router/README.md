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

### Middleware (custom Python enrichment layer)
- `integration/middleware/model_detailed.py` — model enrichment via Python FastAPI

### Infrastructure
- `docker-compose.yml` — Docker Compose with `model-detailed` Python service
- `.env.example` — environment template with fork-specific variables

### i18n — Portuguese Translation
- `i18n/locales/pt.yaml` — Brazilian Portuguese backend translations (278 keys)
- `i18n/i18n.go` — added `LangPt`, `normalizeLang("pt")`, `SupportedLanguages()` includes `pt`

### Frontend i18n
- `web/default/src/i18n/locales/pt.json` — Brazilian Portuguese frontend translations (3910 keys)
- `web/default/src/i18n/config.ts` — added `pt` to `supportedLngs` and `resources`
- `web/default/src/components/language-switcher.tsx` — added `Português` option

### Documentation (fork-specific, PT-BR primary)
- `README.md` — Portuguese (BR) README — primary language
- `README.en.md` — English README — copy of main README
- `docs/` — documentation folder (ARCHITECTURE, GETTING-STARTED, DEVELOPMENT, TESTING, CONFIGURATION)

### Planning & Scripts
- `.planning/` — GSD planning artifacts
- `scripts/` — fork-specific scripts (sync-fork.sh, auto-sync-deploy.sh, deploy-ghcr.sh, version-bump.sh)

### Versioning
- `VERSION` — fork version file (`0.12.14.2`)

## Merge Flow

```
1. git fetch upstream
2. git merge upstream/main (strategy: theirs = prefer upstream on conflict)
3. git checkout --ours integration/middleware/model_detailed.py
4. git checkout --ours docker-compose.yml
5. git checkout --ours README.md README.en.md
6. git checkout --ours i18n/locales/pt.yaml i18n/i18n.go
7. git checkout --ours web/default/src/i18n/locales/pt.json
8. git checkout --ours web/default/src/i18n/config.ts
9. git checkout --ours web/default/src/components/language-switcher.tsx
10. git checkout --ours .planning/
11. git checkout --ours scripts/
12. git checkout --ours VERSION
13. git add -A && git commit -m "chore: restore protected files after upstream merge"
14. ./scripts/version-bump.sh
15. git push
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
