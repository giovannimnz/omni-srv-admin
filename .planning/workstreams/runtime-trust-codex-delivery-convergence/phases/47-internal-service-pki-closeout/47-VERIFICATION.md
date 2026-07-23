---
status: passed
verified: 2026-07-12
phase: 47
---

# Phase 47 Verification

- Linux leaf rotation completed for `atius-srv-1`, `atius-srv-2`, `atius-srv-3` and `horistic-srv`.
- Current Linux leaf fingerprints:
  - `atius-srv-1`: `BA:B5:A1:2A:F1:34:DD:D1:77:2B:AD:98:F0:75:A9:1C:1B:19:5F:7F:B3:4E:54:E2:5A:5E:F7:08:A6:E4:96:8B`
  - `atius-srv-2`: `B2:A4:38:C0:40:30:9A:BB:9A:EB:F8:2A:44:3D:25:C1:11:96:57:D7:2D:37:FD:34:43:85:F2:02:25:24:98:80`
  - `atius-srv-3`: `74:18:40:83:A3:3E:98:93:6D:60:05:AA:F1:9D:9B:FE:D1:9C:C0:88:60:74:BF:8D:5B:96:7A:CC:59:5F:35:B4`
  - `horistic-srv`: `12:37:88:3B:07:15:5F:5A:10:7B:AD:85:CA:A6:E9:11:D2:25:4D:FE:D1:F0:F6:E6:DB:B1:10:E9:21:A9:8F:71`
- Local host verification passed on all four Linux hosts via `omni-fleet-pki-host.sh verify`.
- Cross-host HTTPS checks passed:
  - `srv2`, `srv3`, `horistic` -> Obsidian `10.11.1.11:27124` with both `-verify_ip 10.11.1.11` and `-verify_hostname atius-srv-1`
  - `srv1`, `srv2`, `horistic` -> Vault `10.13.1.13:8202` with both `-verify_ip 10.13.1.13` and `-verify_hostname atius-srv-3`
- Listener bindings updated:
  - Obsidian REST now serves the ATIUS-issued chain from `data.json` on `10.11.1.11:27124`.
  - Vault now advertises `api_addr=https://10.13.1.13:8202` and `cluster_addr=https://10.13.1.13:8203`, serving the ATIUS-issued chain on both `10.13.1.13` and reserve `10.100.100.3`.
- Windows HTTPS passed without insecure flags:
  - Obsidian `https://10.11.1.11:27124/` -> HTTP `200`
  - Vault `https://10.13.1.13:8202/v1/sys/health?standbyok=true&perfstandbyok=true` -> HTTP `503`
- Pre-mutation rollback backups:
  - `srv1`: `/root/.backups/phase47-pki-listeners-20260712T055418Z`
  - `srv3`: `/root/.backups/phase47-pki-listeners-20260712T055417Z`
- Limitation: local Python runtimes available in this session did not include `pytest`, so the focused CLI PKI test file could not be executed here.
