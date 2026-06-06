# Fleet Inventory Model

## Localização

```text
inventory/hosts/*.yaml
inventory/remotes/*.yaml
inventory/groups/*.yaml
```

## Host schema v0

```yaml
id: atius-srv-1
aliases:
  - srv1
role: production
owner: giovanni
access:
  ssh: ubuntu@10.1.1.1
  public_ip: 137.131.190.161
  vpn_ip: 10.1.1.1
platform:
  provider: oracle-oci
  os: ubuntu-22.04
  arch: arm64
status: active
modules:
  - srv1-ops
  - xrdp-abnt2
logs:
  local_dir: /home/ubuntu/.logs
  retention_days: 15
backup:
  gdrive_base: ATIUS-SRV/SRV-1/Backup
notes:
  vault_project: 20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin
```

## Campos

| Campo | Obrigatório | Descrição |
|---|---:|---|
| `id` | sim | identificador estável |
| `aliases` | não | nomes curtos |
| `role` | sim | production, development, sandbox, mobile-node, etc |
| `owner` | sim | dono/responsável |
| `access.ssh` | não | endpoint SSH se aplicável |
| `platform` | sim | provider/OS/arch/device |
| `status` | sim | active, planned, template, retired |
| `modules` | não | módulos aplicáveis |
| `constraints` | não | restrições do host |
| `logs` | não | padrão local de logs |
| `backup` | não | destino e política |

## Remote schema v0

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

## Classes de host

| Classe | Exemplo | Systemd | PM2 | Backup | Remote exec |
|---|---|---:|---:|---:|---:|
| Oracle OCI Ubuntu | SRV-1/2/3 | sim | sim | sim | futuro |
| Termux | S23 host | não | parcial | custom | futuro limitado |
| PRoot Ubuntu | S23 guest | não real | parcial | custom | futuro limitado |
| Workstation | Dell | sim | sim | sim | futuro |
| Support temporary | amigo/cliente | desconhecido | desconhecido | escopo explícito | auditado |

## Regras

- Não inferir capabilities por nome do host.
- Sempre ler `platform` + `constraints`.
- Módulo só roda se listado em `modules` ou explicitamente permitido.
- Execução destrutiva requer backup e aprovação explícita.
