# Internal Service PKI

Authoritative CLI resource:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki plan --json
PYTHONPATH=cli python -m omni fleet trust-pki render-host --host <host-id> --json
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --json
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --json
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host <host-id> --reason ip-change --json
```

## Add A Server

1. Register the server in `inventory/hosts/<host-id>.yaml`.
2. Sync it to DbOmniFleet when DB-backed execution is required:

```bash
PYTHONPATH=cli python -m omni fleet registry sync --host <host-id> --json
```

3. Render the PKI plan:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --source auto --json
```

4. Queue the onboarding sequence in DbOmniFleet:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --source db --db --json
```

5. Approved execution is explicit:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host <host-id> --source db --db --execute --approve --json
```

## IP Or SAN Change

When a host IP, alias or explicit SAN changes:

1. Update `inventory/hosts/<host-id>.yaml`.
2. Sync the host to DbOmniFleet:

```bash
PYTHONPATH=cli python -m omni fleet registry sync --host <host-id> --json
```

3. Reconcile desired SANs against the current certificate. For offline checks,
pass the observed SANs or a local certificate:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --source db --observed-san-json '{"dns":["example"],"ip":["10.1.1.9"]}' --json
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --cert-file /path/to/server.crt.pem --json
```

For remote read-only inspection through the fleet agent:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host <host-id> --source db --db --approve --json
```

4. If drift exists, queue leaf rotation:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host <host-id> --source db --db --reason ip-change --json
```

5. Approved execution stays explicit:

```bash
PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host <host-id> --source db --db --execute --approve --reason ip-change --json
```

If the current certificate cannot be inspected yet, add `--force` to queue a
rotation from the current inventory/DbOmniFleet SANs.

## Execution Model

`onboard-host` creates the per-host sequence:

- `omni.trust-pki.preflight` runs on the target host.
- `omni.trust-pki.ensure-key-csr` runs on the target host.
- `omni.trust-pki.issue-host` runs on `atius-srv-1`.
- `omni.trust-pki.install-ca` runs on the target host.
- `omni.trust-pki.install-leaf` runs on the target host.
- `omni.trust-pki.reconcile` runs read-only on the target host.
- `omni.trust-pki.verify` runs on the target host.

The command templates are registered in
`modules/fleet-control-plane/migrations/0008_internal_service_pki_commands.sql`
and are also available as local CLI fallback allowlist entries.

## Trust Model

- All hosts trust the internal service CA chain.
- Hosts do not install peer leaf certificates as trusted root CAs.
- Each host owns its private key under `/etc/omni-srv-admin/tls/<host-id>/`.
- CA material is owned by `atius-srv-1` under `/var/lib/omni-srv-admin/pki/`.
- Raw keys, passphrases, tokens and private cert material stay out of Git,
  `.planning`, Obsidian, GBrain, DB dry-run payloads and logs.

## Current Gate

Phase 44-01 implements rendering, dry-run, DbOmniFleet queueing, command
allowlist and tests. Live CA/key/cert mutation is still blocked by
`agent-runner` until the Phase 44-02 scripts are implemented and validated.
