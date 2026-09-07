#!/usr/bin/env bash
# Offload seguro de ~/.backups e ~/backups para o Google Drive.
# Regra: snapshot estavel -> tar.gz streaming -> SHA-256 remoto -> manifest -> delete.
set -euo pipefail
IFS=$'\n\t'
umask 077

EXPECTED_HOST="${OFFLOAD_EXPECTED_HOST:-atius-srv-1}"
if [ "$(hostname -s)" != "$EXPECTED_HOST" ]; then
  printf 'SKIP wrong-host current=%s expected=%s\n' "$(hostname -s)" "$EXPECTED_HOST" >&2
  exit 0
fi

HOME_DIR="${HOME_DIR:-/home/ubuntu}"
REMOTE="${REMOTE:-giovanni-drive:}"
APPROVED_REMOTE="giovanni-drive:"
DOT_SRC="${DOT_SRC:-$HOME_DIR/.backups}"
BACKUPS_SRC="${BACKUPS_SRC:-$HOME_DIR/backups}"
DOT_DEST="${DOT_DEST:-ATIUS-SRV/SRV-1/Backup/home/ubuntu/.backups}"
BACKUPS_DEST="${BACKUPS_DEST:-ATIUS-SRV/SRV-1/Backup/home/ubuntu/backups}"
LOG="${LOG:-$HOME_DIR/.logs/offload-dotbackups-to-gdrive.log}"
STATE_DIR="${STATE_DIR:-$HOME_DIR/.local/state/omni/gdrive-backup-offload}"
LOCAL_LOCK="${LOCAL_LOCK:-/tmp/offload-dotbackups-to-gdrive.lock}"
FLEET_LOCK="${FLEET_LOCK:-/tmp/rclone-fleet.lock}"
MIN_AGE_MINUTES="${MIN_AGE_MINUTES:-10}"
PARTIAL_MIN_AGE_MINUTES="${PARTIAL_MIN_AGE_MINUTES:-1440}"
DELETE_AFTER_VERIFY="${DELETE_AFTER_VERIFY:-1}"
BWLIMIT_KBPS="${BWLIMIT_KBPS:-54000}"
TPSLIMIT="${TPSLIMIT:-8}"
RCLONE_TIMEOUT="${RCLONE_TIMEOUT:-7200}"
LOCK_WAIT="${LOCK_WAIT:-1800}"
ITEM_DELAY="${ITEM_DELAY:-5}"
RETRY_BASE_SECONDS="${RETRY_BASE_SECONDS:-30}"
RCLONE_BIN="${RCLONE_BIN:-rclone}"
SUDO_BIN="${SUDO_BIN:-sudo}"
PRIVILEGE_MODE="${PRIVILEGE_MODE:-sudo}"
CONFIG_MODE="${CONFIG_MODE:-vault}"
PERSISTENT_CONFIG="${PERSISTENT_CONFIG:-$HOME_DIR/.config/rclone/rclone.conf}"
QUARANTINE_ROOT_BASE="${QUARANTINE_ROOT_BASE:-/var/lib/omni-offload-quarantine}"
FLEET_HOLD_FILE="${RCLONE_FLEET_HOLD_FILE:-$HOME_DIR/.local/state/omni/rclone-fleet-queue.hold}"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HYDRATOR="${HYDRATOR:-$SCRIPT_DIR/../../fleet-backup/scripts/atius-rclone-vault-hydrate}"

DRY_RUN="${DRY_RUN:-0}"
SOURCE_FILTER=all
RUN_TMP=""
RCLONE_CONFIG=""
EXIT_CODE=0
PROCESSED=0
VERIFIED=0
DELETED=0
KEPT=0
SKIPPED=0

usage() {
  cat <<'EOF'
Usage: offload-dotbackups-to-gdrive.sh [--dry-run] [--keep-local]
       [--source all|dotbackups|backups]

Uploads each top-level backup as a versioned tar.gz, re-reads it from Drive,
compares SHA-256 and uploads a verified manifest before deleting the local item.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --keep-local) DELETE_AFTER_VERIFY=0 ;;
    --source)
      shift; SOURCE_FILTER="${1:-}"
      case "$SOURCE_FILTER" in all|dotbackups|backups) ;; *) usage >&2; exit 2 ;; esac
      ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$(dirname "$LOG")" "$STATE_DIR"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }
write_last_run() {
  local code="$1" status="$2" reason="$3" tmp="$STATE_DIR/last-run.json.tmp.$$"
  printf '{"deleted":%d,"exit":%d,"kept":%d,"processed":%d,"reason":"%s","skipped":%d,"status":"%s","verified":%d}\n' \
    "$DELETED" "$code" "$KEPT" "$PROCESSED" "$reason" "$SKIPPED" "$status" "$VERIFIED" > "$tmp"
  chmod 0600 "$tmp"
  mv -f "$tmp" "$STATE_DIR/last-run.json"
}

validate_delete_roots() {
  local approved_dot approved_backups actual_dot actual_backups
  approved_dot="$(realpath -m "/home/ubuntu/.backups")"
  approved_backups="$(realpath -m "/home/ubuntu/backups")"
  actual_dot="$(realpath -m "$DOT_SRC")"
  actual_backups="$(realpath -m "$BACKUPS_SRC")"
  if [ "$DELETE_AFTER_VERIFY" -eq 1 ] \
    && { [ "$actual_dot" != "$approved_dot" ] || [ "$actual_backups" != "$approved_backups" ]; }; then
    log "FAIL reason=unapproved-delete-root dot=$actual_dot backups=$actual_backups"
    return 1
  fi
}

cleanup() {
  if [ -n "$RUN_TMP" ] && [ -d "$RUN_TMP" ]; then
    find "$RUN_TMP" -depth -delete 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

priv() {
  if [ "$PRIVILEGE_MODE" = direct ] || [ "$(id -u)" -eq 0 ]; then "$@"; else "$SUDO_BIN" -n "$@"; fi
}

rclone_args() {
  printf '%s\n' "--config=$RCLONE_CONFIG" "--bwlimit=${BWLIMIT_KBPS}k" \
    "--tpslimit=$TPSLIMIT" "--tpslimit-burst=$TPSLIMIT" --transfers=1 --checkers=1 \
    --drive-pacer-min-sleep=1s --drive-pacer-burst=1 \
    --retries=1 --low-level-retries=2 --retries-sleep=5s --log-level=ERROR
}

rclone_retry() {
  local label="$1" attempt=1 rc=1 err wait_seconds
  shift
  local -a common=(); mapfile -t common < <(rclone_args)
  while (( attempt <= 5 )); do
    err=$(mktemp "$RUN_TMP/rclone-error.XXXXXX")
    if timeout --signal=TERM --kill-after=30s "${RCLONE_TIMEOUT}s" \
      "$RCLONE_BIN" "$@" "${common[@]}" 2>"$err"; then
      find "$err" -delete; return 0
    else
      rc=$?
    fi
    if grep -Eqi 'rateLimitExceeded|storageQuotaExceeded|Quota exceeded|Rate Limit|too_many_requests|userRateLimitExceeded' "$err"; then
      wait_seconds=$((RETRY_BASE_SECONDS * attempt)); log "RATE $label attempt=$attempt/5 wait=${wait_seconds}s rc=$rc"
      sleep "$wait_seconds"
    else
      log "FAIL $label rc=$rc class=rclone-nonretryable"; find "$err" -delete; return "$rc"
    fi
    find "$err" -delete; attempt=$((attempt + 1))
  done
  log "FAIL $label exhausted_attempts=5"; return 1
}

prepare_config() {
  [ "$REMOTE" = "$APPROVED_REMOTE" ] \
    || { log "FAIL auth unapproved-remote=$REMOTE"; return 1; }
  if [ "$DELETE_AFTER_VERIFY" -eq 1 ]; then
    [ "$CONFIG_MODE" = vault ] \
      || { log "FAIL auth delete-requires-vault-config"; return 1; }
    [ "$QUARANTINE_ROOT_BASE" = /var/lib/omni-offload-quarantine ] \
      || { log "FAIL unsafe-quarantine-root=$QUARANTINE_ROOT_BASE"; return 1; }
  fi
  RUN_TMP=$(mktemp -d /dev/shm/atius-gdrive-offload.XXXXXX) || return 1
  chmod 700 "$RUN_TMP"
  case "$CONFIG_MODE" in
    vault)
      mkdir -m 700 "$RUN_TMP/rclone"
      if ! "$HYDRATOR" --materialize --output-dir "$RUN_TMP/rclone" >"$RUN_TMP/hydrate.json" 2>/dev/null; then
        log "FAIL auth mode=vault class=hydrate-blocked"; return 1
      fi
      RCLONE_CONFIG="$RUN_TMP/rclone/rclone.conf"
      ;;
    persistent) RCLONE_CONFIG="$PERSISTENT_CONFIG" ;;
    *) log "FAIL auth invalid_config_mode=$CONFIG_MODE"; return 1 ;;
  esac
  if [ ! -f "$RCLONE_CONFIG" ] || [ -L "$RCLONE_CONFIG" ]; then
    log "FAIL auth config-invalid"; return 1
  fi
  "$RCLONE_BIN" listremotes --config "$RCLONE_CONFIG" 2>/dev/null | grep -qx "$APPROVED_REMOTE" \
    || { log "FAIL auth approved-remote-missing"; return 1; }
  backend_type="$("$RCLONE_BIN" config show "${APPROVED_REMOTE%:}" --config "$RCLONE_CONFIG" 2>/dev/null \
    | awk -F= '$1 ~ /^[[:space:]]*type[[:space:]]*$/ {gsub(/[[:space:]]/,"",$2); print $2; exit}')"
  [ "$backend_type" = drive ] \
    || { log "FAIL auth approved-remote-backend=${backend_type:-missing}"; return 1; }
  rclone_retry auth-probe lsd "${REMOTE}ATIUS-SRV/SRV-1/Backup" --max-depth=1 >/dev/null \
    || { log "FAIL auth remote-probe-failed"; return 1; }
  log "AUTH PASS mode=$CONFIG_MODE storage=$([ "$CONFIG_MODE" = vault ] && echo tmpfs || echo persistent-cache)"
}

# Snapshot metadata is deterministic, does not follow symlinks and fails closed on unreadable entries.
snapshot() {
  priv python3 - "$1" <<'PY'
import hashlib,json,os,stat,sys
root=os.fsencode(sys.argv[1]); root_st=os.lstat(root); dev=root_st.st_dev
stack=[(root,b'.')]; rows=[]; files=total=0; newest=0
while stack:
    path,rel=stack.pop(); st=os.lstat(path); mode=st.st_mode
    kind=b'f' if stat.S_ISREG(mode) else b'd' if stat.S_ISDIR(mode) else b'l' if stat.S_ISLNK(mode) else b'o'
    target=os.fsencode(os.readlink(path)) if kind==b'l' else b''
    if kind==b'f': files+=1; total+=st.st_size
    newest=max(newest,st.st_mtime_ns)
    rows.append(b'\0'.join((rel,kind,str(stat.S_IMODE(mode)).encode(),str(st.st_uid).encode(),str(st.st_gid).encode(),str(st.st_size).encode(),str(st.st_mtime_ns).encode(),target)))
    if kind==b'd' and st.st_dev==dev:
        entries=sorted(os.scandir(path),key=lambda e:os.fsencode(e.name),reverse=True)
        for entry in entries:
            name=os.fsencode(entry.name); child=name if rel==b'.' else rel+b'/'+name
            stack.append((os.path.join(path,name),child))
h=hashlib.sha256()
for row in sorted(rows): h.update(len(row).to_bytes(8,'big')); h.update(row)
print(json.dumps({'entries':len(rows),'files':files,'bytes':total,'newest_mtime_ns':newest,'fingerprint':h.hexdigest()},sort_keys=True,separators=(',',':')))
PY
}

field() { python3 -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "$1" "$2"; }
old_enough() {
  python3 - "$1" "$2" <<'PY'
import json,sys,time
d=json.loads(sys.argv[1]); raise SystemExit(0 if time.time_ns()-d['newest_mtime_ns'] >= int(sys.argv[2])*60*10**9 else 1)
PY
}
safe_name() {
  local stem suffix; stem=$(printf %s "$1" | LC_ALL=C tr -cs 'A-Za-z0-9._-' '_' | cut -c1-100)
  suffix=$(printf %s "$1" | sha256sum | cut -c1-8); printf '%s--%s' "${stem:-item}" "$suffix"
}

archive_destination() {
  local bucket=_archives
  if [[ "$2" == *.partial ]]; then bucket=_quarantine; fi
  printf '%s%s/%s/%s--%s.tar.gz' "$REMOTE" "$1" "$bucket" "$(safe_name "$2")" "${3:0:20}"
}

stream_archive_once() {
  local item="$1" dest="$2" result="$3" n="$4" parent label fifo hash_file error_file hash_pid rc
  parent=$(dirname -- "$item"); label=$(basename -- "$item")
  fifo="$RUN_TMP/hash-$PROCESSED-$n.fifo"; hash_file="$RUN_TMP/hash-$PROCESSED-$n.json"; error_file="$RUN_TMP/rcat-$PROCESSED-$n.err"
  find "$fifo" "$hash_file" "$error_file" -delete 2>/dev/null || true
  mkfifo -m 600 "$fifo"
  python3 -c 'import hashlib,json,os,sys; h=hashlib.sha256(); n=0
while True:
 b=sys.stdin.buffer.read(1048576)
 if not b: break
 h.update(b); n+=len(b)
f=open(sys.argv[1],"x"); json.dump({"bytes":n,"sha256":h.hexdigest()},f,sort_keys=True,separators=(",",":")); f.write("\n"); f.flush(); os.fsync(f.fileno()); f.close()' "$hash_file" <"$fifo" &
  hash_pid=$!
  local -a common=(); mapfile -t common < <(rclone_args)
  if priv tar -C "$parent" --sort=name --numeric-owner --acls --xattrs --selinux --one-file-system --warning=no-file-changed -cf - -- "$label" \
    | pigz -n --fast -p 1 | tee "$fifo" | pv -q -L "${BWLIMIT_KBPS}k" -W \
    | timeout --signal=TERM --kill-after=30s "${RCLONE_TIMEOUT}s" "$RCLONE_BIN" rcat "$dest" "${common[@]}" 2>"$error_file"; then rc=0; else rc=$?; fi
  wait "$hash_pid" || rc=1; find "$fifo" -delete 2>/dev/null || true
  if [ "$rc" -ne 0 ]; then
    if grep -Eqi 'rateLimitExceeded|RATE_LIMIT_EXCEEDED|Quota exceeded' "$error_file" 2>/dev/null; then
      log "RATE archive=$label rc=$rc class=shared-oauth-project-quota"
    else
      log "FAIL archive=$label rc=$rc class=rcat"
    fi
  fi
  find "$error_file" -delete 2>/dev/null || true
  [ "$rc" -eq 0 ] && [ -s "$hash_file" ] || return 1
  mv "$hash_file" "$result"
}

stream_archive() {
  local n=1 wait_seconds
  while (( n <= 5 )); do
    stream_archive_once "$1" "$2" "$3" "$n" && return 0
    wait_seconds=$((RETRY_BASE_SECONDS*n)); log "RETRY archive=$(basename -- "$1") attempt=$n/5 wait=${wait_seconds}s"; sleep "$wait_seconds"; n=$((n+1))
  done
  return 1
}

remote_meta() {
  local dest="$1" attempt value; local -a common=(); mapfile -t common < <(rclone_args)
  for attempt in 1 2 3 4 5; do
    if value=$(timeout --signal=TERM --kill-after=30s "${RCLONE_TIMEOUT}s" "$RCLONE_BIN" cat "$dest" "${common[@]}" 2>/dev/null | python3 -c 'import hashlib,json,sys
h=hashlib.sha256(); n=0
while True:
 b=sys.stdin.buffer.read(1048576)
 if not b: break
 h.update(b); n+=len(b)
print(json.dumps({"bytes":n,"sha256":h.hexdigest()},sort_keys=True,separators=(",",":")))'); then
      printf '%s\n' "$value"; return 0
    fi
    log "RETRY verify-readback attempt=$attempt/5" >&2; sleep $((15*attempt))
  done
  return 1
}

make_manifest() {
  python3 - "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import datetime,json,os,sys
path,root,item,snap,archive,dest=sys.argv[1:]
d={'schema':'atius-gdrive-offload-v2','status':'PASS','source_root':root,'item':item,'source':json.loads(snap),'archive':json.loads(archive),'remote_object':dest,'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with open(path,'x') as f: json.dump(d,f,sort_keys=True,separators=(',',':')); f.write('\n'); f.flush(); os.fsync(f.fileno())
PY
}

delete_item() {
  local item="$1" parent="$2"
  priv python3 - "$item" "$parent" <<'PY'
from pathlib import Path
import os,re,stat,sys
item=Path(sys.argv[1]); parent=Path(sys.argv[2])
if item.parent != parent or not item.name or item.name in {'.','..'}: raise SystemExit(1)
pfd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
try:
    st=os.stat(item.name,dir_fd=pfd,follow_symlinks=False)
    root_dev=st.st_dev
    root_path=os.path.realpath(item)
    def decode(value):
        return re.sub(r'\\([0-7]{3})',lambda match: chr(int(match.group(1),8)),value)
    for raw in Path('/proc/self/mountinfo').read_text().splitlines():
        fields=raw.split()
        if len(fields)<6: raise ValueError('invalid mountinfo row')
        mountpoint=os.path.realpath(decode(fields[4]))
        if mountpoint==root_path or os.path.commonpath((root_path,mountpoint))==root_path:
            raise OSError(18,'nested mount')
    def remove_tree(name, parent_fd):
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=parent_fd)
        try:
            entries=list(os.scandir(fd))
            for entry in entries:
                est=os.stat(entry.name,dir_fd=fd,follow_symlinks=False)
                if est.st_dev != root_dev: raise OSError(18,'cross-device entry')
                if stat.S_ISDIR(est.st_mode): remove_tree(entry.name,fd)
                else: os.unlink(entry.name,dir_fd=fd)
        finally: os.close(fd)
        os.rmdir(name,dir_fd=parent_fd)
    if stat.S_ISDIR(st.st_mode):
        # Validation walk first: never partially delete before finding a nested mount.
        stack=[item]
        while stack:
            path=stack.pop()
            for entry in os.scandir(path):
                est=os.stat(entry.path,follow_symlinks=False)
                if est.st_dev != root_dev: raise OSError(18,'cross-device entry')
                if stat.S_ISDIR(est.st_mode): stack.append(Path(entry.path))
        remove_tree(item.name,pfd)
    elif stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode): os.unlink(item.name,dir_fd=pfd)
    else: raise SystemExit(1)
    try: os.stat(item.name,dir_fd=pfd,follow_symlinks=False)
    except FileNotFoundError: raise SystemExit(0)
    raise SystemExit(1)
finally:
    os.close(pfd)
PY
}

quarantine_item() {
  local item="$1" src="$2"
  priv python3 - "$item" "$src" "$QUARANTINE_ROOT_BASE" <<'PY'
from pathlib import Path
import os,secrets,stat,sys
item=Path(sys.argv[1]); source=Path(sys.argv[2]); base=Path(sys.argv[3])
if item.parent != source or not item.name or item.name in {'.','..'}: raise SystemExit(1)
flags=os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW
sfd=os.open(source,flags)
try:
    try: os.mkdir(base,0o700)
    except FileExistsError: pass
    bfd=os.open(base,flags)
    try:
        st=os.fstat(bfd)
        if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o700 or st.st_uid!=os.geteuid(): raise SystemExit(1)
        if os.fstat(sfd).st_dev != st.st_dev: raise SystemExit(18)
        for _ in range(100):
            child='item.'+secrets.token_hex(8)
            try: os.mkdir(child,0o700,dir_fd=bfd); break
            except FileExistsError: continue
        else: raise SystemExit(1)
        cfd=os.open(child,flags,dir_fd=bfd)
        moved=False
        try:
            os.rename(item.name,item.name,src_dir_fd=sfd,dst_dir_fd=cfd)
            moved=True
        finally:
            os.close(cfd)
            if not moved:
                os.rmdir(child,dir_fd=bfd)
    finally: os.close(bfd)
finally: os.close(sfd)
print(str(base/child))
PY
}

restore_quarantined_item() {
  local quarantined="$1" item="$2"
  priv python3 - "$quarantined" "$item" <<'PY'
from pathlib import Path
import os,sys
quarantined=Path(sys.argv[1]); item=Path(sys.argv[2])
flags=os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW
qfd=os.open(quarantined.parent,flags); sfd=os.open(item.parent,flags)
try:
    try: os.stat(item.name,dir_fd=sfd,follow_symlinks=False)
    except FileNotFoundError:
        os.rename(quarantined.name,item.name,src_dir_fd=qfd,dst_dir_fd=sfd)
        raise SystemExit(0)
    raise SystemExit(17)
finally:
    os.close(qfd); os.close(sfd)
PY
}

has_open_handles() {
  local target="$1"
  priv python3 - "$target" "$DELETE_AFTER_VERIFY" <<'PY'
from pathlib import Path
import os,stat,sys
try:
    root=Path(sys.argv[1]); strict=sys.argv[2]=='1'; wanted=set(); stack=[root]
    self_mnt=os.stat('/proc/self/ns/mnt')
    while stack:
        path=stack.pop(); st=os.lstat(path); wanted.add((st.st_dev,st.st_ino))
        if stat.S_ISDIR(st.st_mode):
            with os.scandir(path) as entries: stack.extend(Path(entry.path) for entry in entries)
    me=os.getpid()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name)==me: continue
        try:
            proc_mnt=os.stat(proc/'ns/mnt')
            same_mnt=(proc_mnt.st_dev,proc_mnt.st_ino)==(self_mnt.st_dev,self_mnt.st_ino)
        except FileNotFoundError:
            continue
        except PermissionError:
            if strict: raise
            continue
        candidates=[proc/'cwd',proc/'root']
        try: candidates.extend((proc/'fd').iterdir())
        except FileNotFoundError: continue
        except PermissionError:
            if strict and same_mnt: raise
            continue
        try: candidates.extend((proc/'map_files').iterdir())
        except FileNotFoundError: pass
        except PermissionError:
            if strict and same_mnt: raise
            pass
        for candidate in candidates:
            try: st=os.stat(candidate)
            except FileNotFoundError: continue
            except PermissionError:
                if strict and same_mnt: raise
                continue
            if (st.st_dev,st.st_ino) in wanted: raise SystemExit(0)
except SystemExit:
    raise
except BaseException as exc:
    print(f'open-handle scan failed: {exc}',file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(1)
PY
}

has_nested_mount() {
  local target="$1"
  priv python3 - "$target" <<'PY'
from pathlib import Path
import os,re,sys
try:
    root=os.path.realpath(sys.argv[1])
    def decode(value):
        return re.sub(r'\\([0-7]{3})',lambda match: chr(int(match.group(1),8)),value)
    for raw in Path('/proc/self/mountinfo').read_text().splitlines():
        fields=raw.split()
        if len(fields)<6: raise ValueError('invalid mountinfo row')
        mountpoint=os.path.realpath(decode(fields[4]))
        if mountpoint==root or os.path.commonpath((root,mountpoint))==root:
            raise SystemExit(0)
except SystemExit:
    raise
except BaseException as exc:
    print(f'mount scan failed: {exc}',file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(1)
PY
}

quiescence_gate() {
  local target="$1" rc
  QUIESCENCE_REASON=""
  if has_nested_mount "$target"; then
    QUIESCENCE_REASON="nested-mount"; return 1
  else
    rc=$?; [ "$rc" -eq 1 ] || { QUIESCENCE_REASON="mount-scan-failed"; return 1; }
  fi
  if has_open_handles "$target"; then
    QUIESCENCE_REASON="open-writer"; return 1
  else
    rc=$?; [ "$rc" -eq 1 ] || { QUIESCENCE_REASON="open-handle-scan-failed"; return 1; }
  fi
  return 0
}

process_item() {
  local item="$1" src="$2" root="$3" base="$4" label before after age fp files bytes dest meta lh lb rmeta rh rb manifest mdest mh
  local manifest_meta manifest_remote_hash manifest_remote_bytes quarantine_base quarantine_root quarantined quarantine_after
  label=$(basename -- "$item"); age=$MIN_AGE_MINUTES; [[ "$label" == *.partial ]] && age=$PARTIAL_MIN_AGE_MINUTES
  before=$(snapshot "$item" 2>/dev/null) || { log "KEEP root=$root item=$label reason=snapshot-failed"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  old_enough "$before" "$age" || { log "SKIP root=$root item=$label reason=age-gate minutes=$age"; SKIPPED=$((SKIPPED+1)); return; }
  fp=$(field "$before" fingerprint); files=$(field "$before" files); bytes=$(field "$before" bytes); dest=$(archive_destination "$base" "$label" "$fp")
  PROCESSED=$((PROCESSED+1))
  if [ "$DRY_RUN" -eq 1 ]; then log "DRY root=$root item=$label files=$files bytes=$bytes dest=$dest"; return; fi
  quarantine_base="$QUARANTINE_ROOT_BASE"
  quarantine_root="$(quarantine_item "$item" "$src")" \
    || { log "KEEP root=$root item=$label reason=quarantine-base-unsafe"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  quarantined="$quarantine_root/$label"
  if ! quiescence_gate "$quarantined"; then
    if restore_quarantined_item "$quarantined" "$item"; then
      priv rmdir -- "$quarantine_root" 2>/dev/null || true
    fi
    log "KEEP root=$root item=$label reason=$QUIESCENCE_REASON-after-quarantine"; KEPT=$((KEPT+1)); EXIT_CODE=1; return
  fi
  quarantine_after=$(snapshot "$quarantined" 2>/dev/null) || true
  if [ "$quarantine_after" != "$before" ]; then
    if restore_quarantined_item "$quarantined" "$item"; then
      priv rmdir -- "$quarantine_root" 2>/dev/null || true
    fi
    log "KEEP root=$root item=$label reason=quarantine-snapshot-drift quarantine=$quarantined"; KEPT=$((KEPT+1)); EXIT_CODE=1; return
  fi
  restore_quarantine() {
    if restore_quarantined_item "$quarantined" "$item"; then
      priv rmdir -- "$quarantine_root" 2>/dev/null || true
      return 0
    else
      log "KEEP root=$root item=$label reason=restore-collision quarantine=$quarantined"
      return 1
    fi
  }
  restore_or_mark_failed() {
    restore_quarantine || { KEPT=$((KEPT+1)); EXIT_CODE=1; return 1; }
  }
  meta="$RUN_TMP/archive-$PROCESSED.json"; log "COPY root=$root item=$label files=$files bytes=$bytes dest=$dest"
  stream_archive "$quarantined" "$dest" "$meta" || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=upload-failed"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  lh=$(field "$(<"$meta")" sha256); lb=$(field "$(<"$meta")" bytes)
  if ! rmeta=$(remote_meta "$dest"); then restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=remote-readback-failed"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; fi
  rh=$(field "$rmeta" sha256); rb=$(field "$rmeta" bytes)
  [ "$rh" = "$lh" ] || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=remote-hash-mismatch"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  [ "$rb" = "$lb" ] || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=remote-size-mismatch"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  after=$(snapshot "$quarantined" 2>/dev/null) || true
  [ "$after" = "$before" ] || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=source-changed"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  manifest="$RUN_TMP/manifest-$PROCESSED.json"; mdest="$dest.manifest.json"; make_manifest "$manifest" "$root" "$label" "$before" "$(<"$meta")" "$dest"
  mh=$(sha256sum "$manifest" | awk '{print $1}')
  rclone_retry "manifest:$label" copyto "$manifest" "$mdest" || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=manifest-upload-failed"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  manifest_meta="$(remote_meta "$mdest")" || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=manifest-readback-failed"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  manifest_remote_hash="$(field "$manifest_meta" sha256)"
  manifest_remote_bytes="$(field "$manifest_meta" bytes)"
  [ "$manifest_remote_hash" = "$mh" ] && [ "$manifest_remote_bytes" = "$(stat -c %s "$manifest")" ] \
    || { restore_or_mark_failed || return 0; log "KEEP root=$root item=$label reason=manifest-readback-mismatch"; KEPT=$((KEPT+1)); EXIT_CODE=1; return; }
  VERIFIED=$((VERIFIED+1)); log "VERIFY root=$root item=$label sha256=$lh archive_bytes=$lb manifest_upload=PASS manifest_sha256=$mh"
  if [ "$DELETE_AFTER_VERIFY" -eq 1 ]; then
    if ! quiescence_gate "$quarantined"; then
      log "KEEP root=$root item=$label reason=$QUIESCENCE_REASON-before-delete quarantine=$quarantined"
      KEPT=$((KEPT+1)); EXIT_CODE=1; return
    fi
    if delete_item "$quarantined" "$quarantine_root"; then
      priv rmdir -- "$quarantine_root" 2>/dev/null || true
      DELETED=$((DELETED+1)); log "DELETE root=$root item=$label gate=verified-quarantined"
    else
      KEPT=$((KEPT+1)); EXIT_CODE=1
      log "KEEP root=$root item=$label reason=delete-failed quarantine=$quarantined"
    fi
  else
    restore_or_mark_failed || return 0
    KEPT=$((KEPT+1)); log "KEEP root=$root item=$label reason=delete-disabled"
  fi
}

process_source() {
  local src="$1" root="$2" base="$3" item; local -a items=()
  if [ ! -d "$src" ] || [ -L "$src" ]; then
    log "SKIP root=$root reason=source-invalid path=$src"; SKIPPED=$((SKIPPED+1)); return
  fi
  mapfile -d '' items < <(find -P "$src" -mindepth 1 -maxdepth 1 -print0 2>/dev/null | sort -z)
  for item in "${items[@]}"; do
    [ "$(basename -- "$item")" = ".omni-offload-quarantine" ] && continue
    [ -e "$item" ] || [ -L "$item" ] || continue; process_item "$item" "$src" "$root" "$base"
    [ "$DRY_RUN" -eq 1 ] || [ "$ITEM_DELAY" -eq 0 ] || sleep "$ITEM_DELAY"
  done
}

main() {
  if [ -f "$FLEET_HOLD_FILE" ]; then
    log "SKIP fleet-hold-active file=$FLEET_HOLD_FILE"
    return 0
  fi
  validate_delete_roots || { write_last_run 2 "failed" "unapproved-delete-root"; return 2; }
  exec 9>"$LOCAL_LOCK"
  if ! flock -w "$LOCK_WAIT" 9; then
    log "RETRY local-lock-timeout lock=$LOCAL_LOCK"
    write_last_run 75 "retryable" "local-lock-timeout"
    return 75
  fi
  exec 8>"$FLEET_LOCK"
  if ! flock -w "$LOCK_WAIT" 8; then
    log "RETRY fleet-lock-timeout lock=$FLEET_LOCK"
    write_last_run 75 "retryable" "fleet-lock-timeout"
    return 75
  fi
  log "OFFLOAD START sources=$SOURCE_FILTER dry_run=$DRY_RUN delete=$DELETE_AFTER_VERIFY"
  log "DISK before_available_bytes=$(df -B1 --output=avail /home | tail -1 | tr -d ' ')"
  [ "$DRY_RUN" -eq 1 ] || prepare_config || return 1
  case "$SOURCE_FILTER" in all|dotbackups) process_source "$DOT_SRC" dotbackups "$DOT_DEST";; esac
  case "$SOURCE_FILTER" in all|backups) process_source "$BACKUPS_SRC" backups "$BACKUPS_DEST";; esac
  log "DISK after_available_bytes=$(df -B1 --output=avail /home | tail -1 | tr -d ' ')"
  log "OFFLOAD END exit=$EXIT_CODE processed=$PROCESSED verified=$VERIFIED deleted=$DELETED kept=$KEPT skipped=$SKIPPED"
  write_last_run "$EXIT_CODE" "$([ "$EXIT_CODE" -eq 0 ] && echo success || echo failed)" "completed"
  return "$EXIT_CODE"
}
main
