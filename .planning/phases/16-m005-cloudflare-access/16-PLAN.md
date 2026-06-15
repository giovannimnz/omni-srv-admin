---
phase: 16
padded: 16
slug: m005-cloudflare-access
name: M005 Cloudflare Access
date: 2026-06-15
status: ready
wave: 1
depends_on: []
autonomous: true
requirements_addressed:
  - CFL-01
  - CFL-02
  - CFL-03
---

# Phase 16: M005 Cloudflare Access

## Goal

Substituir Apache Basic Auth nos admin edges (`portainer.atius.com.br`,
`docker.atius.com.br`) por Cloudflare Access. Service token pra
automação. Apache Basic Auth retained como fallback documentado.

## Motivation

Hoje, `docker.atius.com.br` e `portainer.atius.com.br` retornam 401 com
Basic Auth challenge. Isso é seguro mas hostil: requer o usuário
lembrar credenciais, não tem SSO, não tem audit log centralizado, e
qualquer leak da credencial expõe o Portainer inteiro.

Cloudflare Access é a solução free-tier da Cloudflare (até 50 users
sem custo) que coloca um SSO na frente do admin edge. Giovanni já tem
Cloudflare configurado (cfk_Br...b03f Global API key documentado no
ROADMAP), só falta habilitar Access no account.

## Tasks

### Task 1: enable Cloudflare Access on account

UI work in Cloudflare dashboard:
- Account → Access → Applications → Add an application → Self-hosted
- Name: `Atius Admin Edge`
- Domain: `portainer.atius.com.br, docker.atius.com.br`
- Session duration: 24h
- Application policies: Allow rule with email `giovannimunizds@hotmail.com` (and any future admins)
- Identity providers: enable One-time PIN (default; no OAuth setup needed for first iteration)

### Task 2: service token for omni-cli automation

Cloudflare dashboard → Access → Service Auth → Generate token
- Name: `omni-cli-automation`
- Duration: 1 year
- Copy token (CF_CLIENT_ID, CF_CLIENT_SECRET) to `~/.hermes/secrets/cloudflare-service-token.json` (mode 600)

Update `omni-cli` to inject the service token when calling admin edges:

```python
# cli/omni/edge.py
CF_SERVICE_TOKEN_FILE = os.path.expanduser("~/.hermes/secrets/cloudflare-service-token.json")
def cf_service_auth_headers():
    if not os.path.exists(CF_SERVICE_TOKEN_FILE):
        return {}
    data = json.loads(open(CF_SERVICE_TOKEN_FILE).read())
    return {
        "CF-Access-Client-Id": data["client_id"],
        "CF-Access-Client-Secret": data["client_secret"],
    }
```

### Task 3: Apache Basic Auth fallback

Don't remove Basic Auth yet. Document the cutover procedure in
`docs/operations/edge-auth.md`:
- Step-by-step how to remove Basic Auth and rely on Cloudflare Access
- How to re-enable Basic Auth if Access is down (incident response)

When ready (gated by user), remove Basic Auth. Until then, the
endpoints work with EITHER Cloudflare Access OR Basic Auth (Cloudflare
just shows a login page first; Basic Auth is the underlying
authentication).

### Task 4: validation + runbook

- `curl -I https://portainer.atius.com.br/` → expect 302 redirect to
  Cloudflare Access login page (not 401 Basic Auth challenge)
- Test with CF service token:
  `curl -H "CF-Access-Client-Id: ..." -H "CF-Access-Client-Secret: ..." https://portainer.atius.com.br/api/status` → 200
- `omni fleet portainer status --use-service-token` → 200 with cluster info
- 16-SUMMARY.md: tasks, deviations, validation

## Success Criteria

- [ ] Cloudflare Access policy live for both admin domains
- [ ] `curl -I https://portainer.atius.com.br/` returns 302 (not 401)
- [ ] Service token works: `curl -H "CF-Access-..."` returns 200
- [ ] `omni-cli` integration tested with the service token
- [ ] `docs/operations/edge-auth.md` documents cutover + rollback
- [ ] Apache Basic Auth still active (fallback) — verify with a direct curl that bypasses Cloudflare (e.g., 10.1.1.1:9444 from inside the VPN)

## Risks

- **Account tier:** Cloudflare Access free tier supports up to 50 users. Currently 1 user (Giovanni), so this is fine. If team grows, may need upgrade.
- **Service token secret rotation:** every 1 year per token, but the secrets file has to be updated. Documented rotation procedure.
- **Total Access outage:** if Cloudflare has an outage, admin edges become inaccessible. Mitigation: Apache Basic Auth remains enabled as fallback. Documented.

## Out of Scope

- OAuth/Google integration for Access (start with email one-time PIN, add OAuth later if needed)
- Per-app Access policies (one policy for both domains is fine for now)
- Access for non-admin domains (jenkins.atius.com.br, cloudbeaver.atius.com.br) — these are public-ish and can keep their current auth

## Next Phase Readiness

Phase 17 (Observability + RWX) is independent and can run in parallel.
