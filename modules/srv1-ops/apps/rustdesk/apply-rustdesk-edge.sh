#!/usr/bin/env bash
set -euo pipefail

NFT_BIN="${NFT_BIN:-/usr/sbin/nft}"
POLICY="${POLICY:-/etc/nftables.d/atius-rustdesk-edge.nft}"
EXPECTED_POLICY_UID="${EXPECTED_POLICY_UID:-0}"
RUNTIME_DIR="${RUNTIME_DIR:-/run}"
FAMILY="inet"
TABLE="atius_rustdesk_edge"

fail() {
  printf 'rustdesk-edge-apply: %s\n' "$*" >&2
  exit 1
}

[ -x "$NFT_BIN" ] || fail "nft binary unavailable: $NFT_BIN"
[ -f "$POLICY" ] && [ ! -L "$POLICY" ] && [ -r "$POLICY" ] \
  || fail "policy must be a readable regular non-symlink: $POLICY"

owner=$(stat -c '%u' "$POLICY")
mode=$(stat -c '%a' "$POLICY")
[ "$owner" = "$EXPECTED_POLICY_UID" ] || fail "policy owner mismatch"
# Decimal digits from stat are octal permission digits; reject group/world write.
case "$mode" in
  *[2367][0-7]|*[0-7][2367]) fail "policy must not be group/world writable: mode=$mode" ;;
esac

grep -Eq '^[[:space:]]*table[[:space:]]+inet[[:space:]]+atius_rustdesk_edge[[:space:]]*\{' "$POLICY" \
  || fail "policy does not declare the managed table"
[ "$(grep -Ec '^[[:space:]]*table[[:space:]]+inet[[:space:]]+atius_rustdesk_edge[[:space:]]*\{' "$POLICY")" -eq 1 ] \
  || fail "policy must declare the managed table exactly once"

batch=$(mktemp "$RUNTIME_DIR/atius-rustdesk-edge.XXXXXX.nft")
trap 'rm -f "$batch"' EXIT
chmod 600 "$batch"

if "$NFT_BIN" list table "$FAMILY" "$TABLE" >/dev/null 2>&1; then
  printf 'delete table %s %s\n' "$FAMILY" "$TABLE" > "$batch"
else
  : > "$batch"
fi
cat -- "$POLICY" >> "$batch"

# nft applies one file as one netlink transaction. Validate the complete batch
# first; an unreadable/invalid source never reaches the live apply.
"$NFT_BIN" -c -f "$batch"
"$NFT_BIN" -f "$batch"
