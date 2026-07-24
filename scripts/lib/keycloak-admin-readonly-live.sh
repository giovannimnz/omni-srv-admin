#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

MODE=""
OPERATION_ID=""
EXPECTED_EXPORTER_SHA=""
EXPECTED_PUT_HELPER_SHA=""
RESULT_PATH=""
REAPPLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --operation-id) OPERATION_ID="$2"; shift 2 ;;
    --expected-exporter-sha256) EXPECTED_EXPORTER_SHA="$2"; shift 2 ;;
    --expected-put-helper-sha256) EXPECTED_PUT_HELPER_SHA="$2"; shift 2 ;;
    --result) RESULT_PATH="$2"; shift 2 ;;
    --rollback-reapply) REAPPLY="true"; shift ;;
    *) echo "unknown live adapter argument: $1" >&2; exit 2 ;;
  esac
done

[[ "${EUID}" -eq 0 ]] || { echo "live adapter requires root" >&2; exit 2; }
[[ "${MODE}" == "apply" ]] || { echo "only apply mode is supported" >&2; exit 2; }
[[ "${REAPPLY}" == "true" ]] || { echo "apply requires --rollback-reapply" >&2; exit 2; }
[[ "${OPERATION_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$ ]] || { echo "invalid operation id" >&2; exit 2; }
[[ "${EXPECTED_EXPORTER_SHA}" =~ ^[a-f0-9]{64}$ ]] || { echo "invalid exporter sha256" >&2; exit 2; }
[[ "${EXPECTED_PUT_HELPER_SHA}" =~ ^[a-f0-9]{64}$ ]] || { echo "invalid Vault put helper sha256" >&2; exit 2; }
[[ -n "${RESULT_PATH}" ]] || { echo "missing result path" >&2; exit 2; }

BASE_URL="http://127.0.0.1:8180"
REALM="atius"
CLIENT_ID="keycloak-admin-readonly"
RECOVERY_ENV="/etc/keycloak/recovery-admin.env"
KCADM="/opt/keycloak/bin/kcadm.sh"
VAULT_TARGET="ubuntu@10.13.1.13"
VAULT_PATH="kv/atius/keycloak/admin-readonly"
EXPORTER="/usr/local/sbin/atius-vault-export-env"
VAULT_PUT_HELPER="/usr/local/sbin/atius-vault-kv-put-json"
LOCAL_VAULT_ENV="/home/ubuntu/.local/bin/atius-vault-env"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TRANSFORM="${SCRIPT_DIR}/keycloak-admin-readonly-exporter-transform.py"
SECRET_PIPE="${SCRIPT_DIR}/keycloak-admin-readonly-secret-pipe.py"
BACKUP="/var/backups/atius-vault-export-env.keycloak-admin-readonly.${OPERATION_ID}.bak"
SCRATCH="/run/keycloak-admin-readonly.${OPERATION_ID}.$$"
KCADM_CONFIG="${SCRATCH}/kcadm.config"
CURRENT_STEP="bootstrap"
CLIENT_UUID=""
SERVICE_ACCOUNT_UUID=""
REALM_MANAGEMENT_UUID=""
VAULT_VERSION=""
INSTALLED_EXPORTER_SHA=""
CLIENT_CREATED="false"
VAULT_WRITTEN="false"
EXPORTER_CHANGED="false"
ROLLBACK_ATTEMPTED="false"
ROLLBACK_SUCCEEDED="false"

mkdir -m 0700 "${SCRATCH}"

cleanup() {
  unset KC_CLI_PASSWORD KC_RECOVERY_ADMIN_PASSWORD KC_RECOVERY_ADMIN_USERNAME || true
  rm -f -- "${KCADM_CONFIG}" 2>/dev/null || true
  rm -rf -- "${SCRATCH}" 2>/dev/null || true
}

remote_vault_soft_delete() {
  local version="$1"
  [[ "${version}" =~ ^[1-9][0-9]*$ ]] || return 1
  ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
    "sudo ${VAULT_PUT_HELPER%/*}/atius-vault kv delete -versions=${version} ${VAULT_PATH} >/dev/null"
}

remote_exporter_transform() {
  local transform_mode="$1"
  shift
  ssh -T -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
    "sudo /usr/bin/python3 - ${transform_mode} --file ${EXPORTER} --backup ${BACKUP} --expected-before-sha256 ${EXPECTED_EXPORTER_SHA} $*" \
    < "${TRANSFORM}"
}

rollback_owned_resources() {
  local rollback_rc=0
  set +e
  ROLLBACK_ATTEMPTED="true"
  if [[ "${CLIENT_CREATED}" == "true" && -n "${CLIENT_UUID}" ]]; then
    local client_id_readback
    client_id_readback="$("${KCADM}" get "clients/${CLIENT_UUID}" -r "${REALM}" --config "${KCADM_CONFIG}" --fields clientId 2>/dev/null | jq -r '.clientId // empty')"
    if [[ "${client_id_readback}" == "${CLIENT_ID}" ]]; then
      if "${KCADM}" delete "clients/${CLIENT_UUID}" -r "${REALM}" --config "${KCADM_CONFIG}" >/dev/null 2>&1; then
        CLIENT_CREATED="false"
      else
        rollback_rc=1
      fi
    else
      rollback_rc=1
    fi
  fi
  if [[ "${VAULT_WRITTEN}" == "true" && -n "${VAULT_VERSION}" ]]; then
    if remote_vault_soft_delete "${VAULT_VERSION}" >/dev/null 2>&1; then
      VAULT_WRITTEN="false"
    else
      rollback_rc=1
    fi
  fi
  if [[ "${EXPORTER_CHANGED}" == "true" && -n "${INSTALLED_EXPORTER_SHA}" ]]; then
    if remote_exporter_transform restore "--expected-installed-sha256 ${INSTALLED_EXPORTER_SHA}" >/dev/null 2>&1; then
      EXPORTER_CHANGED="false"
    else
      rollback_rc=1
    fi
  fi
  if [[ "${rollback_rc}" -eq 0 ]]; then
    ROLLBACK_SUCCEEDED="true"
  else
    ROLLBACK_SUCCEEDED="false"
  fi
  set -e
  return "${rollback_rc}"
}

on_error() {
  local exit_code=$?
  trap - ERR
  rollback_owned_resources || true
  jq -n \
    --arg operationId "${OPERATION_ID}" \
    --arg failedStep "${CURRENT_STEP}" \
    --argjson exitCode "${exit_code}" \
    --argjson rollbackAttempted "${ROLLBACK_ATTEMPTED}" \
    --argjson rollbackSucceeded "${ROLLBACK_SUCCEEDED}" \
    '{
      schemaVersion:"1",
      mode:"live-failure",
      finalVerdict:"NO-GO",
      operationId:$operationId,
      failedStep:$failedStep,
      exitCode:$exitCode,
      automaticRollback:{attempted:$rollbackAttempted,succeeded:$rollbackSucceeded},
      secretsRecorded:false
    }' > "${RESULT_PATH}" 2>/dev/null || true
  cleanup
  exit "${exit_code}"
}

trap on_error ERR
trap cleanup EXIT

assert_recovery_metadata() {
  [[ -f "${RECOVERY_ENV}" && ! -L "${RECOVERY_ENV}" ]]
  [[ "$(stat -c '%a:%U:%G' "${RECOVERY_ENV}")" == "600:root:root" ]]
  mapfile -t names < <(awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $1}' "${RECOVERY_ENV}" | LC_ALL=C sort)
  [[ "${#names[@]}" -eq 2 ]]
  [[ "${names[0]}" == "KC_RECOVERY_ADMIN_PASSWORD" ]]
  [[ "${names[1]}" == "KC_RECOVERY_ADMIN_USERNAME" ]]
}

authenticate_recovery_once() {
  # shellcheck disable=SC1090
  source "${RECOVERY_ENV}"
  [[ -n "${KC_RECOVERY_ADMIN_USERNAME:-}" && -n "${KC_RECOVERY_ADMIN_PASSWORD:-}" ]]
  export KC_CLI_PASSWORD="${KC_RECOVERY_ADMIN_PASSWORD}"
  unset KC_RECOVERY_ADMIN_PASSWORD
  "${KCADM}" config credentials \
    --config "${KCADM_CONFIG}" \
    --server "${BASE_URL}" \
    --realm master \
    --user "${KC_RECOVERY_ADMIN_USERNAME}" >/dev/null
  unset KC_CLI_PASSWORD KC_RECOVERY_ADMIN_USERNAME
  "${KCADM}" get "realms/${REALM}" --config "${KCADM_CONFIG}" --fields realm \
    | jq -e --arg realm "${REALM}" '.realm==$realm' >/dev/null
}

assert_client_absent() {
  "${KCADM}" get clients -r "${REALM}" --config "${KCADM_CONFIG}" \
    -q "clientId=${CLIENT_ID}" --fields id,clientId \
    | jq -e 'length==0' >/dev/null
}

assert_vault_metadata_absent() {
  local status
  status="$(
    ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
      "set +e; out=\$(sudo ${VAULT_PUT_HELPER%/*}/atius-vault kv metadata get -format=json ${VAULT_PATH} 2>&1); rc=\$?; if [ \$rc -eq 0 ]; then printf PRESENT; elif printf '%s' \"\$out\" | grep -qi 'No value found'; then printf ABSENT; else exit \$rc; fi"
  )"
  [[ "${status}" == "ABSENT" ]]
}

capture_remote_preimage() {
  local metadata
  metadata="$(
    ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
      "sudo stat -c '%a %U %G' ${EXPORTER}; sudo sha256sum ${EXPORTER}; sudo stat -c '%a %U %G' ${VAULT_PUT_HELPER}; sudo sha256sum ${VAULT_PUT_HELPER}"
  )"
  local exporter_stat exporter_sha helper_stat helper_sha
  exporter_stat="$(sed -n '1p' <<<"${metadata}")"
  exporter_sha="$(awk 'NR==2{print $1}' <<<"${metadata}")"
  helper_stat="$(sed -n '3p' <<<"${metadata}")"
  helper_sha="$(awk 'NR==4{print $1}' <<<"${metadata}")"
  [[ "${exporter_stat}" == "700 root root" ]]
  [[ "${exporter_sha}" == "${EXPECTED_EXPORTER_SHA}" ]]
  [[ "${helper_stat}" == "700 root root" ]]
  [[ "${helper_sha}" == "${EXPECTED_PUT_HELPER_SHA}" ]]
}

write_client_payload() {
  jq -n '{
    clientId:"keycloak-admin-readonly",
    name:"Keycloak admin read-only automation",
    description:"Vault-hydrated service account limited to client inventory readback",
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
    rootUrl:"",
    baseUrl:"",
    adminUrl:"",
    attributes:{
      "oauth2.device.authorization.grant.enabled":"false",
      "oidc.ciba.grant.enabled":"false"
    }
  }' > "${SCRATCH}/client.json"
}

configure_exact_roles() {
  "${KCADM}" get "clients/${CLIENT_UUID}/service-account-user" -r "${REALM}" \
    --config "${KCADM_CONFIG}" --fields id,username > "${SCRATCH}/service-account.json"
  SERVICE_ACCOUNT_UUID="$(jq -r '.id // empty' "${SCRATCH}/service-account.json")"
  [[ "${SERVICE_ACCOUNT_UUID}" =~ ^[0-9a-fA-F-]{16,64}$ ]]

  "${KCADM}" get clients -r "${REALM}" --config "${KCADM_CONFIG}" \
    -q clientId=realm-management --fields id,clientId > "${SCRATCH}/realm-management-client.json"
  REALM_MANAGEMENT_UUID="$(
    jq -r 'if length==1 and .[0].clientId=="realm-management" then .[0].id else empty end' \
      "${SCRATCH}/realm-management-client.json"
  )"
  [[ "${REALM_MANAGEMENT_UUID}" =~ ^[0-9a-fA-F-]{16,64}$ ]]

  "${KCADM}" get "clients/${REALM_MANAGEMENT_UUID}/roles/query-clients" -r "${REALM}" \
    --config "${KCADM_CONFIG}" > "${SCRATCH}/query-clients.json"
  "${KCADM}" get "clients/${REALM_MANAGEMENT_UUID}/roles/view-clients" -r "${REALM}" \
    --config "${KCADM_CONFIG}" > "${SCRATCH}/view-clients.json"
  jq -s 'sort_by(.name)' "${SCRATCH}/query-clients.json" "${SCRATCH}/view-clients.json" \
    > "${SCRATCH}/roles.json"
  jq -e '[.[].name]|sort==["query-clients","view-clients"]' "${SCRATCH}/roles.json" >/dev/null

  CURRENT_STEP="assign-service-account-roles"
  "${KCADM}" create "users/${SERVICE_ACCOUNT_UUID}/role-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" -f "${SCRATCH}/roles.json" >/dev/null
  CURRENT_STEP="constrain-dedicated-client-scope"
  "${KCADM}" create "clients/${CLIENT_UUID}/scope-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" -f "${SCRATCH}/roles.json" >/dev/null
}

assert_exact_client_and_roles() {
  CURRENT_STEP="exact-token-role-readback"
  "${KCADM}" get "clients/${CLIENT_UUID}" -r "${REALM}" --config "${KCADM_CONFIG}" \
    > "${SCRATCH}/client-readback.json"
  jq -e '
    .clientId=="keycloak-admin-readonly" and
    .enabled==true and .protocol=="openid-connect" and
    .clientAuthenticatorType=="client-secret" and
    .publicClient==false and .bearerOnly==false and
    .standardFlowEnabled==false and .directAccessGrantsEnabled==false and
    .implicitFlowEnabled==false and .serviceAccountsEnabled==true and
    .fullScopeAllowed==false and
    (.redirectUris // [])==[] and (.webOrigins // [])==[] and
    (.rootUrl // "")=="" and (.baseUrl // "")=="" and (.adminUrl // "")==""
  ' "${SCRATCH}/client-readback.json" >/dev/null

  "${KCADM}" get "users/${SERVICE_ACCOUNT_UUID}/role-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" > "${SCRATCH}/direct-roles.json"
  "${KCADM}" get "users/${SERVICE_ACCOUNT_UUID}/role-mappings/clients/${REALM_MANAGEMENT_UUID}/composite" \
    -r "${REALM}" --config "${KCADM_CONFIG}" > "${SCRATCH}/effective-roles.json"
  "${KCADM}" get "clients/${CLIENT_UUID}/scope-mappings/clients/${REALM_MANAGEMENT_UUID}" \
    -r "${REALM}" --config "${KCADM_CONFIG}" > "${SCRATCH}/scope-roles.json"
  for role_file in direct-roles effective-roles scope-roles; do
    jq -e '[.[].name]|sort==["query-clients","view-clients"]' "${SCRATCH}/${role_file}.json" >/dev/null
    if jq -e 'any(.[].name; test("(^realm-admin$|manage|create)"))' \
      "${SCRATCH}/${role_file}.json" >/dev/null; then
      echo "elevated or extra Keycloak role detected" >&2
      return 1
    fi
  done

  "${KCADM}" get "clients/${CLIENT_UUID}/scope-mappings" -r "${REALM}" --config "${KCADM_CONFIG}" \
    > "${SCRATCH}/all-scope-mappings.json"
  jq -e '
    ((.realmMappings // [])|length)==0 and
    ((.clientMappings // {})|keys)==["realm-management"] and
    ([.clientMappings["realm-management"].mappings[].name]|sort)==["query-clients","view-clients"]
  ' "${SCRATCH}/all-scope-mappings.json" >/dev/null

  "${KCADM}" get "clients/${CLIENT_UUID}/client-secret" -r "${REALM}" --config "${KCADM_CONFIG}" \
    | "${SECRET_PIPE}" token-form --base-url "${BASE_URL}" --realm "${REALM}" --client-id "${CLIENT_ID}" \
    | curl --fail --silent --show-error \
        -H 'Content-Type: application/x-www-form-urlencoded' \
        --data-binary @- \
        "${BASE_URL}/realms/${REALM}/protocol/openid-connect/token" \
    | "${SECRET_PIPE}" token-roles > "${SCRATCH}/token-role-readback.json"
}

create_client_and_roles() {
  write_client_payload
  CLIENT_UUID="$(
    "${KCADM}" create clients -r "${REALM}" --config "${KCADM_CONFIG}" \
      -f "${SCRATCH}/client.json" -i
  )"
  [[ "${CLIENT_UUID}" =~ ^[0-9a-fA-F-]{16,64}$ ]]
  CLIENT_CREATED="true"
  configure_exact_roles
  assert_exact_client_and_roles
}

write_vault_secret() {
  "${KCADM}" get "clients/${CLIENT_UUID}/client-secret" -r "${REALM}" --config "${KCADM_CONFIG}" \
    | "${SECRET_PIPE}" vault-json --base-url "${BASE_URL}" --realm "${REALM}" --client-id "${CLIENT_ID}" \
    | ssh -T -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
        "sudo ${VAULT_PUT_HELPER} ${VAULT_PATH}" >/dev/null
  local readback
  readback="$(
    ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
      "sudo ${VAULT_PUT_HELPER%/*}/atius-vault kv get -format=json ${VAULT_PATH} | jq -c '{version:.data.metadata.version,fieldNames:(.data.data|keys|sort)}'"
  )"
  jq -e '
    (.version|type)=="number" and .version>0 and
    .fieldNames==[
      "KEYCLOAK_BASE_URL",
      "KEYCLOAK_READONLY_CLIENT_ID",
      "KEYCLOAK_READONLY_CLIENT_SECRET",
      "KEYCLOAK_REALM"
    ]
  ' <<<"${readback}" >/dev/null
  VAULT_VERSION="$(jq -r '.version' <<<"${readback}")"
  VAULT_WRITTEN="true"
}

apply_exporter_transform() {
  local transform_mode="$1"
  local transform_result
  transform_result="$(remote_exporter_transform "${transform_mode}")"
  INSTALLED_EXPORTER_SHA="$(jq -r '.installedSha256 // empty' <<<"${transform_result}")"
  [[ "${INSTALLED_EXPORTER_SHA}" =~ ^[a-f0-9]{64}$ ]]
  EXPORTER_CHANGED="true"
  remote_exporter_transform verify "--expected-installed-sha256 ${INSTALLED_EXPORTER_SHA}" >/dev/null
}

assert_profile_hydration_and_inventory() {
  "${LOCAL_VAULT_ENV}" keycloak-admin-readonly \
    | "${SECRET_PIPE}" verify-exports > "${SCRATCH}/hydration-readback.json"
  "${LOCAL_VAULT_ENV}" keycloak-admin-readonly \
    | "${SECRET_PIPE}" readonly-client-readback \
        --target-client-id sso.atius.com.br \
        --expected-post-logout-uri 'https://sso.atius.com.br/login?logout=complete' \
        > "${SCRATCH}/sso-client-readback.json"
  jq -e '.clientCount==1 and .client.clientId=="sso.atius.com.br" and .secretsOutput==false' \
    "${SCRATCH}/sso-client-readback.json" >/dev/null
}

assert_rollback_readback() {
  assert_client_absent
  local current_status
  current_status="$(
    ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
      "set +e; sudo ${VAULT_PUT_HELPER%/*}/atius-vault kv get -format=json ${VAULT_PATH} >/dev/null 2>&1; rc=\$?; if [ \$rc -ne 0 ]; then printf SOFT_DELETED; else printf PRESENT; fi"
  )"
  [[ "${current_status}" == "SOFT_DELETED" ]]
  if "${LOCAL_VAULT_ENV}" keycloak-admin-readonly 2>/dev/null \
    | "${SECRET_PIPE}" verify-exports >/dev/null 2>&1; then
    echo "hydration helper did not fail closed after soft delete" >&2
    return 1
  fi
  local restored_hash
  restored_hash="$(
    ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${VAULT_TARGET}" \
      "sudo sha256sum ${EXPORTER} | awk '{print \$1}'"
  )"
  [[ "${restored_hash}" == "${EXPECTED_EXPORTER_SHA}" ]]
}

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

CURRENT_STEP="create-client"
create_client_and_roles

CURRENT_STEP="vault-secret-write"
write_vault_secret

CURRENT_STEP="exporter-transform"
apply_exporter_transform apply

CURRENT_STEP="profile-hydration-readback"
assert_profile_hydration_and_inventory

CURRENT_STEP="apply-readback"
assert_exact_client_and_roles

FIRST_CLIENT_UUID="${CLIENT_UUID}"
FIRST_VAULT_VERSION="${VAULT_VERSION}"
FIRST_INSTALLED_EXPORTER_SHA="${INSTALLED_EXPORTER_SHA}"

CURRENT_STEP="rollback-drill"
rollback_owned_resources

CURRENT_STEP="rollback-readback"
assert_rollback_readback

CURRENT_STEP="reapply"
CLIENT_UUID=""
SERVICE_ACCOUNT_UUID=""
REALM_MANAGEMENT_UUID=""
VAULT_VERSION=""
INSTALLED_EXPORTER_SHA=""
ROLLBACK_ATTEMPTED="false"
ROLLBACK_SUCCEEDED="false"
create_client_and_roles
write_vault_secret
apply_exporter_transform reapply

CURRENT_STEP="reapply-readback"
assert_profile_hydration_and_inventory

CURRENT_STEP="live-secret-scan"
jq -n \
  --arg operationId "${OPERATION_ID}" \
  --arg firstClientUuid "${FIRST_CLIENT_UUID}" \
  --argjson firstVaultVersion "${FIRST_VAULT_VERSION}" \
  --arg firstInstalledExporterSha256 "${FIRST_INSTALLED_EXPORTER_SHA}" \
  --arg finalClientUuid "${CLIENT_UUID}" \
  --argjson finalVaultVersion "${VAULT_VERSION}" \
  --arg finalInstalledExporterSha256 "${INSTALLED_EXPORTER_SHA}" \
  --arg exporterBackup "${BACKUP}" \
  --arg exporterPreimageSha256 "${EXPECTED_EXPORTER_SHA}" \
  '{
    schemaVersion:"1",
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
    secretsRecorded:false
  }' > "${RESULT_PATH}"
chmod 0600 "${RESULT_PATH}"

CLIENT_CREATED="false"
VAULT_WRITTEN="false"
EXPORTER_CHANGED="false"
trap - ERR
exit 0
