---
phase: 45
plan: 45-PLAN
type: implementation
wave: 1
depends_on: []
files_modified:
  - inventory/hosts/*.yaml
  - docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md
  - docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md
  - docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md
  - docs/CLOUDFLARE.md
  - modules/fleet-control-plane/tools/validate_m004.py
  - modules/fleet-network-watchdog/*.sh
  - modules/srv1-network-watchdog/*.sh
autonomous: false
requirements: [DNS-01, DNS-02, DNS-03, DNS-04, DNS-05, DNS-06, DNS-07, DNS-08]
---

# 45-PLAN - Internal DNS and DRG Canonicalization

<objective>
Make internal DNS and service routing DRG/OCI-first across repo, live hosts,
Windows client status, Cloudflare boundary docs, watchdog automation and durable
knowledge stores.
</objective>

<tasks>

<task id="45-01" type="repo-cleanup" wave="1">
<read_first>
- .planning/phases/45-internal-dns-drg-canonicalization/45-CONTEXT.md
- docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md
- docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md
- docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md
- inventory/hosts/atius-srv-1.yaml
- inventory/hosts/atius-srv-2.yaml
- inventory/hosts/atius-srv-3.yaml
- inventory/hosts/horistic-srv.yaml
- inventory/hosts/giovanni-w11-pc.yaml
</read_first>
<action>
Classify every remaining `10.1.1.x` and primary-looking `10.100.100.x` reference in active repo docs, inventory, scripts and validators. Convert active service endpoints to `10.11.1.11`, `10.12.1.12`, `10.13.1.13` or `10.21.1.21` as appropriate. Mark true historical references with explicit wording such as `historical`, `retired`, or `legacy evidence`. Keep `GIOVANNI-W11-PC` on `10.100.100.1:6432` only if the file also states that direct DRG reachability is not yet proven.
</action>
<acceptance_criteria>
- `rg -n "10\\.1\\.1\\." docs inventory modules scripts .planning` returns no active config, active validation, or primary service endpoint lines.
- `rg -n "10\\.100\\.100\\." docs inventory modules scripts .planning` returns only reserve/fallback/exceptions or historical evidence.
- `inventory/hosts/*.yaml` uses `access.oci_private_ip` for canonical routing where present.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` lists PgBouncer as `10.11.1.11:6432`, Obsidian as `10.11.1.11:27124`, Vault as `10.13.1.13:8202`, and TEI as `10.21.1.21:3115`.
</acceptance_criteria>
<verify>
rg -n "10\\.1\\.1\\." docs inventory modules scripts .planning
rg -n "10\\.100\\.100\\." docs inventory modules scripts .planning
</verify>
</task>

<task id="45-02" type="live-resolver-cutover" wave="2">
<read_first>
- docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md
- modules/fleet-network-watchdog/fleet-network-watchdog.sh
- modules/fleet-network-watchdog/srv1-fix-network.sh
- modules/srv1-network-watchdog/srv1-fix-network.sh
</read_first>
<action>
On SRV-1, SRV-2, SRV-3 and Horistic, capture before-state for `/etc/resolv.conf`, `/etc/systemd/resolved.conf`, `resolvectl status`, and any fleet network watchdog scripts. Change resolvers so `10.11.1.11` is the preferred internal DNS endpoint and remove active `10.1.1.2` resolver use. Keep per-host rollback copies. Validate Windows separately with `nslookup atius-srv-1 10.11.1.11` and TCP probes to `10.11.1.11:6432` and `10.11.1.11:27124`; retain reserve exception if direct DRG fails.
</action>
<acceptance_criteria>
- `resolvectl dns` on SRV-1/SRV-2/SRV-3 does not list `10.1.1.2`.
- Horistic resolver does not use `10.100.100.1` as primary.
- `getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv` resolves to OCI/DRG IPs on all Linux hosts.
- Windows has either validated direct DRG reachability or an explicit reserve exception with next action.
</acceptance_criteria>
<verify>
ssh -n ATIUS-SRV-1 "resolvectl dns; getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv"
nslookup atius-srv-1 10.11.1.11
</verify>
</task>

<task id="45-03" type="dns-authority-boundary" wave="3">
<read_first>
- docs/CLOUDFLARE.md
- docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md
- docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md
</read_first>
<action>
Document and validate the split between public Cloudflare DNS and internal DNS. Public records remain under `atius.com.br` in Cloudflare. Internal hostnames use short names and `*.atius.internal` served by internal DNS on `10.11.1.11:53`. Do not add private host identity to Cloudflare. Add or verify internal DNS records for `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv`.
</action>
<acceptance_criteria>
- `dig +short @10.11.1.11 atius-srv-1 A` returns `10.11.1.11`.
- `dig +short @10.11.1.11 atius-srv-2 A` returns `10.12.1.12`.
- `dig +short @10.11.1.11 atius-srv-3 A` returns `10.13.1.13`.
- `dig +short @10.11.1.11 horistic-srv A` returns `10.21.1.21`.
- `docs/CLOUDFLARE.md` states Cloudflare is public-only for this boundary.
</acceptance_criteria>
<verify>
dig +short @10.11.1.11 atius-srv-1 A
dig +short @10.11.1.11 atius-srv-2 A
dig +short @10.11.1.11 atius-srv-3 A
dig +short @10.11.1.11 horistic-srv A
</verify>
</task>

<task id="45-04" type="drift-automation-closeout" wave="4">
<read_first>
- docs/operations/ATIUS-DRG-DNS-SESSION-LEARNINGS.md
- docs/operations/codex-gbrain-obsidian-mcp.md
- modules/fleet-control-plane/tools/validate_m004.py
- scripts/codex-mcp-startup-smoke.ps1
</read_first>
<action>
Add or update lightweight drift checks so future changes fail visibly when `10.1.1.x` returns as active endpoint or `10.100.100.x` is described as primary. Run focused tests and shell syntax checks. Write a concise Obsidian note and sync/capture it into GBrain using the no-embed fallback if needed.
</action>
<acceptance_criteria>
- `pytest cli/omni/tests/test_fleet_pki.py -q` exits 0.
- `pytest modules/fleet-control-plane/tests/test_m004_contract.py -q` exits 0 or any skipped test is explicitly justified.
- `bash -n` passes for edited shell scripts.
- Obsidian has a `60-LOGS` note for Phase 45 closeout.
- GBrain can list or retrieve the Phase 45 closeout slug.
</acceptance_criteria>
<verify>
pytest cli/omni/tests/test_fleet_pki.py -q
pytest modules/fleet-control-plane/tests/test_m004_contract.py -q
wsl.exe bash -n modules/fleet-control-plane/scripts/omni-pg-access-guard.sh
</verify>
</task>

</tasks>

<verification>
- Validate repo cleanup with targeted `rg` queries.
- Validate live DNS with `dig`, `getent`, `nslookup`, and TCP probes.
- Validate code paths with focused pytest and shell syntax checks.
- Validate durable context by reading the Obsidian note and GBrain slug.
</verification>

<success_criteria>
- DRG/OCI private IPs are the default for names and service endpoints.
- `wg100` is reserve-only in docs/configs.
- `10.1.1.0/24` is retired everywhere except historical evidence.
- Phase 42 and Phase 44 can resume without relying on legacy DNS or active WireGuard service routing.
</success_criteria>

## Artifacts This Phase Produces

- `.planning/phases/45-internal-dns-drg-canonicalization/45-CONTEXT.md`
- `.planning/phases/45-internal-dns-drg-canonicalization/45-RESEARCH.md`
- `.planning/phases/45-internal-dns-drg-canonicalization/45-PLAN.md`
- `.planning/phases/45-internal-dns-drg-canonicalization/45-PLAN-CHECK.md`
- `.planning/phases/45-internal-dns-drg-canonicalization/45-VALIDATION.md`
- Updated DNS/DRG operational docs and inventory entries
- Obsidian/GBrain Phase 45 closeout note
