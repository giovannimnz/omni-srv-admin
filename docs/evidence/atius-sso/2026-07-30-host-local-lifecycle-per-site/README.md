# Atius SSO host-local lifecycle evidence — 2026-07-30

## Verdict

PASS.

## Scope

| Site | Cycles | Screenshots | Report |
|---|---:|---:|---|
| `grafana.atius.com.br` | 2 | 8 | `grafana-pass/report.json` |
| `portainer.atius.com.br` | 2 | 8 | `portainer-pass/report.json` |
| `docker.atius.com.br` | 2 | 8 | `docker-pass/report.json` |
| `vpn.atius.com.br` | 2 | 8 | `vpn-pass/report.json` |
| `adguard.atius.com.br` | 2 | 8 | `adguard-pass/report.json` |

Totals: 5 sites, 10 login/logout cycles, 40 screenshots.

## Required cycle per site

1. anonymous access;
2. app-local `/login` on the same hostname;
3. authenticated application view;
4. logout back to app-local `/login`.

The evidence harness asserts:

- no visible `sso.atius.com.br` during the human app flow;
- `auth-token` exists after login;
- `auth-token` is cleared after logout;
- every final logout URL is `https://<site>.atius.com.br/login`;
- screenshots are written with an injected evidence URL banner because headless screenshots do not include the browser address bar.

## Files

- `combined-report.json` — merged report for all five sites.
- `SHA256SUMS` — hash manifest for reports and screenshots.
- `<site>-pass/cycle-*-*.png` — per-site evidence screenshots.

## Notes

- Full five-site run exceeded the 600s foreground tool limit under SRV-1 load. Final evidence was collected per-site to keep the same browser assertions while avoiding central SSO/auth pressure from login bursts.
- Bare non-browser `curl /` on AdGuard fails closed as `401`; browser/document requests with `Accept: text/html` redirect to app-local `/login` and passed the lifecycle harness.
