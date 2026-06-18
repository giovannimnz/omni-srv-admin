# Network migration: srv<N>-podman (CNI) → srv<N>-podman-v2 (netavark)

When the standard `srv<N>-podman` was originally created by the default
CNI backend (no `network_backend=netavark` set), recreating it in
netavark mode requires migrating all live containers off it. The
podman `default network X cannot be removed` error blocks the obvious
approach (rm + create).

## Why this is non-trivial

`podman network rm` refuses to remove the **default** network
(anything matching `containers.conf` `default_network`). To work around:

1. Change `default_network` to a name that doesn't exist
2. `rm` the old network (now allowed — it's not default anymore)
3. `create` the new network
4. Restore `default_network` to the new name

If you skip step 1, you'll get:
```
Error: default network srv1-podman cannot be removed
```

## Procedure (validated 2026-06-16 on SRV-1)

```bash
N=1  # server number
ssh ubuntu@10.1.1.$N '
set -e
# Step 1: change default to a name that will not exist
cp /home/ubuntu/.config/containers/containers.conf \
   /home/ubuntu/.config/containers/containers.conf.tmp-fix.bak
cat > /home/ubuntu/.config/containers/containers.conf <<EOF
[network]
default_network = "tmp-default-net"
default_subnet = "10.10.'$N'.0/24"
EOF

# Step 2: rm old network
/usr/bin/podman network rm srv'$N'-podman
sleep 1

# Step 3: create new network in netavark
/usr/bin/podman network create \
  --subnet 10.10.'$N'.0/24 \
  --gateway 10.10.'$N'.1 \
  srv'$N'-podman

# Step 4: restore canonical containers.conf
cat > /home/ubuntu/.config/containers/containers.conf <<EOF
[network]
default_network = "srv'$N'-podman"
default_subnet = "10.10.'$N'.0/24"
EOF
'
```

After this, `srv1-podman` will exist with `dns_enabled=true` in the
netavark backend. But the live containers (systemd-managed) still
reference the OLD network state in their unit files — they were
created with `--network srv1-podman` and that ID no longer exists.

## Migrating systemd-managed services

For each container unit (e.g. `container-cloudbeaver.service`),
swap the network reference:

```bash
# 1. Backup
cp /home/ubuntu/.config/systemd/user/container-<svc>.service \
   ~/backups/podman-fleet-standardize-$(date +%I%M%S)/

# 2. Sed swap
sed -i 's/srv<N>-podman\b/srv<N>-podman-v2/g' \
  /home/ubuntu/.config/systemd/user/container-<svc>.service
# \b avoids matching srv1-podman-new if it exists

# 3. Validate the diff
diff <(git show HEAD:path/to/unit) /home/ubuntu/.config/systemd/user/container-<svc>.service

# 4. Reload + restart
systemctl --user daemon-reload
systemctl --user restart container-<svc>.service
```

For services that share a **pod** (e.g. `atius-ai-router` with 4 child
containers), edit the `pod-<name>.service` unit's
`--network srv<N>-podman` line. The pod's infra container carries the
network; all 4 child containers follow automatically on next pod
restart.

```bash
# pod-atius-ai-router.service (excerpt)
ExecStartPre=/usr/bin/podman pod create \
  --network srv1-podman-v2 \  # <-- change this line
  ...

# Restart
systemctl --user restart pod-atius-ai-router.service
```

## Why "srv<N>-podman-v2" and not just "srv<N>-podman"

If the old CNI network still exists when systemd tries to start a
container with `--network srv1-podman` (the new name), podman
recreates the network with the **old CNI config** (because the name
collision confuses it). Keeping the `-v2` suffix makes the rollback
trivial: the old name still exists with the old config, and a
downtime-free revert is `sed -i 's/-v2//'` + `systemctl restart`.

Once you're confident the migration is permanent (1+ week in
production), you can:

```bash
ssh ubuntu@10.1.1.$N '
# Remove old CNI network (now unused)
/usr/bin/podman network rm srv'$N'-podman || true

# Migrate units back to bare name (removes -v2 suffix)
sed -i "s/srv'$N'-podman-v2/srv'$N'-podman/g" \
  /home/ubuntu/.config/systemd/user/container-*.service \
  /home/ubuntu/.config/systemd/user/pod-*.service

systemctl --user daemon-reload
# Restart all to pick up the rename
for u in cloudbeaver jenkins model-detailed postgres redis router-ai-atius; do
  systemctl --user restart container-$u.service
done
'
```

## Rollback (if migration breaks something)

```bash
# Restore unit files from backup
for u in cloudbeaver jenkins model-detailed postgres redis router-ai-atius; do
  cp ~/backups/podman-fleet-standardize-*/container-$u.service.orig \
     /home/ubuntu/.config/systemd/user/container-$u.service
done
systemctl --user daemon-reload
for u in cloudbeaver jenkins model-detailed postgres redis router-ai-atius; do
  systemctl --user restart container-$u.service
done
```

The old CNI `srv<N>-podman` is still on disk (just empty) so this
rollback is instant.
