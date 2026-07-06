# FreeIPA DNS and Client Enrollment

**Phase:** 34 - FreeIPA DNS and Client Enrollment
**Status:** 34-01 disposable client gate passed and 34-02 completed with private WireGuard/CoreDNS publishing plus first real host enrollment on `atius-srv-3`.
**Updated:** 2026-07-06T05:20:00-03:00

## Current FreeIPA Baseline

| Item | Value |
|---|---|
| Server container | `freeipa-atius` on `atius-srv-3` |
| Disposable client container | `freeipa-client-test` on `atius-srv-3` |
| Server FQDN | `ipa.atius.internal` |
| Domain | `atius.internal` |
| Realm | `ATIUS.INTERNAL` |
| Current server IP inside Podman | `10.89.53.10` |
| Network | `freeipa-atius-net` |
| Public exposure | None |

No real host enrollment was attempted in 34-01. The managed hosts `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv` remain outside `ATIUS.INTERNAL`.

## 34-02 Result

The first production-ready private integration path is now live:

| Check | Result |
|---|---|
| CoreDNS forwards `atius.internal` to `10.1.1.3` | PASS |
| `ipa.atius.internal` resolves as `10.1.1.3` for WireGuard clients | PASS |
| Private FreeIPA gateway on `atius-srv-3` | PASS |
| Real host enrollment on `atius-srv-3` | PASS |
| `kinit admin` and `ipa ping` on enrolled host | PASS |
| `getent passwd admin`, `id admin`, `sudo -l -U admin` on enrolled host | PASS |
| `horistic-srv` enrollment | DEFERRED by operator; manual-only future gate |
| Reverse PTR for `10.1.1.3` and `10.1.1.7` | PASS, both return `atius-srv-3.atius.internal.` through CoreDNS on `atius-srv-2` |

Live private publish model:

- CoreDNS on `atius-srv-2` forwards only `atius.internal` to `10.1.1.3`
- CoreDNS on `atius-srv-2` serves the fleet reverse PTR override for
  `10.1.1.3` and `10.1.1.7`
- `atius-srv-3` privately forwards FreeIPA ports from `10.1.1.3` to container IP `10.89.53.10`
- no public DNS, Apache, or Cloudflare exposure was added

Operational artifacts:

- CoreDNS backup on `atius-srv-2`:
  `/home/ubuntu/GitHub/vpn-atius/coredns/backups-freeipa-34-02-20260626T102212Z/`
- SRV3 rollback bundle:
  `/root/freeipa-34-02-20260626T102212Z/`
- private gateway service on `atius-srv-3`:
  `/etc/systemd/system/atius-freeipa-wireguard-gateway.service`
- gateway rule script on `atius-srv-3`:
  `/usr/local/sbin/atius-freeipa-wireguard-gateway.sh`

## 34-01 Result

The first client enrollment proof used a disposable AlmaLinux 9 container:

| Check | Result |
|---|---|
| Container start | PASS |
| `freeipa-client` package install | PASS |
| DNS query `ipa.atius.internal @10.89.53.10` | PASS, returned `10.89.53.10` |
| `ipa-client-install` against `ATIUS.INTERNAL` | PASS |
| `kinit admin` plus `ipa ping` | PASS |
| Real host enrollment | NOT ATTEMPTED |

Remote root-only evidence log:

- `/root/freeipa-atius/client-test-20260625T204002Z.log` on `atius-srv-3`

The log must remain root-only because it records enrollment diagnostics. Do not copy it into the repo or vault.

## DNS Authority Model

Current safe model:

1. FreeIPA is authoritative for `atius.internal` inside its own DNS service.
2. FreeIPA currently resolves `ipa.atius.internal` to the Podman-private IP `10.89.53.10`.
3. CoreDNS/WireGuard fleet forwarding is enabled only for the `atius.internal` zone.
4. Production Linux clients do not consume `10.89.53.10` directly; they resolve and connect through `10.1.1.3`.
5. The current design uses a controlled SRV3 private gateway for required FreeIPA ports.

Required services for real client enrollment normally include DNS plus Kerberos, LDAP, HTTP, and related FreeIPA endpoints. Do not expose them on public Cloudflare or Apache vhosts.

## Production Gates Before Real Host Enrollment

Do not enroll additional real fleet hosts until all gates below are satisfied:

1. A reachable `ipa.atius.internal` address is defined for WireGuard clients.
2. CoreDNS forwarding for `atius.internal` is backed up and scoped.
3. Firewall/NAT rules on `atius-srv-3` are backed up and reversible.
4. At least one non-critical host enrollment command is prepared with rollback.
5. Sudo/group policy smoke is defined before enrollment.
6. RDP/SSH access is confirmed independent of FreeIPA credentials.

## DNS Rollback

If CoreDNS forwarding is added later, rollback must restore the previous CoreDNS configuration and restart only the CoreDNS workload or service that was changed.

Minimum rollback record:

```bash
# example placeholders for the later 34-02 change
sudo cp /path/to/coredns-backup/Corefile /path/to/live/Corefile
kubectl -n kube-system rollout restart deployment/coredns
kubectl -n kube-system rollout status deployment/coredns
```

If SRV3 firewall/NAT forwarding is added later, rollback must remove only the FreeIPA-specific rules and leave Landscape, LXD, K3s, Apache, and WireGuard rules intact.

## Client Enrollment Rollback

For a future real Linux client that has been enrolled with `ipa-client-install`, rollback must use:

```bash
sudo ipa-client-install --uninstall -U
sudo systemctl disable --now sssd oddjobd 2>/dev/null || true
sudo rm -f /etc/ipa/default.conf /etc/krb5.conf.ipa-client-install
sudo getent passwd admin || true
```

If DNS resolver changes are made on the client, restore the pre-enrollment resolver backup before restarting any network service.

## Next Step

Next controlled expansion:

- Do not enroll `horistic-srv` automatically. Keep it outside FreeIPA until the
  operator explicitly requests a manual enrollment run.
- If a future manual `horistic-srv` enrollment is requested, reuse the same DNS,
  rollback, SSH/RDP safety, and sudo smoke model from the `atius-srv-3` pilot.
