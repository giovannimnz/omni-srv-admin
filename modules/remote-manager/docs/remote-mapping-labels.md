# Remote Mapping Labels

## Decisão

Labels visuais de remotes são configuráveis via `omni remote-manager`, mas paths técnicos permanecem estáveis.

## Porquê

Scripts e automações dependem de paths estáveis:

```text
/home/ubuntu/Shared_smb
```

Humanos preferem labels limpos no desktop:

```text
Shared
```

Separar label de path evita quebrar:

- `/etc/fstab`
- systemd automount
- backup scripts
- GDrive backup map
- docs/runbooks
- crons
- shell history

## Operação suportada

```bash
omni remote-manager rename-label srv1-shared-smb Shared
```

## Operação não suportada automaticamente

```text
/home/ubuntu/Shared_smb -> /home/ubuntu/Shared
```

Isso exige migração separada:

1. backup
2. ref scan
3. fstab update
4. systemd daemon-reload
5. remount
6. backup-map update
7. docs update
8. validation

## Estado SRV-1

```text
source: //10.1.1.2/Shared
mount_path: /home/ubuntu/Shared_smb
default_label: Shared_smb
```
