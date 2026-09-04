# Getting Started

## Instalar CLI

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
pip install -e cli/
omni --help
```

## Primeiros comandos

```bash
omni fleet list
omni fleet status
omni remote-manager list
omni srv1-ops status
```

## Ver inventário de host

```bash
omni fleet show atius-srv-1
```

Fonte:

```text
inventory/hosts/atius-srv-1.yaml
```

## Ver remote/mount

```bash
omni remote-manager show srv1-shared-smb
```

Fonte:

```text
inventory/remotes/srv1-shared-smb.yaml
```

## Renomear label visual do SMB

Dry-run:

```bash
omni remote-manager rename-label srv1-shared-smb Shared --dry-run
```

Aplicar:

```bash
omni remote-manager rename-label srv1-shared-smb Shared
```

Validar:

```bash
omni remote-manager places | grep Shared
findmnt -R /home/ubuntu/Shared_smb
```

## Rodar operação SRV-1

```bash
omni srv1-ops list
omni srv1-ops resources status
omni srv1-ops resources install
omni srv1-ops logs --limit 30
omni srv1-ops run cleanup-local --dry-run
```

## Validar teclado XRDP ABNT2

```bash
omni xrdp-abnt2 validate
```

Para operar ou recuperar a frota, use `$xrdp-abnt2-fleet`; sua fonte
versionada é
`modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`.
A skill direciona ao runbook canônico e exige evidência nova por host.

## Regras antes de mexer

1. Consultar vault.
2. Fazer backup se a mudança for estrutural/destrutiva.
3. Alterar o módulo correto.
4. Rodar validação.
5. Atualizar README/docs/vault.
6. Só então considerar commit.

## Onde colocar coisas novas

| Coisa | Onde |
|---|---|
| Host novo | `inventory/hosts/<id>.yaml` |
| Remote/mount novo | `inventory/remotes/<id>.yaml` |
| Script SRV-1 | `modules/srv1-ops/scripts/` |
| Profile de recursos SRV-1 | `modules/srv1-ops/configs/resource-governor.env` |
| Script de mount/remote | `modules/remote-manager/scripts/` |
| Doc GitHub | `docs/<area>/` |
| Runbook do módulo | `modules/<module>/README.md` |
| Decisão | vault `21.03-Decisoes-Arquitetura.md` |
| Worklog | vault `21.04-Log-Trabalho.md` + `60-LOGS/64-Worklogs-Agrupados/` |
