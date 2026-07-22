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
source_client=$script_dir/atius-vault-phase52-client
target_local=$target_home/.local
target_dir=$target_local/bin
target_state_parent=$target_local/state
state_dir=$target_state_parent/atius-rustdesk-vault-provider
state_file=$state_dir/install-state
journal_file=$state_dir/transaction-journal
provider_backup=$state_dir/provider.pre-phase52
client_backup=$state_dir/client.pre-phase52
provider_stage=$state_dir/provider.transaction
client_stage=$state_dir/client.transaction
target_provider=$target_dir/rustdesk-vault-provider
target_client=$target_dir/atius-vault-phase52-client

[[ -f "$source_provider" && ! -L "$source_provider" && -x "$source_provider" ]] || fail "versioned provider is unavailable"
[[ -f "$source_client" && ! -L "$source_client" && -x "$source_client" ]] || fail "versioned Phase 52 client is unavailable"
[[ $(stat -c '%u' -- "$source_provider") == "$current_uid" ]] || fail "versioned provider owner mismatch"
[[ $(stat -c '%u' -- "$source_client") == "$current_uid" ]] || fail "versioned client owner mismatch"

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
  local path=$1
  [[ -f "$path" && ! -L "$path" && $(stat -c '%h' -- "$path") == 1 ]] || fail "unsafe managed file: $path"
  [[ $(stat -c '%u' -- "$path") == "$current_uid" ]] || fail "managed file owner mismatch: $path"
  [[ $(realpath -e -- "$(dirname -- "$path")") == "$target_home"/* ]] || fail "managed file escaped target home"
}
ensure_dir() { local path=$1 policy=$2; if [[ -e "$path" || -L "$path" ]]; then assert_dir "$path" "$policy"; else install -d -m 0700 -- "$path"; assert_dir "$path" "$policy"; fi; }
validate_existing_dir() { local path=$1 policy=$2; if [[ -e "$path" || -L "$path" ]]; then assert_dir "$path" "$policy"; fi; }
file_hash() { sha256sum -- "$1" | awk '{print $1}'; }

assert_dir "$target_home" no-go-write
validate_existing_dir "$target_local" no-go-write
validate_existing_dir "$target_dir" no-go-write
validate_existing_dir "$target_state_parent" exact-0700
validate_existing_dir "$state_dir" exact-0700
if $dry_run; then
  printf '{"action":"%s","client_target":"%s","dry_run":true,"secret_material_present":false,"target":"%s"}\n' "$action" "$target_client" "$target_provider"
  exit 0
fi
ensure_dir "$target_local" no-go-write
ensure_dir "$target_dir" no-go-write
ensure_dir "$target_state_parent" exact-0700
ensure_dir "$state_dir" exact-0700

record_value() {
  local file=$1 key=$2
  [[ $(grep -c "^${key}=" "$file") == 1 ]] || fail "transaction record is invalid"
  sed -n "s/^${key}=//p" "$file"
}
validate_prior() {
  local had=$1 mode=$2 gid=$3 digest=$4
  case "$had:$mode:$gid:$digest" in
    0:none:none:none) ;;
    1:[0-7][0-7][0-7]:[0-9]*:*|1:[0-7][0-7][0-7][0-7]:[0-9]*:*) [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || fail "backup digest is invalid" ;;
    *) fail "transaction record is invalid" ;;
  esac
}
load_record() {
  local file=$1 expected_lines=$2 expect_action=$3
  assert_file "$file"
  [[ $(stat -c '%a' -- "$file") == 600 && $(wc -l <"$file") == "$expected_lines" ]] || fail "transaction record is invalid"
  schema_version=$(record_value "$file" schema_version)
  [[ "$schema_version" == 2 ]] || fail "transaction record is invalid"
  if [[ "$expect_action" == yes ]]; then transaction_action=$(record_value "$file" action); fi
  provider_target_path=$(record_value "$file" provider_target_path)
  provider_had_previous=$(record_value "$file" provider_had_previous)
  provider_previous_mode=$(record_value "$file" provider_previous_mode)
  provider_previous_gid=$(record_value "$file" provider_previous_gid)
  provider_previous_sha256=$(record_value "$file" provider_previous_sha256)
  provider_installed_sha256=$(record_value "$file" provider_installed_sha256)
  client_target_path=$(record_value "$file" client_target_path)
  client_had_previous=$(record_value "$file" client_had_previous)
  client_previous_mode=$(record_value "$file" client_previous_mode)
  client_previous_gid=$(record_value "$file" client_previous_gid)
  client_previous_sha256=$(record_value "$file" client_previous_sha256)
  client_installed_sha256=$(record_value "$file" client_installed_sha256)
  [[ "$provider_target_path" == "$target_provider" && "$client_target_path" == "$target_client" ]] || fail "transaction boundary drift"
  [[ "$provider_installed_sha256" =~ ^[0-9a-f]{64}$ && "$client_installed_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "installed digest is invalid"
  validate_prior "$provider_had_previous" "$provider_previous_mode" "$provider_previous_gid" "$provider_previous_sha256"
  validate_prior "$client_had_previous" "$client_previous_mode" "$client_previous_gid" "$client_previous_sha256"
}
write_record() {
  local destination=$1 transaction_action=${2-} tmp=$state_dir/.record.$$
  {
    printf '%s\n' 'schema_version=2'
    [[ -z "$transaction_action" ]] || printf 'action=%s\n' "$transaction_action"
    printf '%s\n' \
      "provider_target_path=$target_provider" "provider_had_previous=$provider_had_previous" \
      "provider_previous_mode=$provider_previous_mode" "provider_previous_gid=$provider_previous_gid" \
      "provider_previous_sha256=$provider_previous_sha256" "provider_installed_sha256=$provider_installed_sha256" \
      "client_target_path=$target_client" "client_had_previous=$client_had_previous" \
      "client_previous_mode=$client_previous_mode" "client_previous_gid=$client_previous_gid" \
      "client_previous_sha256=$client_previous_sha256" "client_installed_sha256=$client_installed_sha256"
  } >"$tmp"
  chmod 0600 -- "$tmp"
  mv -- "$tmp" "$destination"
}
validate_backup() {
  local had=$1 backup=$2 digest=$3 label=$4
  if [[ "$had" == 1 ]]; then
    assert_file "$backup"
    [[ $(stat -c '%a' -- "$backup") == 600 && $(file_hash "$backup") == "$digest" ]] || fail "$label rollback backup drift"
  else
    [[ ! -e "$backup" && ! -L "$backup" ]] || fail "unexpected stale $label rollback backup"
  fi
}
validate_state() {
  load_record "$state_file" 13 no
  assert_file "$target_provider"; assert_file "$target_client"
  [[ $(stat -c '%a' -- "$target_provider") == 700 && $(file_hash "$target_provider") == "$provider_installed_sha256" ]] || fail "installed provider drift"
  [[ $(stat -c '%a' -- "$target_client") == 700 && $(file_hash "$target_client") == "$client_installed_sha256" ]] || fail "installed client drift"
  validate_backup "$provider_had_previous" "$provider_backup" "$provider_previous_sha256" provider
  validate_backup "$client_had_previous" "$client_backup" "$client_previous_sha256" client
}
capture_target() {
  local target=$1 prefix=$2
  local had=0 mode=none gid=none digest=none
  if [[ -e "$target" || -L "$target" ]]; then
    assert_file "$target"; had=1; mode=$(stat -c '%a' -- "$target"); gid=$(stat -c '%g' -- "$target"); digest=$(file_hash "$target")
  fi
  printf -v "${prefix}_had_previous" '%s' "$had"
  printf -v "${prefix}_previous_mode" '%s' "$mode"
  printf -v "${prefix}_previous_gid" '%s' "$gid"
  printf -v "${prefix}_previous_sha256" '%s' "$digest"
}
ensure_backup() {
  local target=$1 backup=$2 had=$3 previous_hash=$4 label=$5
  if [[ "$had" == 0 ]]; then [[ ! -e "$backup" && ! -L "$backup" ]] || fail "unexpected stale $label rollback backup"; return; fi
  if [[ -e "$backup" || -L "$backup" ]]; then
    assert_file "$backup"; [[ $(file_hash "$backup") == "$previous_hash" ]] || fail "$label rollback backup drift"; return
  fi
  assert_file "$target"; [[ $(file_hash "$target") == "$previous_hash" ]] || fail "$label recovery baseline drift"
  install -m 0600 -- "$target" "$backup"
}
install_one() {
  local target=$1 stage=$2 had=$3 previous_hash=$4 installed_hash=$5 label=$6
  if [[ -e "$target" || -L "$target" ]]; then
    assert_file "$target"; current_hash=$(file_hash "$target")
    [[ "$current_hash" == "$previous_hash" || "$current_hash" == "$installed_hash" ]] || fail "$label install recovery target drift"
    if [[ "$current_hash" == "$installed_hash" ]]; then
      [[ $(stat -c '%a' -- "$target") == 700 ]] || fail "$label install recovery mode drift"
      return
    fi
  else
    [[ "$had" == 0 ]] || fail "$label install recovery target missing"
  fi
  assert_file "$stage"; [[ $(stat -c '%a' -- "$stage") == 600 && $(file_hash "$stage") == "$installed_hash" ]] || fail "$label install transaction stage drift"
  install -m 0700 -- "$stage" "$target"
}
restore_one() {
  local target=$1 backup=$2 had=$3 previous_mode=$4 previous_gid=$5 previous_hash=$6 installed_hash=$7 label=$8
  if [[ -e "$target" || -L "$target" ]]; then
    assert_file "$target"; current_hash=$(file_hash "$target")
    if [[ "$current_hash" == "$previous_hash" && "$had" == 1 ]]; then return; fi
    [[ "$current_hash" == "$installed_hash" ]] || fail "$label rollback recovery target drift"
  else
    [[ "$had" == 0 ]] && return
    fail "$label rollback recovery target missing"
  fi
  if [[ "$had" == 1 ]]; then
    assert_file "$backup"; [[ $(file_hash "$backup") == "$previous_hash" ]] || fail "$label rollback backup drift"
    install -m "$previous_mode" -- "$backup" "$target"; chgrp "$previous_gid" -- "$target"
  else
    rm -- "$target"
  fi
}
maybe_interrupt() {
  local point=$1 requested=${ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER:-}
  [[ "$requested" != "$point" && !( "$requested" == target && "$point" == provider-target ) ]] || exit 75
}

provider_installed_sha256=$(file_hash "$source_provider")
client_installed_sha256=$(file_hash "$source_client")

recover_transaction() {
  [[ -e "$journal_file" || -L "$journal_file" ]] || return 1
  load_record "$journal_file" 14 yes
  if [[ "$transaction_action" != "$action" ]]; then
    if [[ "$transaction_action" == install && "$action" == rollback ]]; then
      ensure_backup "$target_provider" "$provider_backup" "$provider_had_previous" "$provider_previous_sha256" provider
      ensure_backup "$target_client" "$client_backup" "$client_had_previous" "$client_previous_sha256" client
      restore_one "$target_provider" "$provider_backup" "$provider_had_previous" "$provider_previous_mode" "$provider_previous_gid" "$provider_previous_sha256" "$provider_installed_sha256" provider
      restore_one "$target_client" "$client_backup" "$client_had_previous" "$client_previous_mode" "$client_previous_gid" "$client_previous_sha256" "$client_installed_sha256" client
      rm -f -- "$state_file" "$provider_backup" "$client_backup" "$journal_file" "$provider_stage" "$client_stage"
      printf '{"action":"rollback","recovered":true,"status":"PASS","secret_material_present":false}\n'
      return 0
    fi
    fail "transaction action conflicts with requested action"
  fi
  case "$transaction_action" in
    install)
      ensure_backup "$target_provider" "$provider_backup" "$provider_had_previous" "$provider_previous_sha256" provider
      ensure_backup "$target_client" "$client_backup" "$client_had_previous" "$client_previous_sha256" client
      install_one "$target_provider" "$provider_stage" "$provider_had_previous" "$provider_previous_sha256" "$provider_installed_sha256" provider
      install_one "$target_client" "$client_stage" "$client_had_previous" "$client_previous_sha256" "$client_installed_sha256" client
      write_record "$state_file"
      ;;
    rollback)
      restore_one "$target_provider" "$provider_backup" "$provider_had_previous" "$provider_previous_mode" "$provider_previous_gid" "$provider_previous_sha256" "$provider_installed_sha256" provider
      restore_one "$target_client" "$client_backup" "$client_had_previous" "$client_previous_mode" "$client_previous_gid" "$client_previous_sha256" "$client_installed_sha256" client
      rm -f -- "$state_file" "$provider_backup" "$client_backup"
      ;;
    *) fail "transaction action is invalid" ;;
  esac
  rm -f -- "$journal_file" "$provider_stage" "$client_stage"
  printf '{"action":"%s","recovered":true,"status":"PASS","secret_material_present":false}\n' "$transaction_action"
  return 0
}
if recover_transaction; then exit 0; fi

for stale_stage in "$provider_stage" "$client_stage"; do
  if [[ -e "$stale_stage" || -L "$stale_stage" ]]; then assert_file "$stale_stage"; rm -- "$stale_stage"; fi
done

if [[ "$action" == install ]]; then
  if [[ -e "$state_file" || -L "$state_file" ]]; then
    validate_state
    printf '{"action":"install","status":"PASS","secret_material_present":false}\n'
    exit 0
  fi
  capture_target "$target_provider" provider
  capture_target "$target_client" client
  install -m 0600 -- "$source_provider" "$provider_stage"
  install -m 0600 -- "$source_client" "$client_stage"
  [[ $(file_hash "$provider_stage") == "$provider_installed_sha256" && $(file_hash "$client_stage") == "$client_installed_sha256" ]] || fail "staged digest mismatch"
  maybe_interrupt stage
  write_record "$journal_file" install
  maybe_interrupt journal
  ensure_backup "$target_provider" "$provider_backup" "$provider_had_previous" "$provider_previous_sha256" provider
  ensure_backup "$target_client" "$client_backup" "$client_had_previous" "$client_previous_sha256" client
  install_one "$target_provider" "$provider_stage" "$provider_had_previous" "$provider_previous_sha256" "$provider_installed_sha256" provider
  maybe_interrupt provider-target
  install_one "$target_client" "$client_stage" "$client_had_previous" "$client_previous_sha256" "$client_installed_sha256" client
  maybe_interrupt client-target
  write_record "$state_file"
  rm -f -- "$journal_file" "$provider_stage" "$client_stage"
else
  [[ -e "$state_file" || -L "$state_file" ]] || fail "rollback state is unavailable"
  validate_state
  write_record "$journal_file" rollback
  maybe_interrupt journal
  restore_one "$target_provider" "$provider_backup" "$provider_had_previous" "$provider_previous_mode" "$provider_previous_gid" "$provider_previous_sha256" "$provider_installed_sha256" provider
  maybe_interrupt provider-target
  restore_one "$target_client" "$client_backup" "$client_had_previous" "$client_previous_mode" "$client_previous_gid" "$client_previous_sha256" "$client_installed_sha256" client
  maybe_interrupt client-target
  rm -f -- "$state_file" "$provider_backup" "$client_backup" "$journal_file"
fi
printf '{"action":"%s","status":"PASS","secret_material_present":false}\n' "$action"
