# Architecture Overview

## Objetivo

`omni-srv-admin` é um sistema operacional versionado para administrar a infraestrutura do Giovanni em modo fleet-first.

## Camadas

```text
┌────────────────────────────────────────────────────────────┐
│ CLI: omni                                                  │
│ fleet | remote-manager | srv1-ops | xrdp-abnt2 | fork-sync │
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
