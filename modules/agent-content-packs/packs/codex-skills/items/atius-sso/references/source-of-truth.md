# Atius SSO - Source of Truth

This registry points to the existing owners. It does not create a second
canonical knowledge page.

## Contract capsule

- Human route: canonical app-local `/login`, kept visible by internal rewrite
  or minimal proxy.
- Compatibility route: `/sso` is internal/controlled and must land cleanly on
  `/login`; `externalLoginToSsoRedirectAllowed=false`.
- Destination lifecycle: `valid | missing | rejected` across entry, login,
  logout-complete, re-entry, and return.
- Missing/rejected context: neutral, never implicit Trade.
- Central logout: POST-only `/api/sso/logout` with real browser `Origin`,
  `Content-Type: application/json`, and session-bound one-time
  `X-CSRF-Token`; GET, wrong Origin, wrong content type, missing/invalid/replayed
  CSRF fail closed.
- App-local logout: one exact/minimal operation, never a general ATS API proxy.
- Rollback: backup, restore, contract rerun, and readback are mandatory.

Exact neutral state:

- `Sessão Atius ativa`
- `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.`
- `Destino seguro`
- `Nenhum destino selecionado`
- URL `https://sso.atius.com.br/login`
- no application navigation controls

Runtime status is **live and visually sealed for the 2026-07-31 fleet scope**:
12/12 sites, 24/24 browser cycles, and 12/12 independent visual review in the
owner evidence pack. Plans 10-04 and 10-05 have materialized runtime promotion
and final browser/visual evidence; older pending-promotion wording is historical.
Future app expansions still need their own lifecycle evidence.

## Canonical owner manuals

- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-manual-index.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-learnings.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-operations-manual.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-wide-sso.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-application-playbook.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-lifecycle-matrix.md`

## Canonical knowledge and readback

- Obsidian:
  `/home/ubuntu/GitHub/obsidian-vault/AiSecondBrain/30-RECURSOS/atius/SSO-Atius-Guia-Canonico.md`
- GBrain full slug:
  `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`

Readback:

```bash
/home/ubuntu/.local/bin/gbrain get \
  aisecondbrain/30-recursos/atius/sso-atius-guia-canonico
```

Do not use the non-resolving short slug and do not duplicate the knowledge
record.

## Workstream evidence

- `/home/ubuntu/GitHub/omni-srv-admin/.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-PATTERNS.md`

## Central ATS code and machine contract

- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/post-logout.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/oidc.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/sso/login/page.tsx`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/logout/route.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/fixtures/sso-lifecycle-contract.json`

## Acceptance

- Skill acceptance matrix:
  `/home/ubuntu/.codex/skills/atius-sso/references/lifecycle-acceptance.md`
- Owner lifecycle matrix:
  `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-lifecycle-matrix.md`
- Audit runner:
  `/home/ubuntu/GitHub/omni-srv-admin/scripts/validate-atius-sso-lifecycle-contract.mjs`

## Secrets rule

HashiCorp Vault is authoritative. Record identifiers only:

- profile `browser-login`
- path `kv/atius/browser-login/access-keys`
- fields `username`, `password`, `totp_secret`

Never use `.env`, `.zshrc`, shell history, chat, Obsidian, or GBrain as a
secret source, and never write a secret value into evidence.
