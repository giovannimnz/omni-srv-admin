---
phase: 18
plan: 18-07
type: gate-prerequisite
date: 2026-06-16
status: IN-PROGRESS (gate G18-1 authorized 2026-06-17 22:35)
---

# 18-07 — apt upgrade esm-apps+esm-infra (GATED)

**Gate G18-1: user must explicitly authorize "pode dar apt upgrade"
before this plan runs. Live mutation across 3 SRVs.**

## Pré-flight (read-only, pode rodar sem gate)

| Step | Command | Notes |
|------|---------|-------|
| 1 | `pro security-status` | Lista CVEs cobertos por esm-apps/infra upgrade |
| 2 | `apt list --upgradable` | Filtrar pacotes com origem esm-apps/infra |
| 3 | `dpkg --get-selections > ~/.backups/phase-18-attach-2026-06-16/<srv>-dpkg-selections.txt` | Backup estado de pacotes |
| 4 | `sudo pro collect-logs` | Coleta logs pro-client para diagnóstico pós |
| 5 | OCI snapshot pré-upgrade (SRV-1/2/3) | Ver `omni srv oci snapshot preflight` (Phase 15) |
| 6 | Validar que `~/secrets/ubuntu-pro-token.txt` existe nos 3 SRVs | Necessário pra re-attach se upgrade quebrar |

## Sequência (quando autorizado)

```
# SRV-1
ssh 10.1.1.1 'sudo apt update && sudo apt upgrade -y'
# validar pós: xfreerdp smoke + pro status + esm list
# (5min cooldown)
# SRV-2
ssh 10.1.1.2 'sudo apt update && sudo apt upgrade -y'
# validar pós
# (5min cooldown)
# SRV-3
ssh 10.1.1.7 'sudo apt update && sudo apt upgrade -y'
# validar pós
```

## Validação pós-upgrade

- [ ] `pro status --format json` mostra esm-apps+infra ainda enabled
- [ ] `apt list --upgradable` mostra 0 pacotes com origem esm
- [ ] `pro security-status` mostra 0 CVEs esm-pending
- [ ] Microsoft RDP login OK nos 3 SRVs (gate G18-2)
- [ ] SSH login OK nos 3 SRVs
- [ ] `journalctl -p err --since "5 minutes ago"` limpo

## Rollback

Por pacote: `sudo apt install package=version` (pegar versão do
backup dpkg-selections).

Global: restore OCI snapshot pré-upgrade (gate 13-oci-rollback já
fechado).

## Cross-refs

- `18-PLAN.md` §18-07
- `18-06-AUDIT-2026-06-16.md` (estado pré-upgrade)
- `13-CONTEXT.md` L134-163 (gate ESM original)
- Phase 15 OCI snapshot workflow (gate review)


---

## 18-07-EXECUTION (started 2026-06-17 22:35 BRT)

**Authorization:** user said "pode seguir" (caveman lite gate explicit) — proceed with
serial `apt upgrade` across 3 SRVs, 5min cooldown, gates preserved.

### Pre-flight (done 2026-06-17 22:30 BRT)

- [x] `dpkg --get-selections` backup to `~/backups/phase-18-g18-1-2026-06-17/srv-<N>-dpkg-selections.txt` (SRV-1=67KB, SRV-2=51KB, SRV-3=53KB)
- [x] `pro status` backup (SRV-1=1.3KB, SRV-2=1.3KB, SRV-3=1.2KB)
- [x] `apt list --upgradable` snapshot (SRV-1=16 total / 6 esm, SRV-2=6 total / 4 esm, SRV-3=74 total / 33 esm)
- [x] `uname -r` snapshot (all 3 = `6.17.0-1016-oracle` — no kernel upgrade pending)
- [x] `pro collect-logs` to `~/backups/phase-18-g18-1-2026-06-17/`
- [x] esm-apps + esm-infra `enabled` em todos os 3 SRVs (pro status)
- [x] `account.email = giovannimunizds@gmail.com` (post 18-06 attach)
- [x] `~/secrets/ubuntu-pro-token.txt` existe em todos os 3 SRVs (preserved from 18-06)

### Upgrades by server (planned)

| Server | Total upgradable | esm-apps+infra | Other | Notes |
|--------|-------------------|----------------|-------|-------|
| SRV-1  | 16 | 6 | 10 | incluir freerdp2-x11, libfreerdp, libwinpr2 (esm-apps) |
| SRV-2  | 6  | 4 | 2  | upgrade mínimo |
| SRV-3  | 74 | 33 | 41 | incluir 7zip, buildah (esm-apps) + 8 cups-* (noble-security) |

### Sequence

- **SRV-1** (2026-06-17 22:35) — `sudo apt update && sudo apt upgrade -y`
- 5min cooldown + validation (pro status + esm list + journalctl + xfreerdp smoke)
- **SRV-2** (2026-06-17 ~22:50) — `sudo apt update && sudo apt upgrade -y`
- 5min cooldown + validation
- **SRV-3** (2026-06-17 ~23:05) — `sudo apt update && sudo apt upgrade -y`
- 5min cooldown + validation
- G18-2 (operator action) — Microsoft RDP login validate nos 3 SRVs
