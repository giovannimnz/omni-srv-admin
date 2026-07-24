# Keycloak Admin Read-only Provisioning

**Status:** offline candidate only; live provisioning requires a fresh human
approval artifact.

## Exact target

| Item | Required value |
|---|---|
| Keycloak host/runtime | `atius-srv-1`, native systemd |
| Base URL | `http://127.0.0.1:8180` |
| Realm | `atius` |
| Client ID | `keycloak-admin-readonly` |
| Vault profile | `keycloak-admin-readonly` |
| Vault path | `kv/atius/keycloak/admin-readonly` |
| Vault fields | `KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_READONLY_CLIENT_ID`, `KEYCLOAK_READONLY_CLIENT_SECRET` |
| Effective roles | exactly `realm-management/query-clients`, `realm-management/view-clients` |

The client is confidential and service-account-only. Standard, direct-access,
and implicit flows are disabled. `publicClient` and `fullScopeAllowed` are
false; `serviceAccountsEnabled` is true. Redirect URIs, web origins, browser
flow, root URL, base URL, and admin URL are empty.

The two direct service-account roles are also the exact dedicated client-scope
intersection. The live gate rejects any extra role, any `manage*`, `create*`,
or `realm-admin` role, and any token `resource_access` client other than
`realm-management`.

## Offline candidate

The candidate command is read-only. It reads only file metadata for
`/etc/keycloak/recovery-admin.env`; it does not source or use the recovery
credential. Vault absence comes from the existing metadata-only Phase 10
preapproval evidence. The exporter and JSON-write helper are bound by
mode/owner/SHA-256 observations without copying their content into evidence.

Run under the 0.8-CPU cap:

```bash
systemd-run --user --scope -p CPUQuota=80% \
  --working-directory=/home/ubuntu/GitHub/omni-srv-admin -- \
  node scripts/provision-keycloak-admin-readonly.mjs candidate \
    --preapproval-evidence /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-preapproval-correction.json \
    --report /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json
```

A valid candidate says `finalVerdict:"GO"`,
`liveProvisioning:false`, `humanApprovalRequired:true`,
`recoveryAdminUsed:false`, and `secretsRecorded:false`. This GO means only that
the offline harness, preimage metadata, mocks, rollback transform, step ordering,
and approval boundary are ready.

## Human gate and approval

The runner cannot create or import the approval producer. After reviewing the
candidate and exact mutation/rollback scope, the human operator may create one
fresh artifact:

```bash
node scripts/create-keycloak-admin-readonly-approval.mjs \
  --candidate /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json \
  --output /run/keycloak-admin-readonly.approval.json \
  --operation-id "keycloak-readonly-$(date -u +%Y%m%dT%H%M%SZ)" \
  --approved-by "$USER" \
  --ttl-seconds 900
```

The producer uses `O_EXCL`, writes mode `0600`, and binds operation,
candidate/source/preimage/target-scope digests. The artifact has
`approvedForKeycloakProvision:true` and cannot be overwritten or reused after
the operation claim exists.

## Governed apply

Only after the checkpoint is approved:

```bash
sudo node scripts/provision-keycloak-admin-readonly.mjs apply \
  --candidate /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json \
  --approval /run/keycloak-admin-readonly.approval.json \
  --report /var/lib/atius-keycloak-admin-readonly/evidence/keycloak-admin-readonly-live.json \
  --rollback-reapply
```

Before authentication, apply rechecks recovery metadata, exporter and Vault
write-helper hashes, and the approval digests. It uses `set +x`, `umask 077`,
sources the root-only recovery env once, supplies its password through
`KC_CLI_PASSWORD`, and keeps the kcadm configuration under `/run` with a trap.
Authentication failure stops before mutation. An existing target client or
Vault metadata path stops for reconciliation; the runner never updates either
in place.

The secret flows only through connected process pipes:

1. Keycloak generates the client secret.
2. A pipe creates the exact four-field JSON.
3. SSH sends stdin to `/usr/local/sbin/atius-vault-kv-put-json` on
   `atius-srv-3`.

No secret is placed in argv, repo files, evidence, persistent temp files, or
terminal output. The exporter profile is inserted by a deterministic Python
transform after an `O_EXCL` backup and exact preimage hash check.

## Readback, rollback, and reapply

Apply proves exact client settings, direct/effective/scope roles, token role
intersection, Vault field-name set and version, exporter hash/marker, profile
hydration, and a metadata-only inventory of `sso.atius.com.br`. The inventory
asserts the fixed post-logout URI without outputting its access token or client
secret.

The same authenticated operation performs a rollback drill and reapply:

1. validate operation, client UUID, and client ID;
2. delete only the operation-created client;
3. soft-delete only the operation-created Vault version;
4. restore the exporter backup after exact hash checks;
5. prove client absence, soft-deleted data, restored exporter, and fail-closed
   hydration;
6. recreate and reread the exact target.

Vault metadata deletion is explicitly excluded. It requires a separate
destructive approval. Any failure trap rolls back partial operation-owned
mutations in the same order and removes `/run` scratch.

## Stop conditions

- approval missing, expired, reused, non-`0600`, or digest-mismatched;
- recovery env metadata/field-name drift;
- exporter or JSON-write-helper mode/owner/hash drift;
- existing client or existing Vault metadata;
- recovery authentication failure;
- extra/missing/elevated role or token role;
- secret-like evidence;
- rollback/readback/reapply mismatch.

Do not mark Phase 10 complete from this prerequisite. After live approval and
provisioning, rerun the existing Phase 10 Plan 10-04 candidate so its
authenticated Keycloak preflight can proceed.
