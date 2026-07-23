---
phase: 45
plan: 45-PLAN
type: implementation
wave: 1
depends_on: []
files_modified:
  - .planning/config.json
  - .planning/MILESTONES.md
  - .planning/PROJECT.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/*.md
  - inventory/hosts/*.yaml
  - docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md
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
Make internal DNS, host naming, resolver configuration and service endpoint
selection DRG/OCI-first across the ATIUS fleet, while keeping `wg100` only as
fallback/edge access and recording all cross-session/cross-repo dependencies in
`.planning`.
</objective>

<premises>
- The primary server-to-server plane is OCI/DRG:
  `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`.
- `10.100.100.0/24` is reserve fallback and W11/S23 edge access only.
- `10.1.1.0/24` is retired; it cannot be used as active resolver, service path,
  validation path, or rollback target.
- Phase planning is canonical only under `.planning`. Docs under `docs/` are
  runbooks, evidence, or operational references, not executable phase plans.
- `oci-admin` owns OCI/DRG evidence; `omni-srv-admin` owns inventory, resolver
  cutover, service endpoint drift checks, and durable knowledge closeout.
</premises>

<tasks>

<task id="45-01" type="planning-convergence" wave="1">
<read_first>
- .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-SESSION-INTAKE.md
- .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-CROSS-PROJECT-DEPENDENCIES.md
- .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-REVIEWS.md
- .planning/MILESTONES.md
- .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md
- .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
- .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
- AGENTS.md
- C:\Users\muniz\Documents\GitHub\oci-admin\AGENTS.md
</read_first>
<action>
Finish the cross-session replan before any DNS mutation. Keep Phase 45 as the
current gate, record the five Codex sessions as intake evidence, enable the
plan-review convergence feature gate, verify `AGENTS.md` parity between local
Windows and `atius-srv-1`, correct stale local `oci-admin` operating notes, and
make `.planning` the only canonical phase-planning surface. Treat docs named
"plan" as legacy/runbook references unless they are explicitly copied into the
Phase 45 planning directory.
</action>
<acceptance_criteria>
- `45-SESSION-INTAKE.md`, `45-CROSS-PROJECT-DEPENDENCIES.md`, and
  `45-REVIEWS.md` exist and are referenced by the main plan.
- `.planning/config.json` has `workflow.plan_review_convergence=true`.
- Local and `atius-srv-1` `omni-srv-admin/AGENTS.md` are semantically aligned on
  DRG primary host identity and Vault `10.13.1.13`.
- `C:\Users\muniz\Documents\GitHub\oci-admin\AGENTS.md` no longer points Vault
  to `10.100.100.3` and states OCI/DRG as the primary server-to-server plane.
- The current delivery order remains Phase 45 -> Phase 42 closeout -> Phase 44
  continuation, with Wayland and home-proxy tracked as parallel dependencies.
</acceptance_criteria>
<verify>
node C:\Users\muniz\.codex\gsd-core\bin\gsd-tools.cjs query config-get workflow.plan_review_convergence
rg -n "10\.100\.100\.3|10\.1\.1\." C:\Users\muniz\Documents\GitHub\oci-admin\AGENTS.md
ssh -n ATIUS-SRV-1 "cd /home/ubuntu/GitHub/omni-srv-admin && sed -n '1,40p' AGENTS.md"
</verify>
</task>

<task id="45-02" type="oci-admin-dependency-gate" wave="2">
<read_first>
- .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-CROSS-PROJECT-DEPENDENCIES.md
- C:\Users\muniz\Documents\GitHub\oci-admin\.planning\PROJECT.md
- C:\Users\muniz\Documents\GitHub\oci-admin\.planning\STATE.md
- C:\Users\muniz\Documents\GitHub\oci-admin\.planning\ROADMAP.md
- C:\Users\muniz\Documents\GitHub\oci-admin\.planning\REQUIREMENTS.md
</read_first>
<action>
Use `oci-admin` as the OCI-side authority before live DNS cutover. Confirm DRG,
route tables, VCN/subnet placement, NSGs/security lists, and private IP
attachments for the four canonical hosts. Validate W11 reachability to OCI
targets through the approved bridge path and keep S23 blocked until outbound
proof is captured from inside the handset. Do not edit broad `oci-admin`
planning while its worktree is dirty; instead, record exact evidence required
here and open/update a dedicated `oci-admin` planning artifact only after that
repo is stable or ownership is explicitly taken.
</action>
<acceptance_criteria>
- `oci-admin` proves the target IP map:
  `atius-srv-1=10.11.1.11`, `atius-srv-2=10.12.1.12`,
  `atius-srv-3=10.13.1.13`, `horistic-srv=10.21.1.21`.
- OCI rules permit the intended internal service ports and do not require
  `10.1.1.0/24`.
- W11 is classified as an edge client reaching DRG targets through `wg100`
  bridge/fallback, not as a native OCI host.
- S23 has either handset-side outbound proof or remains an explicit blocker.
- No Phase 45 DNS cutover step depends on uncommitted remote docs/inventory
  changes from `atius-srv-1`.
</acceptance_criteria>
<verify>
git -C C:\Users\muniz\Documents\GitHub\oci-admin status --short --branch
rg -n "10\.11\.1\.11|10\.12\.1\.12|10\.13\.1\.13|10\.21\.1\.21|10\.1\.1\.0" C:\Users\muniz\Documents\GitHub\oci-admin\.planning
uv run oci-admin --json peering drg-status --profile atius1 --region sa-saopaulo-1
</verify>
</task>

<task id="45-03" type="internal-dns-cutover" wave="3">
<read_first>
- docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md
- docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md
- inventory/hosts/atius-srv-1.yaml
- inventory/hosts/atius-srv-2.yaml
- inventory/hosts/atius-srv-3.yaml
- inventory/hosts/horistic-srv.yaml
- modules/fleet-network-watchdog/fleet-network-watchdog.sh
- modules/fleet-network-watchdog/srv1-fix-network.sh
- modules/srv1-network-watchdog/srv1-fix-network.sh
</read_first>
<action>
Implement or correct the internal DNS/resolver path so `10.11.1.11:53` serves
short names and `*.atius.internal` to the OCI/DRG private IPs. On Linux hosts,
capture before-state, apply resolver changes host by host with rollback copies,
and verify `getent hosts` plus `ping <hostname>`. On Windows, verify
`Resolve-DnsName` and `ping atius-srv-1`; if Windows reaches the DRG targets
through `wg100`, record that as edge-fallback reachability rather than native
DRG membership.
</action>
<acceptance_criteria>
- `dig +short @10.11.1.11 atius-srv-1 A` returns `10.11.1.11`.
- `dig +short @10.11.1.11 atius-srv-2 A` returns `10.12.1.12`.
- `dig +short @10.11.1.11 atius-srv-3 A` returns `10.13.1.13`.
- `dig +short @10.11.1.11 horistic-srv A` returns `10.21.1.21`.
- Linux `getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv`
  resolves to DRG/OCI IPs on all four hosts.
- `ping atius-srv-1` resolves by hostname from Linux and Windows validation
  points; firewall/ICMP failures are classified separately from DNS failures.
- Watchdogs do not reapply `10.1.1.2` or make `10.100.100.1` primary.
</acceptance_criteria>
<verify>
ssh -n ATIUS-SRV-1 "dig +short @10.11.1.11 atius-srv-1 A; getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv"
Resolve-DnsName atius-srv-1 -Server 10.11.1.11
ping atius-srv-1
rg -n "10\.1\.1\.2|10\.100\.100\.1.*primary|primary.*10\.100\.100\.1" modules docs inventory .planning
</verify>
</task>

<task id="45-04" type="fallback-boundary-closeout" wave="4">
<read_first>
- .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-SESSION-INTAKE.md
- .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-VALIDATION.md
- docs/operations/ATIUS-DRG-DNS-SESSION-LEARNINGS.md
- docs/operations/codex-gbrain-obsidian-mcp.md
- modules/fleet-control-plane/tools/validate_m004.py
- modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md
</read_first>
<action>
Close Phase 45 by enforcing drift checks and durable knowledge. Merge or defer
remote `atius-srv-1` dirty docs/inventory changes explicitly, keeping
home-proxy/PPTP as residential fallback and Wayland GSD runtime as a parallel
operator-tooling dependency. Update Obsidian and GBrain with the final canonical
DNS model, validation evidence, and remaining blockers. Keep secret values out
of Git, `.planning`, Obsidian, GBrain, logs and shell history.
</action>
<acceptance_criteria>
- `rg -n "10\.1\.1\." docs inventory modules scripts .planning` returns only
  historical/retired references or explicit cleanup notes.
- `rg -n "10\.100\.100\." docs inventory modules scripts .planning` returns
  only fallback/reserve/edge references or historical evidence.
- Router/TEI references keep `http://10.21.1.21:3115` primary and
  `http://10.100.100.4:3115` reserve only.
- Home edge BE3/PPTP references are not modeled as internal DNS/DRG authority.
- Obsidian has a Phase 45 note in `60-LOGS` and GBrain can retrieve or search
  the corresponding record.
- Local and remote repo status are either clean/aligned or have a documented
  remaining merge queue.
</acceptance_criteria>
<verify>
rg -n "10\.1\.1\." docs inventory modules scripts .planning
rg -n "10\.100\.100\." docs inventory modules scripts .planning
rg -n "10\.21\.1\.21:3115|10\.100\.100\.4:3115|embedding-gte-v1" docs modules inventory .planning
ssh -n ATIUS-SRV-1 "cd /home/ubuntu/GitHub/omni-srv-admin && git status --short --branch"
</verify>
</task>

</tasks>

<verification>
- Run the task-local verify commands at the end of each task.
- Run the full matrix in `45-VALIDATION.md` before declaring the phase complete.
- Treat `ping` failures as DNS failures only when name resolution itself fails;
  ICMP firewall failures must be documented separately.
- Phase 42 and Phase 44 remain paused until Phase 45 proves hostnames and
  internal service endpoints prefer the DRG/OCI private plane.
</verification>

<success_criteria>
- Short hostnames resolve automatically to DRG/OCI private IPs wherever the
  client has a valid internal path.
- `wg100` remains fallback/edge only and is not described as the primary service
  plane.
- `10.1.1.0/24` is absent from active config, scripts, validators and runbooks.
- `oci-admin`, Obsidian and GBrain all contain the final responsibility model
  and evidence trail without secrets.
- The remote `atius-srv-1` dirty worktree is either merged, committed/pushed, or
  explicitly left as a tracked follow-up.
</success_criteria>

## Artifacts This Phase Produces

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-CONTEXT.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-RESEARCH.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-SESSION-INTAKE.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-S23-EDGE-VALIDATION.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-CROSS-PROJECT-DEPENDENCIES.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-REVIEWS.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-PLAN.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-PLAN-CHECK.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-VALIDATION.md`
- Updated DNS/DRG operational docs and inventory entries when execution reaches
  the relevant tasks.
- Obsidian/GBrain Phase 45 closeout note.
