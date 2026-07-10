# fleet-pki

Internal service PKI resource for Omni Fleet hosts.

The operational entrypoint is:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki plan --json
PYTHONPATH=cli python -m omni fleet trust-pki render-host --host horistic-srv --json
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host horistic-srv --json
PYTHONPATH=cli python -m omni fleet trust-pki install-trust --host giovanni-w11-pc --json
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host horistic-srv --json
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host horistic-srv --reason ip-change --json
```

`onboard-host` is the high-level flow for a newly registered server. It resolves
the host from inventory or DbOmniFleet, renders SANs and paths, then optionally
queues allowlisted stages into `TbUpdatePlans`:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --db --json
```

Approved execution still requires the explicit gate:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --db --execute --approve --json
```

When a host IP/SAN changes, `reconcile-host` compares desired SANs from
inventory/DbOmniFleet against observed certificate SANs. `rotate-host` queues the
leaf reissue sequence and records the reason, usually `ip-change`.

As of 2026-07-06 the primary VPN plane for certificate SAN rendering is
The canonical private service plane is now the OCI/DRG map (`10.11.1.11`,
`10.12.1.12`, `10.13.1.13`, `10.21.1.21`). `wg100` / `10.100.100.0/24` stays as
reserve fallback only. The retired `10.1.1.x` range belongs only in historical
notes; do not carry it in active inventory or live service endpoints.

`GIOVANNI-W11-PC` participates as a Windows `trust-client` for operator-side
HTTPS verification. It is included in the default `plan` when
`pki.service_tls.enabled=true`, but receives only CA/trust and verification
stages through `omni.trust-pki.windows.*`; it does not get a Linux-style
service private key/CSR/leaf sequence.

## Trust Model

- Trust stores receive the ATIUS internal service CA chain.
- Peer host leaf certificates are not installed as trusted root CAs.
- Each host owns its private key under `/etc/omni-srv-admin/tls/<host-id>/`.
- Windows trust clients receive the root CA in `Cert:\CurrentUser\Root`, the
  issuing CA in `Cert:\CurrentUser\CA`, and may keep peer public leaf
  certificates only as audit/pinning evidence.
- CA material lives on `atius-srv-1` under `/var/lib/omni-srv-admin/pki/`.
- Raw private keys, passphrases and tokens must not be written to Git,
  `.planning`, Obsidian, GBrain, DB dry-run payloads or logs.

## Current Execution State

Phase 44-01 through 44-03 are implemented for the initial fleet. SRV-1 owns the
root/issuing CA under `/var/lib/omni-srv-admin/pki/`; the four Linux service
hosts have local keys, CSRs, leaf certs, CA trust and peer public cert bundles
under `/etc/omni-srv-admin/tls/`; `GIOVANNI-W11-PC` has the root CA in
`Cert:\CurrentUser\Root`, the issuing CA in `Cert:\CurrentUser\CA`, and peer
public leafs under `C:\Users\muniz\.local\share\omni-service-pki\peers`.

Repeat the live matrix with:

```bash
modules/fleet-pki/scripts/verify-fleet-pki-matrix.sh --json
```

The 2026-07-06 run passed 32/32 Linux HTTPS checks: every source host verified
every target host by both `10.100.100.x` IP SAN and DNS SAN. Windows also
verified HTTPS to `10.100.100.1` through `.4` using the local CA chain.
