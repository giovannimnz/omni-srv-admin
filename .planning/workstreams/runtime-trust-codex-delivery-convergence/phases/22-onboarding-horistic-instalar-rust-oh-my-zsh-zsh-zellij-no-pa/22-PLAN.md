---
phase: 22
title: Onboarding Horistic (rename horistic-srv-1 → horistic-srv + rust/zellij)
status: in-progress
created: 2026-06-17T20:35:00-03:00
owner: Filippo
milestone: M009
depends_on: Phase 21
---

# Phase 22 — Onboarding Horistic (rename + rust/zellij)

## Objetivo

Padronizar `horistic-srv-1` em toda a infra: renomear para `horistic-srv` no host, nos docs, no omni-srv-admin, vault Obsidian, gbrain, e docs em `vpn-atius`/`mt5-arm`. Em paralelo, instalar rust + cargo-binstall + zellij no padrão fleet e configurar zsh/Oh My Zsh auto-start de zellij idêntico ao dos SRV-1/2/3 e KVMs. K3s permanece fora do escopo.

## Escopo

- Host: hostname real, `/etc/hostname`, `/etc/hosts`, `tailscale rename`, `.zcompdump*` cleanup, `.pam_environment`, `/etc/ssh/ssh_host_*` key comment (regenerar não é objetivo).
- Toolchain: rustup stable minimal 1.96.0, cargo-binstall 1.20.0, zellij 0.44.3 via cargo-binstall, com PATH em `/home/horistic/.zshrc` e `/home/horistic/.bashrc`.
- Auto-start zellij interativo (mesmo padrão usado em SRV-2 e KVM-1/2): `[[ -o interactive ]] && [[ -t 0 ]] && [[ -t 1 ]]` então `eval "$(zellij setup --generate-auto-start zsh)"`. Non-interactive SSH não prende.
- Inventário omni: renomear `inventory/hosts/horistic-srv-1.yaml` → `inventory/hosts/horistic-srv.yaml`, atualizar `id`, `aliases`, `wireguard_peer_name`, `dns_name`, `last_readdressed`, `notes`, `validation_summary`.
- DB `DbOmniFleet`: upsert em `TbHosts` (id + ssh_target + vpn_ip + readdressed_at), atualizar `TbNodes`, regenerar `TbNodeTelemetry`.
- VPN/CoreDNS: `vpn-atius/coredns/custom_hosts` `horistic-srv` canonical + alias uppercase legacy; `vpn-atius/peer_aliases.json`; `vpn-atius/README.md`. NÃO mexer no WireGuard do host (chave do peer está sob `10.1.1.4` e o IP público não muda).
- Vault Obsidian: varredura completa de `ideaverse/` substituindo `horistic-srv-1` por `horistic-srv`. Exceções: nomes de arquivo podem ser renomeados quando a string é só de hostname; logs históricos mantém a string se for citação literal (ex: "foi renomeado de horistic-srv-1 em 2026-06-17").
- gbrain: sincronizar vault via `gbrain sync --repo ~/GitHub/obsidian-vault/ideaverse --no-embed` (1 RPM MiniMax rate limit — `--no-embed` evita o 26h embedding pass).
- Docs: `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.4.0, `docs/operations/HORISTIC-SRV-1-UPGRADE-PROSPECTIVE.md` renomeia.
- Network doc vault mirror: `ideaverse/30-RECURSOS/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.4.0.
- `inventory/hosts/horistic-srv.yaml` (novo) deve registrar `no-k3s-member`, `horistic-reverse-proxy`, monitoramento `node_exporter`, e `gdrive_base: ATIUS-SRV/HORISTIC-SRV/Backup` (renomear pasta GDrive opcional fora de escopo, só atualizar o path no yaml).

## Fora do escopo

- K3s membership.
- Rotação de chaves WireGuard (a chave pública do peer não muda).
- Migração do WireGuard do HORISTIC para outro host.
- Renomear a pasta GDrive `HORISTIC-SRV-1` no GDrive (operacional, não-bloqueante).
- Reinicialização obrigatória do host.
- Mudar Apache2 vhost filenames em `/etc/apache2/sites-{available,enabled}/` (será feito apenas se o operador confirmar).

## Requisitos

| ID | Requisito | Validação |
|---|---|---|
| HORSTC-01 | Hostname real `horistic-srv` | `hostname`, `hostnamectl --static`, `/etc/hostname`, `/etc/hosts 127.0.1.1` |
| HORSTC-02 | SSH `horistic@10.1.1.4` continua funcionando | `ssh -i ~/.ssh/horistic-srv-1/id_rsa horistic@10.1.1.4 'hostname'` |
| HORSTC-03 | rustup/cargo 1.96.0, cargo-binstall 1.20.0, zellij 0.44.3 | `PATH=$HOME/.cargo/bin:$PATH` versões via shell interativo `zsh -ic` |
| HORSTC-04 | zsh default + Oh My Zsh | `getent passwd horistic`, `zsh -ic 'print -P "%n@%m:%~ ➜"'` |
| HORSTC-05 | Inventário omni com `id: horistic-srv` | `omni fleet list` mostra `horistic-srv` |
| HORSTC-06 | DB `TbHosts` id `horistic-srv` | `select id from "TbHosts" where id='horistic-srv'` retorna 1 |
| HORSTC-07 | Vault Obsidian sem ocorrências legadas de `horistic-srv-1` fora de logs históricos | `grep -RIn "horistic-srv-1" ideaverse` retorna apenas referências de histórico |
| HORSTC-08 | gbrain indexado | `gbrain pages` lista docs atualizados |
| HORSTC-09 | VPN/CoreDNS lowercase canonical | `getent hosts horistic-srv` retorna `10.1.1.4` no SRV-1/2/3 e Horistic |
| HORSTC-10 | Monitoramento node-exporter ativo | `systemctl is-active prometheus-node-exporter` |
| HORSTC-11 | Network map v1.4.0 (repo + vault) | cabeçalho com `Versão: 1.4.0 — 2026-06-17` |

## Plano de execução

### 22-01 — Plano separado (este doc)
Documento GSD Phase 22 em `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/22-onboarding-horistic-.../22-PLAN.md`. Já existe shell criado por `gsd-phase add`; PLAN.md e `.gitkeep` ficam.

### 22-02 — Subagente no host `horistic-srv`
Subagente com SSH próprio `~/.ssh/horistic-srv-1/id_rsa` para `horistic@10.1.1.4`. Sem sudo destrutivo sem gate. Escopo:
- Backup `~/.backups/horistic-srv-1-to-horistic-srv-*/`.
- `sudo hostnamectl set-hostname horistic-srv`, `sudo sed -i 's/^127\.0\.1\.1.*/127.0.1.1\thoristic-srv\thoristic-srv/' /etc/hosts`.
- `sudo tailscale set --hostname horistic-srv` (ou via API node rename).
- `rm -f ~/.zcompdump*` antes do restart do zsh.
- Instalar rustup + cargo-binstall + zellij idêntico ao método Phase 21 (sem `chsh`, pois já é zsh).
- Adicionar bloco zellij auto-start em `~/.zshrc` (mesmo padrão fleet).
- Garantir `source "$HOME/.cargo/env"` no topo de `~/.bashrc` para shells non-interactive.
- Instalar `prometheus-node-exporter` e habilitar serviço (monitoramento).
- Validar tudo via `zsh -ic '...'`, `PATH=$HOME/.cargo/bin:$PATH ...`, `ss -tlnp | grep ':9100'`.
- Não reiniciar. Não tocar em `/etc/wireguard/wg0.conf`.

### 22-03 — Rename no host (post-install)
Após validação do 22-02, mover `inventory/hosts/horistic-srv-1.yaml` → `inventory/hosts/horistic-srv.yaml` e atualizar `id`, `aliases`, `notes`.

### 22-04 — DB e omni-srv-admin
- `omni fleet validate-inventory` e `omni fleet list`.
- Upsert em `TbHosts`, `TbNodes`, regenerar `TbNodeTelemetry` (mover heartbeats de `horistic-srv-1` para `horistic-srv`).
- Update `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.4.0.

### 22-05 — VPN/docs
- `vpn-atius/coredns/custom_hosts` atualizar para `horistic-srv` (canonical) e manter alias `horistic-srv-1` para compatibilidade.
- `vpn-atius/peer_aliases.json` chaves 4.
- `vpn-atius/README.md` bloco explicativo do rename.
- Em SRV-1/SRV-2/SRV-3, atualizar `/etc/hosts` local e `/etc/coredns/custom_hosts` (já é o mesmo arquivo no SRV-2 — replicar via rsync ou edição direta).
- `getent hosts horistic-srv` validado nos 3 SRVs e no próprio HORISTIC.

### 22-06 — Vault Obsidian
- Varredura sed em `ideaverse/` (excluindo `20-PROJETOS/22-PROJETOS-ARQUIVADOS/mt5-arm/` legado, salvo onde a string é histórica, e excluindo arquivos `.gitkeep`).
- Renomear `30-RECURSOS/operations/HORISTIC-SRV-1-UPGRADE-PROSPECTIVE.md` → `30-RECURSOS/operations/HORISTIC-SRV-UPGRADE-PROSPECTIVE.md`.
- Renomear `ideaverse/60-LOGS/2026-06-17-horistic-srv-1-*.md` para `horistic-srv-*.md` quando apropriado.
- Mirror do network map em `ideaverse/30-RECURSOS/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.4.0.
- Sessão recap: `ideaverse/60-LOGS/2026-06-17-horistic-srv-rename-rust-zellij.md`.
- Entrada no daily: `ideaverse/90-META/91-Diarios/2026-06-17.md`.
- Update `ideaverse/20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin/21.04-Log-Trabalho.md`.

### 22-07 — gbrain
- `gbrain sync --repo ~/GitHub/obsidian-vault/ideaverse --no-embed` (1 RPM MiniMax rate limit).
- `gbrain search "horistic-srv-1"` confirma que 0 docs ativos referenciam a string.

### 22-08 — Validação final e commit
- Graphify: `node $HOME/.Codex/get-shit-done/bin/gsd-tools.cjs graphify status` (Codex) + `node $HOME/.hermes/gsd-core/bin/gsd-tools.cjs graphify status` (Hermes), fresh em ambos.
- `omni fleet monitor hosts --json` mostra `horistic-srv` healthy.
- Branch `feat/horistic-srv-rename` na feat/omni-srv-admin repo.
- Vault log e mirror.

## Critérios de done

- [x] Plano GSD Phase 22.
- [ ] Host renomeado para `horistic-srv`.
- [ ] rust/cargo-binstall/zellij instalados e validados.
- [ ] node-exporter ativo.
- [ ] Inventário omni `horistic-srv` (sem `horistic-srv-1`).
- [ ] DB `horistic-srv` (sem `horistic-srv-1`).
- [ ] VPN/CoreDNS lowercase + alias compat uppercase.
- [ ] Vault Obsidian sem ocorrências legadas fora de histórico.
- [ ] gbrain reindexado.
- [ ] Network map v1.4.0 repo + vault.
- [ ] Branch feat/horistic-srv-rename pushed.
- [ ] Graphify fresh em Codex e Hermes.
