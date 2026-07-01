#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
shift || true

REALM="atius"
CLIENT_ID="sso.atius.com.br"
REDIRECT_URI="https://sso.atius.com.br/api/sso/callback"
WEB_ORIGIN="https://sso.atius.com.br"
POST_LOGOUT_REDIRECT_URI="https://sso.atius.com.br/login?logout=complete"
CLIENT_TYPE="confidential"
SECRET_FILE_PATH="/etc/keycloak/sso.atius.com.br-client.env"
KCADM_BIN="${KCADM_BIN:-/opt/keycloak/bin/kcadm.sh}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/keycloak-sso-client-check.sh inventory [options]
  bash scripts/keycloak-sso-client-check.sh render-apply-plan [options]
  bash scripts/keycloak-sso-client-check.sh assert [options]

Options:
  --realm <realm>
  --client-id <client-id>
  --redirect-uri <uri>
  --web-origin <origin>
  --post-logout-redirect-uri <uri>
  --client-type <confidential|public>
  --secret-file-path <path>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --realm) REALM="$2"; shift 2 ;;
    --client-id) CLIENT_ID="$2"; shift 2 ;;
    --redirect-uri) REDIRECT_URI="$2"; shift 2 ;;
    --web-origin) WEB_ORIGIN="$2"; shift 2 ;;
    --post-logout-redirect-uri) POST_LOGOUT_REDIRECT_URI="$2"; shift 2 ;;
    --client-type) CLIENT_TYPE="$2"; shift 2 ;;
    --secret-file-path) SECRET_FILE_PATH="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

kcadm_ready() {
  [[ -x "${KCADM_BIN}" ]] || return 1
  "${KCADM_BIN}" get "clients" -r "${REALM}" --fields id --limit 1 >/dev/null 2>&1
}

dashboard_checklist() {
  cat <<EOF
Keycloak dashboard checklist for realm '${REALM}' and client '${CLIENT_ID}':
- Client ID: ${CLIENT_ID}
- Protocol: openid-connect
- Enabled: true
- Client type decision: ${CLIENT_TYPE}
- Valid redirect URIs: exactly [${REDIRECT_URI}]
- Web origins: exactly [${WEB_ORIGIN}] with no wildcard
- Valid post logout redirect URIs: exactly [${POST_LOGOUT_REDIRECT_URI}]
- Confidential-only secret file path (do not print value): ${SECRET_FILE_PATH}
- If public client is chosen, operator must record that no client secret is required for the selected flow.
EOF
}

get_client_json() {
  "${KCADM_BIN}" get clients -r "${REALM}" -q "clientId=${CLIENT_ID}"
}

render_inventory() {
  require_cmd jq
  get_client_json | jq 'map({
    id,
    clientId,
    enabled,
    protocol,
    publicClient,
    baseUrl,
    rootUrl,
    adminUrl,
    redirectUris,
    webOrigins,
    postLogoutRedirectUris: (.attributes["post.logout.redirect.uris"] // null)
  })'
}

render_apply_plan() {
  require_cmd jq
  local public_client
  local authenticator
  if [[ "${CLIENT_TYPE}" == "public" ]]; then
    public_client=true
    authenticator=client-secret
  else
    public_client=false
    authenticator=client-secret
  fi

  jq -n \
    --arg clientId "${CLIENT_ID}" \
    --arg redirectUri "${REDIRECT_URI}" \
    --arg webOrigin "${WEB_ORIGIN}" \
    --arg postLogout "${POST_LOGOUT_REDIRECT_URI}" \
    --argjson publicClient "${public_client}" \
    --arg authenticator "${authenticator}" \
    --arg secretPath "${SECRET_FILE_PATH}" \
    '{
      create_or_update_payload: {
        clientId: $clientId,
        enabled: true,
        protocol: "openid-connect",
        publicClient: $publicClient,
        standardFlowEnabled: true,
        directAccessGrantsEnabled: false,
        implicitFlowEnabled: false,
        redirectUris: [$redirectUri],
        webOrigins: [$webOrigin],
        attributes: {
          "post.logout.redirect.uris": $postLogout
        },
        clientAuthenticatorType: $authenticator
      },
      operator_notes: [
        "Default client type is confidential for the server-side ATS facade.",
        "Do not print or diff any client secret value.",
        ("If confidential, store the secret only at " + $secretPath + " with owner root:root and mode 0600."),
        "If public is chosen, record the explicit operator decision and reason in the runbook."
      ]
    }'
}

assert_client() {
  require_cmd jq
  local expected_public
  if [[ "${CLIENT_TYPE}" == "public" ]]; then
    expected_public=true
  else
    expected_public=false
  fi

  get_client_json | jq -e \
    --arg clientId "${CLIENT_ID}" \
    --arg redirectUri "${REDIRECT_URI}" \
    --arg webOrigin "${WEB_ORIGIN}" \
    --arg postLogout "${POST_LOGOUT_REDIRECT_URI}" \
    --argjson publicClient "${expected_public}" \
    '
    length == 1 and
    .[0].clientId == $clientId and
    .[0].protocol == "openid-connect" and
    .[0].enabled == true and
    .[0].publicClient == $publicClient and
    .[0].redirectUris == [$redirectUri] and
    .[0].webOrigins == [$webOrigin] and
    ((.[0].attributes["post.logout.redirect.uris"] // "") == $postLogout)
    ' >/dev/null
}

case "${MODE}" in
  inventory)
    if kcadm_ready; then
      render_inventory
    else
      echo "kcadm.sh is unavailable or not authenticated. Run 'kcadm.sh config credentials' with approved admin access, then re-run this command." >&2
      dashboard_checklist
    fi
    ;;
  render-apply-plan)
    render_apply_plan
    ;;
  assert)
    if kcadm_ready; then
      assert_client
      echo "Keycloak client assert passed for ${CLIENT_ID} in realm ${REALM}."
    else
      echo "kcadm.sh is unavailable or not authenticated. Run 'kcadm.sh config credentials' with approved admin access, then re-run this command." >&2
      dashboard_checklist >&2
      exit 2
    fi
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
