# Remote Manager

> Gestão versionada de mapeamentos remotos: CIFS/SMB, GDrive/rclone, GTK bookmarks, PCManFM Places e labels visuais.

## Objetivo

Separar duas coisas que eram confundidas:

| Conceito | Exemplo | Pode mudar? | Impacto |
|---|---|---:|---|
| Mount path estável | `/home/ubuntu/Shared_smb` | só com migração planejada | scripts, backups, fstab, systemd |
| Label visual | `Shared_smb`, `Shared` | sim | PCManFM/LXDE Places |

A regra é: **renomear label visual não renomeia mount path**.

## Caso real

Entrada GTK atual:

```text
file:///home/ubuntu/Shared_smb Shared_smb
```

Renomear o label visual para `Shared`:

```bash
omni remote-manager rename-label srv1-shared-smb Shared
```

Resultado:

```text
file:///home/ubuntu/Shared_smb Shared
```

O mount continua:

```text
/home/ubuntu/Shared_smb
```

## Comandos

```bash
omni remote-manager list
omni remote-manager show srv1-shared-smb
omni remote-manager places
omni remote-manager status
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
omni remote-manager rename-label srv1-shared-smb Shared
```

## Inventário

Remotes ficam em:

```text
inventory/remotes/*.yaml
```

Exemplo:

```yaml
id: srv1-shared-smb
host_id: atius-srv-1
type: cifs
source: //10.1.1.2/Shared
mount_path: /home/ubuntu/Shared_smb
display_label: Shared_smb
places:
  gtk_bookmarks: /home/ubuntu/.config/gtk-3.0/bookmarks
```

## Segurança

- `rename-label` altera só GTK bookmarks + `display_label` no YAML.
- Não edita `/etc/fstab`.
- Não desmonta mount.
- Não renomeia diretório.
- Não toca em dados do SMB.
- Para mudança real de mount path, abrir migração separada com backup + ref scan.

## PCManFM/LXDE

PCManFM usa GTK bookmarks para a barra lateral `Locais`.

Arquivo:

```text
~/.config/gtk-3.0/bookmarks
```

Formato:

```text
file:///path Label Opcional
```

Sem label, PCManFM usa o nome da pasta.
Com label, PCManFM mostra o label mesmo que o path continue igual.

## Pitfalls

- CIFS também pode aparecer em `Locais` via GVFS/UDisks. Para evitar duplicação, usar `x-gvfs-hide,x-gdu.hide` em `/etc/fstab` e manter só bookmark explícito.
- Não renomear `/home/ubuntu/Shared_smb` sem atualizar backup scripts, fstab, systemd automount, docs, vault e referencias.
- `Shared_smb` é path técnico; `Shared` é label humano.

## Validação

```bash
omni remote-manager places | grep Shared
findmnt -R /home/ubuntu/Shared_smb
```

Esperado:

- Places mostra label novo.
- findmnt continua mostrando `/home/ubuntu/Shared_smb`.
