# fleet-pki

Internal service PKI resource for Omni Fleet hosts.

The operational entrypoint is:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki plan --json
PYTHONPATH=cli python -m omni fleet trust-pki render-host --host horistic-srv --json
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host horistic-srv --json
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

## Trust Model

- Trust stores receive the ATIUS internal service CA chain.
- Peer host leaf certificates are not installed as trusted root CAs.
- Each host owns its private key under `/etc/omni-srv-admin/tls/<host-id>/`.
- CA material lives on `atius-srv-1` under `/var/lib/omni-srv-admin/pki/`.
- Raw private keys, passphrases and tokens must not be written to Git,
  `.planning`, Obsidian, GBrain, DB dry-run payloads or logs.

## Current Execution State

Phase 44-01 implements the CLI resource surface, SAN rendering, dry-run plans
and DbOmniFleet queue integration. Live CA/key/cert mutation remains blocked in
the local `agent-runner` until the Phase 44-02 scripts are installed and
validated.
