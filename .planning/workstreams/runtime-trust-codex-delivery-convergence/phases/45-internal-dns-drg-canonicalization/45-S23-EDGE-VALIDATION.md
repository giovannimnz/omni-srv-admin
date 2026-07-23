---
phase: 45
artifact: s23-edge-validation
created: 2026-07-10
status: partial
---

# 45 S23 Edge Validation

## Result

The `.9` renumbering is validated. The S23 is live on `10.100.100.9/32`,
reachable from the ATIUS control plane, and current repo/Obsidian evidence says
that a real Termux session already resolved the OCI-primary hostnames
successfully. What remains open is only the broader handset-side outbound TCP
proof to every OCI-private service target if Phase 45 wants a full end-to-end
edge matrix, not the correctness of the `.9` identity itself.

## Evidence Captured

From `GIOVANNI-W11-PC`:

- `ping -n 1 10.100.100.9` returned `0%` loss.
- TCP `10.100.100.9:8022` connected from the Windows side.
- `ssh -p 8022 ubuntu@10.100.100.9` reached the Termux SSH daemon from Windows,
  proving the service is up on the live `.9` address, even though that specific
  client path did not have a working credential.
- Other local keys and users tested (`ubuntu`, `root`, `muniz`) also failed
  authentication.
- `adb` is not installed on the Windows host, so ADB could not be used as a
  control channel.

From `atius-srv-1`:

```text
allowed ips: 10.100.100.9/32
latest handshake: 2 minutes, 11 seconds ago
transfer: 165.12 KiB received, 183.67 KiB sent
```

```text
PING 10.100.100.9: 1 packet transmitted, 1 received, 0% packet loss
TCP 10.100.100.9:8022 succeeded
```

Control-plane DRG services from `atius-srv-1` were reachable:

```text
10.11.1.11:53    OK
10.11.1.11:6432  OK
10.11.1.11:27124 OK
10.13.1.13:8202  OK
10.21.1.21:3115  OK
```

## Remaining Blocker

The Phase 45 closeout no longer has an IP-assignment blocker for S23. The only
remaining optional gate is the wider handset-side outbound TCP proof from
inside Termux to every OCI-private service target. Cross-repo evidence in
`oci-admin/docs/oci-primary-vpn-evidence.md` and local inventory notes already
show:

- live identity moved to `10.100.100.9/32`;
- DNS inside Termux resolved `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and
  `horistic-srv` to `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`;
- the remaining technical risk is route scope / client-profile reachability to
  the OCI-private service ports, not the `.9` renumbering itself.

Suggested Termux-side proof:

```bash
date
ip addr show 2>/dev/null || ifconfig
ping -c 2 10.100.100.1
ping -c 2 10.11.1.11
ping -c 2 10.12.1.12
ping -c 2 10.13.1.13
ping -c 2 10.21.1.21
nslookup atius-srv-1 10.11.1.11 || dig @10.11.1.11 atius-srv-1 A
nc -vz -w 3 10.11.1.11 53
nc -vz -w 3 10.11.1.11 6432
nc -vz -w 3 10.11.1.11 27124
nc -vz -w 3 10.13.1.13 8202
nc -vz -w 3 10.21.1.21 3115
```

Treat the `.9` address migration as validated. Treat the full device-side
outbound TCP matrix as a separate edge-proof gate if that depth is still
required for Phase 45 closeout.
