# Architecture Overview

## Objetivo

`omni-srv-admin` é um sistema operacional versionado para administrar a infraestrutura do Giovanni em modo fleet-first.

## Camadas

```text
┌────────────────────────────────────────────────────────────┐
│ CLI: omni                                                  │
│ fleet | remote-manager | srv1-ops | xrdp-abnt2 | dark-theme │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────┐
│ Inventory                                                   │
│ inventory/hosts/*.yaml | inventory/remotes/*.yaml           │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────┐
│ Modules                                                     │
│ modules/fleet | remote-manager | srv1-ops | xrdp-abnt2      │
│ dark-theme-ubuntu | managed-apps | fork-sync                │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────┐
│ Live System                                                 │
│ systemd | PM2 | rclone | CIFS | GTK bookmarks | crontab     │
└────────────────────────────────────────────────────────────┘
```

## Diretórios

| Diretório | Função |
|---|---|
| `cli/omni/` | comandos executáveis |
| `inventory/hosts/` | dados de hosts |
| `inventory/remotes/` | dados de remotes/mounts |
| `modules/` | implementação e docs por domínio |
| `docs/` | documentação GitHub organizada |
| `domain-infrastructure/` | infra de domínio/SSO legada |
| `vscode-profile/` | perfis de dev |

## Princípios

- Inventory é dado, module é comportamento.
- CLI lê inventory e executa módulos.
- Module não deve depender de estado mental/histórico.
- Tudo que muda sistema vivo tem runbook.
- Paths técnicos permanecem estáveis.
- Labels e UX podem ser configurados sem quebrar automação.

## Boundaries

### Fleet

Gerencia hosts, status, constraints e futuro remote execution.

Não executa comandos destrutivos ainda.

### Remote Manager

Gerencia remotes e labels visuais.

Não renomeia mount paths por padrão.

### SRV-1 Ops

Gerencia automações locais de production.

Não deve ser aplicado em outros hosts sem portabilidade explícita.

### XRDP Desktop Standard

`modules/xrdp-abnt2/` e `dark-theme-ubuntu/` formam o padrão portátil de desktop XRDP para todos os servidores Ubuntu ARM64 da fleet. O runbook canônico é `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md`.

### Customization Governance

`omni-srv-admin` governa dois lanes distintos:

- `managed-apps` / runtime instalado:
  wrappers, post-install hooks, rebuild/reapply, políticas locais e serviços ativos.
- `fork-sync` / fork seguindo upstream:
  `protected_paths`, merge strategy, deploy opcional e sincronização periódica.

Quando um mesmo produto existe nas duas formas, registrar ambos no inventário:

- `apps:` para o runtime instalado
- `forks:` para o worktree/fork local

Runbook canônico:

- `docs/operations/customization-governance.md`

## Estado atual

- `inventory/hosts/` ativo.
- `inventory/remotes/srv1-shared-smb.yaml` ativo.
- `omni remote-manager rename-label` implementado.
- Execução remota ampla ainda bloqueada por design.

## Próximo desenho

```text
inventory/groups/
├── oci.yaml
├── mobile.yaml
└── workstations.yaml

modules/backup/
├── scripts/
├── docs/
└── configs/

modules/fleet/
└── policies/
    ├── read-only.yaml
    ├── safe-maintenance.yaml
    └── destructive-requires-approval.yaml
```
