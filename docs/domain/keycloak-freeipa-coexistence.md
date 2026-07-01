# Keycloak FreeIPA Coexistence

**Phase:** 36  
**Updated:** 2026-06-26

## Final state

| Item | Value |
|---|---|
| Host | `atius-srv-1` |
| Keycloak version | `26.6.3` |
| Java runtime | OpenJDK `21` |
| Private listener | `127.0.0.1:8180` |
| Public smoke hostname | `auth.atius.com.br` via Apache reverse proxy |
| Realm used for smoke | `atius` |
| LDAP source | FreeIPA on `ldap://10.1.1.3:389` |
| LDAP bind DN | root-only in `/etc/keycloak/freeipa-bind.env` |
| Temporary admin recovery user | `tmpadm36` in `master` realm |

## Federation choices

The first working federation path is intentionally conservative:

- `editMode = READ_ONLY`
- `importEnabled = true`
- LDAP bind uses a private FreeIPA-backed credential
- UUID attribute uses `ipaUniqueID`
- user source is `cn=users,cn=accounts,dc=atius,dc=internal`

This phase proved user import and OIDC auth flow. It did not attempt user
write-back into FreeIPA.

## OIDC smoke

Smoke client:

- client id: `phase36-smoke`
- realm: `atius`
- direct access grants: enabled

Successful path:

```bash
curl --resolve auth.atius.com.br:443:127.0.0.1 \
  -X POST https://auth.atius.com.br/realms/atius/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=phase36-smoke' \
  --data-urlencode 'username=giovanni' \
  --data-urlencode 'password=<root-only secret>'
```

## Apache coexistence

The legacy Apache/JWT auth path remains intact.

Representative checks kept answering during the phase:

- `https://admin.atius.com.br/` -> login redirect
- `https://api.atius.com.br/` -> same API route behavior as before

No application was migrated to Keycloak in this phase.

## Root-only secrets and paths

| Item | Path |
|---|---|
| Keycloak env | `/etc/keycloak/keycloak.env` |
| FreeIPA LDAP bind env | `/etc/keycloak/freeipa-bind.env` |
| Recovery admin env | `/etc/keycloak/recovery-admin.env` |
| Install backup bundle | latest `/root/keycloak-36-*` |

Do not copy these secrets into repo docs, planning files, chat, or shell history.
