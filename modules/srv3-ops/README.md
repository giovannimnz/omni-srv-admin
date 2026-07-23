# SRV-3 operations

**Canonical host endpoint:** `atius-srv-3.atius.internal` (`10.13.1.13`).
The short value `atius-srv-3` is retained only where a fleet `host_id` is
required; SSH and service references use the FQDN.

## OCI Admin PM2

O runtime do OCI Admin usa o namespace PM2 `oci-admin`, com duas apps:

- `oci-admin-web`: FastAPI backend com frontend Jinja/static integrado;
- `oci-admin-mcp-http`: MCP Streamable HTTP.

O ecosystem canônico pertence ao produto em
`/home/ubuntu/GitHub/oci-admin/deploy/pm2/ecosystem.config.cjs`. O
`pm2-ubuntu.service` é o único boot owner e executa `pm2 resurrect` sobre
`/home/ubuntu/.pm2/dump.pm2`.

O watchdog deste módulo roda a cada 30 segundos, exige duas falhas antes de
agir, aplica cooldown de 120 segundos e recupera somente a app afetada. Falha
do probe público é observada, mas não causa restart local quando os probes
privados estão saudáveis.

`oci-admin-pm2-save` é o único caminho documentado para atualizar o snapshot:
ele aplica mode 0600, rejeita nomes de env sensível no dump e exige as duas
apps do namespace. Logs têm rotação diária/10 MiB e retenção de 14 arquivos.
`oci-admin-pm2-start` inicia o ecosystem com `env -i`; o ecosystem também
filtra os prefixes `ATIUS_`, `OCI_ADMIN_` e `VAULT_`. Isso impede que o
ambiente do operador seja serializado pelo PM2.

Instalação dos artefatos, sem ativar o timer:

```bash
modules/srv3-ops/scripts/install-oci-admin-pm2-monitoring.sh
```

Após o cutover e os smokes:

```bash
sudo systemctl enable --now oci-admin-watchdog.timer
/usr/local/sbin/oci-admin-pm2-save
```
