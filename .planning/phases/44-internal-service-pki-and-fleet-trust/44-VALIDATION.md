# Phase 44 Validation Contract

## Preflight Validation Before Any Mutation

For every active host in scope:

```bash
ssh <target> 'hostname; id -un; sudo -n true; openssl version; command -v update-ca-certificates; timedatectl show -p NTPSynchronized --value'
```

Pass criteria:

- SSH succeeds through the VPN.
- `sudo -n true` succeeds.
- OpenSSL exists and is version 3.x or compatible.
- `update-ca-certificates` exists.
- NTP is synchronized.
- Existing managed PKI paths are either absent or backed up before overwrite.

## Build-Time Validation

Local tests:

```bash
PYTHONPATH=cli pytest -q cli/omni/tests/test_fleet_pki.py modules/fleet-control-plane/tests/test_m004_contract.py
PYTHONPATH=cli python -m omni fleet trust-pki plan --json
PYTHONPATH=cli python -m omni fleet trust-pki preflight --json
git diff --check
```

Pass criteria:

- Inventory SAN rendering is deterministic.
- Commands are dry-run by default.
- Mutating commands require explicit `--execute` or approved local-agent plan.
- No secret material is printed in stdout/stderr/audit JSON.
- Allowlisted commands reject shell strings.

## Certificate Validation

On `atius-srv-1` after CA initialization:

```bash
sudo openssl x509 -in /var/lib/omni-srv-admin/pki/certs/atius-vpn-service-root-ca.crt -noout -subject -issuer -dates -fingerprint -sha256 -ext basicConstraints -ext keyUsage
sudo openssl x509 -in /var/lib/omni-srv-admin/pki/certs/atius-vpn-service-issuing-ca.crt -noout -subject -issuer -dates -fingerprint -sha256 -ext basicConstraints -ext keyUsage
```

For every host leaf:

```bash
sudo openssl x509 -in /etc/omni-srv-admin/tls/<host>/server.crt.pem -noout -subject -issuer -dates -fingerprint -sha256 -ext subjectAltName -ext extendedKeyUsage
sudo openssl verify -CAfile /etc/omni-srv-admin/tls/ca-chain.crt.pem /etc/omni-srv-admin/tls/<host>/server.crt.pem
sudo openssl x509 -checkend 2592000 -noout -in /etc/omni-srv-admin/tls/<host>/server.crt.pem
```

Pass criteria:

- CA cert has `CA:TRUE`.
- Leaf cert has `CA:FALSE`.
- Leaf cert has `serverAuth` and `clientAuth`.
- Leaf SAN includes VPN IP plus declared DNS aliases.
- Leaf validates against the installed CA chain.
- Leaf does not expire within 30 days.

## Trust Store Validation

On every host:

```bash
sudo update-ca-certificates
test -e /etc/ssl/certs/atius-vpn-service-root-ca.pem
openssl verify -CApath /etc/ssl/certs /etc/omni-srv-admin/tls/peers/<peer>.crt.pem
```

Pass criteria:

- CA update reports the expected ATIUS cert.
- Root CA appears in `/etc/ssl/certs`.
- Every peer public leaf validates using system trust.

## Cross-Host HTTPS Matrix

For each target host:

1. Start temporary TLS server on a verified-free high port bound to its VPN IP.
2. From every other host, connect by VPN IP and by DNS alias.
3. Stop the temporary server.

Representative commands:

```bash
sudo openssl s_server -quiet -accept <vpn-ip>:<port> -cert <chain.crt.pem> -key <server.key.pem> -www &
openssl s_client -connect <vpn-ip>:<port> -verify_return_error -CApath /etc/ssl/certs </dev/null
curl --fail --cacert /usr/local/share/ca-certificates/atius-vpn-service-root-ca.crt https://<vpn-ip>:<port>/
curl --fail --resolve <dns-alias>:<port>:<vpn-ip> https://<dns-alias>:<port>/
```

Required matrix:

| Source | Target `atius-srv-1` | Target `atius-srv-2` | Target `atius-srv-3` | Target `horistic-srv` |
|---|---|---|---|---|
| `atius-srv-1` | local verify | HTTPS verify | HTTPS verify | HTTPS verify |
| `atius-srv-2` | HTTPS verify | local verify | HTTPS verify | HTTPS verify |
| `atius-srv-3` | HTTPS verify | HTTPS verify | local verify | HTTPS verify |
| `horistic-srv` | HTTPS verify | HTTPS verify | HTTPS verify | local verify |

Pass criteria:

- 12 remote pair checks pass.
- 4 local checks pass.
- Hostname/IP verification passes, not just TCP connect.
- Temporary listeners are cleaned up.
- Validation JSON records fingerprints and statuses, not private keys.

## Rollback Validation

For every host:

```bash
sudo test -d /root/.backups/omni-fleet-pki-<timestamp>
sudo find /etc/omni-srv-admin/tls -maxdepth 3 -type f -ls
sudo find /usr/local/share/ca-certificates -maxdepth 1 -name 'atius-vpn-service*.crt' -ls
```

Rollback must be able to:

- restore previous TLS directory;
- remove ATIUS service CA from trust store;
- run `update-ca-certificates`;
- prove peer validation fails after removal when using only system trust.
