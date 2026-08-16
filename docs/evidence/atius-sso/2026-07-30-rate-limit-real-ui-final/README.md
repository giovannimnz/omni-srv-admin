# Atius SSO — validação final após correção de rate limit

Data operacional: 2026-07-30 BRT

## Escopo

- `grafana.atius.com.br`
- `portainer.atius.com.br`
- `docker.atius.com.br`
- `vpn.atius.com.br`
- `adguard.atius.com.br`

## Resultado

| Site | Ciclos | Screenshots | Logout usado | Veredito |
|---|---:|---:|---|---|
| Grafana | 2 | 8 | controle visível `Sair do Atius SSO` | PASS |
| Portainer | 2 | 8 | controle visível `Sair do Atius SSO` | PASS |
| Docker | 2 | 8 | controle visível `Sair do Atius SSO` | PASS |
| VPN | 2 | 8 | controle nativo `Sair da Atius VPN` | PASS |
| AdGuard | 2 | 8 | controle nativo `Encerrar sessão` | PASS |

Total: `5` sites, `10` ciclos, `40` screenshots.

## Contrato provado

1. Acesso anônimo termina em `https://<site>.atius.com.br/login`.
2. O login real entra no app e espera a UI protegida ficar pronta.
3. O logout é acionado por controle visível do app, não por navegação artificial do harness.
4. O cookie `auth-token` existe após login e não existe após logout.
5. O logout termina em `https://<site>.atius.com.br/login`.
6. Nenhuma navegação visível usa `sso.atius.com.br`.
7. Os cinco `/login` seguem a identidade visual do modelo `/home/ubuntu/GitHub/Prints/sso-ssh-base-model.png`.

## Causa raiz corrigida

O ATS API aplica `@fastify/rate-limit` global de `100` requests por minuto. Os gateways admin-edge e AdGuard validavam `GET /v1/auth/me` repetidamente para assets e requests do app. A bateria multi-site consumia o budget e fazia `POST /v1/token/generate` retornar `429`. Os adapters apresentavam esse `429` como credencial inválida.

Correções:

- cache positivo de sessão por token e origem por `30s`;
- coalescing de validações concorrentes;
- `401/403` continuam significando sessão/credencial inválida;
- `429/5xx` agora significam indisponibilidade temporária;
- frontend VPN mantém cache de sessão e diferencia indisponibilidade de sessão inválida;
- admin edges expõem logout Atius host-local visível e integram o logout do Portainer;
- harness exige controle de logout visível e marcador de UI pronta.

## Revisão visual

Arquivos:

- `visual-review/login-parity-contact-sheet.png`
- `visual-review/grafana-contact-sheet.png`
- `visual-review/portainer-contact-sheet.png`
- `visual-review/docker-contact-sheet.png`
- `visual-review/vpn-contact-sheet.png`
- `visual-review/adguard-contact-sheet.png`

A primeira revisão detectou estados incompletos no Docker e VPN. O harness foi endurecido e os screenshots foram regenerados. A revisão final marcou os cinco sites como PASS, sem loading/error nos estados autenticados finais.

## Integridade

- `combined-report.json`: resultado agregado.
- `<site>/report.json`: navegações, ciclos, URLs e hashes por site.
- `SHA256SUMS`: manifesto de todos os artefatos.
- Permissões: arquivos privados `0600`; diretórios `0700`.
- Credenciais, cookies e tokens não foram persistidos.

## Observação operacional separada

Três timeouts do upstream Portainer foram registrados depois dos ciclos finais. Não houve `429`, falha de login ou falha dos ciclos associados. Tratar como saúde do upstream `10.12.1.12:9443`, separada do contrato SSO.
