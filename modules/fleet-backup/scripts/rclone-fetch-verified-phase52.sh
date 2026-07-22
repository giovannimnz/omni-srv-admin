#!/usr/bin/env bash
# Bounded read-only fetch for the Phase 52 RustDesk Backup B.
set -euo pipefail
set +x
IFS=$'\n\t'
umask 077

readonly DESTINATION_PREFIX='giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/phase52/backup-b/'
readonly DEFAULT_TIMEOUT_SECONDS=900
readonly MAX_ARCHIVE_BYTES=4294967296
source_remote=''
expected_sha256=''
output=''
expected_size_bytes=''
workdir=''
# Parse/transport failures are redacted: rclone_parse_blocked, stderr_suppressed.

blocked() { printf '{"blocker":"%s","operation":"fetch-verified","secret_material_present":false,"status":"BLOCKED"}\n' "$1"; exit 2; }
cleanup() {
  local rc=$?
  trap - EXIT INT TERM HUP
  if [[ -n "$workdir" && -d "$workdir" && ! -L "$workdir" ]]; then
    rm -f -- "$workdir/rclone.conf" "$workdir/.atius-rclone-vault-provenance.json"
    rmdir -- "$workdir" 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
while (($#)); do
  case "$1" in
    --source) (($# >= 2)) || blocked invalid-interface; source_remote=$2; shift 2 ;;
    --expected-sha256) (($# >= 2)) || blocked invalid-interface; expected_sha256=$2; shift 2 ;;
    --expected-size-bytes) (($# >= 2)) || blocked invalid-interface; expected_size_bytes=$2; shift 2 ;;
    --output) (($# >= 2)) || blocked invalid-interface; output=$2; shift 2 ;;
    *) blocked invalid-interface ;;
  esac
done
[[ "$source_remote" == "$DESTINATION_PREFIX"* ]] || blocked source-outside-allowlist
remote_name=${source_remote#"$DESTINATION_PREFIX"}
[[ "$remote_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.tar$ && "$remote_name" != *..* ]] || blocked source-name-invalid
[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] || blocked expected-sha256-invalid
[[ "$expected_size_bytes" =~ ^[1-9][0-9]*$ ]] || blocked expected-size-invalid
(( expected_size_bytes <= MAX_ARCHIVE_BYTES )) || blocked expected-size-exceeded
[[ "$output" == /* && ! -e "$output" && ! -L "$output" ]] || blocked output-invalid
parent=$(realpath -e -- "$(dirname -- "$output")" 2>/dev/null) || blocked output-parent-invalid
[[ "$parent/$(basename -- "$output")" == "$output" && -d "$parent" && ! -L "$parent" ]] || blocked output-parent-invalid
[[ $(stat -c '%u' -- "$parent") == "$(id -u)" && $((8#$(stat -c '%a' -- "$parent") & 8#022)) -eq 0 ]] || blocked output-parent-insecure
command -v rclone >/dev/null 2>&1 || blocked rclone-missing
command -v timeout >/dev/null 2>&1 || blocked timeout-missing
runtime_input=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
runtime=$(realpath -e -- "$runtime_input" 2>/dev/null) || blocked runtime-root-missing
[[ "$runtime" == "$runtime_input" && $(stat -c '%u:%a' -- "$runtime") == "$(id -u):700" && $(stat -f -c '%T' -- "$runtime") == tmpfs ]] || blocked runtime-root-insecure
workdir=$(mktemp -d "$runtime/rustdesk-phase52-fetch.XXXXXX") || blocked workdir-create-failed
chmod 700 "$workdir"
script_dir=$(unset CDPATH; cd -- "$(dirname -- "$0")" && pwd -P)
hydrator=$script_dir/atius-rclone-vault-hydrate
[[ -x "$hydrator" && -f "$hydrator" && ! -L "$hydrator" ]] || blocked hydrator-missing
"$hydrator" --materialize --output-dir "$workdir" >/dev/null 2>/dev/null || blocked rclone-hydration-blocked
timeout_seconds=${PHASE52_RCLONE_TIMEOUT_SECONDS:-$DEFAULT_TIMEOUT_SECONDS}
[[ "$timeout_seconds" =~ ^[1-9][0-9]{0,3}$ ]] || blocked timeout-invalid
set +e
timeout "$timeout_seconds" rclone cat --config "$workdir/rclone.conf" "$source_remote" 2>/dev/null | \
  python3 -c 'import hashlib,os,pathlib,sys,tempfile
output=pathlib.Path(sys.argv[1]); expected=int(sys.argv[2]); expected_hash=sys.argv[3]
fd,stage_name=tempfile.mkstemp(prefix=".phase52-fetch.",dir=output.parent)
stage=pathlib.Path(stage_name); total=0; digest=hashlib.sha256()
try:
 os.fchmod(fd,0o600)
 while True:
  chunk=sys.stdin.buffer.read(1048576)
  if not chunk: break
  total+=len(chunk)
  if total>expected or total>4294967296: raise SystemExit(2)
  os.write(fd,chunk); digest.update(chunk)
 if total!=expected: raise SystemExit(2)
 if digest.hexdigest()!=expected_hash: raise SystemExit(3)
 os.fsync(fd); os.close(fd); fd=-1
 try: os.link(stage,output,follow_symlinks=False)
 except FileExistsError: raise SystemExit(4)
 parent_fd=os.open(output.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(parent_fd)
 finally: os.close(parent_fd)
finally:
 if fd>=0: os.close(fd)
 stage.unlink(missing_ok=True)' "$output" "$expected_size_bytes" "$expected_sha256"
stream_rc=$?
set -e
case "$stream_rc" in
  0) ;;
  2) blocked stream-size-exceeded ;;
  3) blocked remote-hash-mismatch ;;
  4) blocked output-raced ;;
  *) blocked rclone_parse_blocked ;;
esac
printf '{"hash_verified":true,"operation":"fetch-verified","output_mode":"0600","secret_material_present":false,"status":"PASS"}\n'
