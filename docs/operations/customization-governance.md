# Customization Governance

## Goal

Formalizar dois trilhos distintos de customização dentro do `omni-srv-admin`:

1. `apps` instalados / runtimes ativos no host
2. `forks` que seguem upstream e preservam deltas locais

O `omni-srv-admin` administra os dois, mas eles não devem ser misturados.

## Lane A — Installed Programs / Runtimes

Owners:

- `modules/managed-apps/`
- wrappers host-specific em `modules/fleet/scripts/` quando o caso não cabe num
  installer genérico

Esse lane governa:

- install/upgrade de programas
- wrappers e launchers
- políticas locais
- hooks pós-instalação
- rebuild/reapply de runtime
- units ativas (`systemd`, PM2, podman, etc.)

Inventário:

- `inventory/hosts/*.yaml -> apps:`

Exemplos:

- `brave-browser`
- `chromium`
- `obsidian`
- `gitkraken`
- `wayland` no `atius-srv-3`

## Lane B — Forks Synced From Upstream

Owner:

- `modules/fork-sync/`

Esse lane governa:

- `upstream`
- `protected_paths`
- `merge_strategy`
- `deploy.yaml`
- versionamento/release notes
- dry-run/apply safety

Inventário:

- `inventory/hosts/*.yaml -> forks:`

Exemplos:

- `router-ai-atius` como produto canônico
- `atius-router` como `sync_project` do `fork-sync`
- `atius-router-docs` como componente do mesmo produto
- `aionui`
- `notebooklm-py`
- `horus-spec-driven`

## Quando um produto existe nos dois lanes

Registrar ambos explicitamente:

- `apps:` = runtime instalado no host
- `forks:` = worktree/fork local que segue upstream

Cruzar com:

- `runtime_app_id`
- `canonical_product_id`
- `sync_manifest`
- `customization_entrypoint`

Exemplo:

- `router-ai-atius` runtime em `apps:`
- `router-ai-atius` fork/upstream sync em `forks:` com `sync_project=atius-router`
- `atius-router-docs` como componente desse mesmo produto, não como produto isolado

Regra operacional:

- `router-ai-atius` e `atius-router` referem o mesmo produto em namespaces diferentes
- `router-ai-atius` = identidade canônica do produto/runtime
- `atius-router` = id do projeto no `fork-sync`
- `atius-router-docs` = componente, não app/fork raiz separado no control-plane

## Regra do Wayland

`wayland.atius.com.br` fica no lane de runtime instalado.

- source: `~/GitHub/wayland`
- rebuild/reapply owner: `omni-srv-admin`
- entrypoints canônicos:

```bash
cd ~/GitHub/omni-srv-admin
bash modules/fleet/scripts/wayland-srv3-postinstall-hook.sh
bash modules/fleet/scripts/wayland-srv3-update.sh
bash modules/fleet/scripts/wayland-srv3-update.sh --pull
```

O patch de source continua no repo do Wayland, mas o contrato de runtime não
fica mais “owned” por ele.

## Banco do Omni

DB canônico:

- `DbOmniFleet`
- endpoint declarado: `10.1.1.1:6432`
- transporte: `PgBouncer`

Linux servers:

- preferem `/etc/omni-srv-admin/fleet-db.env`

Workstations / Windows:

- podem usar `OMNI_FLEET_DB_ENV`
- fallback local: `~/.config/omni-srv-admin/fleet-db.env`
- fallback Windows adicional: `%USERPROFILE%\\AppData\\Local\\omni-srv-admin\\fleet-db.env`

Estado atual do `GIOVANNI-W11-PC`:

- `fleet-db.env` local provisionado em `C:\Users\muniz\.config\omni-srv-admin\fleet-db.env`
- client DB ativo via fallback Python `pg8000`
- leitura do mesmo `DbOmniFleet` validada localmente em `2026-07-03`
