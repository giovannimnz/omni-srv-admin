# Omni SRV Admin

> Fleet-first server administration for the Atius infrastructure.
>
> One repo to inventory hosts, operate local services, manage backups, normalize remote mounts, keep documentation current, and scale Giovanni's infrastructure from one Oracle VM to a multi-server/mobile/workstation fleet.

[![scope](https://img.shields.io/badge/scope-fleet--admin-0d1117?style=flat&labelColor=30363d)](#)
[![host](https://img.shields.io/badge/primary--host-atius--srv--1-1f6feb?style=flat)](#)
[![cli](https://img.shields.io/badge/cli-omni-7c3aed?style=flat)](#)
[![backup](https://img.shields.io/badge/backups-gdrive%20%2B%20smb-238636?style=flat)](#)
[![docs](https://img.shields.io/badge/docs-agent--first-f97316?style=flat)](#)

---

## TL;DR

`omni-srv-admin` é o centro operacional versionado para administrar:

- servidores Oracle OCI (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`)
- desktop/workstations Linux
- Termux/PRoot no Galaxy S23
- módulos locais do SRV-1
- backup/offload/cleanup
- mounts remotos e labels no PCManFM/LXDE
- fork sync e documentação operacional

Comando principal:

```bash
omni --help
```

Comandos mais usados:

```bash
omni fleet list
omni fleet show atius-srv-1
omni srv1-ops status
omni srv1-ops logs --limit 30
omni remote-manager list
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
omni xrdp-abnt2 validate
omni fork-sync projects list
```

---

## Filosofia

### 1. Fleet-first

O repo não é mais só "scripts do SRV-1". Ele é um sistema de administração multi-host.

Cada host tem inventário, constraints, backup policy, módulos aplicáveis e documentação.

### 2. Módulos pequenos e separados

Cada domínio operacional fica isolado:

- `srv1-ops` para automações locais do ATIUS-SRV-1
- `fleet` para inventário multi-host
- `remote-manager` para mounts/remotes/labels
- `xrdp-abnt2` para teclado/desktop remoto
- `fork-sync` para sincronização de forks

### 3. Paths técnicos estáveis, labels humanos flexíveis

Exemplo real:

```text
mount path técnico: /home/ubuntu/Shared_smb
label visual:       Shared
```

Renomear o label não quebra scripts.

```bash
omni remote-manager rename-label srv1-shared-smb Shared
```

### 4. Backup antes de mudança

Operação destrutiva ou reorganização estrutural exige snapshot antes.

### 5. Documentação é parte da execução

Sem documentação, a tarefa não terminou.

---

## Estrutura canônica

```text
omni-srv-admin/
├── cli/                         # Python package: comando `omni`
│   └── omni/
│       ├── cli.py               # root CLI + comandos legados
│       ├── fleet.py             # `omni fleet ...`
│       ├── remote_manager.py    # `omni remote-manager ...`
│       ├── srv1_ops.py          # `omni srv1-ops ...`
│       └── xrdp_abnt2.py        # `omni xrdp-abnt2 ...`
├── inventory/                   # fonte de verdade da fleet
│   ├── hosts/                   # inventário por host
│   ├── groups/                  # agrupamentos futuros
│   └── remotes/                 # mounts/remotes/bookmarks
├── modules/                     # módulos operacionais
│   ├── fleet/                   # arquitetura e rollout multi-host
│   ├── remote-manager/          # remotes, mounts, PCManFM/LXDE Places
│   ├── srv1-ops/                # backups, logs, cleanup, sync vault
│   ├── xrdp-abnt2/              # guard teclado ABNT2 para XRDP/LXDE
│   └── fork-sync/               # submodule: sincronização de forks
├── docs/                        # documentação GitHub/readable
│   ├── architecture/            # visão arquitetural
│   ├── fleet/                   # multi-servidor
│   ├── operations/              # runbooks operacionais
│   ├── reference/               # referências e schemas
│   ├── runbooks/                # guias executáveis
│   └── legacy-home-docs/        # docs antigas migradas
├── domain-infrastructure/       # FreeIPA/Keycloak/Samba legado/infra
├── dark-theme-ubuntu/           # LXDE/Openbox/SF fonts
├── antivirus/                   # scripts antivírus legados
└── vscode-profile/              # perfis/workspaces VSCode
```

---

## Inventory

### Hosts

Hosts ficam em:

```text
inventory/hosts/*.yaml
```

Hosts atuais:

| Host | Papel | Estado | Observação |
|---|---|---|---|
| `atius-srv-1` | production | active | Oracle OCI / Ubuntu 22.04 / PRD |
| `atius-srv-2` | development | planned | DEV/Zentrius |
| `atius-srv-3` | sandbox | planned | ARM sandbox |
| `giovanni-s23-termux` | mobile-node | planned | Android Termux host |
| `giovanni-s23-proot` | mobile-ubuntu | planned | Ubuntu PRoot no S23 |
| `dell-inspiron-3520` | personal-workstation | planned | desktop pessoal Linux |
| `support-template` | temporary-support | template | suporte remoto com escopo explícito |

Exemplo:

```bash
omni fleet list
omni fleet show atius-srv-1
```

### Remotes

Remotes ficam em:

```text
inventory/remotes/*.yaml
```

Remote atual:

| Remote | Tipo | Host | Source | Mount | Label |
|---|---|---|---|---|---|
| `srv1-shared-smb` | CIFS | `atius-srv-1` | `//10.1.1.2/Shared` | `/home/ubuntu/Shared_smb` | `Shared_smb` |

Renomear label visual:

```bash
omni remote-manager rename-label srv1-shared-smb Shared
```

---

## CLI

### Instalação editable

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
pip install -e cli/
```

### Root

```bash
omni --help
omni version
```

### Fleet

```bash
omni fleet list
omni fleet show atius-srv-1
omni fleet status
```

Status atual: inventário e status local. Execução remota destrutiva ainda não está habilitada.

### Remote Manager

```bash
omni remote-manager list
omni remote-manager show srv1-shared-smb
omni remote-manager places
omni remote-manager status
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
omni remote-manager rename-label srv1-shared-smb Shared
```

O comando `rename-label`:

- altera `~/.config/gtk-3.0/bookmarks`
- atualiza `inventory/remotes/<remote>.yaml`
- preserva `mount_path`
- não edita `/etc/fstab`
- não desmonta CIFS
- não renomeia diretórios

### SRV-1 Ops

```bash
omni srv1-ops list
omni srv1-ops status
omni srv1-ops logs --limit 30
omni srv1-ops run sync-vault
omni srv1-ops run cleanup-local --dry-run
omni srv1-ops run backup-gdrive
omni srv1-ops run offload-dotbackups
```

### XRDP ABNT2

```bash
omni xrdp-abnt2 status
omni xrdp-abnt2 validate
omni xrdp-abnt2 diff
omni xrdp-abnt2 install
```

### Fork Sync

```bash
omni fork-sync projects list
omni fork-sync sync aionui --repo-path /home/ubuntu/GitHub/forks/AionUi
omni fork-sync manuals list
```

---

## Módulos

### `modules/fleet/`

Responsável por:

- inventário multi-host
- arquitetura de orquestração
- rollout gradual
- restrições por tipo de host

Docs:

```text
modules/fleet/README.md
modules/fleet/docs/architecture.md
modules/fleet/docs/rollout-plan.md
```

### `modules/remote-manager/`

Responsável por:

- mapeamentos remotos
- labels visuais de remotes
- PCManFM/LXDE Places
- GTK bookmarks
- futura integração com rsync, Samba e GDrive

Docs:

```text
modules/remote-manager/README.md
modules/remote-manager/docs/remote-mapping-labels.md
```

### `modules/srv1-ops/`

Responsável por automações locais do `atius-srv-1`:

- sync do vault
- backup para GDrive
- offload de `~/.backups`
- cleanup local
- backup SMB legado
- health-check Atius web
- logs em `~/.logs`

### `modules/xrdp-abnt2/`

Responsável por manter teclado ABNT2 no fluxo Windows 11 RDP → Ubuntu LXDE.

### `modules/fork-sync/`

Submodule/lib para sincronização de forks com proteção de customizações.

---

## Backup e logs

### Logs locais

```text
/home/ubuntu/.logs/
```

Retenção local padrão: 15 dias.

### Backup SRV-1

Destino GDrive:

```text
giovanni-drive:ATIUS-SRV/SRV-1/Backup/
```

Mapa:

```text
modules/srv1-ops/configs/backup-map.yaml
```

### Timers relevantes

```bash
systemctl --user list-timers --all | grep -E 'backup|cleanup|offload'
```

---

## Remote Manager: renomear `Shared_smb` para `Shared`

O SRV-1 tem mount CIFS estável:

```text
/home/ubuntu/Shared_smb
```

Para mostrar outro nome no PCManFM/LXDE Places:

```bash
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
omni remote-manager rename-label srv1-shared-smb Shared
```

Validação:

```bash
omni remote-manager places | grep Shared
findmnt -R /home/ubuntu/Shared_smb
```

Por que não renomear o diretório direto?

- backup scripts usam `/home/ubuntu/Shared_smb`
- `/etc/fstab` usa `/home/ubuntu/Shared_smb`
- systemd automount usa o path
- docs e runbooks usam o path
- renomear path exige migração separada

---

## Fluxo seguro de mudança

Antes de alterar infraestrutura:

```bash
git status --short
mkdir -p /home/ubuntu/.backups/<task>
cp -a ~/.config/systemd/user /home/ubuntu/.backups/<task>/systemd-user
crontab -l > /home/ubuntu/.backups/<task>/crontab.bak
```

Durante:

```bash
# editar módulo certo
# validar comando
# atualizar docs
# atualizar vault
```

Depois:

```bash
python3 -m compileall cli/omni
omni fleet status
omni remote-manager status
omni srv1-ops status
```

---

## Roadmap

### Curto prazo

- [x] Inventário em `inventory/hosts/`.
- [x] Remotes em `inventory/remotes/`.
- [x] `omni remote-manager rename-label`.
- [x] Docs GitHub reorganizadas.
- [ ] Schema YAML formal para hosts/remotes.
- [ ] `omni fleet doctor`.
- [ ] `omni fleet backup-plan <host>`.

### Médio prazo

- [ ] `omni fleet ssh <host>`.
- [ ] `omni fleet run <host> <safe-command>` com allowlist.
- [ ] `omni remote-manager mount-check`.
- [ ] `omni remote-manager rsync-plan`.
- [ ] `omni backup verify <host>`.

### Longo prazo

- [ ] suporte remoto temporário auditável.
- [ ] policies por classe de host.
- [ ] dashboards de saúde multi-host.
- [ ] sync cruzado SRV-1/SRV-2/SRV-3.

---

## Segurança

- Não armazenar senhas em docs.
- Não commitar `.backups/`.
- Não aplicar scripts SRV-1 em Termux/PRoot.
- Não habilitar execução remota ampla sem allowlist.
- Não rodar cleanup destrutivo sem backup e validação.
- Não renomear mount path sem plano de migração.

---

## Links rápidos

- `docs/architecture/overview.md`
- `docs/fleet/inventory-model.md`
- `docs/operations/remote-manager.md`
- `docs/operations/srv1-ops.md`
- `modules/remote-manager/README.md`
- `modules/srv1-ops/README.md`
- `modules/fleet/README.md`
