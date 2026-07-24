#!/usr/bin/env python3
"""Secret-safe pipe transforms.

Secret-bearing input and output are intended only for connected pipes. The
script never writes a file and never includes a secret in argv or diagnostics.
"""

from __future__ import annotations

import argparse
import base64
import json
import shlex
import sys
import urllib.parse
import urllib.request


EXPECTED_FIELDS = sorted(
    [
        "KEYCLOAK_BASE_URL",
        "KEYCLOAK_REALM",
        "KEYCLOAK_READONLY_CLIENT_ID",
        "KEYCLOAK_READONLY_CLIENT_SECRET",
    ]
)
EXPECTED_ROLES = ["query-clients", "view-clients"]


def load_secret() -> str:
    payload = json.load(sys.stdin)
    value = payload.get("value")
    if not isinstance(value, str) or not value:
        raise SystemExit("client secret response is missing a non-empty value")
    return value


def vault_json(args: argparse.Namespace) -> None:
    secret = load_secret()
    json.dump(
        {
            "KEYCLOAK_BASE_URL": args.base_url,
            "KEYCLOAK_REALM": args.realm,
            "KEYCLOAK_READONLY_CLIENT_ID": args.client_id,
            "KEYCLOAK_READONLY_CLIENT_SECRET": secret,
        },
        sys.stdout,
        separators=(",", ":"),
    )


def token_form(args: argparse.Namespace) -> None:
    secret = load_secret()
    sys.stdout.write(
        urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": args.client_id,
                "client_secret": secret,
            }
        )
    )


def token_roles(_: argparse.Namespace) -> None:
    payload = json.load(sys.stdin)
    token = payload.get("access_token")
    if not isinstance(token, str):
        raise SystemExit("token endpoint response has no access_token")
    segments = token.split(".")
    if len(segments) != 3:
        raise SystemExit("access_token is not a JWT")
    encoded = segments[1] + "=" * (-len(segments[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(encoded))
    resource_access = claims.get("resource_access", {})
    if set(resource_access) != {"realm-management"}:
        raise SystemExit("token contains extra or missing resource_access clients")
    roles = sorted(resource_access["realm-management"].get("roles", []))
    if roles != EXPECTED_ROLES:
        raise SystemExit("token realm-management roles are not the exact read-only set")
    json.dump(
        {
            "resourceAccessClients": ["realm-management"],
            "realmManagementRoles": roles,
            "exact": True,
        },
        sys.stdout,
        separators=(",", ":"),
    )


def verify_exports(_: argparse.Namespace) -> None:
    names = []
    non_empty = []
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if not line.startswith("export ") or "=" not in line:
            raise SystemExit("hydration output contains a non-export line")
        name, value = line[7:].split("=", 1)
        names.append(name)
        non_empty.append(bool(value))
    if sorted(names) != EXPECTED_FIELDS or not all(non_empty):
        raise SystemExit("hydration output field-name set or non-empty contract failed")
    json.dump({"fieldNames": sorted(names), "allNonEmpty": True}, sys.stdout, separators=(",", ":"))


def parse_exports() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if not line.startswith("export "):
            raise SystemExit("hydration output contains a non-export line")
        parsed = shlex.split(line[7:])
        if len(parsed) != 1 or "=" not in parsed[0]:
            raise SystemExit("hydration export line is malformed")
        name, value = parsed[0].split("=", 1)
        values[name] = value
    if sorted(values) != EXPECTED_FIELDS or not all(values.values()):
        raise SystemExit("hydration output field-name set or non-empty contract failed")
    return values


def request_json(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> object:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except Exception as error:
        raise SystemExit(f"Keycloak read-only request failed: {type(error).__name__}") from None


def readonly_client_readback(args: argparse.Namespace) -> None:
    values = parse_exports()
    if (
        values["KEYCLOAK_BASE_URL"] != "http://127.0.0.1:8180"
        or values["KEYCLOAK_REALM"] != "atius"
        or values["KEYCLOAK_READONLY_CLIENT_ID"] != "keycloak-admin-readonly"
    ):
        raise SystemExit("hydrated non-secret routing fields do not match the exact contract")
    token_response = request_json(
        f'{values["KEYCLOAK_BASE_URL"]}/realms/{values["KEYCLOAK_REALM"]}/protocol/openid-connect/token',
        data=urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": values["KEYCLOAK_READONLY_CLIENT_ID"],
                "client_secret": values["KEYCLOAK_READONLY_CLIENT_SECRET"],
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = token_response.get("access_token") if isinstance(token_response, dict) else None
    if not isinstance(token, str) or not token:
        raise SystemExit("read-only client token response is missing access_token")
    query = urllib.parse.urlencode({"clientId": args.target_client_id})
    clients = request_json(
        f'{values["KEYCLOAK_BASE_URL"]}/admin/realms/{values["KEYCLOAK_REALM"]}/clients?{query}',
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if not isinstance(clients, list) or len(clients) != 1:
        raise SystemExit("read-only inventory did not return exactly one target client")
    client = clients[0]
    post_logout = (client.get("attributes") or {}).get("post.logout.redirect.uris")
    if args.expected_post_logout_uri and post_logout != args.expected_post_logout_uri:
        raise SystemExit("read-only target client post-logout URI mismatch")
    json.dump(
        {
            "clientCount": 1,
            "client": {
                "id": client.get("id"),
                "clientId": client.get("clientId"),
                "enabled": client.get("enabled"),
                "protocol": client.get("protocol"),
                "publicClient": client.get("publicClient"),
                "redirectUris": client.get("redirectUris") or [],
                "webOrigins": client.get("webOrigins") or [],
                "postLogoutRedirectUri": post_logout,
            },
            "secretsOutput": False,
        },
        sys.stdout,
        separators=(",", ":"),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("vault-json", "token-form"):
        child = subparsers.add_parser(mode)
        child.add_argument("--base-url", default="http://127.0.0.1:8180")
        child.add_argument("--realm", default="atius")
        child.add_argument("--client-id", default="keycloak-admin-readonly")
    subparsers.add_parser("token-roles")
    subparsers.add_parser("verify-exports")
    readback = subparsers.add_parser("readonly-client-readback")
    readback.add_argument("--target-client-id", required=True)
    readback.add_argument("--expected-post-logout-uri")
    return parser.parse_args()


if __name__ == "__main__":
    options = parse_args()
    {
        "vault-json": vault_json,
        "token-form": token_form,
        "token-roles": token_roles,
        "verify-exports": verify_exports,
        "readonly-client-readback": readonly_client_readback,
    }[options.mode](options)
