# Internal Service PKI

Authoritative CLI resource:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki plan --json
PYTHONPATH=cli python -m omni fleet trust-pki render-host --host <host-id> --json
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --json
PYTHONPATH=cli python -m omni fleet trust-pki install-trust --host giovanni-w11-pc --json
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --json
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host <host-id> --reason ip-change --json
```

## Add A Server

1. Register the server in `inventory/hosts/<host-id>.yaml`.
2. Sync it to DbOmniFleet when DB-backed execution is required:

```bash
PYTHONPATH=cli python -m omni fleet registry sync --host <host-id> --json
```

3. Render the PKI plan:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --source auto --json
```

4. Queue the onboarding sequence in DbOmniFleet:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --source db --db --json
```

5. Approved execution is explicit:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --source db --db --execute --approve --json
```

## IP Or SAN Change

When a host IP, alias or explicit SAN changes:

1. Update `inventory/hosts/<host-id>.yaml`.
   - The primary VPN SAN comes from `access.vpn_ip`.
   - The canonical private service plane is now the OCI/DRG map
     (`10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`).
   - `wg100` / `10.100.100.0/24` remains reserve fallback only.
   - The retired `10.1.1.0/24` range belongs only in historical notes, not in
     active inventory fields or service endpoints.
   - Do not change live service URLs from `http://10.1.1.x` to
     `https://10.100.100.x` until that service has an explicit TLS/rebind
     validation.
2. Sync the host to DbOmniFleet:

```bash
PYTHONPATH=cli python -m omni fleet registry sync --host <host-id> --json
```

3. Reconcile desired SANs against the current certificate. For offline checks,
pass the observed SANs or a local certificate:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --source db --observed-san-json '{"dns":["example"],"ip":["10.100.100.9"]}' --json
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --cert-file /path/to/server.crt.pem --json
```

For remote read-only inspection through the fleet agent:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --source db --db --approve --json
```

4. If drift exists, queue leaf rotation:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host <host-id> --source db --db --reason ip-change --json
```

5. Approved execution stays explicit:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host <host-id> --source db --db --execute --approve --reason ip-change --json
```

If the current certificate cannot be inspected yet, add `--force` to queue a
rotation from the current inventory/DbOmniFleet SANs.

## Execution Model

`onboard-host` creates the per-host server sequence:

- `omni.trust-pki.preflight` runs on the target host.
- `omni.trust-pki.ensure-key-csr` runs on the target host.
- `omni.trust-pki.issue-host` runs on `atius-srv-1`.
- `omni.trust-pki.install-ca` runs on the target host.
- `omni.trust-pki.install-leaf` runs on the target host.
- `omni.trust-pki.reconcile` runs read-only on the target host.
- `omni.trust-pki.verify` runs on the target host.

`GIOVANNI-W11-PC` is a Windows `trust-client`, not a service leaf owner. Its
automatic path is `TbUpdatePlans -> OmniFleetAgent -> omni.trust-pki.windows.*`
and includes:

- `omni.trust-pki.windows.preflight`
- `omni.trust-pki.windows.install-ca`
- `omni.trust-pki.windows.verify`

Use this to queue the CA/trust refresh through the automatic agent path:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki install-trust --host giovanni-w11-pc --source db --db --json
```

The command templates are registered in
`modules/fleet-control-plane/migrations/0008_internal_service_pki_commands.sql`
and are also available as local CLI fallback allowlist entries.

## Trust Model

- All hosts trust the internal service CA chain.
- Hosts do not install peer leaf certificates as trusted root CAs.
- Each host owns its private key under `/etc/omni-srv-admin/tls/<host-id>/`.
- `GIOVANNI-W11-PC` receives the root CA in `Cert:\CurrentUser\Root`, the
  issuing CA in `Cert:\CurrentUser\CA`, and may keep peer public leaf
  certificates only as audit/pinning evidence.
- CA material is owned by `atius-srv-1` under `/var/lib/omni-srv-admin/pki/`.
- Raw keys, passphrases, tokens and private cert material stay out of Git,
  `.planning`, Obsidian, GBrain, DB dry-run payloads and logs.

## Current Status

2026-07-06 rollout:

- SRV-1 PgBouncer now listens on `10.11.1.11:6432`, reserve `10.100.100.1:6432`,
  and `127.0.0.1:6432`.
- `/usr/local/sbin/omni-pg-access-guard.sh` on SRV-1 now allows
  OCI private peers (`10.12/10.13/10.21`) plus reserve `wg100` / `10.100.100.0/24`
  to PgBouncer `6432`, while direct PostgreSQL `8745` remains rejected.
- Windows `GIOVANNI-W11-PC` connects to DbOmniFleet through
  `10.11.1.11:6432` when direct DRG is available, otherwise reserve
  `10.100.100.1:6432`; `omni fleet agent cycle --host giovanni-w11-pc
  --apply --json` returned `status=idle` with telemetry `healthy`.
- The Windows trust-client plan
  `22097c7e-cf44-4841-9133-33517578f21f` was marked `succeeded` after
  root/issuing CA import and `agent-runner verify status=ok`.

CA state:

- CA host: `atius-srv-1`.
- CA base: `/var/lib/omni-srv-admin/pki/`.
- Linux TLS base: `/etc/omni-srv-admin/tls/`.
- Windows trust-client base: `C:\Users\muniz\.local\share\omni-service-pki`.
- Root fingerprint SHA256:
  `8C:F9:68:BB:8D:CA:10:8C:4F:5F:34:FB:63:BC:55:C0:28:01:B0:FC:9C:E5:BB:C0:F0:D6:07:FB:85:04:CB:0E`.
- Issuing fingerprint SHA256:
  `A0:5D:2C:F3:47:BA:9E:9A:9D:FE:CE:2C:E9:E1:ED:48:23:45:72:03:2E:A8:AB:2D:D0:9A:21:7A:BD:3E:3D:51`.
- Windows root store thumbprint:
  `13CDB8BF5ADD824B206B5EBD93E38073B12DAA54` in `Cert:\CurrentUser\Root`.
- Windows issuing store thumbprint:
  `0356342C9C3F634E2F5BD65EFCF020E9F49B9A15` in `Cert:\CurrentUser\CA`.

Leafs:

| Host | Serial | SHA256 fingerprint |
|---|---:|---|
| `atius-srv-1` | `1001` | `F7:D7:14:C3:ED:5C:34:C2:3D:EC:13:B9:E7:F0:4B:75:04:03:34:EC:48:51:28:09:A8:5F:F9:8F:C6:9B:DA:20` |
| `atius-srv-2` | `1002` | `CE:F9:2C:7F:A9:06:4A:C4:D0:7C:A7:C6:FD:53:82:7C:44:5A:88:87:C2:43:05:39:BE:C4:91:84:44:4D:5B:DE` |
| `atius-srv-3` | `1003` | `F2:FB:2D:04:E3:A4:4D:B8:B8:74:AC:85:25:54:E3:54:FD:2D:F2:65:36:9E:D1:7B:77:6F:6C:D0:ED:0F:3C:C1` |
| `horistic-srv` | `1004` | `04:38:1C:0F:52:4E:D6:A1:7B:3E:EA:8D:A1:33:9E:B9:FE:14:B5:89:31:AF:E3:EE:56:4C:7C:B7:8D:62:DC:9D` |

2026-07-12 Phase 47 closeout:

- Rotated all four Linux service leafs to remove legacy `10.1.1.x` SANs and
  include the canonical OCI/DRG private IPs.
- New leaf fingerprints:

| Host | Serial | SHA256 fingerprint |
|---|---:|---|
| `atius-srv-1` | `1006` | `BA:B5:A1:2A:F1:34:DD:D1:77:2B:AD:98:F0:75:A9:1C:1B:19:5F:7F:B3:4E:54:E2:5A:5E:F7:08:A6:E4:96:8B` |
| `atius-srv-2` | `1007` | `B2:A4:38:C0:40:30:9A:BB:9A:EB:F8:2A:44:3D:25:C1:11:96:57:D7:2D:37:FD:34:43:85:F2:02:25:24:98:80` |
| `atius-srv-3` | `1008` | `74:18:40:83:A3:3E:98:93:6D:60:05:AA:F1:9D:9B:FE:D1:9C:C0:88:60:74:BF:8D:5B:96:7A:CC:59:5F:35:B4` |
| `horistic-srv` | `1009` | `12:37:88:3B:07:15:5F:5A:10:7B:AD:85:CA:A6:E9:11:D2:25:4D:FE:D1:F0:F6:E6:DB:B1:10:E9:21:A9:8F:71` |

- Obsidian REST on `atius-srv-1` now serves the ATIUS-issued chain on
  `https://10.11.1.11:27124`.
- HashiCorp Vault on `atius-srv-3` now serves the ATIUS-issued chain on
  `https://10.13.1.13:8202`, with `api_addr`/`cluster_addr` updated to
  `10.13.1.13` and reserve fallback still available on `10.100.100.3`.
- Cross-host validation was completed using real listeners instead of the
  temporary `39447` matrix helper because the helper assumes direct host SSH on
  the private IP plane. The closeout proved 12 HTTPS checks:
  - `srv2`, `srv3`, `horistic` -> Obsidian by IP and hostname
  - `srv1`, `srv2`, `horistic` -> Vault by IP and hostname
- Windows validated both listeners without insecure flags:
  - Obsidian `https://10.11.1.11:27124/` -> HTTP `200`
  - Vault `https://10.13.1.13:8202/v1/sys/health?standbyok=true&perfstandbyok=true` -> HTTP `503`

Validation:

```bash
modules/fleet-pki/scripts/verify-fleet-pki-matrix.sh --json
# status=ok, 32/32 Linux HTTPS checks passed
```

- The Linux matrix validates every source host to every target host by both
  `10.100.100.x` IP SAN and DNS SAN.
- Windows validated HTTPS from `GIOVANNI-W11-PC` to `10.100.100.1` through
  `10.100.100.4` using `C:\Users\muniz\.local\share\omni-service-pki\ca\ca-chain.crt.pem`.
- Obsidian note:
  `60-LOGS/2026-07-06-internal-service-pki-fleet.md`.
- GBrain slug:
  `omni-srv-admin-internal-service-pki-2026-07-06`.

Backups:

- SRV-1 PgBouncer guard:
  `/usr/local/sbin/omni-pg-access-guard.sh.20260706-093523.bak`.
- SRV-1 PKI backup directory observed:
  `/root/.backups/omni-fleet-pki-20260706T124732Z`.
- Windows public trust material backups, when overwritten:
  `C:\Users\muniz\.local\share\omni-service-pki\.backups\YYYYMMDD-HHMMSS`.

Service adapter rule:

PKI readiness does not automatically migrate production services from HTTP to
HTTPS. TEI, Vault, Obsidian REST, Keycloak, Apache vhosts and similar services
still need service-specific TLS/rebind gates before changing live URLs such as
`http://10.1.1.x` to `https://10.100.100.x`.
