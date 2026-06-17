# rust-zellij-fleet

Gerenciamento fleet-wide de **rust (rustup)** + **zellij (cargo-binstall)** nos 3 servers ATIUS-SRV-1/2/3.

## Inventário fonte

`inventory/hosts/atius-srv-{1,2,3}.yaml` — cada host registra os apps:
- `rust-toolchain` (runtime: `local-rustup`, install_type: `rustup-managed`)
- `cargo-binstall` (runtime: `local-binary`, install_type: `manual-release-binary`)
- `zellij` (runtime: `local-rustup-binary`, install_type: `cargo-binstall`)

Versões pinadas:
- rustc/cargo **1.96.0** stable + profile minimal
- cargo-binstall **1.20.0**
- zellij **0.44.3** (aarch64-unknown-linux-musl pré-compilado)

## Script

`scripts/fleet-rust-zellij.sh` — orquestra status/update/audit nos 3 hosts via SSH (paralelo).

| Comando | O que faz |
|---------|-----------|
| `status` | Mostra rustc/cargo/binstall/zellij version em cada host |
| `update [rust\|zellij\|all] [--dry-run]` | Atualiza rust/zellij nos 3 em paralelo |
| `audit` | Compara inventory (desired_version) vs real, mostra DRIFT |

## Padrão de update

```bash
# Dry-run primeiro (caveman-lite friendly, mostra comandos sem rodar)
./scripts/fleet-rust-zellij.sh update --dry-run

# Update real (paralelo nos 3 hosts)
./scripts/fleet-rust-zellij.sh update

# Só rust
./scripts/fleet-rust-zellij.sh update rust

# Só zellij
./scripts/fleet-rust-zellij.sh update zellij
```

Logs em `~/.logs/rust-zellij-fleet/`.

## Segurança

- **Lock anti-concorrência**: `flock /tmp/rust-zellij-fleet.lock.update` — não roda dois updates simultâneos.
- **SSH timeout 30s** por host; falha de 1 não aborta os outros.
- **Idempotente**: `rustup update stable` é no-op se já na versão.
- **Sem compilação local**: `cargo binstall zellij` baixa binário pré-compilado (~5MB, ~2s).

## PATH pós-install

Os 3 hosts têm `. "$HOME/.cargo/env"` adicionado ao `~/.bashrc`. Em shells novos, `rustc/cargo/zellij` ficam disponíveis direto. Em shells ativos: `source ~/.bashrc` ou `source ~/.cargo/env`.

## Próxima evolução (TODO)

- Wire no CLI `omni` como subcomando: `omni fleet rust-zellij status|update|audit`.
- Auto-audit diário via cron (compara desired vs real, alerta se drift).
- Auto-update quando sai nova versão stable (gated por `update_policy`).