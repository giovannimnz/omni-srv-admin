#!/usr/bin/env python3
"""Secret-safe pipe transforms.

Secret-bearing input and output are intended only for connected pipes. The
script never writes a file and never includes a secret in argv or diagnostics.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
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
SECRET_KEY_RE = re.compile(
    r"(?:^|_)(?:password|secret|access_token|refresh_token|root_token|private_key)(?:$|_)",
    re.IGNORECASE,
)
RAW_SECRET_RE = re.compile(
    r"""(?ix)
    \b(?:client_secret|access_token|refresh_token|password|root_token)\b
    \s*[:=]\s*
    ["']?[A-Za-z0-9+/=_-]{16,}
    """
)
SERVER_OWNED_CLIENT_METADATA = frozenset({"access"})


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


def extract_json_field(args: argparse.Namespace) -> None:
    payload = json.load(sys.stdin)
    value = payload.get(args.field) if isinstance(payload, dict) else None
    if value is None and args.optional:
        return
    if not isinstance(value, str) or not value:
        raise SystemExit("requested secret response field is missing")
    sys.stdout.write(value)


def exact_client_projection(args: argparse.Namespace) -> None:
    expected_path = pathlib.Path(args.expected)
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = json.load(sys.stdin)
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        raise SystemExit("client projection requires JSON objects")
    unexpected = set(actual) - set(expected) - SERVER_OWNED_CLIENT_METADATA
    missing = set(expected) - set(actual)
    if unexpected or missing:
        raise SystemExit("client readback top-level field set is not exact")
    projected = {key: actual[key] for key in expected}
    if projected != expected:
        raise SystemExit("client readback does not match the exact emitted projection")
    attributes = projected.get("attributes")
    if not isinstance(attributes, dict) or set(attributes) != set(expected.get("attributes", {})):
        raise SystemExit("client readback attribute set is not exact")
    json.dump(
        {
            "clientId": projected.get("clientId"),
            "exactTopLevelFields": sorted(projected),
            "strippedServerMetadata": sorted(set(actual) & SERVER_OWNED_CLIENT_METADATA),
            "exact": True,
            "secretsRecorded": False,
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
    result = {
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
    }
    if args.ephemeral_material:
        ephemeral = [values["KEYCLOAK_READONLY_CLIENT_SECRET"], token]
        refresh_token = token_response.get("refresh_token") if isinstance(token_response, dict) else None
        if isinstance(refresh_token, str) and refresh_token:
            ephemeral.append(refresh_token)
        result["_ephemeralSecretMaterial"] = ephemeral
    json.dump(result, sys.stdout, separators=(",", ":"))


def scan_json_scalars(value: object, source: pathlib.Path, findings: list[str], prefix: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            if SECRET_KEY_RE.search(key) and child not in (None, False, "", "process-memory-and-pipes-only"):
                findings.append(f"{source}:{child_prefix}")
            scan_json_scalars(child, source, findings, child_prefix)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_json_scalars(child, source, findings, f"{prefix}[{index}]")


def secret_variants(material: bytes) -> set[bytes]:
    variants = {
        material,
        base64.b64encode(material),
        base64.urlsafe_b64encode(material),
        base64.urlsafe_b64encode(material).rstrip(b"="),
        urllib.parse.quote_from_bytes(material, safe="").encode(),
        urllib.parse.quote_plus(material.decode("utf-8"), safe="").encode(),
        material.hex().encode(),
        hashlib.sha256(material).hexdigest().encode(),
    }
    return {value for value in variants if value}


def secret_materials_from_stdin(enabled: bool) -> list[set[bytes]]:
    if not enabled:
        return []
    payload = sys.stdin.buffer.read()
    materials = [item for item in payload.split(b"\0") if item]
    if any(len(item) < 8 for item in materials):
        raise SystemExit("secret material fingerprint input is unexpectedly short")
    return [secret_variants(item) for item in materials]


def scan_artifacts(args: argparse.Namespace) -> None:
    findings: list[str] = []
    scanned: list[str] = []
    material_variants = secret_materials_from_stdin(args.secret_material_stdin)
    for raw_path in args.path:
        target = pathlib.Path(raw_path)
        candidates = [target]
        if target.is_dir():
            candidates = []
            for item in sorted(target.rglob("*")):
                if item.is_symlink():
                    raise SystemExit(f"secret scan refuses symlink artifact under {target}")
                if item.is_file():
                    candidates.append(item)
        for candidate in candidates:
            metadata = candidate.lstat()
            if candidate.is_symlink() or not candidate.is_file():
                raise SystemExit(f"secret scan refuses non-regular artifact: {candidate}")
            if metadata.st_size > 2 * 1024 * 1024:
                raise SystemExit(f"secret scan artifact exceeds 2 MiB: {candidate}")
            raw = candidate.read_bytes()
            text = raw.decode("utf-8", errors="strict")
            scanned.append(str(candidate))
            if RAW_SECRET_RE.search(text):
                findings.append(f"{candidate}:raw-secret-like-assignment")
            if any(variant in raw for variants in material_variants for variant in variants):
                findings.append(f"{candidate}:known-secret-material-or-fingerprint")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            if payload is not None:
                scan_json_scalars(payload, candidate, findings)
    if findings:
        raise SystemExit(
            "secret-like scalar/material found in emitted evidence: "
            + ", ".join(sorted(findings))
        )
    json.dump(
        {"scannedFiles": sorted(scanned), "findingCount": 0, "secretsRecorded": False},
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
    readback.add_argument("--ephemeral-material", action="store_true")
    extract = subparsers.add_parser("extract-json-field")
    extract.add_argument("--field", required=True)
    extract.add_argument("--optional", action="store_true")
    projection = subparsers.add_parser("exact-client-projection")
    projection.add_argument("--expected", required=True)
    scan = subparsers.add_parser("scan-artifacts")
    scan.add_argument("--path", action="append", required=True)
    scan.add_argument("--secret-material-stdin", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    options = parse_args()
    {
        "vault-json": vault_json,
        "token-form": token_form,
        "token-roles": token_roles,
        "extract-json-field": extract_json_field,
        "exact-client-projection": exact_client_projection,
        "verify-exports": verify_exports,
        "readonly-client-readback": readonly_client_readback,
        "scan-artifacts": scan_artifacts,
    }[options.mode](options)
