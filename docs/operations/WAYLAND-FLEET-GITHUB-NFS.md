# Wayland Fleet GitHub NFS

## Final topology

Wayland on `atius-srv-3` sees every Linux host under one stable tree:

| Host | Source | Wayland path | Type |
|---|---|---|---|
| `atius-srv-1` | `10.11.1.11:/home/ubuntu/GitHub` | `/home/ubuntu/Servers/atius-srv-1/GitHub` | NFSv4.2 |
| `atius-srv-2` | `10.12.1.12:/home/ubuntu/GitHub` | `/home/ubuntu/Servers/atius-srv-2/GitHub` | NFSv4.2 |
| `atius-srv-3` | `/home/ubuntu/GitHub` | `/home/ubuntu/Servers/atius-srv-3/GitHub` | bind |
| `horistic-srv` | `10.21.1.21:/home/horistic/GitHub` | `/home/ubuntu/Servers/horistic-srv/GitHub` | NFSv4.2 |

OCI/DRG is the only primary server-to-server plane. `wg100` is not used by these mounts.

## Runtime contract

Wayland treats these mounted GitHub trees as hybrid workspaces:

- edit/read/search/diff happen on the mounted path under `/home/ubuntu/Servers`
- validation defaults to the owner host via its canonical SSH alias
- owner-host path translation is:
  `atius-srv-1`/`atius-srv-2` -> `/home/ubuntu/GitHub/...`
  `horistic-srv` -> `/home/horistic/GitHub/...`
- reserve `10.100.100.0/24` addresses are not the primary execution path when
  the OCI/DRG alias is available

## Security contract

Each remote export is restricted to `10.13.1.13` and uses:

```text
rw,sync,no_subtree_check,root_squash,secure,sec=sys
```

The operational users on all four hosts are `UID/GID 1001:1001`. Do not enable
`no_root_squash`, wildcard exports, or a public source CIDR. NFSv3 and UDP are
disabled in `/etc/nfs.conf.d/atius-wayland.conf` on the three exporters.

## Server files

Exports live in `/etc/exports.d/atius-wayland-github.exports`:

```text
# srv-1 and srv-2
/home/ubuntu/GitHub 10.13.1.13(rw,sync,no_subtree_check,root_squash,secure,sec=sys)

# horistic-srv
/home/horistic/GitHub 10.13.1.13(rw,sync,no_subtree_check,root_squash,secure,sec=sys)
```

Validate with `sudo exportfs -v`, `systemctl is-active nfs-server`, and
`ss -H -lnt 'sport = :2049'`.

## Client files

`atius-srv-3` uses paired `.mount` and `.automount` units named from each path
with `systemd-escape --path`. Remote mounts use:

```text
rw,hard,vers=4.2,proto=tcp,noatime,nconnect=4,rsize=1048576,wsize=1048576,timeo=600,retrans=2,actimeo=1
```

Automount idle timeout is 600 seconds. The units intentionally do not declare
`After=network-online.target`: automounts below `/home` otherwise create a
`local-fs.target` ordering cycle. NFS mount units are classified as remote by
their filesystem type.

## Validation evidence

Validated on 2026-07-12:

- TCP `2049` passed from `srv-3` to all three exporters over DRG.
- All three NFS mounts negotiated NFSv4.2, 1 MiB read/write sizes, and four connections.
- Create, content read, rename, source-host visibility, and delete passed.
- Mounted ownership is `1001:1001`; no root-owned smoke artifacts remained.
- Representative `git status --short -uno` times were about 0.57s (`srv-1` Router),
  0.43s (`srv-2` ATS), 0.13s (Horistic), and 0.04s for the local `srv-3` bind.

## Rollback

1. Disable the four `.automount` units on `atius-srv-3`.
2. Stop their paired `.mount` units and confirm `findmnt -t nfs4` is empty for this tree.
3. Remove `/etc/systemd/system/home-ubuntu-Servers-*.mount` and `.automount`, then daemon-reload.
4. Remove `/etc/exports.d/atius-wayland-github.exports` from each exporter and run `exportfs -rav`.
5. Disable `nfs-server` only if no other exports were added later.
6. Restore from `/var/backups/atius-wayland-nfs-20260712T025438Z` when required.

SSHFS remains a fallback for hosts whose Unix identity cannot be aligned. It is
not the primary path for this DRG-connected fleet.
