# Tailscale Operations

## Source-of-truth

- **ACL live:** https://login.tailscale.com/admin/acls/file (tailnet `tail1233af.ts.net`)
- **ACL mirror:** `docs/operations/tailscale/acl.hujson` (this repo)
- **Pre-mutation backup:** `.backups/tailscale-pre-acl-2026-06-16/acl-current.json`
- **Vault doc:** `30-RECURSOS/31-NETWORKING/02-Tailscale/Tailscale-Setup-ATIUS.md`
- **Phase 13 closure:** `.planning/phases/13-k3s-ha-portainer-oci/13-ACL-CLOSURE-2026-06-16.md`

## Apply ACL (runbook)

```bash
# 1. Backup current ACL
mkdir -p ~/GitHub/omni-srv-admin/.backups/tailscale-acl-$(date +%Y%m%d)
curl -s -H "Authorization: Bearer $TAILSCALE_API_KEY" \
  https://api.tailscale.com/api/v2/tailnet/-/acl \
  > ~/GitHub/omni-srv-admin/.backups/tailscale-acl-$(date +%Y%m%d)/acl-pre.json

# 2. Apply new ACL
curl -s -X POST -H "Authorization: Bearer $TAILSCALE_API_KEY" \
  -H "Content-Type: application/hujson" \
  --data-binary @docs/operations/tailscale/acl.hujson \
  https://api.tailscale.com/api/v2/tailnet/-/acl

# 3. Verify
curl -s -H "Authorization: Bearer $TAILSCALE_API_KEY" \
  https://api.tailscale.com/api/v2/tailnet/-/acl
```

## Disable MagicDNS

```bash
curl -s -X POST -H "Authorization: Bearer $TAILSCALE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"magicDNSEnabled": false}' \
  https://api.tailscale.com/api/v2/tailnet/-/dns/preferences
```

## Disable DNS injection on each host

```bash
for srv in atius-srv-1 atius-srv-2 atius-srv-3; do
  ssh $srv "tailscale set --accept-dns=false"
done
```

## Validate

```bash
# SSH 22 over Tailscale
for srv in atius-srv-1 atius-srv-2 atius-srv-3; do
  ssh $srv "tailscale status; tailscale ping atius-srv-1; tailscale ping atius-srv-2; tailscale ping atius-srv-3"
done

# Port 22 from each to each (should succeed)
for srv in atius-srv-1 atius-srv-2 atius-srv-3; do
  ssh $srv "nc -zv 100.76.56.62 22; nc -zv 100.93.43.113 22; nc -zv 100.72.102.57 22"
done

# Port 80 deny test (SRV→SRV)
ssh atius-srv-1 "nc -zv 100.93.43.113 80"   # should timeout
```

## Architecture decision

**OCI/DRG private interfaces = K3s transport. Tailscale = management plane (100.x).**
Tailscale is never K3s transport. If the DRG path fails, Tailscale is the
recovery path for SSH administration; `wg100` remains the separate reserve edge
plane and must not become the cluster identity.
