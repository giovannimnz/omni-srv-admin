---
phase: 45
status: planned
created: 2026-07-10
updated: 2026-07-10
---

# 45 Validation Matrix

This validation contract is mandatory at the end of each Phase 45 task and
again before phase closeout. Prefer cheap/read-only checks first, then live
resolver/service checks.

## Gate 45-01 - Planning And Parity

```powershell
Set-Location C:\Users\muniz\Documents\GitHub\omni-srv-admin
node C:\Users\muniz\.codex\gsd-core\bin\gsd-tools.cjs query config-get workflow.plan_review_convergence
Test-Path .planning\phases\45-internal-dns-drg-canonicalization\45-SESSION-INTAKE.md
Test-Path .planning\phases\45-internal-dns-drg-canonicalization\45-CROSS-PROJECT-DEPENDENCIES.md
Test-Path .planning\phases\45-internal-dns-drg-canonicalization\45-REVIEWS.md
rg -n "10\.100\.100\.3|10\.1\.1\." C:\Users\muniz\Documents\GitHub\oci-admin\AGENTS.md
```

Expected:

- `workflow.plan_review_convergence` returns `true`.
- The three Phase 45 intake/dependency/review artifacts exist.
- `oci-admin/AGENTS.md` has no active `10.100.100.3` Vault endpoint and no new
  active `10.1.1.x` instruction.

## Gate 45-02 - OCI Admin Dependency

```powershell
Set-Location C:\Users\muniz\Documents\GitHub\oci-admin
git status --short --branch
rg -n "10\.11\.1\.11|10\.12\.1\.12|10\.13\.1\.13|10\.21\.1\.21" .planning
rg -n "10\.1\.1\.0|10\.1\.1\.2|10\.100\.100\.0" .planning
uv run oci-admin --json peering drg-status --profile atius1 --region sa-saopaulo-1
```

Expected:

- Dirty `oci-admin` state is understood before editing; do not mix Phase 45
  dependency changes into unrelated active work.
- OCI evidence covers DRG attachment/routing and security for DNS, PgBouncer,
  Obsidian, Vault and TEI ports.
- Historical `10.1.1.0/24` references are either retired/classified or tracked
  as cleanup, not accepted as current service path.

## Gate 45-03 - Internal DNS Records

```bash
dig +short @10.11.1.11 atius-srv-1 A
dig +short @10.11.1.11 atius-srv-2 A
dig +short @10.11.1.11 atius-srv-3 A
dig +short @10.11.1.11 horistic-srv A
dig +short @10.11.1.11 atius-srv-1.atius.internal A
dig +short @10.11.1.11 atius-srv-2.atius.internal A
dig +short @10.11.1.11 atius-srv-3.atius.internal A
dig +short @10.11.1.11 horistic-srv.atius.internal A
```

Expected:

- `atius-srv-1` and `atius-srv-1.atius.internal` return `10.11.1.11`.
- `atius-srv-2` and `atius-srv-2.atius.internal` return `10.12.1.12`.
- `atius-srv-3` and `atius-srv-3.atius.internal` return `10.13.1.13`.
- `horistic-srv` and `horistic-srv.atius.internal` return `10.21.1.21`.

## Gate 45-03 - Linux Resolver And Ping

Run from each Linux host or through controlled SSH:

```bash
resolvectl dns || cat /etc/resolv.conf
getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv
ping -c 2 atius-srv-1
ping -c 2 atius-srv-2
ping -c 2 atius-srv-3
ping -c 2 horistic-srv
```

Expected:

- Resolution returns the DRG/OCI private IPs.
- ICMP failure is not automatically a DNS failure; if `getent` is correct and
  `ping` fails, record firewall/ICMP classification separately.
- No host resolver prefers `10.1.1.2`.
- `10.100.100.1` can remain reserve/fallback only, not primary.

## Gate 45-03 - Windows And Edge Clients

```powershell
Resolve-DnsName atius-srv-1 -Server 10.11.1.11
Resolve-DnsName atius-srv-2 -Server 10.11.1.11
Resolve-DnsName atius-srv-3 -Server 10.11.1.11
Resolve-DnsName horistic-srv -Server 10.11.1.11
ping atius-srv-1
Test-NetConnection atius-srv-1 -Port 6432
Test-NetConnection 10.11.1.11 -Port 27124
Test-NetConnection 10.13.1.13 -Port 8202
Test-NetConnection 10.21.1.21 -Port 3115
```

Expected:

- W11 resolves short hostnames via internal DNS.
- W11 reaches the OCI targets through the approved bridge/fallback route.
- W11 remains classified as an edge client unless a native DRG path exists.
- S23 closeout requires a Termux-side outbound proof, not only bridge-side
  ping/TCP evidence.

## Gate 45-04 - Service Endpoints

```bash
nc -vz 10.11.1.11 53
nc -vz 10.11.1.11 6432
curl -k https://10.11.1.11:27124/
curl -k https://10.13.1.13:8202/v1/sys/health
curl http://10.21.1.21:3115/health
```

Expected:

- Service checks use DRG/OCI private IPs first.
- TEI primary is `10.21.1.21:3115`; `10.100.100.4:3115` is reserve only.
- Vault primary is `10.13.1.13:8202`; `10.100.100.3:8202` must not be the
  canonical endpoint in current docs/instructions.

## Gate 45-04 - Repo Drift

```bash
rg -n "10\.1\.1\." docs inventory modules scripts .planning
rg -n "10\.100\.100\." docs inventory modules scripts .planning
rg -n "10\.21\.1\.21:3115|10\.100\.100\.4:3115|embedding-gte-v1" docs modules inventory .planning
rg -n "home-proxy|PPTP|192\.168\.1\.8|192\.168\.1\.9|acp\.customAgents|gsd-" .planning docs inventory modules
```

Expected:

- `10.1.1.x` hits are historical, retired, or explicit cleanup notes.
- `10.100.100.x` hits are fallback/reserve/edge references or historical
  evidence.
- Home-proxy/PPTP is residential fallback only.
- Wayland GSD references do not model GSD skills as runtime agents.

## Closeout Evidence

- Obsidian note in `60-LOGS` with final DNS/DRG model and validation summary.
- GBrain entry retrievable by search/query; use no-embed sync fallback if direct
  write fails.
- Local `omni-srv-admin`, remote `atius-srv-1` `omni-srv-admin`, and
  `oci-admin` dirty states are either clean/aligned or documented as a merge
  queue with owner and next action.
- Phase 42 and Phase 44 remain paused until this validation passes or an
  explicit exception is signed.
