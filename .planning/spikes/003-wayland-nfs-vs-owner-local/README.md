---
spike: 003
name: wayland-nfs-vs-owner-local
type: standard
validates: "Persistent owner-local sessions make complete removal of the srv-3 NFS workspace tree beneficial and safe"
verdict: INVALIDATED
related: [48]
tags: [wayland, nfs, remote-development, resources]
---

# Spike 003: Wayland NFS Versus Owner-Local Development

## What This Validates

This spike tests whether persistent SSH/remote sessions make the Wayland NFS
workspace tree unnecessary, or whether the two mechanisms solve different
parts of the development workflow.

## Research

- OpenSSH multiplexing reuses transport for commands, shells, tunnels and
  SFTP. It does not provide a local filesystem namespace, locking or caching.
- NFSv4.2 is a stateful filesystem protocol with open/lock/cache/recovery
  semantics. The current ATIUS mounts are NFSv4.2 over OCI/DRG with `hard`,
  TCP, `nconnect=4`, 1 MiB read/write sizes and `actimeo=1`.
- A remote-development runtime can avoid network-filesystem metadata cost by
  running editor services, Git, search, watchers, LSP and commands beside the
  owner filesystem. It also introduces a per-host session lifecycle and
  resource/failure domain that a mounted path does not provide.

Primary references:

- https://www.rfc-editor.org/info/rfc8881/
- https://code.visualstudio.com/docs/remote/ssh
- `docs/operations/WAYLAND-FLEET-GITHUB-NFS.md`
- `modules/fork-sync/projects/wayland/UPSTREAM-SYNC-GUARDS.md`

## Investigation Trail

- At capture time, srv-1 was the only active NFS mount; srv-2, Horistic and the
  srv-3 bind were waiting behind automount. NFS RPC counters did not change
  during a five-second idle sample.
- The active mount owned four TCP connections. Shared user-space NFS processes
  used roughly 3.3 MiB RSS (`rpcbind`) plus 4.9 MiB RSS (`rpc.gssd`); this is
  not a per-mount cost.
- Cold `ssh true` measured about 0.57 s to srv-1 and 0.53 s to srv-2. The
  separately controlled master test measured 14-18 ms warm.
- Previously documented representative `git status --short -uno` results were
  about 0.57 s on the srv-1 NFS repo, 0.43 s on srv-2, 0.13 s on Horistic and
  0.04 s on the local srv-3 bind. These are different repositories, so they
  show order of magnitude, not a controlled same-repo comparison.
- The Wayland unit used about 735 MiB current memory with a 1.45 GiB observed
  peak. The existing remote ACP user unit used about 285 MiB current with a
  666 MiB peak. NFS idle cost is therefore not a credible reason by itself to
  add always-on agent runtimes to every host.
- The current Wayland seam injects owner-host SSH guidance into the agent
  prompt. It does not own a persistent SSH pool or a per-owner remote workspace
  lifecycle.

## Results

Verdict: INVALIDATED.

Persistent connections do not justify complete NFS removal. They solve command
startup, while NFS supplies the unified `/home/ubuntu/Servers` tree used by
project discovery, directory picking, cross-host reads/diffs and compatibility
with local Wayland workspace behavior.

The recommended target changes the role of NFS without deleting it:

```text
Wayland on srv-3
  |-- NFS automount: discovery, picker, light read/diff, fallback
  |-- owner-local remote session: active edit/search/Git/LSP/test/build/runtime
  `-- OpenSSH control master: terminal and one-off owner commands
```

Until the owner-local mode exists and passes parity, keep the current hybrid
contract: edit/read on the mounted path and execute on the owner. After parity,
make owner-local the preferred active-development path and keep NFS as an
automounted discovery/fallback plane.

NFS can be retired only per host and only after proving all of these gates:

- remote project browse, folder picker and Recent Chats ownership parity;
- edit/search/diff, Git, watcher and LSP behavior on the owner filesystem;
- explicit reconnect, stale-session detection, teardown and rollback;
- measured idle CPU/RSS and concurrency within the fleet resource budget;
- loss-of-owner/DRG isolation without a blocked Wayland UI;
- no UID mismatch or security requirement stronger than the current restricted
  `sec=sys` export contract.

The existing automounts should not be removed merely to save resources: their
observed idle cost is small and they naturally expire after 600 seconds.
