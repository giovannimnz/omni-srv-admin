# Fleet Autoclean

Autoclean seguro para os hosts `ATIUS-SRV-1`, `ATIUS-SRV-2` e `ATIUS-SRV-3`.

## Commands

```bash
PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/cli \
  python3 -m omni srv storage-audit all

PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/cli \
  python3 -m omni srv autoclean all

PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/cli \
  python3 -m omni srv autoclean all --apply
```

Use `OMNI_SRV_PUBLIC_FIRST=1` quando a VPN `10.1.1.0/24` estiver fora e os
IPs publicos estiverem respondendo.

## Safety

- `autoclean` roda em dry-run por padrao.
- `--apply` limpa apenas itens regeneraveis: `/tmp` antigo, caches, logs
  grandes/antigos, imagens dangling e journal.
- Volumes de containers nao entram por padrao. Use `--include-volumes` apenas
  depois de validar que nao ha volumes vivos.
- Backups grandes como `pre-upgrade-24.04-backup`,
  `srv3-disk-relief-before-config-clone-*`, `.config-clone-backups` e
  `.backups` entram como manual-review, nunca delete automatico.

## Jobs

Units versionadas:

```text
modules/fleet-autoclean/systemd/fleet-storage-audit.service
modules/fleet-autoclean/systemd/fleet-storage-audit.timer
modules/fleet-autoclean/systemd/fleet-autoclean.service
modules/fleet-autoclean/systemd/fleet-autoclean.timer
```

Instalacao live deve copiar para `~/.config/systemd/user/`, rodar
`systemctl --user daemon-reload` e habilitar timers manualmente.
