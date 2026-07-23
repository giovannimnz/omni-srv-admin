---
phase: 21
title: Onboarding ATIUS-MT5-KVM-1/2 como hosts gerenciados
status: in-progress
created: 2026-06-17T20:12:00-03:00
owner: Filippo
milestone: M009
k3s_scope: excluded
---

# Phase 21 — Onboarding ATIUS-MT5-KVM-1/2

## Objetivo

Adicionar `atius-mt5-kvm-1` e `atius-mt5-kvm-2` ao ciclo completo de gestão do `omni-srv-admin`, sem ingressar no K3s por enquanto.

## Escopo

- Inventário `inventory/hosts/*.yaml`.
- Registro em `DbOmniFleet` (`TbHosts`, `TbNodes`, `TbPrograms`, `TbNodeTelemetry`).
- Monitoramento completo por SSH + `node-exporter` + heartbeat local.
- Hostnames lowercase: `atius-mt5-kvm-1`, `atius-mt5-kvm-2`.
- VPN/CoreDNS/docs em `vpn-atius` no SRV-2.
- Docs `mt5-arm` no SRV-2.
- Vault Obsidian + mirror do mapa de rede.
- Shell padrão: zsh + Oh My Zsh + prompt `ubuntu@host:~/path ➜`.
- Rust stable minimal + `cargo-binstall` + `zellij` com auto-start seguro interativo.

## Fora do escopo

- K3s membership.
- Reboot obrigatório.
- Mudança do runtime MT5/EA atual.
- Rotação de chaves WireGuard.

## Requisitos

| ID | Requisito | Validação |
|---|---|---|
| MT5KVM-01 | Hosts no inventário omni com nomes lowercase | `omni fleet validate-inventory` |
| MT5KVM-02 | Hosts registrados no DB | `select id from "TbHosts" where id like 'atius-mt5-kvm-%'` |
| MT5KVM-03 | VPN e CoreDNS lowercase no SRV-2 | `getent hosts atius-mt5-kvm-1/2` via DNS interno |
| MT5KVM-04 | Hostname real lowercase | `hostname`, `hostnamectl --static`, `/etc/hostname`, `/etc/hosts` |
| MT5KVM-05 | zsh/Oh My Zsh default | `getent passwd ubuntu`, `zsh -ic ...` |
| MT5KVM-06 | Rust/cargo-binstall/zellij | versões reais em ambos os hosts |
| MT5KVM-07 | Monitoramento completo | `prometheus-node-exporter.service active`, `:9100/metrics`, telemetry DB |
| MT5KVM-08 | Portas MT5 preservadas | KVM-1 `:9001`, KVM-2 `:9002` |
| MT5KVM-09 | Graphify compatível Hermes/Codex | ambos `gsd-tools.cjs graphify status` fresh + query funcional |
| MT5KVM-10 | Documentação cruzada completa | repo + VPN + mt5-arm + vault atualizados |

## Plano de execução

### 21-01 — Graphify + plano separado
- Validar `.planning/config.json graphify.enabled=true`.
- Rodar `gsd-tools.cjs graphify status` via runtime Codex e Hermes.
- Criar esta Phase 21 como plano separado para histórico futuro.

### 21-02 — Inventário + DB
- Criar `inventory/hosts/atius-mt5-kvm-1.yaml`.
- Criar `inventory/hosts/atius-mt5-kvm-2.yaml`.
- Upsert em `TbHosts`, `TbNodes`, `TbPrograms`, `TbNodeTelemetry`.
- Validar `omni fleet list`, `show`, `programs`, `monitor hosts --json`.

### 21-03 — VPN/CoreDNS/docs SRV-2
- Atualizar `peer_aliases.json` para lowercase.
- Atualizar `coredns/custom_hosts` com aliases lowercase e compat uppercase se necessário.
- Atualizar docs do `vpn-atius`.
- Validar `wg-quick strip wg0`, `getent hosts`, `dig @127.0.0.1`.

### 21-04 — Hostname + shell/runtime nos KVMs
- Backup em cada host: `~/.backups/mt5-kvm-onboarding-*`.
- `hostnamectl set-hostname` lowercase.
- Instalar zsh/Oh My Zsh/syntax plugin.
- Criar `.zshrc` limpo sem secrets.
- `chsh -s /usr/bin/zsh ubuntu`.
- Instalar Rust/cargo-binstall/zellij.
- Validar prompt e non-interactive SSH.

### 21-05 — Monitoramento completo
- Instalar e habilitar `prometheus-node-exporter`.
- Preservar listeners `:9001` e `:9002`.
- Inserir telemetry inicial no DB.
- Documentar ausência de K3s como constraint, não falha.

### 21-06 — Docs finais e validação
- Atualizar `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md`.
- Atualizar mirror no vault.
- Atualizar docs no SRV-2 `~/GitHub/mt5-arm`.
- Atualizar docs no SRV-2 `~/GitHub/vpn-atius`.
- Rebuild Graphify após mudanças.

## Critérios de done

- [x] Plano separado criado.
- [x] Hostnames lowercase aplicados.
- [x] zsh/Rust/zellij validados por subagentes paralelos.
- [x] node-exporter ativo nos dois hosts.
- [x] 2 hosts no inventário local.
- [x] 2 hosts no DB.
- [x] 2 hosts no monitoramento DB.
- [x] VPN/CoreDNS docs atualizados.
- [x] Vault + mt5-arm + network map atualizados.
- [ ] Graphify fresh após mudanças.
