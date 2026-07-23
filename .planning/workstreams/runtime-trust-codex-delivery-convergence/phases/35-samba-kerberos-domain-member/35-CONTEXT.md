# Phase 35: Samba Kerberos Domain Member - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning
**Mode:** Directed carry-over execution after FreeIPA Phase 34 closeout

<domain>
## Phase Boundary

Phase 35 will migrate the current Samba file-serving role from `atius-srv-2`
to `atius-srv-1`, while switching authentication to FreeIPA/Kerberos.

The currently mounted client path on `atius-srv-1` is:

- `//10.1.1.2/Shared -> /home/ubuntu/Shared_smb`

The existing share source remains on `atius-srv-2`:

- share path: `/home/ubuntu/Shared`
- Samba users currently listed: `ubuntu`, `horistic`, `giovanni`, `sambauser`

</domain>

<decisions>
## Implementation Decisions

### D-01 | Target host | Samba destination is `atius-srv-1`
Operator selected `atius-srv-1` as the final Samba host for Phase 35.

### D-02 | Migration order | Copy first, cut over later
The existing share data must be copied to `srv1` before the old Samba service
on `srv2` is disabled or the mount on `srv1` is repointed.

### D-03 | Auth model | FreeIPA/Kerberos, not standalone Samba users
Samba on `srv1` should authenticate through FreeIPA/Kerberos, not through a
standalone local Samba password database.

### D-04 | Scope | Linux-first file-serving path
This phase focuses on a Linux file server integrated with FreeIPA. It does not
need public exposure and should avoid Windows/AD-trust complexity unless the
existing share semantics require it.

### D-05 | Safety | Live share cutover is a checkpoint
Disabling `smbd/nmbd` on `srv2`, switching the mount on `srv1`, and publishing
the new share on `srv1` are all live mutations and must be treated as a cutover
checkpoint.

</decisions>

<code_context>
## Existing Runtime Insights

- `srv1` currently does not serve Samba: `smbd`, `nmbd`, and `winbind` are
  inactive/not found there.
- `srv1` mounts `//10.1.1.2/Shared` through `/etc/fstab` to
  `/home/ubuntu/Shared_smb`.
- `srv2` actively serves the `[Shared]` share from `/home/ubuntu/Shared`.
- Current share size on `srv2` is about `8.8G`.
- Available disk on `srv1` is about `25G`, enough for an initial copy of the
  current share data.
- FreeIPA private DNS and first real host enrollment are now working through
  Phase 34.

</code_context>

<specifics>
## Specific Ideas

- Join `atius-srv-1` to FreeIPA before configuring Samba there.
- Add the `cifs/atius-srv-1.atius.internal` service principal and fetch a
  keytab for Samba.
- Stage a local target path on `srv1`, likely under `/srv/Shared`, and copy the
  current data from `srv2` with ownership/ACL preservation.
- Preserve the stable mount path `/home/ubuntu/Shared_smb` on `srv1` if
  possible, but repoint it only during the cutover checkpoint.
- Validate access with `smbclient -k` and a Kerberos-backed user path before
  declaring the migration complete.

</specifics>

<deferred>
## Deferred Ideas

- `horistic-srv` realm enrollment remains after the first Samba cutover.
- Keycloak/OIDC stays in Phase 36.
- Any Windows AD trust flow stays out of scope unless it becomes mandatory for
  the current Samba share behavior.

</deferred>
