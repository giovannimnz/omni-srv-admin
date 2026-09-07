---
name: oci-arm64-new-server-bootstrap
description: Bootstrap and validate a new ATIUS OCI Ubuntu ARM64 server without copying secrets or misconfiguring subnet routing.
---

# OCI ARM64 New Server Bootstrap

Use for a new ATIUS OCI Ubuntu 24.04 ARM64 server.

## Read first

- `docs/runbooks/atius-srv4-bootstrap.md`
- `docs/operations/rdp-trust-pki.md`
- `modules/xrdp-abnt2/README.md`
- `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`
- `inventory/hosts/atius-srv-4.yaml` when applicable

## Workflow

Canonical resumable entry point:
`modules/fleet/scripts/oci-arm64-host-setup.sh`. Run `--dry-run`, then one full
`--apply` without resume, then an independent `--verify-only`; preserve the step receipts under
`~/.local/state/omni/oci-arm64-host-setup/`. Receipts are bound to the
`SOURCE-MANIFEST.json` SHA-256; any changed staged artifact invalidates stale
PASS state instead of skipping new gates. Preflight verifies containment, no
symlinks, bytes, mode and SHA-256 for every manifest item. Parent-side
`agent-content` apply
remains item-scoped because a target must not receive an outbound private key
merely to SSH to itself.

Generate the staging tree with
`modules/fleet/scripts/build-oci-arm64-host-setup-staging.py` and the exact
allowlist `modules/fleet/configs/oci-arm64-host-setup-files.txt`. Do not create
`SOURCE-MANIFEST.json` manually: the builder is the contract for byte/mode/hash,
deterministic archive metadata and restore validation.

1. Wait for cloud-init and package installers to finish.
2. Use `oci_admin_http` reads to verify instance/VNIC, security list, NSG,
   gateway and the effective subnet route table.
3. Require a route through the IGW before testing public SSH. Test TCP first,
   then compare public/private-key fingerprints before troubleshooting auth.
4. Create `~/GitHub` and `~/GitHub/containers`; copy only a clean Git source.
5. Install the ARM64 baseline and verify Podman rootless.
   - Install the versioned public APT keyrings/sources for `chatgpt` and
     `google-chrome-stable` before `apt-get update`; a fresh host cannot resolve
     those packages from Ubuntu defaults.
   - Promote `~/.local/bin/podman-compose` with the pinned package
     `podman-compose==1.6.0`:
     `python3 -m pip install --user --break-system-packages --force-reinstall
     podman-compose==1.6.0 python-dotenv`; the Ubuntu APT 1.0.6 package remains
     an installed fallback, testable without user site packages through
     `PYTHONNOUSERSITE=1 /usr/bin/podman-compose --version`.
   - Require `command -v podman-compose` to resolve the user-local binary, then
     run a disposable compose config/run/down smoke and prove zero container
     and network residue.
6. Invoke `$xrdp-abnt2-fleet` for the keyboard stage after installing the
   `omni` CLI; keep the transactional guard's backup evidence and validate the
   timer. Treat the new host as its own bootstrap target, not as evidence that
   it participated in an earlier fleet rollout.
7. Add the host inventory and publish sanitized evidence to GBrain/Obsidian.
   - Add the host to `omni-version-matrix.json` and the Linux heartbeat/noop/
     self-update allowlists.
   - `systemctl active` is insufficient for Fleet Agent acceptance. Require
     fresh local heartbeat/version cache plus fresh `TbNodes` and `TbVersion`
     readback through PgBouncer. Prove the heartbeat timestamp advances without
     restarting the service.
8. For a full agent node, install Node.js/npm/Bun, Codex, Hermes Agent, official
   GSD Core and Graphify. Hydrate only required runtime variables from Vault;
   never copy OAuth/session state from a peer.
   - Persist `~/.local/bin`, Cargo and Bun in `~/.zshenv` before invoking
     `npx`; source order cannot recover a command that is absent from PATH.
   - Install Codex and Hermes GSD sequentially with the pinned fleet baseline
     `@opengsd/gsd-core@1.13.0` and `--profile=full`.
   - Pin Hermes to the fleet-validated commit declared by
     `OMNI_SETUP_HERMES_COMMIT`; never use moving `origin/main` as a completion
     condition. Current seal: `01ae7a5668ce0fa2efca524a4567cacdd0786c95`.
   - Set Hermes timezone to the IANA key `America/Sao_Paulo`, not `UTC-3`.
   - Run/re-run the Hermes GSD install only after the final `hermes update`:
     Hermes bundled-skill sync may overwrite `~/.hermes/skills/gsd/**` while
     leaving an old GSD manifest behind.
   - Validate `.gsd-profile=full`, `VERSION`, `gsd-tools check auto-mode`,
     effective skill names and manifests. For GSD Core 1.13.0, require all
     868 entries in each manifest; account explicitly for the 72 Codex skills
     relocated to `~/.agents/skills`. Hermes has no relocation exception.
   - Install and verify `browser-default-reconciler` with
     `BROWSER_DESKTOP=google-chrome.desktop` and `CODEX_DESKTOP=chatgpt.desktop`.
     Require `.path` and `.timer` active plus state `success` before closeout.
9. Allocate WireGuard from a proven-free slot. Existing generated peer slots
   are identities, not a numbering suggestion; `10.100.100.14` cannot be reused
   for SRV-4, whose validated reserve address is `10.100.100.18`.
10. Use a dedicated GitHub deploy key and pull-only systemd timer for an
    Obsidian replica. GBrain and the Obsidian HTTP MCP remain authoritative on
    SRV-1; do not create a second brain authority.
11. On NetworkManager/Netplan hosts, remove competing public/OCI resolvers from
    the active profile and keep `10.11.1.11` as the only resolver. Validate
    every `.atius.internal` peer through `resolvectl` and `getent`, not only
    with direct `dig @10.11.1.11`.
    - When CoreDNS answers a new host but peers still return NXDOMAIN, install
      `modules/fleet/configs/systemd/resolved.conf.d/60-atius-internal.conf`,
      restart `systemd-resolved`, flush caches, and revalidate all SRV names.
    - Fix stale self-host mappings such as SRV-2's `127.0.1.1` FQDN line; self
      FQDN must resolve to the OCI private IP, not loopback.
12. Install resource governance with `omni srv1-ops resources install
    --generic-host`. Never copy the SRV-1-only `inviolable-watchdog` to a generic
    node. Prove `doctor_ok: True`, `cpu.max=80000 100000` on 4 vCPUs, and a real
    build process inside `omni-builds.slice`.
    Always rerun `install-build-cpu-guard.sh`, even when doctor is already green.
    The wrapper must bypass nested routing whenever `/proc/self/cgroup` already
    contains `omni-builds`; requiring an inherited env marker deadlocks
    `npm -> node-gyp -> make` on the ancestor's semaphore.
13. Complete a real XRDP first login on display `:1`. Disable per-user
    `light-locker.desktop` before the acceptance rerun because it crashes under
    XRDP; preserve any Apport report before clearing it.
    - Require `/etc/xrdp/atius-rdp/server.{crt,key}.pem`, ATIUS RDP Fleet Root
      CA verification, 30-day validity, serverAuth, key match and SAN coverage
      for public/OCI-private/wg100 addresses plus canonical aliases.
    - Require the journal to select SSL and establish TLS; RDP fallback is a
      hard failure even if the desktop opens.
    - Sign `ATIUS-SRV-4.rdp` with the trusted ATIUS publisher and target
      `10.100.100.18` unless the operator contract changes.
    - Keyboard/panel watchers must exit when their X display disappears; no
      abandoned session scope or orphan watcher may remain after a test login.
14. Attach Ubuntu Pro through an attach-config file with `--no-auto-enable`,
    then enable only ESM Apps/Infra. Preserve the Landscape self-hosted
    `standalone` endpoints. Keep the subscription token in HashiCorp Vault;
    remove target hydration files after attach.
15. Never pipe a long HTTP body from `curl` into `head` while `pipefail` is
    enabled. `head` closes early and a healthy endpoint makes curl exit 23.
    Use `curl -o <temporary-file>` plus `-w` for status/size, then inspect the
    saved file with `sed -n '1p'` or `grep -m1`.
16. Before the final Graphify rebuild, create `.graphifyignore` as a complete
    copy of `.gitignore` plus `.planning/graphs/` and `graphify-out/`. Prove the
    detector returns zero derived files. If the safe overwrite guard rejects a
    smaller graph, compare node IDs/source files and use one checksummed
    `--force` only when zero real nodes disappear; then require a second
    no-force rebuild with no topology changes.
17. A restore drill that finishes comparisons but exits while deleting
    root-owned extracted files is a harness failure, not automatic backup
    failure. Preserve the historical exit, rerun checksum/root/user/bundle
    readbacks, clean scratch with `sudo rm -rf`, and require zero residue.
18. Treat `--resume` as recovery only. Preflight and final verify never skip,
    and a fresh-host seal requires one full apply without resume so every
    handler executes against the same source-manifest/input signature.
19. Seal the staged manifest after acquiring the setup lock. Require its
    out-of-band SHA-256, read it with `O_NOFOLLOW`, and verify every declared
    byte/mode/hash before any mutation. Builder output/archive/receipt paths
    must be non-overlapping and promotion rollback must finish before
    best-effort cleanup of transaction backups.
20. Never `source` Vault-generated env files. Parse only allowlisted keys as
    data and materialize least-privilege caches with mode `0600`. Use dedicated
    profiles for Landscape registration, Fleet DB, XRDP leaf, Router/MCP and
    Obsidian read-only deploy key.
21. Graphify parity includes runtime dependencies and behavior: pin
    `graphifyy==0.9.23` with `openai==2.24.0`, load `atius-router-gpt`, require
    both labeling/extraction stream patch markers, reject hollow responses and
    execute a real API smoke.
22. Generic-host resource governance must purge and verify absence of every
    SRV-1-only service/timer/path. Systemd state queries are fail-closed; reset
    only units whose `ActiveState=failed`, because valid installed units may be
    `not-loaded` before first activation.
23. Obsidian fresh-host provisioning is part of setup: hydrate a dedicated
    read-only deploy key, pin the GitHub ED25519 host key, clone atomically,
    configure pull-only sync, and require clean branch/origin/service readback.
24. Record the exact final manifest, apply/verify run IDs, backup and independent
    runtime verdict in a non-package evidence pack. Do not hardcode the current
    package manifest in this allowlisted skill: editing the skill necessarily
    changes that manifest. The SRV-4 reference evidence lives at
    `docs/operations/evidence/2026-09-06-srv4-final-runtime-v11/` and includes
    runtime review GO plus MCP tool counts `115/16/12`.

## Never do

- Copy private keys, Vault material, `.env`, agent state, PM2 dumps or caches.
- Reuse an ingress route table as a subnet egress table.
- Add a host to K3s, DRG, Vault or a production container role merely because
  another server has that role.
- Copy `auth.json`, `.env`, private keys, live session databases or memories
  from another agent runtime.
