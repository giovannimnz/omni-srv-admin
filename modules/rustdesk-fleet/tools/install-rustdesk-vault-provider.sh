#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

usage() { echo "usage: $0 [--install|--rollback] [--dry-run] [--home ABSOLUTE_HOME]" >&2; exit 64; }
fail() { echo "$1" >&2; exit 2; }

action=install
dry_run=false
target_home=${HOME:?HOME is required}
while (($#)); do
  case "$1" in
    --install) action=install ;;
    --rollback) action=rollback ;;
    --dry-run) dry_run=true ;;
    --home) shift; (($#)) || usage; target_home=$1 ;;
    *) usage ;;
  esac
  shift
done

current_uid=$(id -u)
[[ "$target_home" == /* && "$target_home" != / && -d "$target_home" && ! -L "$target_home" ]] || usage
[[ $(realpath -e -- "$target_home") == "$target_home" ]] || fail "target home contains a symlink or non-canonical component"
[[ $(stat -c '%u' -- "$target_home") == "$current_uid" ]] || fail "target home owner mismatch"

script_dir=$(unset CDPATH; cd -- "$(dirname -- "$0")" && pwd -P)
source_provider=$script_dir/rustdesk-vault-provider
target_local=$target_home/.local
target_dir=$target_local/bin
target_state_parent=$target_local/state
target_provider=$target_dir/rustdesk-vault-provider
state_dir=$target_state_parent/atius-rustdesk-vault-provider
state_file=$state_dir/install-state
backup_file=$state_dir/provider.pre-phase52
journal_file=$state_dir/transaction-journal
stage_file=$state_dir/provider.transaction

[[ -f "$source_provider" && ! -L "$source_provider" && -x "$source_provider" ]] || fail "versioned provider is unavailable"
[[ $(stat -c '%u' -- "$source_provider") == "$current_uid" ]] || fail "versioned provider owner mismatch"

mode_safe() { local mode; mode=$(stat -c '%a' -- "$1"); (( (8#$mode & 8#022) == 0 )); }
assert_dir() {
  local path=$1 policy=$2 canonical
  [[ -d "$path" && ! -L "$path" ]] || fail "unsafe managed directory: $path"
  [[ $(stat -c '%u' -- "$path") == "$current_uid" ]] || fail "managed directory owner mismatch: $path"
  canonical=$(realpath -e -- "$path")
  [[ "$canonical" == "$target_home" || "$canonical" == "$target_home"/* ]] || fail "managed directory escaped target home"
  mode_safe "$path" || fail "managed directory is group/world writable: $path"
  [[ "$policy" != exact-0700 || $(stat -c '%a' -- "$path") == 700 ]] || fail "state directory mode drift: $path"
}
assert_file() {
  local path=$1 parent
  [[ -f "$path" && ! -L "$path" ]] || fail "unsafe managed file: $path"
  [[ $(stat -c '%u' -- "$path") == "$current_uid" ]] || fail "managed file owner mismatch: $path"
  parent=$(realpath -e -- "$(dirname -- "$path")")
  [[ "$parent" == "$target_home"/* ]] || fail "managed file escaped target home"
}
ensure_dir() { local path=$1 policy=$2; if [[ -e "$path" || -L "$path" ]]; then assert_dir "$path" "$policy"; else install -d -m 0700 -- "$path"; assert_dir "$path" "$policy"; fi; }
validate_existing_dir() { local path=$1 policy=$2; if [[ -e "$path" || -L "$path" ]]; then assert_dir "$path" "$policy"; fi; }

assert_dir "$target_home" no-go-write
validate_existing_dir "$target_local" no-go-write
validate_existing_dir "$target_dir" no-go-write
validate_existing_dir "$target_state_parent" exact-0700
validate_existing_dir "$state_dir" exact-0700
if $dry_run; then
  printf '{"action":"%s","dry_run":true,"secret_material_present":false,"target":"%s"}\n' "$action" "$target_provider"
  exit 0
fi

ensure_dir "$target_local" no-go-write
ensure_dir "$target_dir" no-go-write
ensure_dir "$target_state_parent" exact-0700
ensure_dir "$state_dir" exact-0700

record_value() { local file=$1 key=$2; [[ $(grep -c "^${key}=" "$file") == 1 ]] || fail "transaction record is invalid"; sed -n "s/^${key}=//p" "$file"; }
load_record() {
  local file=$1 lines=$2
  assert_file "$file"
  [[ $(stat -c '%a' -- "$file") == 600 && $(wc -l <"$file") == "$lines" ]] || fail "transaction record is invalid"
  schema_version=$(record_value "$file" schema_version)
  recorded_target=$(record_value "$file" target_path)
  had_previous=$(record_value "$file" had_previous)
  previous_mode=$(record_value "$file" previous_mode)
  previous_sha256=$(record_value "$file" previous_sha256)
  installed_sha256=$(record_value "$file" installed_sha256)
  [[ "$schema_version" == 1 && "$recorded_target" == "$target_provider" ]] || fail "transaction boundary drift"
  [[ "$installed_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "installed digest is invalid"
  case "$had_previous:$previous_mode:$previous_sha256" in
    0:none:none) ;;
    1:[0-7][0-7][0-7]:*|1:[0-7][0-7][0-7][0-7]:*) [[ "$previous_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "backup digest is invalid" ;;
    *) fail "transaction record is invalid" ;;
  esac
}
validate_state() {
  load_record "$state_file" 6
  assert_file "$target_provider"
  [[ $(sha256sum -- "$target_provider" | awk '{print $1}') == "$installed_sha256" ]] || fail "installed provider drift"
  if [[ "$had_previous" == 1 ]]; then
    assert_file "$backup_file"
    [[ $(stat -c '%a' -- "$backup_file") == 600 ]] || fail "rollback backup mode drift"
    [[ $(sha256sum -- "$backup_file" | awk '{print $1}') == "$previous_sha256" ]] || fail "rollback backup drift"
  else
    [[ ! -e "$backup_file" && ! -L "$backup_file" ]] || fail "unexpected stale rollback backup"
  fi
}
write_state() {
  local tmp=$state_dir/.install-state.$$
  printf '%s\n' 'schema_version=1' "target_path=$target_provider" "had_previous=$had_previous" "previous_mode=$previous_mode" "previous_sha256=$previous_sha256" "installed_sha256=$installed_sha256" >"$tmp"
  chmod 0600 -- "$tmp"; mv -- "$tmp" "$state_file"
}
write_journal() {
  local transaction_action=$1 tmp=$state_dir/.journal.$$
  printf '%s\n' 'schema_version=1' "target_path=$target_provider" "had_previous=$had_previous" "previous_mode=$previous_mode" "previous_sha256=$previous_sha256" "installed_sha256=$installed_sha256" "action=$transaction_action" >"$tmp"
  chmod 0600 -- "$tmp"; mv -- "$tmp" "$journal_file"
}
maybe_interrupt() { [[ ${ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER:-} != "$1" ]] || exit 75; }

recovered_action=none
recover_transaction() {
  [[ -e "$journal_file" || -L "$journal_file" ]] || return 0
  load_record "$journal_file" 7
  transaction_action=$(record_value "$journal_file" action)
  case "$transaction_action" in
    install)
      assert_file "$stage_file"
      [[ $(stat -c '%a' -- "$stage_file") == 600 && $(sha256sum -- "$stage_file" | awk '{print $1}') == "$installed_sha256" ]] || fail "install transaction stage drift"
      if [[ "$had_previous" == 1 && ! -e "$backup_file" ]]; then
        assert_file "$target_provider"
        [[ $(sha256sum -- "$target_provider" | awk '{print $1}') == "$previous_sha256" ]] || fail "install recovery baseline drift"
        install -m 0600 -- "$target_provider" "$backup_file"
      fi
      if [[ "$had_previous" == 1 ]]; then assert_file "$backup_file"; [[ $(sha256sum -- "$backup_file" | awk '{print $1}') == "$previous_sha256" ]] || fail "install recovery backup drift"; fi
      install -m 0700 -- "$stage_file" "$target_provider"
      write_state
      rm -- "$journal_file"
      rm -- "$stage_file"
      ;;
    rollback)
      if [[ "$had_previous" == 1 ]]; then
        if [[ -e "$backup_file" ]]; then assert_file "$backup_file"; [[ $(sha256sum -- "$backup_file" | awk '{print $1}') == "$previous_sha256" ]] || fail "rollback recovery backup drift"; install -m "$previous_mode" -- "$backup_file" "$target_provider"
        else assert_file "$target_provider"; [[ $(sha256sum -- "$target_provider" | awk '{print $1}') == "$previous_sha256" ]] || fail "rollback recovery target drift"; fi
      elif [[ -e "$target_provider" ]]; then
        assert_file "$target_provider"; [[ $(sha256sum -- "$target_provider" | awk '{print $1}') == "$installed_sha256" ]] || fail "rollback recovery target drift"; rm -- "$target_provider"
      fi
      rm -f -- "$state_file" "$backup_file" "$journal_file"
      ;;
    *) fail "transaction action is invalid" ;;
  esac
  recovered_action=$transaction_action
}

recover_transaction
if [[ "$recovered_action" == "$action" ]]; then printf '{"action":"%s","recovered":true,"status":"PASS","secret_material_present":false}\n' "$action"; exit 0; fi
if [[ -e "$stage_file" || -L "$stage_file" ]]; then
  [[ ! -e "$journal_file" && ! -L "$journal_file" ]] || fail "transaction journal/stage invariant drift"
  assert_file "$stage_file"
  rm -- "$stage_file"
fi

if [[ "$action" == install ]]; then
  source_sha256=$(sha256sum -- "$source_provider" | awk '{print $1}')
  if [[ -e "$state_file" || -L "$state_file" ]]; then validate_state
  else
    had_previous=0; previous_mode=none; previous_sha256=none
    if [[ -e "$target_provider" || -L "$target_provider" ]]; then assert_file "$target_provider"; had_previous=1; previous_mode=$(stat -c '%a' -- "$target_provider"); previous_sha256=$(sha256sum -- "$target_provider" | awk '{print $1}')
    elif [[ -e "$backup_file" || -L "$backup_file" ]]; then fail "stale rollback backup exists without state"; fi
  fi
  installed_sha256=$source_sha256
  install -m 0600 -- "$source_provider" "$stage_file"
  [[ $(sha256sum -- "$stage_file" | awk '{print $1}') == "$installed_sha256" ]] || fail "staged provider digest mismatch"
  maybe_interrupt stage
  write_journal install
  maybe_interrupt journal
  if [[ "$had_previous" == 1 && ! -e "$backup_file" ]]; then install -m 0600 -- "$target_provider" "$backup_file"; fi
  install -m 0700 -- "$stage_file" "$target_provider"
  maybe_interrupt target
  write_state
  rm -- "$journal_file"
  rm -- "$stage_file"
else
  [[ -e "$state_file" || -L "$state_file" ]] || fail "rollback state is unavailable"
  validate_state
  write_journal rollback
  maybe_interrupt journal
  if [[ "$had_previous" == 1 ]]; then install -m "$previous_mode" -- "$backup_file" "$target_provider"; else rm -- "$target_provider"; fi
  maybe_interrupt target
  rm -f -- "$state_file" "$backup_file" "$journal_file"
fi
printf '{"action":"%s","status":"PASS","secret_material_present":false}\n' "$action"
