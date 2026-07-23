# Phase 36: Keycloak SSO and Coexistence - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning
**Mode:** Directed carry-over execution after FreeIPA and Samba phases

<domain>
## Phase Boundary

Phase 36 introduces Keycloak as a new OIDC identity provider federated to the
existing FreeIPA realm, while preserving the current Apache SSO/JWT path.

This phase is not an app migration phase. It must prove that:

- Keycloak runs safely on `atius-srv-1`
- it reads identities from FreeIPA
- it can expose a tested OIDC endpoint
- and it does not break the legacy Apache SSO model already serving the fleet

</domain>

<decisions>
## Implementation Decisions

### D-01 | Host | Keycloak runs on `atius-srv-1`
The identity stack is converging on `srv1`, where Samba already landed and
where the legacy Apache auth surface exists.

### D-02 | Coexistence | Legacy Apache SSO must remain untouched
No existing app is migrated away from the Apache/JWT flow in this phase.
Keycloak is additive.

### D-03 | Port model | Avoid collisions with existing Apache alt ports
`srv1` already serves Apache on `9080` and `8443`. Keycloak must use a distinct
private listen pair and be published through a controlled reverse-proxy path.

### D-04 | Federation mode | FreeIPA-backed read path first
The first implementation should favor a safe federation mode that proves login
and attribute sync without letting Keycloak mutate FreeIPA user records.

### D-05 | Exposure | `auth.atius.com.br` only after local/private smoke
Do not publish `auth.atius.com.br` until Keycloak is healthy locally and the
FreeIPA federation path is proven.

</decisions>

<code_context>
## Existing Runtime Insights

- `srv1` already runs Apache on `9080` and `8443`.
- Java 17 is installed on `srv1`; research recommends Java 21 for the current
  Keycloak line.
- FreeIPA on `srv3` now provides private DNS, Kerberos, Samba trust support,
  and real host enrollment through `atius.internal`.
- The Apache legacy SSO path remains production-critical and must not regress.

</code_context>

<specifics>
## Specific Ideas

- Install Keycloak natively on `srv1` with its own systemd unit.
- Keep Keycloak on private ports first.
- Validate LDAP/realm connectivity to FreeIPA before exposing the public
  hostname.
- Use a controlled local or private callback path for the first OIDC smoke.
- Only after that, wire `auth.atius.com.br` through Apache.

</specifics>

<deferred>
## Deferred Ideas

- Application migration to Keycloak remains after coexistence is proven.
- Group/role design for real apps is deferred beyond this phase.
- Any public cutover that touches the current Apache SSO logic remains out of
  scope here.

</deferred>
