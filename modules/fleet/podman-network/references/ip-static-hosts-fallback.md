# IP estático + extra_hosts fallback (for multi-container stacks)

When a stack has 3+ containers that need stable DNS resolution
between them, and the aardvark-dns rootless bug is biting (self-lookup
NXDOMAIN or external resolution TIMEOUT), the workaround is:

1. Recreate the network with explicit `--subnet` and a known gateway
2. Assign each container a **static IP** via `networks.<name>.ipv4_address`
3. Inject cross-service hostnames via `extra_hosts` mapping name → IP

This pattern was validated on the **plane-app v1.3.1 cutover** (SRV-1,
2026-06-16) and is now the standard for any multi-container stack on
the fleet.

## Why not just use aardvark

Three reasons:

1. **Self-lookup NXDOMAIN** in podman 4.9.3 rootless — even when
   `dns_enabled=true` is set, some setups return NXDOMAIN for queries
   within the same network namespace
2. **External resolution TIMEOUT** — aardvark has no upstream
   forwarder unless `--dns` was set at network creation
3. **Container IP churn** — DHCP-assigned IPs can shift across
   podman-compose restarts; static IPs give reproducible behavior
   for cross-references in `.env` and config files

The trade-off: you must maintain an IP allocation table (e.g.
`10.89.1.0/24`, IPs `.2` through `.30`) and update `extra_hosts` in
each service's compose when adding new services.

## Procedure (validated for plane-app)

### Step 1: pick a subnet

Use a `10.89.X.0/24` subnet to match the `atius` convention (SRV-1's
`atius` is `10.89.1.0/24`). Pick X to avoid collision with the
default `10.89.0.0/24` that podman auto-creates.

```bash
/usr/bin/podman network create \
  --subnet 10.89.1.0/24 \
  --gateway 10.89.1.1 \
  atius
```

(For new stacks, pick `10.89.<N>.0/24` where N ≠ existing networks.)

### Step 2: allocate IPs

Plan the IP table before writing the compose. For 13 services:

| Service       | IP           | Service       | IP           |
|---------------|--------------|---------------|--------------|
| plane-db      | 10.89.1.2    | api           | 10.89.1.20   |
| plane-redis   | 10.89.1.3    | worker        | 10.89.1.21   |
| plane-mq      | 10.89.1.4    | beat-worker   | 10.89.1.22   |
| plane-minio   | 10.89.1.5    | migrator      | 10.89.1.23   |
| web           | 10.89.1.10   | proxy         | 10.89.1.30   |
| space         | 10.89.1.11   |               |              |
| admin         | 10.89.1.12   |               |              |
| live          | 10.89.1.13   |               |              |

Reserve `.2-.5` for stateful infra (db, redis, mq, minio).
Reserve `.10-.19` for stateless frontends (web, space, admin, live).
Reserve `.20-.29` for backend services (api, worker, beat, migrator).
Reserve `.30-.39` for proxies and ingress.

### Step 3: write the compose

For each service, add:

```yaml
services:
  web:
    image: ...
    networks:
      atius:
        ipv4_address: 10.89.1.10
    extra_hosts:
      - "api:10.89.1.20"
      - "plane-db:10.89.1.2"
      # ... only the services this one contacts
```

For services that depend on each other, you need entries for both
directions. The minimum set for plane-app:

- web: api, worker, plane-db, plane-redis, plane-mq, plane-minio
- api: plane-db, plane-redis, plane-mq, plane-minio
- worker: api, plane-db, plane-redis, plane-mq, plane-minio
- migrator: plane-db, plane-redis
- proxy: web, space, admin, live, api
- backend services don't need extra_hosts for the proxy

### Step 4: validate

```bash
cd /path/to/project
podman-compose --env-file .env up -d
sleep 5

# Check static IPs are honored
podman inspect plane-app_web_1 \
  --format '{{.NetworkSettings.Networks.atius.IPAddress}}'
# should print 10.89.1.10

# Check name resolution from proxy container
podman exec plane-app_proxy_1 \
  wget -qO- http://web/ 2>&1 | head -3
# should return HTML (not "bad address")

# Check internal DB connection from API
podman exec plane-app_api_1 sh -c '
  psql -h plane-db -U plane -d plane -c "SELECT 1"
' 2>&1
# should print "(1 row)"
```

## Pitfalls

### 1. DHCP conflict after restart

If you specify `ipv4_address` but the address is also in the
IPAM lease range, podman may assign it to another container by
DHCP. The fix: the IPAM lease range is the full subnet by default,
so always pass `--ipam-driver host-local` and let the static IP
override. Verify with:

```bash
podman network inspect atius | python3 -c "
import sys, json
d = json.load(sys.stdin)[0]
subnets = d.get('subnets', [])
for s in subnets:
    if 'lease_range' in s:
        print('LEASE:', s['lease_range'])
    else:
        print('NO_LEASE_RANGE_DEFINED')
"
```

If you see `lease_range` overlapping with your static IPs, set
`ipam_options` to a non-overlapping range. Default is fine for most
cases (the static IPs win).

### 2. `extra_hosts` doesn't survive `podman exec --network host`

If you `podman exec --network host ...` into a container, the
`extra_hosts` from compose are NOT applied (host netns has no
container /etc/hosts). The container process can still resolve
itself via the static IP, but the extra-host names won't be there.

For debugging, prefer `podman exec -it <container> sh` (default
network, not host).

### 3. `extra_hosts` syntax for compose-v1 vs compose-v2

podman-compose 1.6.0 accepts both:

```yaml
extra_hosts:
  - "api:10.89.1.20"  # array of strings (v1 syntax)
  # OR
  api: 10.89.1.20      # map (v2 syntax, supported)
```

The v1 array syntax is more portable.

### 4. Adding a new service after the IP table is set

Pick the next free IP in your allocation scheme (e.g. `.31` for the
next proxy), add `ipv4_address` to the service definition, and add
`extra_hosts` entries in every other service that calls it.

## When to abandon this pattern

If you can guarantee that:
- `systemd-resolved` is installed and active on the host
- The network was created with `--dns=1.1.1.1,8.8.8.8` (or
  similar explicit forwarders)
- Self-lookup works in a test container (use the smoke test in
  `SKILL.md`)

…then aardvark is reliable and you don't need IPs estáticos. For
production stacks with 3+ services, I'd still recommend static IPs
even when aardvark works, because the IP table is also a
documentation artifact (you can see the service graph from the
allocation).

## Origin

This pattern was developed for the plane-app v1.2.1 → v1.3.1 cutover
on SRV-1 (2026-06-16, see `vault/60-LOGS/2026-06-16-plane-app-podman-v131-cutover.md`).
The aardvark rootless bug was confirmed in the cutover, and the
13-service IP table + extra_hosts matrix was constructed to bypass it.
The pattern was then generalized for the 6 SRV-1 systemd services
that migrated to `srv1-podman-v2` in the same session.
