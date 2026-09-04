# Atius Router upstream sync guards

Updated: 2026-08-14

This file is the operational warning for upstream sync maintainers. The Atius Router fork has production-only behavior that must survive merges from `QuantumNous/new-api`.

## Do not overwrite these behaviors

- `GET /v1/models` is owned by the Go backend, not by Python/model-detailed or another service.
- Public `/v1/models` returns root `{"data":[...]}` only for model-list modes.
- Public `/v1/models` must not expose `pricing_source`, `pricing_estimated` or `pricing_version`.
- Model ordering must keep text before embeddings, MiniMax before DeepSeek before OpenAI/Codex, higher numeric versions first, `-highspeed` above standard, and `pro` above `flash`.
- Codex embeddings use channel 5 `OpenAI - Codex` and the same OAuth credential used by Codex chat/responses.
- Codex text models must keep `Responses` as the default endpoint reference in user-facing snippets/catalog surfaces when `openai-response` is available.
- Channel type `57` is the canonical `OpenAI - Codex` channel. Its admin UI must not expose generic `Base URL`, `API Key`, reveal/copy or multi-key controls.
- Type `57` must keep the Router-owned OAuth lifecycle routes for sanitized metadata, refresh, explicit probe and PKCE regeneration under `/api/channel/:id/codex/*`.
- Internal Router API-key failures and Codex upstream OAuth failures are distinct contracts. Preserve `codex_upstream_auth_failed`, `codex_upstream_token_invalidated` and `codex_upstream_refresh_token_invalidated` across Responses and Chat Completions paths.
- A future local expiration timestamp is not proof of validity after an upstream auth failure. Preserve non-secret credential health in `channel.setting.codex_credential_health` and never expose token material in metadata or diagnostics.
- Do not activate a separate OpenAI-key embeddings channel as the default route for `text-embedding-3-*`.
- MiniMax must remain a single active provider channel: `MiniMax`, type `35`, base `https://api.minimax.io`, covering OpenAI-compatible chat, Anthropic-compatible messages and `embo-01` embeddings.
- DeepSeek must remain a single active provider channel: `DeepSeek`, type `43`, base `https://api.deepseek.com`, covering OpenAI-compatible chat and Anthropic-compatible messages.
- Provider base URLs may be stored either at provider root or with trailing `/v1`; Go must normalize both forms and must not produce duplicated `/v1/v1` paths. MiniMax/DeepSeek must strip a trailing `/v1` before appending Anthropic/native paths.
- Do not reintroduce active split channels named `MiniMax - OpenAI-Compatible`, `MiniMax - Anthropic-Compatible`, `MiniMax - Embeddings`, `DeepSeek - OpenAI-Compatible`, `DeepSeek - Anthropic-Compatible`, `OpenAI - Embeddings`, or `Codex - Embeddings`.
- Do not add or reactivate a Python/container sidecar as the canonical owner for `/v1/`, detailed models, or Codex embeddings.
- Local TEI embeddings must remain governed inside the Go router through `service/embeddinggovernor/` and `relay/embedding_handler.go`; do not move this path back to Python/model-detailed or a separate sidecar/container. Default governed model is `embedding-gte-v1`.
- Local TEI reranking uses public alias `reranker-gte-v1`. Preserve the Advanced Custom converter `jina_rerank_to_tei_native`, the `/v1/rerank` to `/rerank` protocol conversion, and acquisition of the same Go-native governor from `relay/rerank_handler.go`. TEI-native `texts`/`score` must remain hidden behind the public `documents`/`results[].relevance_score` contract.
- Runtime directories must stay excluded from image build context through `.dockerignore`: `/backups`, `/data`, `/logs`, `/runtime`.
- Router Docs buttons and config must stay same-origin and localized:
  English uses `/en/docs`; Portuguese uses `/pt/docs`. Do not restore
  `https://docs.newapi.pro` in the router app or Apache redirect rules.
- Legacy API-doc aliases must remain local JSON endpoints:
  `/docs.json`, `/docs/openapi.json`, `/json` and `/json/` must resolve to
  the docs app OpenAPI 3.x JSON, not to the Go SPA HTML and not to the retired
  `model-detailed` sidecar.
- PT-BR is mandatory in backend, web/default and web/classic. A protected glob
  is not sufficient by itself: `scripts/smoke-pt-br-i18n.sh` must pass after
  every sync and the release preflight must reject missing registrations,
  locale key drift or placeholder drift.
- The personal Atius Router must never accept or reject a local request based
  on account, user-wallet or subscription balance. Negative wallet balance is
  valid accounting state. Subscription absence/exhaustion must fall back to
  wallet accounting even when `allow_wallet_overflow=false`. Finite token
  quota and upstream-provider quota/auth errors remain separate contracts.
- `scripts/atius-user-quota-guard.sh repair` is mandatory after every sync. It
  is idempotent, creates a backup, applies the recovery patch only after
  `git apply --check`, and finishes with the same fail-closed audit. The
  `omni-srv-admin` release preflight independently scans the admission paths
  and blocks deploy if `GetUserQuota`, `insufficient_user_quota`,
  `quota_not_enough`, subscription-overflow authorization, or direct
  `userQuota`/`.UserQuota` admission access returns there. Post-accounting
  balance notifications outside `PreWssConsumeQuota` remain allowed.
- `patches/atius-user-quota-unlimited.patch` is the recovery artifact. Run the
  Router guard in `repair` mode only from a reviewed checkout, then rerun the
  default audit and focused tests before build/deploy.

## Protected paths that carry this behavior

- `.dockerignore`
- `controller/model.go`
- `controller/model_list_test.go`
- `controller/channel.go`
- `controller/codex_*.go`
- `service/modelcatalog/`
- `relay/common/relay_utils.go`
- `relay/common/relay_utils_test.go`
- `relay/embedding_handler.go`
- `relay/embedding_handler_test.go`
- `relay/rerank_handler.go`
- `service/embeddinggovernor/`
- `service/pre_consume_quota.go`
- `service/billing_session.go`
- `service/quota.go`
- `relay/mjproxy_handler.go`
- `service/billing_session_wallet_overdraft_test.go`
- `scripts/atius-user-quota-guard.sh`
- `patches/atius-user-quota-unlimited.patch`
- `docs/ATIUS-USER-QUOTA-INVARIANT.md`
- `common/endpoint_type.go`
- `common/endpoint_type_test.go`
- `constant/channel.go`
- `dto/embedding.go`
- `relay/channel/codex/`
- `relay/channel/advancedcustom/`
- `relay/codex_auth_error.go`
- `relay/responses_handler.go`
- `relay/compatible_handler.go`
- `relay/chat_completions_via_responses.go`
- `relay/helper/valid_request.go`
- `relay/channel/minimax/`
- `relay/channel/deepseek/`
- `service/codex_*.go`
- `router/channel-router.go`
- `types/error.go`
- `dto/channel_settings.go`
- `dto/channel_settings_tei_rerank_test.go`
- `k8s/router-ai-atius/configmap.yaml`
- `web/default/src/features/channels/`
- `setting/console_setting/`
- `web/default/src/features/pricing/components/model-details-api.tsx`
- `web/default/src/features/system-settings/content/default-api-info.ts`
- `web/default/src/features/system-settings/content/index.tsx`
- `.github/workflows/sync.yml`
- `.github/codex/`
- `tools/clianything.py`
- `tests/test_clianything.py`
- `docs/`
- `.planning/`
- `controller/misc.go`
- `setting/operation_setting/general_setting.go`
- `web/default/src/lib/docs-link.ts`
- `web/default/src/hooks/use-top-nav-links.ts`
- `web/default/src/components/layout/types.ts`
- `web/default/src/components/layout/components/nav-link-item.tsx`
- `web/default/src/components/layout/components/top-nav.tsx`
- `web/default/src/components/layout/components/public-header.tsx`
- `web/default/src/components/layout/components/public-navigation.tsx`
- `web/default/src/components/layout/components/mobile-drawer.tsx`
- `web/default/src/features/home/components/sections/hero.tsx`
- `web/default/src/components/layout/components/footer.tsx`
- `web/default/src/features/system-settings/general/quota-settings-section.tsx`
- `web/classic/src/helpers/docs.js`
- `web/classic/src/hooks/common/useNavigation.js`
- `web/classic/src/components/layout/headerbar/index.jsx`
- `web/classic/src/components/layout/headerbar/Navigation.jsx`
- `web/classic/src/pages/Home/index.jsx`
- `web/classic/src/components/layout/Footer.jsx`
- `web/classic/src/pages/Setting/Operation/SettingsGeneral.jsx`
- `docs/atius-router-docs/src/lib/i18n.ts`
- `docs/atius-router-docs/next.config.mjs`
- `docs/atius-router-docs/middleware.ts`
- `docs/atius-router-docs/src/app/json/route.ts`
- `docs/atius-router-docs/src/app/[lang]/layout.tsx`
- `docs/atius-router-docs/src/app/[lang]/(home)/layout.tsx`
- `docs/atius-router-docs/src/components/footer.tsx`
- `docs/atius-router-docs/content/docs/pt/guide/index.mdx`
- `docs/atius-router-docs/content/docs/pt/guide/meta.json`
- `docs/atius-router-docs/content/docs/pt/guide/project-introduction.mdx`
- `docs/atius-router-docs/content/docs/pt/guide/technical-architecture.mdx`
- `scripts/smoke-docs-links.sh`
- `i18n/locales/pt.yaml`
- `i18n/i18n.go`
- `web/default/src/i18n/config.ts`
- `web/default/src/i18n/languages.ts`
- `web/default/src/i18n/locales/pt.json`
- `web/default/scripts/sync-i18n.mjs`
- `web/classic/src/i18n/`
- `web/classic/src/components/layout/headerbar/LanguageSelector.jsx`
- `web/classic/src/components/settings/personal/cards/PreferencesSettings.jsx`
- `scripts/smoke-pt-br-i18n.sh`

## Required post-sync checks

Run from `/home/ubuntu/GitHub/containers/router-ai-atius` after any upstream sync:

```bash
scripts/atius-user-quota-guard.sh repair
scripts/smoke-pt-br-i18n.sh
go test ./common ./controller ./service/modelcatalog ./relay/common ./relay/channel/minimax ./relay/channel/deepseek ./relay/channel/codex ./service ./service/embeddinggovernor ./relay -count=1
python3 -m py_compile tools/clianything.py scripts/smoke-provider-consolidation.py scripts/smoke-embeddings.py
python3 -m unittest discover -s tests -p 'test_clianything*.py'
bin/clianything status --strict
bin/clianything providers --all
scripts/smoke-docs-links.sh
```

The first command automatically repairs a recognized upstream regression and
then audits the resulting tree. It remains fail-closed: do not push, build or
deploy a sync that it cannot repair and validate. The separate
`omni-srv-admin` release preflight repeats the static admission-path audit
before `fork-sync` starts the production build. The configured `post_sync`
also runs the focused governed-reranker tests through the Router resource
wrapper, and the release preflight requires both governed aliases in the
ConfigMap before deployment.

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
- Current active embeddings route: channel `Atius Local` with public model `embedding-gte-v1`, HA upstream `http://10.21.1.21:31115` over OCI-primary, dimension `768`, protected by the Go-native governor. `http://10.100.100.4:3115` remains reserve fallback, not the primary router upstream.
- Active Apache `/v1/` and `/health` route directly to Go on `127.0.0.1:3000`; do not restore `127.0.0.1:3300`, `127.0.0.1:3399`, or pod port `3001`.
