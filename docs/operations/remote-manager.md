# Remote Manager Operations

## Comandos

```bash
omni remote-manager list
omni remote-manager show srv1-shared-smb
omni remote-manager places
omni remote-manager status
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
omni remote-manager rename-label srv1-shared-smb Shared
```

## Renomear label visual

Caso: mostrar `Shared` no PCManFM sem renomear `/home/ubuntu/Shared_smb`.

```bash
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
omni remote-manager rename-label srv1-shared-smb Shared
```

Validação:

```bash
omni remote-manager places | grep Shared
findmnt -R /home/ubuntu/Shared_smb
```

## Arquivo alterado

```text
~/.config/gtk-3.0/bookmarks
```

Exemplo antes:

```text
file:///home/ubuntu/Shared_smb Shared_smb
```

Depois:

```text
file:///home/ubuntu/Shared_smb Shared
```

## Arquivo de inventário atualizado

```text
inventory/remotes/srv1-shared-smb.yaml
```

Campo:

```yaml
display_label: Shared
```

## Não faz

- Não altera `/etc/fstab`.
- Não desmonta CIFS.
- Não renomeia diretório.
- Não altera backup scripts.
- Não mexe em dados remotos.

## Migração de mount path

Se um dia quiser trocar path técnico:

```text
/home/ubuntu/Shared_smb -> /home/ubuntu/Shared
```

Abrir tarefa separada:

1. backup
2. scan refs
3. editar `/etc/fstab`
4. `systemctl daemon-reload`
5. remount
6. atualizar scripts
7. atualizar docs/vault
8. validar backups

## Pitfall: duplicação em PCManFM

`Shared_smb` pode aparecer duas vezes em `Locais` por duas fontes:

- GVFS/UDisks detectando o CIFS do fstab
- GTK bookmark manual

Mitigação:

```text
/etc/fstab options: x-gvfs-hide,x-gdu.hide
~/.config/gtk-3.0/bookmarks: entrada única com label desejado
```
