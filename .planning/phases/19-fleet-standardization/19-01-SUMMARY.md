phase: 19
plan: 19-01
title: "Fleet Standardization — hostnames, chromium, dark theme"
date: 2026-06-17
status: complete
hosts:
  - atius-srv-1 (10.1.1.1)
  - atius-srv-2 (10.1.1.2)
  - atius-srv-3 (10.1.1.3; 10.1.1.7 K3s/etcd alias)
  - horistic-srv-1 (10.1.1.4 / 163.176.232.119)
---

# Phase 19 — Plan 19-01 SUMMARY

## Resultado

Execução completa em **4 hosts paralelos via delegate_task** (138-278s cada subagente). Todo o trabalho planejado em `19-PLAN.md` foi entregue:

> Correção posterior: o primeiro patch de atalhos deixou `.desktop` inválido
> em alguns hosts. O estado final correto está em
> `19-02-DESKTOP-SHORTCUTS-HOTFIX-2026-06-17.md`.

### Hostnames (lowercase enforced)

| Host | Antes | Depois |
|------|-------|--------|
| 10.1.1.1 | `ATIUS-SRV-1` | `atius-srv-1` ✅ |
| 10.1.1.2 | `ATIUS-SRV-2` | `atius-srv-2` ✅ |
| 10.1.1.3 | `ATIUS-SRV-3` | `atius-srv-3` ✅ |
| 10.1.1.4 | `horistic-srv-1` | `horistic-srv-1` (já era) ✅ |

### Chromium 149.0.7827.114 (PPA xtradeb/apps)

| Host | Antes | Depois | Método |
|------|-------|--------|--------|
| SRV-1 | 149.0.7827.102-1xtradeb1.2204.1 (.deb) | 149.0.7827.114-1xtradeb1.2404.1 (.deb) | `apt install --only-upgrade` |
| SRV-2 | snap chromium | 149.0.7827.114 (.deb) | `snap remove chromium` + `apt install chromium chromium-common chromium-sandbox` |
| SRV-3 | snap chromium | 149.0.7827.114 (.deb) | `snap remove chromium` + `apt install chromium chromium-common chromium-sandbox` |
| horistic-srv-1 | snap chromium | 149.0.7827.114 (.deb) | `snap remove chromium` + `apt install chromium chromium-common chromium-sandbox` |

PPA xtradeb/apps: habilitado nos 4 hosts. Formato: `deb https://ppa.launchpadcontent.net/xtradeb/apps/ubuntu/ noble main`.

### Atalhos (Desktop + menu Internet)

| Host | `~/Desktop/chromium.desktop` | `/usr/share/applications/chromium.desktop` |
|------|------------------------------|-------------------------------------------|
| SRV-1 | criado ✅ | já existia ✅ |
| SRV-2 | criado ✅ | já existia ✅ |
| SRV-3 | criado ✅ | já existia ✅ |
| horistic-srv-1 | criado em `/home/horistic/Desktop/` ✅ | já existia ✅ |

### Dark theme (LXDE canônico SRV-1 → fleet)

9 arquivos canônicos do SRV-1 sincronizados para os outros 3 hosts via rsync:

| File | md5 canônico |
|------|--------------|
| `~/.gtkrc-2.0` | f7891825 |
| `~/.config/gtk-3.0/settings.ini` | 18743cba |
| `~/.config/lxsession/LXDE/desktop.conf` | 7ffabad4 |
| `~/.config/openbox/lxde-rc.xml` | adcd300f |
| `~/.config/lxpanel/LXDE/panels/panel` | d07cba7e |
| `~/.config/lxpanel/LXDE/panels/00-background` | e5c23c4d |
| `~/.config/lxpanel/LXDE/panels/status-right` | 90b1dc23 |
| `~/.config/lxpanel/LXDE/panel-background.xpm` | ed45c038 |
| `~/.local/share/icons/omni-dark-theme/omni-network-{wired,error,ok}.svg` | 96f98dc5/7c1dbd14/aa22c8a3 |

**Status:** theme em disco, **não ativo visualmente** (preservar sessão RDP). User precisa fazer logout/login OU restart manual do LXDE.

## Decisões & Lições

### D19-01: PPA xtradeb no Noble

- O user adicionou PPA no Jammy (22.04). SRV-1 (Noble) tinha `noble main` desabilitada.
- O PPA xtradeb/apps TEM versão Noble (`dists/noble/main/binary-arm64/Packages.xz`), mas precisa ser habilitada separadamente.
- Workaround aplicado: SRV-1 `sed` descomentou `noble main`; outros 3 criados do zero com `add-apt-repository` ou manualmente.

### D19-02: GPG key correta do PPA xtradeb

- Briefing original pediu `0E3F0440E825C30AB1ACBC95` (errada).
- Chave correta: `82BB6851C64F6880` (descoberta via `apt-key adv --recv-keys` no SRV-2 e confirmada nos outros 3).

### D19-03: chromium-snap → chromium-deb (transitional)

- SRV-2/3/horistic tinham `chromium-browser` (transitional → snap) + `chromium` snap. `apt install chromium` puxa o transitional mas o apt resolvia para snap.
- Solução: `snap remove chromium` + `apt install chromium chromium-common chromium-sandbox` (instala o .deb).

### D19-04: apt-key deprecado no Noble (warning cosmético)

- Ubuntu 24.04 (Noble) deprecou `apt-key` (warning: "Key is stored in legacy trusted.gpg keyring"). Funciona, mas gera warning.
- Não corrigido agora (warning cosmético). Pendente para 18-09 (canonical ubuntu-pro-fleet.md + watchdog cron).

### D19-05: Dark theme — preservar sessão RDP

- O `dark-themectl.sh apply` é o método oficial mas reinicia LXDE (derruba RDP).
- Solução aplicada: `cp -a` direto dos 9 arquivos canônicos + backup pré-flight em `.backups/dark-theme-apply-2026-06-17/`.
- Theme em disco, não ativo. Logout/login manual do user ativa.

## Backups

- `~/.backups/phase-19-fleet-std-2026-06-17/` — snapshots hostname+theme por host
- `~/.backups/dark-theme-apply-2026-06-17/` — backups pré-theme apply (4 hosts)

## Commits

Nenhum commit novo no omni-srv-admin para 19-01 (todo o trabalho foi em `/home/ubuntu/` dos hosts, não em arquivos do repo). Doc canônico no PLAN.md.

## Pendente (fora do escopo 19-01)

- ~~Manual LXDE restart pelo user para atalhos~~ — resolvido no hotfix 19-02 por recarga controlada do PCManFM nos 3 ATIUS.
- Tema visual ainda pode exigir logout/login se painel/GTK antigo estiver cacheado.
- **G18-1 apt upgrade esm-apps+infra** (gate explícito, espera autorização do user)
- **18-09 docs** (canonical ubuntu-pro-fleet.md + watchdog cron)
- **Inventory update** em `inventory/hosts/*.yaml` (hostname lowercase já refletido em SRV-1/2/3 yaml files)

## Cross-refs

- `.planning/phases/19-fleet-standardization/19-PLAN.md` (planejamento original)
- `vault/60-LOGS/2026-06-17-phase-19-fleet-std-execution.md` (vault log)
- `dark-theme-ubuntu/config_files/` (canônico, md5 sync'd 4 hosts)
- `~/.backups/phase-19-fleet-std-2026-06-17/` (snapshots)
- `~/.backups/dark-theme-apply-2026-06-17/` (pre-flight)

## Status

✅ **Plan 19-01 DONE.** Phase 19 fechada. Pronto para Phase 20 (M008-b podman networking standardization) ou para retomar G18-1 (apt upgrade esm-apps+infra) conforme autorização do operator.
