# GDrive backup offload — SRV-1

## Contrato

- `/home/ubuntu/.backups` → `ATIUS-SRV/SRV-1/Backup/home/ubuntu/.backups`
- `/home/ubuntu/backups` → `ATIUS-SRV/SRV-1/Backup/home/ubuntu/backups`

Cada item de primeiro nível vira um `tar.gz` versionado pelo fingerprint da
árvore. A rotina não usa `~/GDrive` para escrita nem cria archive temporário em
disco: `tar | pigz -p1 | rclone rcat`. O SHA-256 é calculado no stream e
recalculado com `rclone cat`; o mesmo readback conta os bytes. Estabilidade da
origem e ACK do upload do manifest também precisam passar. Só então ocorre a
remoção local.

Arquivos `.partial` mais novos que 24 horas ficam locais. Após o age gate, são
armazenados em `_quarantine`, com o mesmo readback, antes da remoção.

## Auth e serialização

O padrão é `atius-rclone-vault-hydrate`, que materializa a referência
`kv/atius/fleet-backup/rclone/giovanni-drive#rclone_conf` em tmpfs. Nunca
imprimir o conteúdo. `CONFIG_MODE=persistent` é fallback explícito de recovery.
O backup diário usa o mesmo hydrator (`RCLONE_CONFIG_MODE=persistent` é seu
fallback explícito equivalente).

`/tmp/rclone-fleet.lock` é comum ao offload, backup diário e fleet queue. O mount
user `rclone-gdrive-mount.service` é o único mount permitido; a unit system-wide
legada `rclone-gdrive.service` deve permanecer inativa.

## Operação

```bash
modules/srv1-ops/scripts/install-gdrive-backup-offload.sh --dry-run
modules/srv1-ops/scripts/install-gdrive-backup-offload.sh --apply
modules/srv1-ops/scripts/offload-dotbackups-to-gdrive.sh --dry-run
systemctl --user start offload-dotbackups-to-gdrive.service
cat ~/.local/state/omni/gdrive-backup-offload/last-run.json
```

Gate final: service `inactive/dead` com `Result=success`, timer `active/waiting`
com próximo trigger finito, duas roots vazias ou só com itens no age gate,
objetos e manifests remotos presentes e nenhum writer `rclone` órfão.

## Falhas que bloqueiam delete

- auth/hydration ou rate limit não recuperado;
- origem ilegível, alterada durante upload ou fora das duas roots;
- falha no stream/tar/rclone;
- SHA-256 ou tamanho remoto diferente;
- manifest ausente ou com hash diferente;
- falha ao remover o item exato.

O autoclean genérico nunca remove essas roots; a única exceção é este offload
allowlisted depois do gate remoto.

## Rollback

O installer salva as units anteriores em
`~/.backups/gdrive-backup-offload-install-<timestamp>`. Para rollback, pare os
timers, restaure as quatro units em `~/.config/systemd/user/`, execute
`systemctl --user daemon-reload` e valide o snapshot antes de reativar. Não
reative a unit system-wide duplicada enquanto o mount user estiver ativo.
