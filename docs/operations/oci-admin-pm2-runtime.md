# OCI Admin PM2 runtime

## Contrato

- Host: `atius-srv-3`.
- Caminho primario: OCI/DRG `10.13.1.13`; `10.100.100.3` e reserve.
- Namespace: `oci-admin`.
- Apps: `oci-admin-web` e `oci-admin-mcp-http`.
- Boot owner: `pm2-ubuntu.service` via `pm2 resurrect`.
- Snapshot: `/home/ubuntu/.pm2/dump.pm2`.
- Monitor: `oci-admin-watchdog.timer`, a cada 30 segundos.
- Ecosystem canônico: ponteiro
  `/home/ubuntu/.local/share/oci-admin/current/deploy/pm2/ecosystem.config.cjs`,
  com alvo imutável em `releases/<commit>`.

O processo web reune FastAPI, rotas backend, templates Jinja e static assets.
Nao ha frontend Node independente. O CLI continua on-demand.
O checkout de controle não é runtime: mudanças locais não commitadas nunca
entram em restart, watchdog ou resurrect.

## Secrets

`oci-admin-env.service` e `oci-admin-mcp-env.service` hidratam arquivos
efemeros sob `/run`. Os runners PM2 leem esses arquivos somente no processo
filho. O ecosystem e o `dump.pm2` nao recebem valores de secret. O start
canonico e `/usr/local/sbin/oci-admin-pm2-start`, que usa `env -i`; iniciar o
ecosystem diretamente de um shell hidratado e proibido.

## Recovery

PM2 faz autorestart com delay de 5 segundos, limite de 100 restarts instaveis
e memory ceilings por app. O watchdog adiciona health recovery com threshold
de duas falhas e cooldown de 120 segundos. Toda recuperacao e direcionada a
uma unica app; restart amplo do namespace ou daemon e proibido no watchdog.
Os logs sao rotacionados diariamente ou ao atingir 10 MiB, com 14 arquivos de
retencao.

O drop-in systemd executa o daemon como usuario estatico nao-root e aplica
hardening. O gate live de `systemd-analyze security` classificou supervisor e
watchdog como `2.9 OK` em 2026-07-22.

## MCP

- Nome client-side: `oci_admin_http`.
- URL: `https://mcp.atius.com.br/oci-admin`.
- Identidade protocolar: `serverInfo.name=oci-admin`.
- Bearer: `ATIUS_MCP_TOKEN`, profile Vault `atius-mcp`.
- Contrato: GET/HEAD `405`; POST sem bearer `401`; `initialize` autenticado
  `200`; `tools/list` `200` com exatamente nove tools allowlisted.

## Gates

```bash
pm2 jlist | jq -r '.[] | select(.pm2_env.namespace == "oci-admin") | [.name,.pm2_env.status,.pm2_env.restart_time] | @tsv'
curl -fsS http://10.13.1.13:8080/healthz
curl -fsS http://10.13.1.13:8090/healthz
systemctl is-enabled pm2-ubuntu.service oci-admin-watchdog.timer
systemctl is-active pm2-ubuntu.service oci-admin-watchdog.timer
```

Depois de qualquer mudanca intencional de topologia:

```bash
/usr/local/sbin/oci-admin-pm2-save
```
