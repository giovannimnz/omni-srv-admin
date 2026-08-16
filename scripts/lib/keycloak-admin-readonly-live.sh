#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 077
export PATH="/usr/sbin:/usr/bin:/sbin:/bin:/opt/keycloak/bin"

MODE=""
OPERATION_ID=""
CLIENT_UUID=""
STATE_DIR=""
EXPECTED_EXPORTER_SHA=""
EXPECTED_PUT_HELPER_SHA=""
RESULT_PATH=""
REAPPLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --operation-id) OPERATION_ID="$2"; shift 2 ;;
    --client-uuid) CLIENT_UUID="$2"; shift 2 ;;
    --state-dir) STATE_DIR="$2"; shift 2 ;;
    --expected-exporter-sha256) EXPECTED_EXPORTER_SHA="$2"; shift 2 ;;
    --expected-put-helper-sha256) EXPECTED_PUT_HELPER_SHA="$2"; shift 2 ;;
    --result) RESULT_PATH="$2"; shift 2 ;;
    --rollback-reapply) REAPPLY="true"; shift ;;
    *) echo "unknown live adapter argument: $1" >&2; exit 2 ;;
  esac
done

BASE_URL="http://127.0.0.1:8180"
REALM="atius"
CLIENT_ID="keycloak-admin-readonly"
RECOVERY_ENV="/etc/keycloak/recovery-admin.env"
KCADM="/opt/keycloak/bin/kcadm.sh"
KCADM_TIMEOUT_SECONDS="30"
VAULT_TARGET="ubuntu@10.13.1.13"
VAULT_PATH="kv/atius/keycloak/admin-readonly"
EXPORTER="/usr/local/sbin/atius-vault-export-env"
VAULT_PUT_HELPER="/usr/local/sbin/atius-vault-kv-put-json"
REMOTE_VAULT="/usr/local/sbin/atius-vault"
LOCAL_VAULT_ENV="/home/ubuntu/.local/bin/atius-vault-env"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TRANSFORM="${SCRIPT_DIR}/keycloak-admin-readonly-exporter-transform.py"
SECRET_PIPE="${SCRIPT_DIR}/keycloak-admin-readonly-secret-pipe.py"
STATE_HELPER="${SCRIPT_DIR}/keycloak-admin-readonly-operation-state.py"
VAULT_CAS_HELPER="${SCRIPT_DIR}/keycloak-admin-readonly-vault-cas-put.py"
CURRENT_STEP="bootstrap"
SERVICE_ACCOUNT_UUID=""
REALM_MANAGEMENT_UUID=""
EXPECTED_INSTALLED_EXPORTER_SHA=""
VAULT_EXPECTED_VERSION=""
CLIENT_ARMED="false"
VAULT_ARMED="false"
EXPORTER_ARMED="false"
ROLLBACK_ATTEMPTED="false"
ROLLBACK_SUCCEEDED="false"
ROLLBACK_EVENT_PREFIX="09"
FORWARD_EVENT_PREFIX="0"
SCRATCH=""
KCADM_CONFIG=""
BACKUP=""
TEST_HARNESS="${SCRIPT_DIR%/lib}/tests/keycloak-admin-readonly-harness.mjs"
SECRET_MATERIALS=()

is_test_transaction() {
  [[ "${MODE}" == "test-transaction" ]]
}

verify_test_harness() {
  [[ "${KARO_TEST_CONTEXT:-}" == "runner-v1" ]]
  [[ "${KARO_TEST_PARENT_PID:-}" == "${PPID}" ]]
  [[ -r "/proc/${PPID}/cmdline" ]]
  /usr/bin/tr '\0' '\n' < "/proc/${PPID}/cmdline" |
    /usr/bin/grep -Fxq "${TEST_HARNESS}"
  local root_info root_real
  root_real="$(/usr/bin/readlink -f -- "${KARO_TEST_ROOT:?KARO_TEST_ROOT required}")"
  [[ "${root_real}" == /tmp/karo-harness-* ]]
  root_info="$(/usr/bin/stat -Lc '%a:%u:%g:%F' "${root_real}")"
  [[ "${root_info}" == "700:$(id -u):$(id -g):directory" ]]
}

remember_secret_material() {
  local value="$1"
  [[ "${#value}" -ge 8 ]] || {
    echo "secret material is unexpectedly short" >&2
    return 1
  }
  SECRET_MATERIALS+=("${value}")
}

if is_test_transaction; then
  verify_test_harness || {
    echo "test transaction requires the explicit internally rooted harness" >&2
    exit 2
  }
else
  if /usr/bin/env | /usr/bin/grep -q '^KARO_TEST_'; then
    echo "production modes reject KARO_TEST_* environment controls" >&2
    exit 2
  fi
  [[ "${EUID}" -eq 0 ]] || { echo "live adapter requires root" >&2; exit 2; }
  [[ "${MODE}" == "apply" || "${MODE}" == "preflight" ]] || {
    echo "only preflight/apply modes are supported" >&2
    exit 2
  }
fi
[[ "${EXPECTED_EXPORTER_SHA}" =~ ^[a-f0-9]{64}$ ]] || {
  echo "invalid exporter sha256" >&2
  exit 2
}
[[ "${EXPECTED_PUT_HELPER_SHA}" =~ ^[a-f0-9]{64}$ ]] || {
  echo "invalid Vault put helper sha256" >&2
  exit 2
}

if [[ "${MODE}" == "preflight" ]]; then
  [[ "${RESULT_PATH}" == "/run/keycloak-admin-readonly.preflight.$$."*"result.json" ||
     "${RESULT_PATH}" == "/run/keycloak-admin-readonly.preflight.${PPID}.result.json" ||
     "${RESULT_PATH}" =~ ^/run/keycloak-admin-readonly\.preflight\.[0-9]+\.result\.json$ ]] || {
    echo "preflight result path outside fixed scope" >&2
    exit 2
  }
  [[ -z "${OPERATION_ID}${CLIENT_UUID}${STATE_DIR}" && "${REAPPLY}" == "false" ]] || {
    echo "preflight cannot accept mutation arguments" >&2
    exit 2
  }
else
  [[ "${OPERATION_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$ ]] || {
    echo "invalid operation id" >&2
    exit 2
  }
  [[ "${CLIENT_UUID}" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] || {
    echo "invalid precomputed client UUID" >&2
    exit 2
  }
  if is_test_transaction; then
    TEST_ROOT="${KARO_TEST_ROOT:?KARO_TEST_ROOT required}"
    [[ "${STATE_DIR}" == "${TEST_ROOT}/operations/${OPERATION_ID}" ]] || {
      echo "test state path outside sandbox" >&2
      exit 2
    }
    [[ "${RESULT_PATH}" == "${TEST_ROOT}/result.json" ]] || {
      echo "test result path outside sandbox" >&2
      exit 2
    }
    SCRATCH="${TEST_ROOT}/scratch"
    BACKUP="${TEST_ROOT}/exporter.backup"
  else
    [[ "${MODE}" == "apply" && "${REAPPLY}" == "true" ]] || {
      echo "apply requires --rollback-reapply" >&2
      exit 2
    }
    [[ "${STATE_DIR}" == "/var/lib/atius-keycloak-admin-readonly/operations/${OPERATION_ID}" ]] || {
      echo "operation state path outside fixed scope" >&2
      exit 2
    }
    [[ "${RESULT_PATH}" == "/run/keycloak-admin-readonly.${OPERATION_ID}.result.json" ]] || {
      echo "apply result path outside fixed scope" >&2
      exit 2
    }
    SCRATCH="/run/keycloak-admin-readonly.${OPERATION_ID}.$$"
    BACKUP="/var/backups/atius-vault-export-env.keycloak-admin-readonly.${OPERATION_ID}.bak"
  fi
fi

[[ ! -e "${RESULT_PATH}" && ! -L "${RESULT_PATH}" ]] || {
  echo "result artifact already exists" >&2
  exit 2
}
mkdir -m 0700 "${SCRATCH:-/run/keycloak-admin-readonly.preflight.$$}"
SCRATCH="${SCRATCH:-/run/keycloak-admin-readonly.preflight.$$}"
BACKUP="${BACKUP:-/var/backups/atius-vault-export-env.keycloak-admin-readonly.preflight.${PPID}.bak}"
KCADM_CONFIG="${SCRATCH}/kcadm.config"

write_private_exclusive() {
  local target="$1"
  /usr/bin/python3 -c '
import os,sys
p=sys.argv[1]
flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
fd=os.open(p,flags,0o600)
try:
  while True:
    b=sys.stdin.buffer.read(1048576)
    if not b: break
    os.write(fd,b)
  os.fsync(fd)
finally:
  os.close(fd)
' "${target}"
}

journal_event() {
  local event_file="$1"
  local resource="$2"
  local status="$3"
  local identifier="$4"
  /usr/bin/jq -n \
    --arg operationId "${OPERATION_ID}" \
    --arg observedAt "$(/usr/bin/date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg resource "${resource}" \
    --arg status "${status}" \
    --arg identifier "${identifier}" \
    '{
      schemaVersion:"2",
      operationId:$operationId,
      observedAt:$observedAt,
      resource:$resource,
      status:$status,
      identifier:$identifier,
      secretsRecorded:false
    }' |
    /usr/bin/python3 "${STATE_HELPER}" event \
      --operation-id "${OPERATION_ID}" --event-file "${event_file}"
}

cleanup() {
  unset KC_CLI_PASSWORD KC_RECOVERY_ADMIN_PASSWORD KC_RECOVERY_ADMIN_USERNAME || true
  if [[ -n "${KCADM_CONFIG}" ]]; then /usr/bin/rm -f -- "${KCADM_CONFIG}" 2>/dev/null || true; fi
  if [[ -n "${SCRATCH}" ]]; then /usr/bin/rm -rf -- "${SCRATCH}" 2>/dev/null || true; fi
}

vault_ssh() {
  /usr/bin/sudo -u ubuntu /usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=10 "$@"
}

local_vault_env() {
  /usr/bin/sudo -u ubuntu "${LOCAL_VAULT_ENV}" "$@"
}

kcadm_exec() {
  /usr/bin/timeout "${KCADM_TIMEOUT_SECONDS}s" "${KCADM}" "$@"
}

remote_vault_metadata_json() {
  vault_ssh -n "${VAULT_TARGET}" \
    "sudo ${REMOTE_VAULT} kv metadata get -format=json ${VAULT_PATH}"
}

assert_vault_metadata_absent() {
  local status
  status="$(
    vault_ssh -n "${VAULT_TARGET}" \
      "set +e; out=\$(sudo ${REMOTE_VAULT} kv metadata get -format=json ${VAULT_PATH} 2>&1); rc=\$?; if [ \$rc -eq 0 ]; then printf PRESENT; elif printf '%s' \"\$out\" | /usr/bin/grep -qi 'No value found'; then printf ABSENT; else exit \$rc; fi"
  )"
  [[ "${status}" == "ABSENT" ]]
}

remote_vault_soft_delete() {
  local version="$1"
  [[ "${version}" =~ ^[12]$ ]] || return 1
  vault_ssh -n "${VAULT_TARGET}" \
    "sudo ${REMOTE_VAULT} kv delete -versions=${version} ${VAULT_PATH} >/dev/null"
}

remote_vault_metadata_delete() {
  vault_ssh -n "${VAULT_TARGET}" \
    "sudo ${REMOTE_VAULT} kv metadata delete ${VAULT_PATH} >/dev/null"
}

remote_exporter_transform() {
  local transform_mode="$1"
  shift
  vault_ssh -T "${VAULT_TARGET}" \
    "sudo /usr/bin/python3 - ${transform_mode} --file ${EXPORTER} --backup ${BACKUP} --expected-before-sha256 ${EXPECTED_EXPORTER_SHA} $*" \
    < "${TRANSFORM}"
}

remote_exporter_hash() {
  vault_ssh -n "${VAULT_TARGET}" \
    "sudo /usr/bin/sha256sum ${EXPORTER} | /usr/bin/awk '{print \$1}'"
}

rollback_exporter() {
  [[ "${EXPORTER_ARMED}" == "true" ]] || return 0
  local current_hash
  current_hash="$(remote_exporter_hash)"
  if [[ "${current_hash}" == "${EXPECTED_INSTALLED_EXPORTER_SHA}" ]]; then
    remote_exporter_transform restore \
      "--expected-installed-sha256 ${EXPECTED_INSTALLED_EXPORTER_SHA}" >/dev/null
  elif [[ "${current_hash}" != "${EXPECTED_EXPORTER_SHA}" ]]; then
    return 1
  fi
  [[ "$(remote_exporter_hash)" == "${EXPECTED_EXPORTER_SHA}" ]]
  journal_event "${ROLLBACK_EVENT_PREFIX}1-exporter-restored.json" \
    "exporter" "restored-readback" "${EXPECTED_EXPORTER_SHA}"
  EXPORTER_ARMED="false"
}

rollback_vault() {
  [[ "${VAULT_ARMED}" == "true" ]] || return 0
  local metadata=""
  if metadata="$(remote_vault_metadata_json 2>/dev/null)"; then
    if /usr/bin/jq -e --arg version "${VAULT_EXPECTED_VERSION}" \
      '.data.versions[$version] != null and (.data.versions[$version].deletion_time // "") == ""' \
      <<<"${metadata}" >/dev/null; then
      remote_vault_soft_delete "${VAULT_EXPECTED_VERSION}" >/dev/null
      metadata="$(remote_vault_metadata_json)"
    fi
    /usr/bin/jq -e --arg version "${VAULT_EXPECTED_VERSION}" \
      '.data.versions[$version] != null and (.data.versions[$version].deletion_time|length)>0' \
      <<<"${metadata}" >/dev/null
  else
    # No metadata means the CAS write never committed.
    assert_vault_metadata_absent
  fi
  journal_event "${ROLLBACK_EVENT_PREFIX}2-vault-restored-v${VAULT_EXPECTED_VERSION}.json" \
    "vault" "soft-deleted-readback" "${VAULT_EXPECTED_VERSION}"
  VAULT_ARMED="false"
}

rollback_keycloak() {
  [[ "${CLIENT_ARMED}" == "true" ]] || return 0
  [[ -f "${KCADM_CONFIG}" ]] || return 1
  local readback
  if readback="$(kcadm_exec get "clients/${CLIENT_UUID}" -r "${REALM}" \
      --config "${KCADM_CONFIG}" --fields id,clientId 2>/dev/null)"; then
    /usr/bin/jq -e --arg id "${CLIENT_UUID}" --arg clientId "${CLIENT_ID}" \
      '.id==$id and .clientId==$clientId' <<<"${readback}" >/dev/null
    kcadm_exec delete "clients/${CLIENT_UUID}" -r "${REALM}" \
      --config "${KCADM_CONFIG}" >/dev/null
  fi
  if kcadm_exec get "clients/${CLIENT_UUID}" -r "${REALM}" \
    --config "${KCADM_CONFIG}" >/dev/null 2>&1; then
    return 1
  fi
  journal_event "${ROLLBACK_EVENT_PREFIX}3-keycloak-restored.json" "keycloak-client" \
    "absent-readback" "${CLIENT_UUID}"
  CLIENT_ARMED="false"
}

rollback_owned_resources() {
  local rollback_rc=0
  set +e
  ROLLBACK_ATTEMPTED="true"
  # Reverse dependency order: exporter -> Vault version -> Keycloak client.
  rollback_exporter || rollback_rc=1
  rollback_vault || rollback_rc=1
  rollback_keycloak || rollback_rc=1
  if [[ "${rollback_rc}" -eq 0 ]]; then
    ROLLBACK_SUCCEEDED="true"
  else
    ROLLBACK_SUCCEEDED="false"
  fi
  set -e
  return "${rollback_rc}"
}

restore_retryable_vault_absence_after_failure() {
  local metadata=""
  if ! metadata="$(remote_vault_metadata_json 2>/dev/null)"; then
    assert_vault_metadata_absent
    return 0
  fi
  /usr/bin/jq -e --arg version "${VAULT_EXPECTED_VERSION}" \
    '.data.versions[$version] != null and (.data.versions[$version].deletion_time|length)>0' \
    <<<"${metadata}" >/dev/null
  remote_vault_metadata_delete >/dev/null
  assert_vault_metadata_absent
  journal_event "${ROLLBACK_EVENT_PREFIX}4-vault-metadata-pruned.json" \
    "vault" "metadata-absent-readback" "${VAULT_EXPECTED_VERSION}"
}

write_failure_result() {
  local exit_code="$1"
  /usr/bin/jq -n \
    --arg operationId "${OPERATION_ID}" \
    --arg failedStep "${CURRENT_STEP}" \
    --argjson exitCode "${exit_code}" \
    --argjson rollbackAttempted "${ROLLBACK_ATTEMPTED}" \
    --argjson rollbackSucceeded "${ROLLBACK_SUCCEEDED}" \
    '{
      schemaVersion:"2",
      mode:"live-failure",
      finalVerdict:"NO-GO",
      operationId:$operationId,
      failedStep:$failedStep,
      exitCode:$exitCode,
      automaticRollback:{attempted:$rollbackAttempted,succeeded:$rollbackSucceeded},
      secretsRecorded:false
    }' | write_private_exclusive "${RESULT_PATH}" 2>/dev/null || true
}

on_error() {
  local exit_code=$?
  trap - ERR INT TERM HUP
  rollback_owned_resources || true
  restore_retryable_vault_absence_after_failure || true
  write_failure_result "${exit_code}"
  cleanup
  exit "${exit_code}"
}

on_signal() {
  CURRENT_STEP="signal-interrupted"
  false
}

trap on_error ERR
trap on_signal INT TERM HUP
trap cleanup EXIT

assert_recovery_metadata() {
  [[ -f "${RECOVERY_ENV}" && ! -L "${RECOVERY_ENV}" ]]
  [[ "$(stat -c '%a:%U:%G' "${RECOVERY_ENV}")" == "600:root:root" ]]
  mapfile -t names < <(/usr/bin/python3 - "${RECOVERY_ENV}" <<'PY'
import pathlib,re,sys
lines=pathlib.Path(sys.argv[1]).read_text().splitlines()
names=[]
for line in lines:
    if not line or line.lstrip().startswith("#"):
        continue
    match=re.fullmatch(r"(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)",line)
    if not match:
        raise SystemExit("invalid recovery env record")
    names.append(match.group(1))
print("\n".join(sorted(names)))
PY
  )
  [[ "${names[*]}" == "KC_RECOVERY_ADMIN_PASSWORD KC_RECOVERY_ADMIN_USERNAME" ]]
}

authenticate_recovery_once() {
  local values=()
  mapfile -d '' -t values < <(/usr/bin/python3 - "${RECOVERY_ENV}" <<'PY'
import pathlib,re,shlex,sys
values={}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if not line or line.lstrip().startswith("#"):
        continue
    match=re.fullmatch(r"(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)",line)
    if not match:
        raise SystemExit("invalid recovery env record")
    parsed=shlex.split(match.group(2),posix=True)
    if len(parsed)!=1 or not parsed[0]:
        raise SystemExit("invalid recovery env scalar")
    values[match.group(1)]=parsed[0]
expected={"KC_RECOVERY_ADMIN_PASSWORD","KC_RECOVERY_ADMIN_USERNAME"}
if set(values)!=expected:
    raise SystemExit("recovery env field set mismatch")
sys.stdout.buffer.write(values["KC_RECOVERY_ADMIN_USERNAME"].encode()+b"\0")
sys.stdout.buffer.write(values["KC_RECOVERY_ADMIN_PASSWORD"].encode()+b"\0")
PY
  )
  [[ "${#values[@]}" -eq 2 ]]
  local recovery_username="${values[0]}"
  remember_secret_material "${values[1]}"
  export KC_CLI_PASSWORD="${values[1]}"
  unset 'values[1]'
  kcadm_exec config credentials \
    --config "${KCADM_CONFIG}" \
    --server "${BASE_URL}" \
    --realm master \
    --user "${recovery_username}" >/dev/null
  unset KC_CLI_PASSWORD recovery_username values
  kcadm_exec get "realms/${REALM}" --config "${KCADM_CONFIG}" --fields realm |
    /usr/bin/jq -e --arg realm "${REALM}" '.realm==$realm' >/dev/null
}

assert_client_absent() {
  kcadm_exec get clients -r "${REALM}" --config "${KCADM_CONFIG}" \
    -q "clientId=${CLIENT_ID}" --fields id,clientId |
    /usr/bin/jq -e 'length==0' >/dev/null
}

capture_remote_preimage() {
  local metadata
  metadata="$(
    vault_ssh -n "${VAULT_TARGET}" \
      "sudo /usr/bin/stat -Lc '%a %U %G' ${EXPORTER}; sudo /usr/bin/sha256sum ${EXPORTER}; sudo /usr/bin/stat -Lc '%a %U %G' ${VAULT_PUT_HELPER}; sudo /usr/bin/sha256sum ${VAULT_PUT_HELPER}"
  )"
  [[ "$(sed -n '1p' <<<"${metadata}")" == "700 root root" ]]
  [[ "$(awk 'NR==2{print $1}' <<<"${metadata}")" == "${EXPECTED_EXPORTER_SHA}" ]]
  [[ "$(sed -n '3p' <<<"${metadata}")" == "700 root root" ]]
  [[ "$(awk 'NR==4{print $1}' <<<"${metadata}")" == "${EXPECTED_PUT_HELPER_SHA}" ]]
  local preview
  preview="$(remote_exporter_transform preview)"
  EXPECTED_INSTALLED_EXPORTER_SHA="$(
    /usr/bin/jq -r '.installedSha256 // empty' <<<"${preview}"
  )"
  [[ "${EXPECTED_INSTALLED_EXPORTER_SHA}" =~ ^[a-f0-9]{64}$ ]]
}

write_client_payload() {
  /usr/bin/jq -n --arg id "${CLIENT_UUID}" '{
    id:$id,
    clientId:"keycloak-admin-readonly",
    enabled:true,
    protocol:"openid-connect",
    clientAuthenticatorType:"client-secret",
    publicClient:false,
    bearerOnly:false,
    standardFlowEnabled:false,
    directAccessGrantsEnabled:false,
    implicitFlowEnabled:false,
    serviceAccountsEnabled:true,
    fullScopeAllowed:false,
    redirectUris:[],
    webOrigins:[],
    attributes:{}
  }' > "${SCRATCH}/client.json"
}

maybe_inject_response_loss() {
  local boundary="$1"
  if is_test_transaction && [[ "${KARO_FAIL_AFTER:-}" == "${boundary}" ]]; then
    return 1
  fi
}

configure_exact_roles() {
  kcadm_exec get "clients/${CLIENT_UUID}/service-account-user" -r "${REALM}" \
    --config "${KCADM_CONFIG}" --fields id,username > "${SCRATCH}/service-account.json"
  SERVICE_ACCOUNT_UUID="$(/usr/bin/jq -r '.id // empty' "${SCRATCH}/service-account.json")"
  [[ "${SERVICE_ACCOUNT_UUID}" =~ ^[0-9a-fA-F-]{16,64}$ ]]
  kcadm_exec get clients -r "${REALM}" --config "${KCADM_CONFIG}" \
    -q clientId=realm-management --fields id,clientId > "${SCRATCH}/realm-management-client.json"
  REALM_MANAGEMENT_UUID="$(
    /usr/bin/jq -r 'if length==1 and .[0].clientId=="realm-management" then .[0].id else empty end' \
      "${SCRATCH}/realm-management-client.json"
  )"
  [[ "${REALM_MANAGEMENT_UUID}" =~ ^[0-9a-fA-F-]{16,64}$ ]]
  kcadm_exec get "clients/${REALM_MANAGEMENT_UUID}/roles/query-clients" -r "${REALM}" \
    --config "${KCADM_CONFIG}" > "${SCRATCH}/query-clients.json"
  kcadm_exec get "clients/${REALM_MANAGEMENT_UUID}/roles/view-clients" -r "${REALM}" \
    --config "${KCADM_CONFIG}" > "${SCRATCH}/view-clients.json"
  /usr/bin/jq -s 'sort_by(.name)' "${SCRATCH}/query-clients.json" \
    "${SCRATCH}/view-clients.json" > "${SCRATCH}/roles.json"
  /usr/bin/jq -e '[.[].name]|sort==["query-clients","view-clients"]' \
    "${SCRATCH}/roles.json" >/dev/null

  CURRENT_STEP="assign-service-account-roles"
  journal_event "${FORWARD_EVENT_PREFIX}20-roles-armed.json" \
    "service-account-roles" "armed" "${CLIENT_UUID}"
  kcadm_exec create "users/${SERVICE_ACCOUNT_UUID}/role-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" -f "${SCRATCH}/roles.json" >/dev/null
  maybe_inject_response_loss "assign-service-account-roles"
  CURRENT_STEP="constrain-dedicated-client-scope"
  journal_event "${FORWARD_EVENT_PREFIX}30-scope-armed.json" \
    "dedicated-client-scope" "armed" "${CLIENT_UUID}"
  kcadm_exec create "clients/${CLIENT_UUID}/scope-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" -f "${SCRATCH}/roles.json" >/dev/null
  maybe_inject_response_loss "constrain-dedicated-client-scope"
}

run_exact_role_readback_once() {
  kcadm_exec get "clients/${CLIENT_UUID}" -r "${REALM}" --config "${KCADM_CONFIG}" \
    > "${SCRATCH}/client-readback.json"
  "${SECRET_PIPE}" exact-client-projection \
    --expected "${SCRATCH}/client.json" \
    < "${SCRATCH}/client-readback.json" \
    > "${SCRATCH}/client-projection-readback.json"
  /usr/bin/rm -f -- "${SCRATCH}/client-readback.json"

  kcadm_exec get "users/${SERVICE_ACCOUNT_UUID}/role-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" > "${SCRATCH}/direct-roles.json"
  kcadm_exec get "users/${SERVICE_ACCOUNT_UUID}/role-mappings/clients/${REALM_MANAGEMENT_UUID}/composite" \
    -r "${REALM}" --config "${KCADM_CONFIG}" > "${SCRATCH}/effective-roles.json"
  kcadm_exec get "clients/${CLIENT_UUID}/scope-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" > "${SCRATCH}/scope-roles.json"
  for role_file in direct-roles effective-roles scope-roles; do
    /usr/bin/jq -e '[.[].name]|sort==["query-clients","view-clients"]' \
      "${SCRATCH}/${role_file}.json" >/dev/null
  done
  kcadm_exec get "clients/${CLIENT_UUID}/scope-mappings" -r "${REALM}" \
    --config "${KCADM_CONFIG}" > "${SCRATCH}/all-scope-mappings.json"
  /usr/bin/jq -e '
    ((.realmMappings // [])|length)==0 and
    ((.clientMappings // {})|keys)==["realm-management"] and
    ([.clientMappings["realm-management"].mappings[].name]|sort)==["query-clients","view-clients"]
  ' "${SCRATCH}/all-scope-mappings.json" >/dev/null
  local secret_response client_secret token_response access_token refresh_token
  secret_response="$(kcadm_exec get "clients/${CLIENT_UUID}/client-secret" -r "${REALM}" \
    --config "${KCADM_CONFIG}")"
  client_secret="$(printf '%s' "${secret_response}" |
    "${SECRET_PIPE}" extract-json-field --field value)"
  remember_secret_material "${client_secret}"
  token_response="$(printf '%s' "${secret_response}" |
    "${SECRET_PIPE}" token-form --base-url "${BASE_URL}" --realm "${REALM}" \
      --client-id "${CLIENT_ID}" |
    /usr/bin/curl --fail --silent --show-error \
      -H 'Content-Type: application/x-www-form-urlencoded' --data-binary @- \
      "${BASE_URL}/realms/${REALM}/protocol/openid-connect/token")"
  access_token="$(printf '%s' "${token_response}" |
    "${SECRET_PIPE}" extract-json-field --field access_token)"
  remember_secret_material "${access_token}"
  refresh_token="$(printf '%s' "${token_response}" |
    "${SECRET_PIPE}" extract-json-field --field refresh_token --optional)"
  if [[ -n "${refresh_token}" ]]; then remember_secret_material "${refresh_token}"; fi
  printf '%s' "${token_response}" |
    "${SECRET_PIPE}" token-roles > "${SCRATCH}/token-role-readback.json"
  unset secret_response client_secret token_response access_token refresh_token
}

assert_exact_client_and_roles() {
  local attempt
  CURRENT_STEP="exact-token-role-readback"
  for attempt in 1 2 3 4 5; do
    if run_exact_role_readback_once; then
      return 0
    fi
    [[ "${attempt}" -eq 5 ]] && return 1
    /usr/bin/sleep 1
  done
}

create_client_and_roles() {
  write_client_payload
  CURRENT_STEP="create-client"
  journal_event "${FORWARD_EVENT_PREFIX}10-client-armed.json" \
    "keycloak-client" "armed" "${CLIENT_UUID}"
  CLIENT_ARMED="true"
  kcadm_exec create clients -r "${REALM}" --config "${KCADM_CONFIG}" \
    -f "${SCRATCH}/client.json" >/dev/null
  maybe_inject_response_loss "create-client"
  kcadm_exec get "clients/${CLIENT_UUID}" -r "${REALM}" --config "${KCADM_CONFIG}" \
    --fields id,clientId |
    /usr/bin/jq -e --arg id "${CLIENT_UUID}" --arg clientId "${CLIENT_ID}" \
      '.id==$id and .clientId==$clientId' >/dev/null
  journal_event "${FORWARD_EVENT_PREFIX}11-client-observed.json" \
    "keycloak-client" "created-readback" "${CLIENT_UUID}"
  configure_exact_roles
  assert_exact_client_and_roles
}

write_vault_secret() {
  local cas="$1"
  local expected_version="$2"
  local event_prefix="$3"
  CURRENT_STEP="vault-secret-write"
  VAULT_EXPECTED_VERSION="${expected_version}"
  journal_event "${event_prefix}-vault-armed-v${expected_version}.json" \
    "vault" "armed-cas-${cas}" "${expected_version}"
  VAULT_ARMED="true"
  local helper_b64
  helper_b64="$(/usr/bin/base64 -w0 "${VAULT_CAS_HELPER}")"
  local secret_response client_secret
  secret_response="$(kcadm_exec get "clients/${CLIENT_UUID}/client-secret" -r "${REALM}" \
    --config "${KCADM_CONFIG}")"
  client_secret="$(printf '%s' "${secret_response}" |
    "${SECRET_PIPE}" extract-json-field --field value)"
  remember_secret_material "${client_secret}"
  printf '%s' "${secret_response}" |
    "${SECRET_PIPE}" vault-json --base-url "${BASE_URL}" --realm "${REALM}" \
      --client-id "${CLIENT_ID}" |
    vault_ssh -T "${VAULT_TARGET}" \
      "sudo /usr/bin/python3 -c \"import base64;exec(base64.b64decode('${helper_b64}'))\" '${VAULT_PATH}' '${cas}' '${expected_version}'" \
      > "${SCRATCH}/vault-write-result.json"
  unset secret_response client_secret
  maybe_inject_response_loss "vault-secret-write-v${expected_version}"
  /usr/bin/jq -e --argjson expected "${expected_version}" '.version==$expected' \
    "${SCRATCH}/vault-write-result.json" >/dev/null
  local readback
  readback="$(
    vault_ssh -n "${VAULT_TARGET}" \
      "sudo ${REMOTE_VAULT} kv get -format=json ${VAULT_PATH} | /usr/bin/jq -c '{version:.data.metadata.version,fieldNames:(.data.data|keys|sort)}'"
  )"
  /usr/bin/jq -e --argjson expected "${expected_version}" '
    .version==$expected and
    .fieldNames==[
      "KEYCLOAK_BASE_URL",
      "KEYCLOAK_READONLY_CLIENT_ID",
      "KEYCLOAK_READONLY_CLIENT_SECRET",
      "KEYCLOAK_REALM"
    ]
  ' <<<"${readback}" >/dev/null
  journal_event "${event_prefix}-vault-observed-v${expected_version}.json" \
    "vault" "created-readback" "${expected_version}"
}

apply_exporter_transform() {
  local transform_mode="$1"
  local event_prefix="$2"
  CURRENT_STEP="exporter-transform"
  journal_event "${event_prefix}-exporter-armed.json" "exporter" \
    "armed" "${EXPECTED_INSTALLED_EXPORTER_SHA}"
  EXPORTER_ARMED="true"
  remote_exporter_transform "${transform_mode}" \
    "--expected-installed-sha256 ${EXPECTED_INSTALLED_EXPORTER_SHA}" \
    > "${SCRATCH}/exporter-${transform_mode}.json"
  maybe_inject_response_loss "exporter-${transform_mode}"
  remote_exporter_transform verify \
    "--expected-installed-sha256 ${EXPECTED_INSTALLED_EXPORTER_SHA}" >/dev/null
  [[ "$(remote_exporter_hash)" == "${EXPECTED_INSTALLED_EXPORTER_SHA}" ]]
  journal_event "${event_prefix}-exporter-observed.json" "exporter" \
    "installed-readback" "${EXPECTED_INSTALLED_EXPORTER_SHA}"
}

run_profile_hydration_and_inventory_once() {
  local inventory_with_material material_count material_index material
  if ! local_vault_env keycloak-admin-readonly \
    2>"${SCRATCH}/hydration-helper.stderr" |
    "${SECRET_PIPE}" verify-exports \
      > "${SCRATCH}/hydration-readback.json" \
      2>"${SCRATCH}/hydration-verify.stderr"; then
    if [[ -s "${SCRATCH}/hydration-helper.stderr" ]]; then
      printf 'profile-hydration helper stderr: %s\n' \
        "$(<"${SCRATCH}/hydration-helper.stderr")" >&2
    fi
    if [[ -s "${SCRATCH}/hydration-verify.stderr" ]]; then
      printf 'profile-hydration verify stderr: %s\n' \
        "$(<"${SCRATCH}/hydration-verify.stderr")" >&2
    fi
    return 1
  fi
  if ! inventory_with_material="$(local_vault_env keycloak-admin-readonly \
    2>"${SCRATCH}/inventory-helper.stderr" |
    "${SECRET_PIPE}" readonly-client-readback \
      --target-client-id sso.atius.com.br \
      --expected-post-logout-uri 'https://sso.atius.com.br/login?logout=complete' \
      --ephemeral-material \
      2>"${SCRATCH}/inventory-readback.stderr")"; then
    if [[ -s "${SCRATCH}/inventory-helper.stderr" ]]; then
      printf 'profile-hydration inventory helper stderr: %s\n' \
        "$(<"${SCRATCH}/inventory-helper.stderr")" >&2
    fi
    if [[ -s "${SCRATCH}/inventory-readback.stderr" ]]; then
      printf 'profile-hydration readonly-client-readback stderr: %s\n' \
        "$(<"${SCRATCH}/inventory-readback.stderr")" >&2
    fi
    return 1
  fi
  material_count="$(/usr/bin/jq -r '._ephemeralSecretMaterial|length' <<<"${inventory_with_material}")"
  for ((material_index=0; material_index<material_count; material_index++)); do
    material="$(/usr/bin/jq -r --argjson index "${material_index}" \
      '._ephemeralSecretMaterial[$index]' <<<"${inventory_with_material}")"
    remember_secret_material "${material}"
  done
  /usr/bin/jq 'del(._ephemeralSecretMaterial)' <<<"${inventory_with_material}" \
    > "${SCRATCH}/sso-client-readback.json"
  unset inventory_with_material material_count material_index material
  /usr/bin/jq -e \
    '.clientCount==1 and .client.clientId=="sso.atius.com.br" and .secretsOutput==false' \
    "${SCRATCH}/sso-client-readback.json" >/dev/null
}

assert_profile_hydration_and_inventory() {
  local attempt
  for attempt in 1 2 3 4 5; do
    if run_profile_hydration_and_inventory_once; then
      return 0
    fi
    [[ "${attempt}" -eq 5 ]] && return 1
    /usr/bin/sleep 1
  done
}

assert_rollback_readback() {
  assert_client_absent
  local metadata
  metadata="$(remote_vault_metadata_json)"
  /usr/bin/jq -e --arg version "${VAULT_EXPECTED_VERSION}" \
    '.data.versions[$version] != null and (.data.versions[$version].deletion_time|length)>0' \
    <<<"${metadata}" >/dev/null
  if local_vault_env keycloak-admin-readonly 2>/dev/null |
    "${SECRET_PIPE}" verify-exports >/dev/null 2>&1; then
    echo "hydration helper did not fail closed after soft delete" >&2
    return 1
  fi
  [[ "$(remote_exporter_hash)" == "${EXPECTED_EXPORTER_SHA}" ]]
}

emit_authenticated_preflight() {
  /usr/bin/jq -n \
    --arg observedAt "$(/usr/bin/date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" \
    --arg clientId "${CLIENT_ID}" \
    --arg vaultPath "${VAULT_PATH}" \
    --arg exporterPath "${EXPORTER}" \
    --arg exporterSha "${EXPECTED_EXPORTER_SHA}" \
    '{
      schemaVersion:"2",
      mode:"authenticated-read-only-preflight",
      observedAt:$observedAt,
      authenticated:true,
      client:{clientId:$clientId,absent:true},
      vault:{path:$vaultPath,absent:true,authenticatedMetadataRead:true},
      exporter:{
        path:$exporterPath,sha256:$exporterSha,mode:"700",owner:"root",group:"root"
      },
      secretsRecorded:false
    }' | write_private_exclusive "${RESULT_PATH}"
}

run_test_transaction() {
  mkdir -p "${STATE_DIR}"
  chmod 0700 "${STATE_DIR}"
  : > "${SCRATCH}/client"
  CLIENT_ARMED="true"
  journal_event "010-client-armed.json" "keycloak-client" "armed" "${CLIENT_UUID}"
  maybe_inject_response_loss "create-client"
  journal_event "020-roles-armed.json" "service-account-roles" "armed" "${CLIENT_UUID}"
  maybe_inject_response_loss "assign-service-account-roles"
  journal_event "030-scope-armed.json" "dedicated-client-scope" "armed" "${CLIENT_UUID}"
  maybe_inject_response_loss "constrain-dedicated-client-scope"
  : > "${SCRATCH}/vault"
  VAULT_ARMED="true"
  VAULT_EXPECTED_VERSION="1"
  journal_event "040-vault-armed-v1.json" "vault" "armed-cas-0" "1"
  maybe_inject_response_loss "vault-secret-write-v1"
  printf 'preimage' > "${BACKUP}"
  printf 'installed' > "${SCRATCH}/exporter"
  EXPORTER_ARMED="true"
  EXPECTED_INSTALLED_EXPORTER_SHA="installed"
  journal_event "050-exporter-armed.json" "exporter" "armed" "installed"
  maybe_inject_response_loss "exporter-apply"
  false
}

if is_test_transaction; then
  # Failure-injection model uses the same append-before-side-effect journal and
  # reverse rollback contract without touching any live target.
  rollback_exporter() {
    [[ "${EXPORTER_ARMED}" == "true" ]] || return 0
    /usr/bin/rm -f "${SCRATCH}/exporter"
    printf 'exporter\n' >> "${KARO_TEST_ROOT}/rollback-order.log"
    EXPORTER_ARMED="false"
  }
  rollback_vault() {
    [[ "${VAULT_ARMED}" == "true" ]] || return 0
    /usr/bin/rm -f "${SCRATCH}/vault"
    printf 'vault\n' >> "${KARO_TEST_ROOT}/rollback-order.log"
    VAULT_ARMED="false"
  }
  rollback_keycloak() {
    [[ "${CLIENT_ARMED}" == "true" ]] || return 0
    /usr/bin/rm -f "${SCRATCH}/client"
    printf 'keycloak\n' >> "${KARO_TEST_ROOT}/rollback-order.log"
    CLIENT_ARMED="false"
  }
  run_test_transaction
  exit 1
fi

CURRENT_STEP="recovery-metadata-validate"
assert_recovery_metadata
CURRENT_STEP="recovery-authenticate"
authenticate_recovery_once
CURRENT_STEP="preimage-client-absence"
assert_client_absent
CURRENT_STEP="preimage-vault-metadata-absence"
assert_vault_metadata_absent
CURRENT_STEP="preimage-exporter-capture"
capture_remote_preimage

if [[ "${MODE}" == "preflight" ]]; then
  emit_authenticated_preflight
  trap - ERR INT TERM HUP
  exit 0
fi

CURRENT_STEP="create-client"
create_client_and_roles
write_vault_secret "0" "1" "040"
apply_exporter_transform apply "050"
CURRENT_STEP="profile-hydration-readback"
assert_profile_hydration_and_inventory
CURRENT_STEP="apply-readback"
assert_exact_client_and_roles

FIRST_CLIENT_UUID="${CLIENT_UUID}"
FIRST_VAULT_VERSION="${VAULT_EXPECTED_VERSION}"
FIRST_INSTALLED_EXPORTER_SHA="${EXPECTED_INSTALLED_EXPORTER_SHA}"

CURRENT_STEP="rollback-drill"
rollback_owned_resources
CURRENT_STEP="rollback-readback"
assert_rollback_readback

CURRENT_STEP="reapply"
ROLLBACK_ATTEMPTED="false"
ROLLBACK_SUCCEEDED="false"
ROLLBACK_EVENT_PREFIX="19"
FORWARD_EVENT_PREFIX="1"
create_client_and_roles
write_vault_secret "1" "2" "140"
apply_exporter_transform reapply "150"
CURRENT_STEP="reapply-readback"
assert_profile_hydration_and_inventory
assert_exact_client_and_roles

CURRENT_STEP="live-secret-scan"
/usr/bin/jq -n \
  --arg operationId "${OPERATION_ID}" \
  --arg firstClientUuid "${FIRST_CLIENT_UUID}" \
  --argjson firstVaultVersion "${FIRST_VAULT_VERSION}" \
  --arg firstInstalledExporterSha256 "${FIRST_INSTALLED_EXPORTER_SHA}" \
  --arg finalClientUuid "${CLIENT_UUID}" \
  --argjson finalVaultVersion "${VAULT_EXPECTED_VERSION}" \
  --arg finalInstalledExporterSha256 "${EXPECTED_INSTALLED_EXPORTER_SHA}" \
  --arg exporterBackup "${BACKUP}" \
  --arg exporterPreimageSha256 "${EXPECTED_EXPORTER_SHA}" \
  '{
    schemaVersion:"2",
    mode:"live-provision-rollback-reapply",
    finalVerdict:"GO",
    operationId:$operationId,
    expectedStepIds:[
      "approval-validate","operation-claim","recovery-metadata-validate",
      "recovery-authenticate","preimage-client-absence",
      "preimage-vault-metadata-absence","preimage-exporter-capture",
      "create-client","assign-service-account-roles",
      "constrain-dedicated-client-scope","exact-token-role-readback",
      "vault-secret-write","exporter-transform","profile-hydration-readback",
      "apply-readback","rollback-drill","rollback-readback","reapply",
      "reapply-readback","live-secret-scan"
    ],
    steps:([
      "approval-validate","operation-claim","recovery-metadata-validate",
      "recovery-authenticate","preimage-client-absence",
      "preimage-vault-metadata-absence","preimage-exporter-capture",
      "create-client","assign-service-account-roles",
      "constrain-dedicated-client-scope","exact-token-role-readback",
      "vault-secret-write","exporter-transform","profile-hydration-readback",
      "apply-readback","rollback-drill","rollback-readback","reapply",
      "reapply-readback","live-secret-scan"
    ]|map({id:.,status:"PASS"})),
    firstApply:{
      clientUuid:$firstClientUuid,
      vaultVersion:$firstVaultVersion,
      exporterInstalledSha256:$firstInstalledExporterSha256
    },
    rollback:{
      order:["exporter","vault","keycloak"],
      clientAbsent:true,
      vaultCreatedVersionSoftDeleted:true,
      vaultMetadataDeleted:false,
      exporterRestoredSha256:$exporterPreimageSha256,
      hydrationFailedClosed:true
    },
    finalReapply:{
      clientUuid:$finalClientUuid,
      vaultVersion:$finalVaultVersion,
      exporterInstalledSha256:$finalInstalledExporterSha256
    },
    exporter:{
      path:"/usr/local/sbin/atius-vault-export-env",
      backup:$exporterBackup,
      preimageSha256:$exporterPreimageSha256
    },
    exactRoles:[
      "realm-management/query-clients",
      "realm-management/view-clients"
    ],
    recoveryAdminUseCount:1,
    clientSecretTransport:"process-memory-and-pipes-only",
    kcadmConfig:"ephemeral-under-run-removed-by-trap",
    automaticRollback:{attempted:true,succeeded:true},
    secretsRecorded:false
  }' > "${SCRATCH}/report-draft.json"

/usr/bin/jq -n \
  --arg path "${BACKUP}" \
  --arg sha256 "${EXPECTED_EXPORTER_SHA}" \
  '{path:$path,mode:"600",owner:"root",group:"root",sha256:$sha256,secretsRecorded:false}' \
  > "${SCRATCH}/backup-metadata.json"

REMOTE_BACKUP_COPY="${SCRATCH}/retained-exporter-backup"
vault_ssh -n "${VAULT_TARGET}" "sudo /usr/bin/cat ${BACKUP}" > "${REMOTE_BACKUP_COPY}"
/usr/bin/chmod 600 "${REMOTE_BACKUP_COPY}"

SCAN_ROOT="${SCRATCH}/scan-root"
/usr/bin/mkdir -m 700 "${SCAN_ROOT}"
/usr/bin/find "${SCRATCH}" -maxdepth 1 -type f ! -name "$(basename "${KCADM_CONFIG}")" -print0 |
  while IFS= read -r -d '' candidate; do
    /usr/bin/cp --preserve=mode,timestamps "${candidate}" "${SCAN_ROOT}/"
  done

printf '%s\0' "${SECRET_MATERIALS[@]}" |
  "${SECRET_PIPE}" scan-artifacts \
    --secret-material-stdin \
    --path "${SCAN_ROOT}" \
    --path "${STATE_DIR}" \
    --path "${REMOTE_BACKUP_COPY}" \
    > "${SCRATCH}/secret-scan.json"
/usr/bin/jq --slurpfile scan "${SCRATCH}/secret-scan.json" \
  '.secretScan=$scan[0]' "${SCRATCH}/report-draft.json" |
  write_private_exclusive "${RESULT_PATH}"

trap - ERR INT TERM HUP
exit 0
