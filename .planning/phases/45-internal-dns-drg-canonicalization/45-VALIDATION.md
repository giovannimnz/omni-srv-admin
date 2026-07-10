---
phase: 45
status: planned
created: 2026-07-10
---

# 45 Validation Matrix

## Repo Validation

```bash
rg -n "10\\.1\\.1\\." docs inventory modules scripts .planning
rg -n "10\\.100\\.100\\." docs inventory modules scripts .planning
pytest cli/omni/tests/test_fleet_pki.py -q
pytest modules/fleet-control-plane/tests/test_m004_contract.py -q
```

## Linux DNS Validation

```bash
dig +short @10.11.1.11 atius-srv-1 A
dig +short @10.11.1.11 atius-srv-2 A
dig +short @10.11.1.11 atius-srv-3 A
dig +short @10.11.1.11 horistic-srv A
getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv
```

## Service Validation

```bash
nc -vz 10.11.1.11 6432
curl -k https://10.11.1.11:27124/
curl -k https://10.13.1.13:8202/v1/sys/health
curl http://10.21.1.21:3115/v1/models
```

## Windows Validation

```powershell
nslookup atius-srv-1 10.11.1.11
Test-NetConnection 10.11.1.11 -Port 6432
Test-NetConnection 10.11.1.11 -Port 27124
```

## Closeout Evidence

- Obsidian note in `60-LOGS`.
- GBrain slug retrievable after `gbrain sync --full --no-embed` when needed.
- Both Windows and ATIUS-SRV-1 checkouts are clean and aligned to the same pushed `origin/main`.
