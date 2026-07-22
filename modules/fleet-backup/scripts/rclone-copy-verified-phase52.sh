#!/usr/bin/env bash
# Copy-only uploader for the Phase 52 RustDesk Backup B on horistic-srv.
set -euo pipefail
IFS=$'\n\t'
umask 077

readonly DESTINATION_PREFIX='giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/phase52/backup-b/'
readonly APPROVED_REMOTE='giovanni-drive'
readonly PROVENANCE_BASENAME='.atius-rclone-vault-provenance.json'
readonly PROVENANCE_SCHEMA='atius-rclone-vault-provenance-v2'
readonly RETENTION='phase57-pass-plus-30-days'
readonly DEFAULT_TIMEOUT_SECONDS=900
readonly DEFAULT_BWLIMIT='4M'
readonly MAX_ARCHIVE_BYTES=4294967296
# All parser failures are fail-closed with rclone_parse_blocked and stderr_suppressed.

source_archive=''
destination=''
rclone_config=''
workdir=''
expected_size_bytes=''

emit_error() {
  printf '{"blocker":"%s","operation":"copy-only","secret_material_present":false,"status":"BLOCKED"}\n' "$1"
}

die() {
  emit_error "$1"
  exit 2
}

cleanup() {
  local rc=$?
  trap - EXIT ERR INT TERM HUP
  if [[ -n "$workdir" && -d "$workdir" && ! -L "$workdir" ]]; then
    rm -f -- \
      "$workdir/source.snapshot" \
      "$workdir/rclone.conf" \
      "$workdir/$PROVENANCE_BASENAME" \
      "$workdir/rclone.snapshot.conf" \
      "$workdir/provenance.snapshot.json"
    rmdir -- "$workdir" 2>/dev/null || true
  fi
  exit "$rc"
}

trap cleanup EXIT
trap 'exit 1' ERR
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

usage() {
  echo 'usage: rclone-copy-verified-phase52.sh --source ARCHIVE --destination REMOTE_FILE --expected-size-bytes BYTES' >&2
  exit 2
}

canonical_file() {
  local path=$1 canonical
  canonical=$(realpath -e -- "$path" 2>/dev/null) || return 1
  [[ "$path" == "$canonical" && -f "$path" && ! -L "$path" ]] || return 1
  printf '%s\n' "$canonical"
}

validate_owned_file() {
  local path=$1 expected_mode=$2 identity
  identity=$(stat -c '%u:%h:%a' -- "$path" 2>/dev/null) || return 1
  [[ "$identity" == "$(id -u):1:$expected_mode" ]]
}

validate_owned_parent() {
  local path=$1 expected_mode=${2:-} canonical identity
  canonical=$(realpath -e -- "$path" 2>/dev/null) || return 1
  [[ "$path" == "$canonical" && -d "$path" && ! -L "$path" ]] || return 1
  identity=$(stat -c '%u:%a' -- "$path" 2>/dev/null) || return 1
  [[ ${identity%%:*} == "$(id -u)" ]] || return 1
  [[ -z "$expected_mode" || ${identity#*:} == "$expected_mode" ]] || return 1
  (( (8#${identity#*:} & 8#022) == 0 ))
}

file_identity() {
  stat -c '%d:%i:%u:%h:%a:%s' -- "$1"
}

copy_exclusive_bounded() {
  python3 - "$1" "$2" "$3" <<'PY'
import os,pathlib,sys
source=pathlib.Path(sys.argv[1]); destination=pathlib.Path(sys.argv[2]); maximum=int(sys.argv[3]); total=0
fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
try:
 with source.open('rb') as input_handle:
  while True:
   chunk=input_handle.read(1048576)
   if not chunk: break
   total+=len(chunk)
   if total>maximum: raise SystemExit(2)
   os.write(fd,chunk)
 os.fsync(fd)
finally: os.close(fd)
PY
}

snapshot_stable_file() {
  local original=$1 snapshot=$2 expected_mode=$3 before after original_hash snapshot_hash
  before=$(file_identity "$original") || return 1
  original_hash=$(sha256sum -- "$original" | awk '{print $1}') || return 1
  copy_exclusive_bounded "$original" "$snapshot" "$MAX_ARCHIVE_BYTES" || return 1
  chmod "$expected_mode" "$snapshot" || return 1
  after=$(file_identity "$original") || return 1
  snapshot_hash=$(sha256sum -- "$snapshot" | awk '{print $1}') || return 1
  [[ "$before" == "$after" && "$original_hash" == "$snapshot_hash" ]] || return 1
  validate_owned_file "$snapshot" "$expected_mode" || return 1
  printf '%s\t%s\n' "$before" "$original_hash"
}

while (($#)); do
  case "$1" in
    --source)
      (($# >= 2)) || usage
      source_archive=$2
      shift 2
      ;;
    --destination)
      (($# >= 2)) || usage
      destination=$2
      shift 2
      ;;
    --expected-size-bytes)
      (($# >= 2)) || usage
      expected_size_bytes=$2
      shift 2
      ;;
    --help|-h) usage ;;
    *) usage ;;
  esac
done

[[ -n "$source_archive" && -n "$destination" && "$expected_size_bytes" =~ ^[1-9][0-9]*$ ]] || usage
(( expected_size_bytes <= MAX_ARCHIVE_BYTES )) || die 'expected-size-exceeded'
command -v python3 >/dev/null 2>&1 || die 'python3-missing'
command -v rclone >/dev/null 2>&1 || die 'rclone-missing'
command -v timeout >/dev/null 2>&1 || die 'timeout-missing'

source_archive=$(canonical_file "$source_archive") || die 'source-not-canonical-regular'
validate_owned_file "$source_archive" 600 || die 'source-identity-invalid'
source_parent=$(dirname -- "$source_archive")
validate_owned_parent "$source_parent" || die 'source-parent-insecure'
[[ $(stat -c '%s' -- "$source_archive") == "$expected_size_bytes" ]] || die 'source-size-mismatch'

[[ "$destination" == "$DESTINATION_PREFIX"* ]] || die 'destination-outside-allowlist'
destination_name=${destination#"$DESTINATION_PREFIX"}
[[ -n "$destination_name" && "$destination_name" != */* ]] || die 'destination-outside-allowlist'
[[ "$destination_name" != *..* ]] || die 'destination-name-invalid'
[[ "$destination_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.tar$ ]] || die 'destination-name-invalid'

timeout_seconds=${PHASE52_RCLONE_TIMEOUT_SECONDS:-$DEFAULT_TIMEOUT_SECONDS}
bwlimit=${PHASE52_RCLONE_BWLIMIT:-$DEFAULT_BWLIMIT}
[[ "$timeout_seconds" =~ ^[1-9][0-9]{0,3}$ ]] || die 'timeout-invalid'
[[ "$bwlimit" =~ ^[1-9][0-9]*([KMG])?$ ]] || die 'bwlimit-invalid'

runtime_root_input=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
runtime_root=$(realpath -e -- "$runtime_root_input" 2>/dev/null) || die 'runtime-root-missing'
[[ "$runtime_root_input" == "$runtime_root" ]] || die 'runtime-root-not-canonical'
validate_owned_parent "$runtime_root" 700 || die 'runtime-root-insecure'
[[ $(stat -f -c '%T' -- "$runtime_root" 2>/dev/null) == 'tmpfs' ]] || die 'runtime-root-not-tmpfs'
workdir=$(mktemp -d "$runtime_root/rustdesk-phase52-backup-b.XXXXXX") || die 'snapshot-dir-create-failed'
chmod 700 "$workdir"
validate_owned_parent "$workdir" 700 || die 'snapshot-dir-insecure'

uploader_dir=$(realpath -e -- "$(dirname -- "$0")" 2>/dev/null) || die 'uploader-dir-invalid'
validate_owned_parent "$uploader_dir" || die 'uploader-dir-insecure'
hydrator="$uploader_dir/atius-rclone-vault-hydrate"
hydrator=$(canonical_file "$hydrator") || die 'canonical-hydrator-missing'
hydrator_mode=$(stat -c '%a' -- "$hydrator")
[[ "$hydrator_mode" == 700 || "$hydrator_mode" == 755 ]] || die 'canonical-hydrator-mode-invalid'
validate_owned_file "$hydrator" "$hydrator_mode" || die 'canonical-hydrator-identity-invalid'
[[ -x "$hydrator" ]] || die 'canonical-hydrator-not-executable'
hydrator_identity=$(file_identity "$hydrator")
hydrator_sha256=$(sha256sum -- "$hydrator" | awk '{print $1}')
if ! "$hydrator" --materialize --output-dir "$workdir" >/dev/null 2>/dev/null; then
  die 'rclone-hydration-blocked'
fi
[[ $(file_identity "$hydrator") == "$hydrator_identity" ]] || die 'canonical-hydrator-changed'
[[ $(sha256sum -- "$hydrator" | awk '{print $1}') == "$hydrator_sha256" ]] || die 'canonical-hydrator-changed'

rclone_config="$workdir/rclone.conf"
rclone_config=$(canonical_file "$rclone_config") || die 'hydrated-rclone-config-missing'
validate_owned_file "$rclone_config" 600 || die 'hydrated-rclone-config-identity-invalid'
provenance="$workdir/$PROVENANCE_BASENAME"
provenance=$(canonical_file "$provenance") || die 'rclone-provenance-missing'
validate_owned_file "$provenance" 600 || die 'rclone-provenance-identity-invalid'

source_snapshot="$workdir/source.snapshot"
config_snapshot="$workdir/rclone.snapshot.conf"
provenance_snapshot="$workdir/provenance.snapshot.json"
source_snapshot_record=$(snapshot_stable_file "$source_archive" "$source_snapshot" 600) || die 'source-snapshot-unstable'
copy_exclusive_bounded "$rclone_config" "$config_snapshot" 65536 || die 'rclone-config-snapshot-unstable'
chmod 600 "$config_snapshot"
validate_owned_file "$config_snapshot" 600 || die 'rclone-config-snapshot-unstable'
cmp -s -- "$rclone_config" "$config_snapshot" || die 'rclone-config-snapshot-unstable'
snapshot_stable_file "$provenance" "$provenance_snapshot" 600 >/dev/null || die 'rclone-provenance-snapshot-unstable'

config_identity=$(file_identity "$rclone_config")
config_original_identity=$config_identity
IFS=: read -r config_device config_inode config_uid _ <<< "$config_identity"
python3 - \
  "$provenance_snapshot" "$PROVENANCE_SCHEMA" "$(basename -- "$rclone_config")" \
  "$config_device" "$config_inode" "$config_uid" "$APPROVED_REMOTE" <<'PY' \
  >/dev/null || die 'rclone-provenance-invalid'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
expected = {
    "schema": sys.argv[2],
    "status": "PASS",
    "materialized_by": "atius-rclone-vault-hydrate",
    "config_basename": sys.argv[3],
    "profile": "rclone-giovanni-drive-phase52",
    "protocol": "rclone-giovanni-drive-phase52-v1",
    "vault_path": "kv/atius/fleet-backup/rclone/giovanni-drive",
    "field": "rclone_conf",
    "config_device": int(sys.argv[4]),
    "config_inode": int(sys.argv[5]),
    "config_uid": int(sys.argv[6]),
    "config_mode": "0600",
    "config_size_bytes": path.parent.joinpath(sys.argv[3]).stat().st_size,
    "approved_remote": sys.argv[7],
    "secret_material_present": False,
}
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError):
    raise SystemExit(1)
if payload != expected:
    raise SystemExit(1)
PY

python3 - "$source_snapshot" <<'PY' >/dev/null || die 'source-not-state-only'
import pathlib
import stat
import sys
import tarfile

archive_path = pathlib.Path(sys.argv[1])
try:
    with tarfile.open(archive_path, "r:") as archive:
        members = archive.getmembers()
        if [member.name for member in members] != ["db_v2.sqlite3"]:
            raise ValueError("allowlist")
        member = members[0]
        candidate = pathlib.PurePosixPath(member.name)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not member.isfile()
            or member.issym()
            or member.islnk()
            or stat.S_IMODE(member.mode) != 0o600
        ):
            raise ValueError("allowlist")
except (OSError, UnicodeError, tarfile.TarError, ValueError):
    raise SystemExit(1)
PY

local_sha256=${source_snapshot_record#*$'\t'}
size_bytes=$(stat -c '%s' -- "$source_snapshot")
[[ "$size_bytes" == "$expected_size_bytes" && "$size_bytes" -le "$MAX_ARCHIVE_BYTES" ]] || die 'source-size-mismatch'
snapshot_identity=$(file_identity "$source_snapshot")
config_snapshot_identity=$(file_identity "$config_snapshot")

if ! timeout "$timeout_seconds" rclone copyto "$source_snapshot" "$destination" \
  --config "$config_snapshot" \
  --transfers 1 \
  --checkers 1 \
  --bwlimit "$bwlimit" \
  --retries 2 \
  --low-level-retries 3 \
  --immutable \
  --log-level ERROR \
  >/dev/null 2>/dev/null; then
  die 'rclone-copy-failed'
fi

remote_sha256=$(
  timeout "$timeout_seconds" rclone cat "$destination" \
    --config "$config_snapshot" \
    --bwlimit "$bwlimit" \
    --retries 2 \
    --low-level-retries 3 \
    --log-level ERROR \
    2>/dev/null | python3 -c 'import hashlib,sys
expected=int(sys.argv[1]); total=0; digest=hashlib.sha256()
while True:
 chunk=sys.stdin.buffer.read(1048576)
 if not chunk: break
 total+=len(chunk)
 if total>expected or total>4294967296: raise SystemExit(2)
 digest.update(chunk)
if total!=expected: raise SystemExit(2)
print(digest.hexdigest())' "$expected_size_bytes"
) || die 'rclone-rehash-failed'

[[ "$remote_sha256" == "$local_sha256" ]] || die 'remote-hash-mismatch'
[[ $(file_identity "$source_snapshot") == "$snapshot_identity" ]] || die 'source-snapshot-changed'
[[ $(sha256sum -- "$source_snapshot" | awk '{print $1}') == "$local_sha256" ]] || die 'source-snapshot-changed'
[[ $(file_identity "$config_snapshot") == "$config_snapshot_identity" ]] || die 'rclone-config-snapshot-changed'
[[ $(file_identity "$rclone_config") == "$config_original_identity" ]] || die 'rclone-config-snapshot-changed'
cmp -s -- "$rclone_config" "$config_snapshot" || die 'rclone-config-snapshot-changed'

python3 - "$destination" "$local_sha256" "$remote_sha256" "$size_bytes" "$RETENTION" <<'PY'
import json
import sys
print(json.dumps({
    "status": "PASS",
    "operation": "copy-only",
    "destination": sys.argv[1],
    "local_sha256": sys.argv[2],
    "remote_sha256": sys.argv[3],
    "size_bytes": int(sys.argv[4]),
    "verified_copy": True,
    "source_snapshot_private": True,
    "config_provenance_verified": True,
    "retention": {
        "retain_until": sys.argv[5],
        "deletion_requires_new_explicit_approval": True,
    },
    "secret_material_present": False,
}, sort_keys=True))
PY
