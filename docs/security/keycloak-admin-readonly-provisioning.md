# Keycloak Admin Read-only Provisioning

**Status:** offline harness candidate only. The current candidate is expected to
say `approvalReady:false` and `livePreflightStatus:"BLOCKED_AUTH"` until a human
authorizes one-shot use of the recovery administrator for an authenticated,
read-only preflight. It is not a live provisioning approval.

## Exact target and source contract

| Item | Required value |
|---|---|
| Keycloak host/runtime | `atius-srv-1`, native systemd, Keycloak `26.6.3` |
| Base URL / realm | `http://127.0.0.1:8180`, `atius` |
| Client ID | `keycloak-admin-readonly` |
| Vault profile/path | `keycloak-admin-readonly`, `kv/atius/keycloak/admin-readonly` |
| Vault fields | `KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_READONLY_CLIENT_ID`, `KEYCLOAK_READONLY_CLIENT_SECRET` |
| Effective roles | exactly `realm-management/query-clients`, `realm-management/view-clients` |
| Approval operation | exactly `provision-and-drill` |

The emitted Keycloak representation contains only the required client fields.
It does not emit `name`, `description`, root/base/admin URLs, device grant
attributes, or CIBA attributes. Readback requires the exact emitted projection,
empty redirect/web-origin arrays, and an empty `attributes` map. This follows
the Keycloak 26.x `ClientRepresentation` schema and Admin REST client endpoints;
the precomputed internal ID remains part of the exact comparison and only the
frozen server-owned `access` authorization-metadata object is stripped.
Unexpected fields such as `secret`, `rootUrl`, base/admin URLs, flow bindings,
attributes, redirect URIs, or web origins fail closed:

- <https://www.keycloak.org/docs-api/latest/rest-api/index.html>
- <https://github.com/keycloak/keycloak/blob/main/core/src/main/java/org/keycloak/representations/idm/ClientRepresentation.java>

The approval producer is itself part of `SOURCE_FILES`. Its path and SHA-256
are bound into `sourceDigest`, the candidate, and the approval. Candidate
validation, approval production, and apply all recompute `sourceDigest`,
`preimageDigest`, `targetScopeDigest`, and `candidateDigest` from canonical
inputs; copied digest strings are never accepted on their own.

## Direct metadata and chronology

The topology fixture must be regenerated from direct current metadata:

- Keycloak version and recovery env metadata on `atius-srv-1`;
- exact recovery env field names, without sourcing or recording values;
- exporter and Vault helper mode/owner/size/SHA-256 on `atius-srv-3`;
- an authenticated `vault kv metadata get` for the exact target path.

A broad Vault leaf search is not absence evidence. The offline topology does
not authenticate to Keycloak and therefore records the target client as
`UNKNOWN_AUTH`; it must not claim client absence. Candidate `generatedAt` must
be at or after every `observedAt`, and no timestamp may exceed the current
clock by more than the documented 30-second skew. Every direct metadata
observation, including the topology, exact Vault absence, and authenticated
preflight, expires after 120 seconds. Approval production revalidates those
timestamps and re-reads the exact recovery-file metadata; apply repeats that
check and then performs a new authenticated target preflight before mutation.

## Offline candidate

Remove only the previous exact candidate before regenerating it; report
publication is `O_EXCL|O_NOFOLLOW`, mode `0600`, and cannot overwrite evidence.
Run the complete suite and candidate under the 0.8-CPU scope:

```bash
systemd-run --user --scope -p CPUQuota=80% \
  --working-directory=/home/ubuntu/GitHub/omni-srv-admin -- \
  node scripts/provision-keycloak-admin-readonly.mjs candidate \
    --report /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json
```

The candidate has exactly eight PASS gates. Its `GO` means the offline harness,
canonical digests, path scope, mocks, secret scan, rollback ownership, and
approval boundary are reproducible. While it says `approvalReady:false`, the
approval producer must reject it.

`KARO_TEST_*` variables are rejected by candidate, preflight, apply, and the
approval producer. Sandbox transactions are reachable only through
`scripts/tests/keycloak-admin-readonly-harness.mjs`, which creates a private
ephemeral root internally and whose process identity/ancestry is verified by
the live adapter and Python helpers. Caller-selected test roots are not an
alternate artifact scope.

## Human authorization and read-only preflight

After the human authorizes one-shot recovery-admin use, run this read-only
preflight before creating approval:

```bash
sudo node scripts/provision-keycloak-admin-readonly.mjs preflight \
  --candidate /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json \
  --report /run/keycloak-admin-readonly.preflight.json
```

It parses the two recovery records without `source`/shell evaluation, uses
`KC_CLI_PASSWORD` in process memory, authenticates once, and performs no
mutation. It must freshly prove:

1. exact Keycloak client absence through authenticated Admin REST;
2. exact Vault metadata absence;
3. exporter preimage hash/mode/owner.

Then regenerate the exact candidate with
`--live-preflight /run/keycloak-admin-readonly.preflight.json`. The preflight is
valid for at most 120 seconds. The resulting candidate may say
`approvalReady:true` / `livePreflightStatus:"READY"`.

## Approval

Only the separate producer may write the fixed approval:

```bash
sudo node scripts/create-keycloak-admin-readonly-approval.mjs \
  --candidate /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json \
  --output /run/keycloak-admin-readonly.approval.json \
  --operation-id "keycloak-readonly-$(date -u +%Y%m%dT%H%M%SZ)" \
  --approved-by "$USER" \
  --ttl-seconds 900
```

The producer uses `O_EXCL|O_NOFOLLOW`, mode `0600`, and only operation
`provision-and-drill`. `rollback-only` and every other operation are rejected.
Validation requires `issuedAt <= now + 30s`, `issuedAt` no older than 900
seconds, `expiresAt > now`, and TTL at most 900 seconds.

## Governed apply

The only allowed live report is
`/var/lib/atius-keycloak-admin-readonly/evidence/keycloak-admin-readonly-live.json`:

```bash
sudo node scripts/provision-keycloak-admin-readonly.mjs apply \
  --candidate /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json \
  --approval /run/keycloak-admin-readonly.approval.json \
  --report /var/lib/atius-keycloak-admin-readonly/evidence/keycloak-admin-readonly-live.json \
  --rollback-reapply
```

Apply repeats the authenticated client/Vault/exporter preflight immediately
before mutation. The operation claim, append-only journal, scratch path,
approval, report, retained backup prefix, client/Vault/exporter targets, and
mutation steps are all in `targetScopeDigest`. Arbitrary paths and existing
report/approval/state/backup artifacts fail closed.

The write-ahead journal arms ownership before every side effect:

- Keycloak uses a precomputed explicit UUID, so response loss does not lose
  ownership;
- Vault uses CAS=0/version 1 for first apply and CAS=1/version 2 for reapply;
- exporter preview computes the exact installed SHA before replacement and
  binds it to an `O_EXCL` retained backup.

Response/readback loss therefore leaves enough durable identifiers to
reconcile and roll back. Rollback order is always reverse:
`exporter -> Vault exact version -> Keycloak exact UUID`. A resource is marked
restored only after exact readback; ambiguous recovery remains
`rollback-incomplete-manual-recovery-required`.

## Evidence secret scan and stop conditions

The live scan recursively reads the complete private scratch tree, the complete
append-only operation state/journal tree, and the retained exporter backup.
Besides key-name and assignment heuristics, the live process supplies the
actual recovery password, generated client secrets, and available access or
refresh tokens to the scanner only through a pipe. The scanner rejects exact
material, base64/base64url/URL/hex encodings, and SHA-256 fingerprints even
under innocuous keys. The source material list is never written and diagnostics
never include the material.

Stop before mutation on any:

- offline/BLOCKED_AUTH or stale authenticated preflight;
- future/stale/expired/wrong-operation approval;
- canonical digest, producer hash, topology, target path, or step drift;
- existing/symlinked/out-of-scope artifact;
- existing Keycloak client or exact Vault metadata;
- exporter/helper metadata or hash drift;
- extra client attribute, flow, URI, role, scope, or token role;
- incomplete rollback ownership/readback;
- secret-like emitted evidence.

Do not create `10-04-SUMMARY.md` or mark Phase 10 complete from this
prerequisite.
